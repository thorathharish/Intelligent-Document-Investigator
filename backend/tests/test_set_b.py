"""Checkpoint 7: demo seed, the unrelated Set B, investigation isolation and the acceptance script.

The LLM is replaced by a scripted stand-in routed by question, so nothing here uses the network.
"""
import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.investigation import analyst
from app.main import app
from app.retrieval import retriever
from test_qa import ScriptedLLM

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import acceptance  # noqa: E402

PAYMENT = [
    ("Payment period", "within thirty (30) days of the invoice date", "30 days", "duration"),
    ("Payment period", "within 30 days of the invoice date", "30 days", "duration"),
    ("Payment period", "Payment due within 45 days of the invoice date", "45 days", "duration"),
]
SCRIPTS = {
    "What is the late payment fee?": ScriptedLLM([("Late fee", "late fee of 1.5% per month", "1.5%", "percent")]),
    "What is the invoice total, and who has to approve it?": ScriptedLLM([
        ("Invoice total", "The total amount due is USD 48,500", "USD 48,500", "money"),
        ("Approver", "must be approved by the Finance Director", "Finance Director", "text")]),
    "Who approves invoices above USD 25,000?": ScriptedLLM([
        ("Approver", "must be approved by the Finance Director", "Finance Director", "text")]),
    "What are the payment terms?": ScriptedLLM(PAYMENT),
    "Are the payment terms consistent across the documents?": ScriptedLLM(PAYMENT),
    "What payment terms apply after the amendment, and does the invoice follow them?": ScriptedLLM(PAYMENT),
    "How much notice is needed to terminate the agreement?": ScriptedLLM(
        [("Termination notice", "giving 60 days' written notice", "60 days", "duration"),
         ("Termination notice", "giving 90 days' written notice", "90 days", "duration")],
        supersession_quote="This Amendment replaces clause 9.1 of the Agreement"),
    "What is the warranty period for the equipment?": ScriptedLLM([]),
    "How many days of annual leave do employees get?": ScriptedLLM([
        ("Annual leave", "18 days of paid annual leave", "18 days", "number"),
        ("Annual leave", "24 days of paid annual leave", "24 days", "number")]),
    "How long is the probation period?": ScriptedLLM([
        ("Probation period", "probation period of six months", "six months", "duration"),
        ("Probation period", "probation period of 6 months", "6 months", "duration")]),
    "Is remote work permitted?": ScriptedLLM([
        ("Remote work", "Remote work is permitted for up to two days per week", "yes", "boolean"),
        ("Remote work", "remote work is not permitted for any employee", "no", "boolean")]),
    "What is the notice period?": ScriptedLLM([("Notice period", "giving 30 days' written notice", "30 days", "duration")]),
    "How much is the health insurance cover?": ScriptedLLM([]),
}
_QUESTION = re.compile(r"QUESTION:\n(.*?)\n\nEVIDENCE:", re.S)


class RoutedLLM:
    """Hands each question to its script; fails loudly on a question it was not given."""

    def __init__(self, scripts=SCRIPTS):
        self.scripts, self.asked = scripts, []

    def complete_json(self, system, user, validate):
        question = _QUESTION.search(user).group(1)
        self.asked.append(question)
        return self.scripts[question].complete_json(system, user, validate)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def llm(monkeypatch):
    routed = RoutedLLM()
    monkeypatch.setattr(analyst, "get_llm_client", lambda: routed)
    return routed


def _seed(client, name):
    response = client.post("/api/demo/seed", json={"set": name})
    assert response.status_code == 200
    return response.json()


def _ask(client, investigation_id, question):
    return client.post(f"/api/investigations/{investigation_id}/questions",
                       json={"question": question, "fresh": True}).json()


def _positions(result):
    names = {c["id"]: c["evidence"]["document"] for c in result["claims"]}
    return {p["display"]: sorted({names[cid] for cid in p["claim_ids"]})
            for a in result["aspects"] for p in a["positions"]}


# --- documents and seed -----------------------------------------------------------


def test_set_b_documents_and_manifests_exist():
    for name, count in (("set_a", 4), ("set_b", 3)):
        manifest = json.loads((ROOT / "demo_docs" / name / "manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["files"]) == count and manifest["title"].startswith("Demo:")
        assert all((ROOT / "demo_docs" / name / f).is_file() for f in manifest["files"])
    memo = (ROOT / "demo_docs" / "set_b" / "HR_Memo_2025-07.txt").read_text(encoding="utf-8")
    assert "remote work is not permitted for any employee" in memo
    # the missing-information case is genuinely absent from every Set B file
    assert "insurance" not in memo.lower()


def test_seed_set_b_ingests_and_indexes_through_the_normal_pipeline(client):
    seeded = _seed(client, "B")
    documents = {d["filename"]: d for d in client.get(f"/api/investigations/{seeded['id']}/documents").json()}
    assert set(documents) == {"Employee_Handbook.pdf", "Offer_Letter.docx", "HR_Memo_2025-07.txt"}
    assert all(d["status"] == "ready" and d["chunk_count"] > 0 for d in documents.values())
    assert documents["Employee_Handbook.pdf"]["page_count"] == 2

    chunks = db.query("SELECT c.*, d.filename FROM chunks c JOIN documents d ON d.id = c.document_id"
                      " WHERE c.investigation_id = ?", (seeded["id"],))
    assert all(c["embedding"] is not None for c in chunks)
    text = " ".join(c["text"] for c in chunks).lower()
    assert "18 days" in text and "24 days" in text and "insurance" not in text
    notice = next(c for c in chunks if "30 days' written notice" in c["text"])
    assert (notice["filename"], notice["page"], notice["section"]) == ("Employee_Handbook.pdf", 2, "4. Notice Period")


def test_seed_is_repeatable_and_sets_are_separate(client):
    a1, b1 = _seed(client, "A"), _seed(client, "B")
    a2, b2 = _seed(client, "a"), _seed(client, "B")
    assert a1["id"] == a2["id"] and b1["id"] == b2["id"] and a1["id"] != b1["id"]
    assert a1["title"] != b1["title"]
    count = db.query_one("SELECT COUNT(*) AS n FROM documents WHERE investigation_id = ?", (a1["id"],))["n"]
    assert count == 4  # seeding again added nothing


def test_unknown_demo_set_is_rejected(client):
    for name in ("Z", "../set_a", ""):
        response = client.post("/api/demo/seed", json={"set": name})
        assert response.status_code == 400 and response.json()["error"]["code"] == "unknown_demo_set"


# --- Set B through the unchanged pipeline --------------------------------------------


def test_b1_annual_leave_conflict(client, llm):
    result = _ask(client, _seed(client, "B")["id"], "How many days of annual leave do employees get?")
    assert result["state"] == "CONFLICT" and result["headline"] == "The documents disagree on annual leave."
    assert _positions(result) == {"18 days": ["Employee_Handbook.pdf"], "24 days": ["Offer_Letter.docx"]}
    assert sorted(s["text"] for s in result["answer"]) == [
        "Employee_Handbook.pdf states 18 days.", "Offer_Letter.docx states 24 days."]
    handbook = next(c for c in result["claims"] if c["evidence"]["document"] == "Employee_Handbook.pdf")
    assert handbook["evidence"]["page"] == 1 and handbook["evidence"]["section"] == "1. Annual Leave"


def test_b3_remote_work_yes_no_conflict(client, llm):
    result = _ask(client, _seed(client, "B")["id"], "Is remote work permitted?")
    assert result["state"] == "CONFLICT"
    assert _positions(result) == {"Yes": ["Employee_Handbook.pdf"], "No": ["HR_Memo_2025-07.txt"]}
    assert {c["position_key"] for c in result["claims"]} == {"boolean:yes", "boolean:no"}


def test_b2_probation_agrees_across_two_documents(client, llm):
    result = _ask(client, _seed(client, "B")["id"], "How long is the probation period?")
    assert result["state"] == "HIGH" and result["aspects"][0]["status"] == "consistent"
    assert _positions(result) == {"6 months": ["Employee_Handbook.pdf", "Offer_Letter.docx"]}


def test_b4_notice_period_single_document(client, llm):
    result = _ask(client, _seed(client, "B")["id"], "What is the notice period?")
    assert result["state"] == "MEDIUM" and _positions(result) == {"30 days": ["Employee_Handbook.pdf"]}
    assert "Only one document (Employee_Handbook.pdf) states this." in result["reasons"]


def test_b5_missing_information(client, llm):
    result = _ask(client, _seed(client, "B")["id"], "How much is the health insurance cover?")
    assert result["state"] == "INSUFFICIENT" and result["answer"] == [] and result["claims"] == []
    assert result["related"] and all("insurance" not in r["quote"].lower() for r in result["related"])


# --- isolation ------------------------------------------------------------------------


def test_set_a_and_set_b_do_not_share_evidence_or_cache(client, llm):
    a, b = _seed(client, "A")["id"], _seed(client, "B")["id"]
    a_files = {d["filename"] for d in client.get(f"/api/investigations/{a}/documents").json()}
    b_files = {d["filename"] for d in client.get(f"/api/investigations/{b}/documents").json()}
    assert not a_files & b_files

    # a notice-period question matches text in both sets; each investigation only sees its own documents
    assert {e["document"] for e in retriever.retrieve(a, "What is the notice period?")} <= a_files
    assert {e["document"] for e in retriever.retrieve(b, "What is the notice period?")} <= b_files

    question = "What is the notice period?"
    first_b = client.post(f"/api/investigations/{b}/questions", json={"question": question}).json()
    again_b = client.post(f"/api/investigations/{b}/questions", json={"question": question}).json()
    assert again_b["cached"] is True and again_b["run_id"] == first_b["run_id"]
    for claim in again_b["claims"]:
        owner = db.query_one("SELECT investigation_id FROM chunks WHERE id = ?", (claim["evidence"]["chunk_id"],))
        assert owner["investigation_id"] == b


# --- acceptance script ------------------------------------------------------------------


def test_acceptance_script_passes_on_set_a_then_set_b(client, llm):
    report = acceptance.run(client, ["A", "B"], settings.db_path)
    assert report.failed == [], report.failed
    assert report.known_gaps == []  # with a well-behaved analyst there is no gap
    groups = {row[0] for row in report.rows}
    assert groups == {"A", "B", "G", "H"} and len(report.rows) > 80
    assert set(q["question"] for name in ("A", "B") for q in acceptance.SETS[name]) <= set(SCRIPTS)


def test_acceptance_script_reports_failures(client, monkeypatch):
    # an analyst that finds nothing: the conflict and value checks must fail, not pass silently
    silent = RoutedLLM({q: ScriptedLLM([]) for q in SCRIPTS})
    monkeypatch.setattr(analyst, "get_llm_client", lambda: silent)
    for name in ("A", "B"):
        investigation_id = _seed(client, name)["id"]
        db.execute("DELETE FROM runs WHERE investigation_id = ?", (investigation_id,))  # no cached answers
    report = acceptance.run(client, ["B"], settings.db_path)
    failed = [name for _, name, ok, _ in report.rows if not ok]
    assert any("B1" in name and "state" in name for name in failed)
    assert any("B3" in name and "positions" in name for name in failed)
    assert not any("B5" in name for name in failed)  # the missing-information case still passes
    db.execute("DELETE FROM runs WHERE investigation_id = ?", (_seed(client, "B")["id"],))
