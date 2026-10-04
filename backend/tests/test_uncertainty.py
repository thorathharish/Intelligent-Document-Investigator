"""Deterministic evidence state (LLD section 14): one test per ordered rule, plus reasons and signals."""
from app.investigation import composer
from app.investigation.uncertainty import evaluate


def claim(cid, aspect="A1", document="Agreement", explicit=True, ocr=None, chunk=None, scope=None):
    return {
        "id": cid, "aspect_id": aspect, "explicit": explicit, "scope": scope, "position_key": "quantity:30|day",
        "value": "30 days",
        "evidence": {"chunk_id": chunk or f"chunk-{cid}", "document_id": f"doc-{document}", "document": f"{document}.pdf",
                     "extraction_method": "ocr" if ocr else "text", "ocr_quality": ocr, "page": 1, "section": None,
                     "paragraph": 1, "quote": "q"},
    }


def aspect(aid="A1", label="Payment period", status="consistent", positions=None, notes=None, basis="typed"):
    return {"id": aid, "label": label, "status": status, "basis": basis, "positions": positions or [], "notes": notes or []}


def state(aspects, claims, **kwargs):
    return evaluate(aspects, claims, [], **kwargs)


def test_rule_1_evidence_only_is_low():
    verdict = state([], [], evidence_only=True)
    assert (verdict["state"], verdict["rule"]) == ("LOW", 1)
    assert verdict["reasons"] == ["Automatic analysis was unavailable, so only the closest passages are shown."]


def test_rule_2_no_ready_documents_is_insufficient():
    verdict = state([], [], has_ready_documents=False)
    assert (verdict["state"], verdict["rule"]) == ("INSUFFICIENT", 2)
    assert verdict["reasons"] == ["No processed documents are available yet."]


def test_rule_2_zero_verified_claims_is_insufficient():
    verdict = state([aspect(status="uncovered")], [], claims_dropped=2)
    assert (verdict["state"], verdict["rule"]) == ("INSUFFICIENT", 2)
    assert verdict["reasons"][0] == "None of the retrieved passages states an answer to this question."
    assert "2 extracted statements were discarded because the quote could not be found in the source." in verdict["reasons"]


CONFLICT_POSITIONS = [
    {"key": "quantity:30|day", "display": "30 days", "claim_ids": ["C1", "C2"], "document_ids": ["doc-Agreement", "doc-Amendment"]},
    {"key": "quantity:45|day", "display": "45 days", "claim_ids": ["C3"], "document_ids": ["doc-Invoice"]},
]


def test_rule_3_conflict_takes_precedence_over_high_and_low_signals():
    claims = [claim("C1"), claim("C2", document="Amendment"), claim("C3", document="Invoice")]
    verdict = state([aspect(status="conflict", positions=CONFLICT_POSITIONS)], claims, ambiguous=True)
    assert (verdict["state"], verdict["rule"]) == ("CONFLICT", 3)
    assert verdict["reasons"] == [
        "3 relevant passages were confirmed across 3 documents.",
        "2 documents state 30 days; 1 document states 45 days.",
        "Because the documents disagree, no single answer is given.",
    ]


def test_conflict_with_supersession_note_stays_conflict():
    note = {"text": "x", "evidence": {"document": "Amendment.pdf"}}
    claims = [claim("C1"), claim("C3", document="Invoice")]
    verdict = state([aspect(status="conflict", positions=CONFLICT_POSITIONS, notes=[note])], claims)
    assert verdict["state"] == "CONFLICT"
    assert ("Amendment.pdf states that it replaces an earlier provision; the conflict is still shown so you can decide."
            in verdict["reasons"])


def test_rule_4_ambiguous_question_is_low():
    claims = [claim("C1"), claim("C2", document="Amendment")]
    verdict = state([aspect()], claims, ambiguous=True, ambiguity_note="'terms' could mean payment or termination.")
    assert (verdict["state"], verdict["rule"]) == ("LOW", 4)
    assert "The question can be read in more than one way: 'terms' could mean payment or termination." in verdict["reasons"]


def test_rule_5_uncovered_aspect_is_low():
    claims = [claim("C1"), claim("C2", document="Amendment")]
    verdict = state([aspect(), aspect("A2", "Warranty period", status="uncovered")], claims)
    assert (verdict["state"], verdict["rule"]) == ("LOW", 5)
    assert "No evidence was found for: warranty period." in verdict["reasons"]


def test_rule_6_inferred_only_is_low():
    claims = [claim("C1", explicit=False), claim("C2", document="Amendment", explicit=False)]
    verdict = state([aspect()], claims)
    assert (verdict["state"], verdict["rule"]) == ("LOW", 6)
    assert "The documents do not state this directly; the answer is inferred." in verdict["reasons"]


def test_rule_7_only_low_quality_ocr_is_low():
    claims = [claim("C1", ocr="low"), claim("C2", document="Scan2", ocr="low")]
    verdict = state([aspect()], claims)
    assert (verdict["state"], verdict["rule"]) == ("LOW", 7)
    assert "All supporting text comes from a low-quality scan." in verdict["reasons"]
    assert "2 passages come from scanned images." in verdict["reasons"]


def test_rule_8_two_independent_documents_is_high():
    claims = [claim("C1"), claim("C2", document="Policy")]
    verdict = state([aspect()], claims)
    assert (verdict["state"], verdict["rule"]) == ("HIGH", 8)
    assert verdict["reasons"] == [
        "2 relevant passages were confirmed across 2 documents.",
        "2 independent documents state the same thing directly.",
    ]


def test_high_allows_a_good_scan_and_one_low_scan_with_a_text_source():
    assert state([aspect()], [claim("C1"), claim("C2", document="Scan", ocr="low")])["state"] == "HIGH"
    assert state([aspect()], [claim("C1", ocr="good"), claim("C2", document="Scan", ocr="good")])["state"] == "HIGH"


def test_high_is_downgraded_when_low_quality_scans_are_the_only_support_for_an_aspect():
    claims = [claim("C1"), claim("C2", document="Policy"),
              claim("C3", aspect="A2", document="ScanA", ocr="low"), claim("C4", aspect="A2", document="ScanB", ocr="low")]
    verdict = state([aspect(), aspect("A2", "Invoice total")], claims)
    assert (verdict["state"], verdict["rule"]) == ("MEDIUM", 9)
    assert "Support for invoice total comes only from low-quality scans." in verdict["reasons"]


def test_rule_9_single_document_is_medium():
    verdict = state([aspect()], [claim("C1", document="Policy")])
    assert (verdict["state"], verdict["rule"]) == ("MEDIUM", 9)
    assert verdict["reasons"] == [
        "1 relevant passage was confirmed across 1 document.",
        "Only one document (Policy.pdf) states this.",
    ]


def test_two_passages_from_the_same_document_are_not_independent():
    assert state([aspect()], [claim("C1"), claim("C2")])["state"] == "MEDIUM"


def test_same_passage_in_two_files_is_not_independent():
    claims = [claim("C1", chunk="c1"), claim("C2", document="AgreementCopy", chunk="c2")]
    evidence = [{"chunk_id": "c1", "text_hash": "same"}, {"chunk_id": "c2", "text_hash": "same"}]
    assert evaluate([aspect()], claims, evidence)["state"] == "MEDIUM"


def test_second_source_only_inferred_is_medium_not_high():
    verdict = state([aspect()], [claim("C1"), claim("C2", document="Policy", explicit=False)])
    assert verdict["state"] == "MEDIUM"
    assert "Only one document states payment period directly." in verdict["reasons"]


def test_one_aspect_with_a_single_source_keeps_a_multi_aspect_answer_at_medium():
    claims = [claim("C1"), claim("C2", document="Policy"), claim("C3", aspect="A2", document="Invoice")]
    verdict = state([aspect(), aspect("A2", "Invoice total")], claims)
    assert verdict["state"] == "MEDIUM"
    assert "Only one document (Invoice.pdf) states invoice total." in verdict["reasons"]


def test_failed_conflict_check_caps_high_at_medium():
    claims = [claim("C1"), claim("C2", document="Policy")]
    verdict = state([aspect()], claims, conflict_check_failed=True)
    assert (verdict["state"], verdict["rule"]) == ("MEDIUM", 9)
    assert "The conflict check could not be completed." in verdict["reasons"]


def test_complementary_and_text_basis_reasons():
    positions = [{"key": "text:a", "display": "A", "claim_ids": ["C1"], "document_ids": ["d1"]},
                 {"key": "text:b", "display": "B", "claim_ids": ["C2"], "document_ids": ["d2"]}]
    claims = [claim("C1", scope="domestic invoices"), claim("C2", document="Policy", scope="export invoices")]
    verdict = state([aspect(status="complementary", positions=positions, basis="text")], claims)
    assert "Different values apply to different conditions: domestic invoices, export invoices." in verdict["reasons"]
    assert any("compared as text" in r for r in verdict["reasons"])


def test_the_same_inputs_always_give_the_same_verdict():
    claims = [claim("C1"), claim("C2", document="Policy")]
    assert state([aspect()], claims) == state([aspect()], claims)


def test_signals():
    claims = [claim("C1"), claim("C2", document="Amendment", explicit=False), claim("C3", document="Invoice", ocr="low")]
    aspects = [aspect(status="conflict", positions=CONFLICT_POSITIONS), aspect("A2", "Warranty", status="uncovered")]
    signals = composer._signals([{}] * 10, 5, claims, 2, aspects, ambiguous=False, llm_source="live")
    assert signals == {
        "evidence_retrieved": 10, "claims_extracted": 5, "claims_verified": 3, "claims_dropped": 2,
        "documents_cited": 3, "aspects_total": 2, "aspects_covered": 1, "conflicting_aspects": 1,
        "explicit_claims": 2, "ocr_claims": 1, "ocr_low_claims": 1, "ambiguous": False,
        "inferred_claims": 1, "aspects_uncovered": 1, "agreeing_documents": 2, "evidence_only": False,
        "conflict_check_failed": False, "llm_source": "live",
    }
