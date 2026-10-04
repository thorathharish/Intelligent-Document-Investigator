"""End-to-end question flow on demo Set A with a scripted stand-in for the LLM (no network)."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.investigation import analyst
from app.llm.base import LLMResult, LLMUnavailable
from app.main import app

SET_A = Path(__file__).resolve().parents[2] / "demo_docs" / "set_a"
FILES = ["Master_Services_Agreement.pdf", "Amendment_1.pdf", "Invoice_INV-2041.pdf", "Vendor_Payment_Policy.docx"]
_BLOCK = re.compile(r'<evidence id="(E\d+)"[^>]*>\n(.*?)\n</evidence>', re.S)


class ScriptedLLM:
    """Plays the analyst: for each scripted fact, cites every evidence passage that contains the quote."""

    def __init__(self, facts, extra_claims=(), supersession_quote=None):
        self.facts, self.extra_claims, self.calls = facts, list(extra_claims), 0
        self.supersession_quote = supersession_quote

    def complete_json(self, system, user, validate):
        self.calls += 1
        aspects, claims, answer, supersession = [], [], [], []
        for eid, text in _BLOCK.findall(user):
            if self.supersession_quote and self.supersession_quote in text:
                supersession.append({"evidence": eid, "quote": self.supersession_quote, "aspect": "A1", "note": "x"})
        for label, quote, value, value_type in self.facts:
            existing = next((a for a in aspects if a["label"] == label), None)
            aspect_id = existing["id"] if existing else f"A{len(aspects) + 1}"
            if not existing:
                aspects.append({"id": aspect_id, "label": label})
            for eid, text in _BLOCK.findall(user):
                if quote in text:
                    claim_id = f"C{len(claims) + 1}"
                    claims.append({"id": claim_id, "aspect": aspect_id, "evidence": eid, "quote": quote,
                                   "value": value, "value_type": value_type, "scope": None, "explicit": True})
                    answer.append({"text": f"{label}: {value}.", "claims": [claim_id]})
        for extra in self.extra_claims:
            claims.append(extra)
            answer.append({"text": "An unsupported statement.", "claims": [extra["id"]]})
        data = {"aspects": aspects, "claims": claims, "answer": answer, "ambiguous": False,
                "supersession": supersession}
        return LLMResult(value=validate(data), model="scripted", latency_ms=1, from_recording=False)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def inv(client):
    investigation_id = client.post("/api/investigations", json={"title": "Set A"}).json()["id"]
    client.post(
        f"/api/investigations/{investigation_id}/documents",
        files=[("files", (name, (SET_A / name).read_bytes(), "application/octet-stream")) for name in FILES],
    )
    documents = client.get(f"/api/investigations/{investigation_id}/documents").json()
    assert [d["status"] for d in documents] == ["ready"] * 4
    return investigation_id


def _ask(client, inv, question, llm, monkeypatch):
    monkeypatch.setattr(analyst, "get_llm_client", lambda: llm)
    response = client.post(f"/api/investigations/{inv}/questions", json={"question": question})
    assert response.status_code == 200
    return response.json()


def _assert_grounded(result):
    """Every displayed quote and location must match the stored chunk row."""
    for claim in result["claims"]:
        ev = claim["evidence"]
        row = db.query_one(
            "SELECT c.text, c.page, c.section, c.document_id, d.filename FROM chunks c JOIN documents d"
            " ON d.id = c.document_id WHERE c.id = ?", (ev["chunk_id"],))
        assert ev["quote"] in row["text"]
        assert (ev["page"], ev["section"], ev["document_id"], ev["document"]) == (
            row["page"], row["section"], row["document_id"], row["filename"])
    cited = {cid for sentence in result["answer"] for cid in sentence["claim_ids"]}
    assert cited <= {c["id"] for c in result["claims"]}


def test_a1_normal_question_has_verified_citations(client, inv, monkeypatch):
    fabricated = {"id": "C99", "aspect": "A1", "evidence": "E1", "quote": "a late fee of 9% per week applies to all",
                  "value": "9%", "value_type": "percent"}
    llm = ScriptedLLM([("Late fee", "late fee of 1.5% per month", "1.5%", "percent")], [fabricated])
    result = _ask(client, inv, "What is the late payment fee?", llm, monkeypatch)

    assert llm.calls == 1
    assert result["state"] == "MEDIUM" and result["degraded"] is False
    assert {c["evidence"]["document"] for c in result["claims"]} == {
        "Master_Services_Agreement.pdf", "Vendor_Payment_Policy.docx"}
    assert all(c["position_key"] == "percent:1.5" for c in result["claims"])
    agreement = next(c for c in result["claims"] if c["evidence"]["document"].startswith("Master"))
    assert agreement["evidence"]["page"] == 2 and agreement["evidence"]["section"] == "4.3 Late Payment"
    # the fabricated claim and the sentence built on it are gone
    assert result["signals"]["claims_dropped"] == 1 and result["signals"]["claims_verified"] == 2
    assert all("unsupported" not in s["text"].lower() for s in result["answer"])
    assert sorted(c["citation"] for c in result["claims"]) == [1, 2]
    _assert_grounded(result)


def test_cross_document_question_cites_both_documents(client, inv, monkeypatch):
    llm = ScriptedLLM([
        ("Invoice total", "The total amount due is USD 48,500", "USD 48,500", "money"),
        ("Approver", "must be approved by the Finance Director", "Finance Director", "text"),
    ])
    result = _ask(client, inv, "What is the invoice total, and who has to approve it?", llm, monkeypatch)

    documents = {c["evidence"]["document"] for c in result["claims"]}
    assert documents == {"Invoice_INV-2041.pdf", "Vendor_Payment_Policy.docx"}
    assert result["signals"]["documents_cited"] == 2 and len(result["answer"]) == 2
    assert len(result["aspects"]) == 2 and all(a["status"] == "consistent" for a in result["aspects"])
    _assert_grounded(result)


def test_payment_terms_conflict_shows_both_positions_and_no_winner(client, inv, monkeypatch):
    llm = ScriptedLLM([
        ("Payment period", "within thirty (30) days of the invoice date", "30 days", "duration"),
        ("Payment period", "within 30 days of the invoice date", "30 days", "duration"),
        ("Payment period", "Payment due within 45 days of the invoice date", "45 days", "duration"),
    ])
    result = _ask(client, inv, "What are the payment terms?", llm, monkeypatch)

    assert result["state"] == "CONFLICT" and result["headline"] == "The documents disagree on payment period."
    (aspect,) = result["aspects"]
    assert aspect["status"] == "conflict" and aspect["notes"] == []
    names = {c["id"]: c["evidence"]["document"] for c in result["claims"]}
    positions = {p["display"]: sorted(names[cid] for cid in p["claim_ids"]) for p in aspect["positions"]}
    assert positions == {
        "30 days": ["Amendment_1.pdf", "Master_Services_Agreement.pdf"],
        "45 days": ["Invoice_INV-2041.pdf"],
    }
    # the answer states each side with its documents and prefers neither
    assert [s["text"] for s in result["answer"]] == [
        "Master_Services_Agreement.pdf and Amendment_1.pdf state 30 days.",
        "Invoice_INV-2041.pdf states 45 days.",
    ]
    assert result["signals"]["conflicting_aspects"] == 1 and result["signals"]["documents_cited"] == 3
    _assert_grounded(result)


def test_termination_notice_conflict_keeps_the_cited_supersession_note(client, inv, monkeypatch):
    llm = ScriptedLLM(
        [("Termination notice", "giving 60 days' written notice", "60 days", "duration"),
         ("Termination notice", "giving 90 days' written notice", "90 days", "duration")],
        supersession_quote="This Amendment replaces clause 9.1 of the Agreement",
    )
    result = _ask(client, inv, "How much notice is needed to terminate the agreement?", llm, monkeypatch)

    assert result["state"] == "CONFLICT"
    (aspect,) = result["aspects"]
    assert {p["display"] for p in aspect["positions"]} == {"60 days", "90 days"}
    (note,) = aspect["notes"]
    assert note["evidence"]["document"] == "Amendment_1.pdf" and "replaces clause 9.1" in note["evidence"]["quote"]
    assert note["text"].startswith("Amendment_1.pdf states that it replaces")
    assert len(result["answer"]) == 2  # both sides are still stated
    _assert_grounded(result)


def test_agreeing_documents_are_one_position_without_conflict(client, inv, monkeypatch):
    llm = ScriptedLLM([("Late fee", "late fee of 1.5% per month", "1.5%", "percent")])
    result = _ask(client, inv, "What is the late payment fee?", llm, monkeypatch)
    (aspect,) = result["aspects"]
    assert result["state"] == "MEDIUM" and aspect["status"] == "consistent"
    assert len(aspect["positions"]) == 1 and len(aspect["positions"][0]["document_ids"]) == 2


def test_conflict_engine_failure_still_returns_the_answer(client, inv, monkeypatch):
    from app.investigation import conflicts

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(conflicts, "detect", broken)
    llm = ScriptedLLM([("Late fee", "late fee of 1.5% per month", "1.5%", "percent")])
    result = _ask(client, inv, "What is the late payment fee?", llm, monkeypatch)
    assert result["state"] == "MEDIUM" and len(result["claims"]) == 2
    assert "The conflict check could not be completed." in result["warnings"]


def test_a5_missing_information_is_not_answered(client, inv, monkeypatch):
    result = _ask(client, inv, "What is the warranty period for the equipment?", ScriptedLLM([]), monkeypatch)
    assert result["state"] == "INSUFFICIENT"
    assert result["answer"] == [] and result["claims"] == []
    assert 0 < len(result["related"]) <= 3


def test_only_unverifiable_claims_means_no_answer(client, inv, monkeypatch):
    invented = {"id": "C1", "aspect": "A1", "evidence": "E1", "quote": "the equipment is covered by a five year warranty",
                "value": "5 years", "value_type": "duration"}
    llm = ScriptedLLM([], [invented])
    llm.facts = []
    monkeypatch.setattr(analyst, "get_llm_client", lambda: llm)
    # the scripted aspect list is empty, so add one for the invented claim to attach to
    original = llm.complete_json

    def with_aspect(system, user, validate):
        return original(system, user, lambda data: validate({**data, "aspects": [{"id": "A1", "label": "Warranty"}]}))

    llm.complete_json = with_aspect
    result = client.post(f"/api/investigations/{inv}/questions", json={"question": "How long is the warranty?"}).json()
    assert result["state"] == "INSUFFICIENT" and result["answer"] == [] and result["claims"] == []
    assert result["signals"]["claims_dropped"] == 1


def test_llm_failure_gives_evidence_only_result(client, inv, monkeypatch):
    class Down:
        def complete_json(self, system, user, validate):
            raise LLMUnavailable("429 after retry")

    result = _ask(client, inv, "What is the late payment fee?", Down(), monkeypatch)
    assert result["degraded"] is True and result["state"] == "LOW"
    assert result["answer"] == [] and result["claims"] == [] and len(result["related"]) == 5


def test_runs_are_persisted_and_question_is_validated(client, inv):
    runs = client.get(f"/api/investigations/{inv}/runs").json()
    assert len(runs) >= 4 and runs[0]["question"] == "What is the late payment fee?"
    empty = client.post(f"/api/investigations/{inv}/questions", json={"question": "   "})
    assert empty.status_code == 400 and empty.json()["error"]["code"] == "empty_question"
    long = client.post(f"/api/investigations/{inv}/questions", json={"question": "x" * 501})
    assert long.status_code == 400 and long.json()["error"]["code"] == "question_too_long"
    missing = client.post("/api/investigations/nope/questions", json={"question": "hi"})
    assert missing.status_code == 404


def test_question_without_documents(client):
    empty = client.post("/api/investigations", json={}).json()["id"]
    result = client.post(f"/api/investigations/{empty}/questions", json={"question": "Anything?"}).json()
    assert result["state"] == "INSUFFICIENT" and result["reasons"] == ["No processed documents are available yet."]
