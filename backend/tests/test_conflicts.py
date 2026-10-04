"""Deterministic conflict detection (LLD section 13): analyst output -> verifier -> conflict engine."""
from app.investigation import conflicts, verifier
from app.schemas import validate_analyst_output


def _chunk(n, document, text):
    return {"eid": f"E{n}", "chunk_id": f"chunk-{n}", "document_id": f"doc-{document}", "document": f"{document}.pdf",
            "page": 1, "section": None, "paragraph": 1, "text": text, "text_hash": f"hash-{text}",
            "extraction_method": "text", "ocr_confidence": None}


AGREEMENT = _chunk(1, "Agreement", "The Customer shall pay each undisputed invoice within thirty (30) days of the invoice date.")
AMENDMENT = _chunk(2, "Amendment", "This Amendment replaces clause 9.1. The Customer shall pay each invoice within 30 days of the invoice date. Notice of termination is 90 days.")
INVOICE = _chunk(3, "Invoice", "Payment due within 45 days of the invoice date. The total amount due is USD 48,500.")
EVIDENCE = [AGREEMENT, AMENDMENT, INVOICE]

THIRTY_A = ("E1", "within thirty (30) days of the invoice date", "30 days", "duration")
THIRTY_B = ("E2", "within 30 days of the invoice date", "thirty days", "duration")
FORTY_FIVE = ("E3", "Payment due within 45 days of the invoice date", "45 days", "duration")


def _detect(claim_specs, aspects=("Payment period",), evidence=EVIDENCE, supersession=()):
    """claim_specs: (evidence id, quote, value, type[, aspect index[, scope]])."""
    claims = []
    for i, spec in enumerate(claim_specs, start=1):
        eid, quote, value, value_type = spec[:4]
        aspect = spec[4] if len(spec) > 4 else 0
        scope = spec[5] if len(spec) > 5 else None
        claims.append({"id": f"C{i}", "aspect": f"A{aspect + 1}", "evidence": eid, "quote": quote, "value": value,
                       "value_type": value_type, "scope": scope})
    output = validate_analyst_output({
        "aspects": [{"id": f"A{i + 1}", "label": label} for i, label in enumerate(aspects)],
        "claims": claims,
        "supersession": [{"evidence": e, "quote": q, "aspect": "A1", "note": "model text"} for e, q in supersession],
    })
    verification = verifier.verify(output, evidence)
    result = conflicts.detect(output.aspects, verification["claims"], evidence, verification["notes"])
    return result, verification


# --- positions ----------------------------------------------------------------


def test_same_value_from_two_documents_is_one_position():
    (aspect,), _ = _detect([THIRTY_A, THIRTY_B])
    assert aspect["status"] == "consistent" and aspect["basis"] == "typed"
    assert len(aspect["positions"]) == 1
    position = aspect["positions"][0]
    assert position["key"] == "quantity:30|day" and position["display"] == "30 days"
    assert position["claim_ids"] == ["C1", "C2"] and position["document_ids"] == ["doc-Agreement", "doc-Amendment"]


def test_thirty_versus_forty_five_days_is_a_conflict_with_no_winner():
    (aspect,), _ = _detect([THIRTY_A, FORTY_FIVE, THIRTY_B])
    assert aspect["status"] == "conflict"
    assert [(p["display"], p["document_ids"]) for p in aspect["positions"]] == [
        ("30 days", ["doc-Agreement", "doc-Amendment"]),
        ("45 days", ["doc-Invoice"]),
    ]
    # positions carry support only; nothing marks one as correct
    assert all(set(p) == {"key", "display", "claim_ids", "document_ids"} for p in aspect["positions"])


def test_two_independent_positions_conflict_whatever_the_order():
    (aspect,), _ = _detect([FORTY_FIVE, THIRTY_A])
    assert aspect["status"] == "conflict" and len(aspect["positions"]) == 2


def test_duplicate_claim_does_not_create_a_second_position_or_source():
    (aspect,), verification = _detect([THIRTY_A, ("E1", "undisputed invoice within thirty (30) days", "30 days", "duration")])
    assert len(verification["claims"]) == 1 and len(aspect["positions"]) == 1
    assert aspect["positions"][0]["document_ids"] == ["doc-Agreement"]


def test_identical_passage_in_a_copied_document_is_one_source_and_no_conflict():
    copy = {**AGREEMENT, "eid": "E4", "chunk_id": "chunk-4", "document_id": "doc-AgreementCopy", "document": "Agreement_copy.pdf"}
    (aspect,), _ = _detect([THIRTY_A, ("E4",) + THIRTY_A[1:]], evidence=EVIDENCE + [copy])
    assert aspect["status"] == "consistent"
    assert aspect["positions"][0]["document_ids"] == ["doc-Agreement"]


# --- no false conflicts -------------------------------------------------------


def test_different_aspects_do_not_conflict():
    result, _ = _detect(
        [THIRTY_A, ("E2", "Notice of termination is 90 days", "90 days", "duration", 1)],
        aspects=("Payment period", "Termination notice"),
    )
    assert [a["status"] for a in result] == ["consistent", "consistent"]


def test_incompatible_scopes_are_complementary_not_conflicting():
    (aspect,), _ = _detect([THIRTY_A + (0, "domestic invoices"), FORTY_FIVE + (0, "International Invoices")])
    assert aspect["status"] == "complementary" and len(aspect["positions"]) == 2


def test_equal_or_unspecified_scopes_conflict():
    (same,), _ = _detect([THIRTY_A + (0, "Domestic invoices"), FORTY_FIVE + (0, "domestic  invoices")])
    assert same["status"] == "conflict"
    (one_unspecified,), _ = _detect([THIRTY_A + (0, "domestic invoices"), FORTY_FIVE])
    assert one_unspecified["status"] == "conflict"


def test_two_values_in_one_passage_do_not_conflict():
    text = "Payment is due within 30 days for services and within 45 days for equipment purchases."
    (aspect,), _ = _detect(
        [("E1", "within 30 days for services", "30 days", "duration"),
         ("E1", "within 45 days for equipment purchases", "45 days", "duration")],
        evidence=[_chunk(1, "Terms", text)],
    )
    assert aspect["status"] == "complementary"


def test_different_value_families_do_not_conflict():
    (aspect,), _ = _detect([THIRTY_A, ("E3", "The total amount due is USD 48,500", "USD 48,500", "money")])
    assert aspect["status"] == "complementary"


def test_different_units_are_not_compared():
    month = _chunk(4, "Memo", "Invoices are payable within one month of receipt by the customer.")
    (aspect,), _ = _detect([THIRTY_A, ("E4", "payable within one month of receipt", "1 month", "duration")], evidence=EVIDENCE + [month])
    assert aspect["status"] == "complementary"  # neither equal nor contradictory: equivalence is not guessed


def test_unverified_or_mismatched_claims_cannot_create_a_conflict():
    # invented quote is dropped; a real quote with the wrong value is kept as inferred with no position
    (aspect,), verification = _detect([
        THIRTY_A,
        ("E3", "Payment is due within ninety days of delivery", "90 days", "duration"),
        ("E2", "within 30 days of the invoice date", "60 days", "duration"),
    ])
    assert aspect["status"] == "consistent" and len(aspect["positions"]) == 1
    assert [d["reason"] for d in verification["dropped"]] == ["quote_not_found"]
    assert [c["position_key"] for c in verification["claims"]] == ["quantity:30|day", None]


def test_non_comparable_claims_have_no_position():
    (aspect,), _ = _detect([("E1", "The Customer shall pay each undisputed invoice", "pays invoices", "none")])
    assert aspect["status"] == "consistent" and aspect["positions"] == []


def test_aspect_without_claims_is_uncovered():
    result, _ = _detect([THIRTY_A], aspects=("Payment period", "Warranty"))
    assert [a["status"] for a in result] == ["consistent", "uncovered"]


def test_aspects_with_the_same_label_are_merged():
    result, _ = _detect([THIRTY_A, FORTY_FIVE + (1,)], aspects=("Payment period", "payment  period."))
    assert len(result) == 1 and result[0]["status"] == "conflict"


def test_other_comparable_types_conflict_too():
    a = _chunk(1, "Handbook", "Remote work is permitted for up to two days per week for all staff.")
    b = _chunk(2, "Memo", "Effective 1 July 2025, remote work is not permitted for any employee.")
    (boolean,), _ = _detect(
        [("E1", "Remote work is permitted for up to two days", "yes", "boolean"),
         ("E2", "remote work is not permitted for any employee", "no", "boolean")],
        aspects=("Remote work",), evidence=[a, b])
    assert boolean["status"] == "conflict" and {p["display"] for p in boolean["positions"]} == {"Yes", "No"}

    c = _chunk(1, "Contract", "This agreement is governed by the laws of Delaware in all respects.")
    d = _chunk(2, "Addendum", "This agreement is governed by the laws of New York in all respects.")
    (text,), _ = _detect(
        [("E1", "governed by the laws of Delaware", "Delaware", "text"),
         ("E2", "governed by the laws of New York", "New York", "text")],
        aspects=("Governing law",), evidence=[c, d])
    assert text["status"] == "conflict" and text["basis"] == "text"


# --- supersession -------------------------------------------------------------


def test_supersession_is_a_cited_note_and_does_not_change_the_status():
    spec = [THIRTY_A, FORTY_FIVE]
    (without,), _ = _detect(spec)
    (with_note,), _ = _detect(spec, supersession=[("E2", "This Amendment replaces clause 9.1")])
    assert without["status"] == with_note["status"] == "conflict"
    assert without["positions"] == with_note["positions"]
    (note,) = with_note["notes"]
    assert note["text"] == "Amendment.pdf states that it replaces or amends an earlier provision."
    assert "model text" not in note["text"]
    assert note["evidence"]["quote"] == "This Amendment replaces clause 9.1" and note["evidence"]["document"] == "Amendment.pdf"


def test_unverified_or_inexplicit_supersession_is_discarded():
    (invented,), _ = _detect([THIRTY_A], supersession=[("E2", "This Amendment overrides every earlier agreement")])
    assert invented["notes"] == []
    (no_cue,), _ = _detect([THIRTY_A], supersession=[("E3", "Payment due within 45 days of the invoice date")])
    assert no_cue["notes"] == []


def test_fallback_marks_covered_aspects_consistent():
    output = validate_analyst_output({"aspects": [{"id": "A1", "label": "x"}, {"id": "A2", "label": "y"}], "claims": []})
    result = conflicts.fallback(output.aspects, [{"aspect_id": "A1"}])
    assert [(a["status"], a["positions"]) for a in result] == [("consistent", []), ("uncovered", [])]
