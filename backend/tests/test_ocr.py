"""Checkpoint 6: OCR path, quality metadata, fuzzy quote verification and their effect on the evidence state."""
import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import db
from app.ingestion import IngestionError, extract, ocr
from app.investigation import analyst, conflicts, verifier
from app.investigation.uncertainty import evaluate
from app.investigation.verifier import find_quote, ocr_quality
from app.main import app
from app.retrieval import retriever
from app.schemas import validate_analyst_output
from test_qa import ScriptedLLM

SCAN_TEXT = "Payment due within 45 days of the invoice date."
TEXT_PAGE = "This cover page describes the freight services supplied to the customer during February."


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _text_pdf(lines: list[str], size: float = 16) -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(72, 72, 523, 400), "\n\n".join(lines), fontsize=size, fontname="helv")
    return doc


def _scanned_page_pdf() -> bytes:
    """Two pages: page 1 has a text layer; page 2 is only an image of text, as a scanner would produce."""
    source = _text_pdf([SCAN_TEXT, "The total amount due is USD 48,500."])
    picture = source[0].get_pixmap(dpi=150)
    doc = _text_pdf([TEXT_PAGE], size=11)
    scanned = doc.new_page()
    scanned.insert_image(scanned.rect, pixmap=picture)
    assert scanned.get_text().strip() == ""  # no text layer on the scanned page
    data = doc.tobytes()
    doc.close()
    source.close()
    return data


def _upload(client, files):
    inv = client.post("/api/investigations", json={"title": "OCR"}).json()["id"]
    client.post(f"/api/investigations/{inv}/documents",
                files=[("files", (name, data, "application/octet-stream")) for name, data in files])
    return inv, {d["filename"]: d for d in client.get(f"/api/investigations/{inv}/documents").json()}


def _chunks(document_id):
    return db.query("SELECT * FROM chunks WHERE document_id = ? ORDER BY ordinal", (document_id,))


# --- scanned PDF page -------------------------------------------------------------


def test_scanned_pdf_page_goes_through_ocr_and_keeps_its_location(client, monkeypatch):
    seen = []
    real = ocr.ocr_image

    def spy(image):
        seen.append(image.shape)
        return real(image)

    monkeypatch.setattr(extract.ocr, "ocr_image", spy)
    inv, docs = _upload(client, [("scanned.pdf", _scanned_page_pdf())])
    doc = docs["scanned.pdf"]

    assert doc["status"] == "ready" and doc["page_count"] == 2 and doc["extraction_method"] == "mixed"
    # only the page without a text layer is OCR'd, rendered at 200 DPI (A4 = 595 x 842 pt)
    assert len(seen) == 1
    height, width, channels = seen[0]
    assert abs(width - 595 / 72 * 200) <= 2 and abs(height - 842 / 72 * 200) <= 2 and channels == 3

    by_page = {c["page"]: c for c in _chunks(doc["id"])}
    assert set(by_page) == {1, 2}
    assert by_page[1]["extraction_method"] == "text" and by_page[1]["ocr_confidence"] is None
    scanned = by_page[2]
    assert scanned["extraction_method"] == "ocr" and "45 days" in scanned["text"] and "48,500" in scanned["text"]
    assert 0.80 <= scanned["ocr_confidence"] <= 1  # a clean render is good-quality OCR
    assert scanned["embedding"] is not None and scanned["document_id"] == doc["id"]

    # the OCR metadata survives retrieval, verification and the result contract
    evidence = retriever.retrieve(inv, "When is payment due on the invoice?")
    item = next(e for e in evidence if e["chunk_id"] == scanned["id"])
    assert (item["extraction_method"], item["page"], item["document_id"]) == ("ocr", 2, doc["id"])
    assert item["ocr_confidence"] == scanned["ocr_confidence"]

    llm = ScriptedLLM([("Payment period", "Payment due within 45 days of the invoice date", "45 days", "duration")])
    monkeypatch.setattr(analyst, "get_llm_client", lambda: llm)
    result = client.post(f"/api/investigations/{inv}/questions", json={"question": "When is payment due?"}).json()
    (claim,) = result["claims"]
    assert claim["evidence"]["extraction_method"] == "ocr" and claim["evidence"]["ocr_quality"] == "good"
    assert claim["evidence"]["page"] == 2 and claim["evidence"]["document"] == "scanned.pdf"
    assert claim["evidence"]["chunk_id"] == scanned["id"] and claim["evidence"]["quote"] in scanned["text"]
    assert result["state"] == "MEDIUM" and result["signals"]["ocr_claims"] == 1
    assert "1 passage comes from scanned images." in result["warnings"]


def test_blank_scanned_page_does_not_fail_the_document(client):
    doc = _text_pdf([TEXT_PAGE], size=11)
    doc.new_page()  # an empty page: no text layer and nothing for OCR to read
    inv, docs = _upload(client, [("with-blank.pdf", doc.tobytes())])
    assert docs["with-blank.pdf"]["status"] == "ready" and docs["with-blank.pdf"]["page_count"] == 2
    assert {c["page"] for c in _chunks(docs["with-blank.pdf"]["id"])} == {1}


# --- quality classification ---------------------------------------------------------


@pytest.mark.parametrize("method, confidence, expected", [
    ("ocr", 0.99, "good"), ("ocr", 0.80, "good"), ("ocr", 0.7999, "low"), ("ocr", 0.2, "low"),
    ("ocr", None, "good"), ("text", None, None), ("text", 0.1, None),
])
def test_ocr_quality_bands(method, confidence, expected):
    assert ocr.OCR_LOW_THRESHOLD == 0.80
    assert ocr_quality({"extraction_method": method, "ocr_confidence": confidence}) == expected


# --- quote verification on OCR text --------------------------------------------------

OCR_CHUNK = ("INVOICEINV-2041 From Orion Logistics Pvt. Ltd. to Kestrel Foods Ltd. The total amount due is "
             "USD 48,500. Payment due within 45 days of the invoice date.")
EXACT = "Payment due within 45 days of the invoice date"
SLIP = "Paymenl due withn 45 days of the lnvoce dale"          # scores about 91: between 88 and 92
ALTERED_NUMBER = "Payment due within 90 days of the invoice date"   # reads the same, states a different value


def _ocr_evidence(confidence=0.95, method="ocr"):
    return [{"eid": "E1", "chunk_id": "scan-1", "document_id": "doc-invoice", "document": "Invoice.png", "page": 1,
             "section": None, "paragraph": 1, "text": OCR_CHUNK, "text_hash": "h1", "extraction_method": method,
             "ocr_confidence": confidence if method == "ocr" else None}]


def _verify(quote, value="45 days", evidence=None):
    output = validate_analyst_output({
        "aspects": [{"id": "A1", "label": "Payment period"}],
        "claims": [{"id": "C1", "aspect": "A1", "evidence": "E1", "quote": quote, "value": value, "value_type": "duration"}],
    })
    return output, verifier.verify(output, evidence or _ocr_evidence())


def test_exact_ocr_quote_is_accepted_unchanged():
    _, result = _verify(EXACT)
    assert result["dropped"] == [] and result["claims"][0]["evidence"]["quote"] == EXACT
    assert result["claims"][0]["position_key"] == "quantity:45|day" and result["claims"][0]["explicit"] is True


def test_minor_distortion_passes_only_at_the_ocr_threshold():
    assert (verifier.FUZZY_TEXT, verifier.FUZZY_OCR) == (92, 88)
    span = find_quote(SLIP, OCR_CHUNK, is_ocr=True)
    assert span is not None
    assert find_quote(SLIP, OCR_CHUNK, is_ocr=False) is None  # the same slip is too far for a text chunk


def test_accepted_fuzzy_quote_displays_the_stored_text_in_whole_words():
    _, result = _verify(SLIP)
    shown = result["claims"][0]["evidence"]["quote"]
    assert shown == EXACT                       # stored document text, not the model's spelling
    assert shown in OCR_CHUNK and SLIP not in OCR_CHUNK
    assert result["claims"][0]["position_key"] == "quantity:45|day"


def test_quote_with_a_different_number_is_rejected():
    for is_ocr in (True, False):
        assert find_quote(ALTERED_NUMBER, OCR_CHUNK, is_ocr=is_ocr) is None
    _, result = _verify(ALTERED_NUMBER, value="90 days")
    assert result["claims"] == [] and result["dropped"] == [{"id": "C1", "reason": "quote_not_found"}]


@pytest.mark.parametrize("quote", [
    "Payment is due ninety days after delivery of the goods",
    "The equipment is covered by a five year warranty",
])
def test_meaningfully_different_or_invented_quote_is_rejected(quote):
    _, result = _verify(quote)
    assert result["claims"] == [] and result["dropped"][0]["reason"] == "quote_not_found"


# --- OCR quality and the evidence state ------------------------------------------------


def _state(evidence, claims_spec):
    output = validate_analyst_output({
        "aspects": [{"id": "A1", "label": "Payment period"}],
        "claims": [{"id": f"C{i}", "aspect": "A1", "evidence": eid, "quote": quote, "value": "45 days",
                    "value_type": "duration"} for i, (eid, quote) in enumerate(claims_spec, start=1)],
    })
    verification = verifier.verify(output, evidence)
    aspects = conflicts.detect(output.aspects, verification["claims"], evidence, verification["notes"])
    return evaluate(aspects, verification["claims"], evidence), aspects, verification["claims"]


TEXT_SOURCE = {"eid": "E2", "chunk_id": "text-1", "document_id": "doc-letter", "document": "Letter.pdf", "page": 1,
               "section": None, "paragraph": 1, "text": "As agreed, payment is due within 45 days of the invoice date.",
               "text_hash": "h2", "extraction_method": "text", "ocr_confidence": None}
SECOND_SCAN = {**_ocr_evidence(0.5)[0], "eid": "E2", "chunk_id": "scan-2", "document_id": "doc-scan2",
               "document": "Receipt.png", "text_hash": "h3"}


def test_low_quality_ocr_alone_is_low_and_never_high():
    verdict, _, claims = _state(_ocr_evidence(0.6), [("E1", EXACT)])
    assert claims[0]["evidence"]["ocr_quality"] == "low"
    assert (verdict["state"], verdict["rule"]) == ("LOW", 7)
    assert "All supporting text comes from a low-quality scan." in verdict["reasons"]

    two_low_scans, _, _ = _state(_ocr_evidence(0.6) + [SECOND_SCAN], [("E1", EXACT), ("E2", EXACT)])
    assert two_low_scans["state"] == "LOW"  # two documents, but both low-quality scans


def test_good_quality_ocr_alone_is_medium():
    verdict, _, _ = _state(_ocr_evidence(0.95), [("E1", EXACT)])
    assert verdict["state"] == "MEDIUM"


def test_text_source_plus_low_quality_scan_can_be_high():
    verdict, aspects, claims = _state(_ocr_evidence(0.6) + [TEXT_SOURCE],
                                      [("E1", EXACT), ("E2", "payment is due within 45 days of the invoice date")])
    assert verdict["state"] == "HIGH"
    # quality changes neither the value nor the grouping: one position, no conflict
    assert aspects[0]["status"] == "consistent" and len(aspects[0]["positions"]) == 1
    assert {c["position_key"] for c in claims} == {"quantity:45|day"}
    assert {c["evidence"]["ocr_quality"] for c in claims} == {"low", None}


def test_ocr_quality_never_creates_a_conflict_by_itself():
    _, low, _ = _state(_ocr_evidence(0.3) + [TEXT_SOURCE], [("E1", EXACT), ("E2", "payment is due within 45 days of the invoice date")])
    _, good, _ = _state(_ocr_evidence(0.99) + [TEXT_SOURCE], [("E1", EXACT), ("E2", "payment is due within 45 days of the invoice date")])
    assert low[0]["status"] == good[0]["status"] == "consistent"
    assert low[0]["positions"][0]["key"] == good[0]["positions"][0]["key"]


# --- failure isolation --------------------------------------------------------------------


def test_ocr_failure_is_isolated_to_its_document(client, monkeypatch):
    def broken(image):
        raise IngestionError("OCR engine unavailable")

    monkeypatch.setattr(extract.ocr, "ocr_image", broken)
    picture = _text_pdf([SCAN_TEXT])[0].get_pixmap(dpi=150).tobytes("png")
    note = b"Kestrel Foods confirmed that the late fee is 1.5% per month on overdue invoices from Orion Logistics.\n"
    inv, docs = _upload(client, [("scan.png", picture), ("note.txt", note), ("scanned.pdf", _scanned_page_pdf())])

    assert docs["scan.png"]["status"] == "failed" and docs["scan.png"]["error_message"] == "OCR engine unavailable"
    assert docs["scanned.pdf"]["status"] == "failed"
    assert docs["note.txt"]["status"] == "ready"

    # the investigation is still usable with the documents that did process
    llm = ScriptedLLM([("Late fee", "late fee is 1.5% per month", "1.5%", "percent")])
    monkeypatch.setattr(analyst, "get_llm_client", lambda: llm)
    result = client.post(f"/api/investigations/{inv}/questions", json={"question": "What is the late fee?"}).json()
    assert result["state"] == "MEDIUM" and result["claims"][0]["evidence"]["document"] == "note.txt"


def test_unreadable_image_fails_with_a_clear_message(client):
    blank = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 120), False)
    blank.set_rect(blank.irect, (255, 255, 255))
    _, docs = _upload(client, [("blank.png", blank.tobytes("png"))])
    assert docs["blank.png"]["status"] == "failed" and docs["blank.png"]["error_message"] == "No readable text found"


def test_ocr_groups_lines_into_rows_and_reports_mean_confidence():
    image = _text_pdf(["Total due", SCAN_TEXT])[0].get_pixmap(dpi=150)
    array = np.frombuffer(image.samples, dtype=np.uint8).reshape(image.height, image.width, image.n)
    paragraphs, confidence = ocr.ocr_image(array)
    assert any("45 days" in p for p in paragraphs) and 0 < confidence <= 1
