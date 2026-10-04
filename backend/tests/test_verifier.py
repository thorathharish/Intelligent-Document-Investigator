from app.investigation.verifier import find_quote, verify
from app.schemas import validate_analyst_output

CHUNK = "4.2 Payment Terms\nThe Customer shall pay each undisputed invoice within thirty (30) days of the invoice date."
OTHER = "Invoice INV-2041. The total amount due is USD 48,500. Payment due within 45 days of the invoice date."


def _evidence(**overrides):
    base = {"eid": "E1", "chunk_id": "chunk-1", "document_id": "doc-1", "document": "Agreement.pdf", "page": 2,
            "section": "4.2 Payment Terms", "paragraph": 12, "text": CHUNK, "extraction_method": "text",
            "ocr_confidence": None}
    return {**base, **overrides}


EVIDENCE = [
    _evidence(),
    _evidence(eid="E2", chunk_id="chunk-2", document_id="doc-2", document="Invoice.pdf", page=1, section=None,
              paragraph=1, text=OTHER),
]


def _run(claims, evidence=EVIDENCE):
    output = validate_analyst_output({"aspects": [{"id": "A1", "label": "Payment period"}], "claims": claims})
    return verify(output, evidence)


def _claim(**overrides):
    base = {"id": "C1", "aspect": "A1", "evidence": "E1", "value": "30 days", "value_type": "duration",
            "quote": "pay each undisputed invoice within thirty (30) days of the invoice date"}
    return {**base, **overrides}


def test_valid_exact_quote_gets_database_location():
    result = _run([_claim()])
    assert result["dropped"] == []
    claim = result["claims"][0]
    assert claim["position_key"] == "quantity:30|day" and claim["explicit"] is True
    assert claim["evidence"] == {
        "chunk_id": "chunk-1", "document_id": "doc-1", "document": "Agreement.pdf", "page": 2,
        "section": "4.2 Payment Terms", "paragraph": 12, "extraction_method": "text", "ocr_quality": None,
        "quote": "pay each undisputed invoice within thirty (30) days of the invoice date",
    }


def test_displayed_quote_is_always_stored_text():
    result = _run([_claim(quote='"PAY each  undisputed invoice within thirty (30) days of the invoice date."')])
    quote = result["claims"][0]["evidence"]["quote"]
    assert quote in CHUNK and quote.startswith("pay each")


def test_invented_quote_is_dropped():
    result = _run([_claim(quote="the customer must pay within ninety days of delivery of goods")])
    assert result["claims"] == [] and result["dropped"] == [{"id": "C1", "reason": "quote_not_found"}]


def test_missing_evidence_id_is_dropped():
    result = _run([_claim(evidence="E9")])
    assert result["claims"] == [] and result["dropped"][0]["reason"] == "unknown_evidence"


def test_quote_from_a_different_chunk_is_dropped():
    # the text is real, but it is in E2, not in the cited E1
    result = _run([_claim(quote="Payment due within 45 days of the invoice date", value="45 days")])
    assert result["claims"] == [] and result["dropped"][0]["reason"] == "quote_not_found"


def test_quote_length_limits():
    assert _run([_claim(quote="30 days")])["dropped"][0]["reason"] == "bad_quote_length"
    assert _run([_claim(quote="x" * 301)])["dropped"][0]["reason"] == "bad_quote_length"


def test_typed_value_mismatch_is_kept_as_inferred_and_not_comparable():
    result = _run([_claim(value="45 days")])  # real quote, but it says 30 days
    claim = result["claims"][0]
    assert claim["explicit"] is False and claim["position_key"] is None


def test_valid_typed_values():
    result = _run([_claim(evidence="E2", quote="The total amount due is USD 48,500", value="$48,500", value_type="money")])
    assert result["claims"][0]["position_key"] == "money:USD|48500"
    assert result["claims"][0]["value"] == "USD 48,500"


def test_duplicate_claims_collapse():
    result = _run([_claim(), _claim(id="C2", value="thirty days", quote="within thirty (30) days of the invoice date")])
    assert len(result["claims"]) == 1 and result["dropped"] == [{"id": "C2", "reason": "duplicate"}]


def test_ellipsis_quote_matches_in_order():
    span = find_quote("The Customer shall pay ... thirty (30) days of the invoice date", CHUNK, False)
    assert span is not None and CHUNK[span[0]:span[1]].startswith("The Customer shall pay")
    assert find_quote("thirty (30) days of the invoice date ... The Customer shall pay", CHUNK, False) is None


def test_ocr_typo_passes_fuzzy_but_text_is_strict():
    typo = "Payment due within 45 days of the invoce date"
    assert find_quote(typo, OTHER, is_ocr=True) is not None
    result = _run(
        [_claim(evidence="E2", quote=typo, value="45 days")],
        [EVIDENCE[0], {**EVIDENCE[1], "extraction_method": "ocr", "ocr_confidence": 0.7}],
    )
    claim = result["claims"][0]
    assert claim["evidence"]["quote"] in OTHER and claim["evidence"]["ocr_quality"] == "low"
    assert claim["position_key"] == "quantity:45|day"


def test_unknown_aspect_is_dropped():
    assert _run([_claim(aspect="A7")])["dropped"][0]["reason"] == "unknown_aspect"
