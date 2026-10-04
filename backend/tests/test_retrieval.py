import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.retrieval import embedder, retriever

PAYMENT = b"""1. Payment Terms

The customer shall pay each undisputed invoice within thirty days of the invoice date by bank transfer.

2. Late Payment

Any amount not paid when due accrues a late fee of 1.5% per month on the outstanding balance.

3. Invoices

Invoices are issued monthly in arrears and list every consignment delivered during the month.

4. Disputes

The customer must raise any invoice dispute in writing within ten days of receiving the invoice.
"""
LEAVE = b"Every employee is entitled to eighteen days of annual leave in each calendar year of service.\n"
GARDEN = b"Tomato seedlings should be planted after the last frost and watered twice a week in summer.\n"
OTHER_INVESTIGATION = b"The annual leave allowance for contractors is zero days because contractors are not employees.\n"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _investigation(client, files):
    inv = client.post("/api/investigations", json={"title": "Retrieval"}).json()["id"]
    client.post(f"/api/investigations/{inv}/documents",
                files=[("files", (name, data, "text/plain")) for name, data in files])
    return inv


@pytest.fixture(scope="module")
def inv(client):
    return _investigation(client, [("payment.txt", PAYMENT), ("leave.txt", LEAVE), ("garden.txt", GARDEN)])


def test_retrieval_is_scoped_to_the_investigation(client, inv):
    other = _investigation(client, [("contractors.txt", OTHER_INVESTIGATION)])
    evidence = retriever.retrieve(inv, "How many days of annual leave do employees get?")
    own = {row["id"] for row in db.query("SELECT id FROM chunks WHERE investigation_id = ?", (inv,))}
    assert evidence and all(e["chunk_id"] in own for e in evidence)
    assert all(e["document"] != "contractors.txt" for e in evidence)
    assert [e["document"] for e in retriever.retrieve(other, "annual leave")] == ["contractors.txt"]


def test_bm25_ranks_the_relevant_chunk_first(inv):
    evidence = retriever.retrieve(inv, "What is the late fee on overdue amounts?")
    best = next(e for e in evidence if e["bm25_rank"] == 1)
    assert "late fee of 1.5% per month" in best["text"]
    assert evidence[0]["document"] == "payment.txt"


def test_evidence_ids_are_sequential_and_stable(inv):
    first = retriever.retrieve(inv, "When must invoices be paid?")
    second = retriever.retrieve(inv, "When must invoices be paid?")
    assert [e["eid"] for e in first] == [f"E{i}" for i in range(1, len(first) + 1)]
    assert [(e["eid"], e["chunk_id"]) for e in first] == [(e["eid"], e["chunk_id"]) for e in second]
    assert len({e["chunk_id"] for e in first}) == len(first)


def test_every_document_keeps_a_slot(inv):
    # payment.txt has four strongly matching chunks; with only three slots the other documents still appear
    evidence = retriever.retrieve(inv, "invoice payment late fee dispute", top_k=3)
    assert len(evidence) == 3
    assert {e["document"] for e in evidence} == {"payment.txt", "leave.txt", "garden.txt"}
    wide = retriever.retrieve(inv, "invoice payment late fee dispute")
    assert sum(e["document"] == "payment.txt" for e in wide) == 4


def test_bm25_only_when_dense_search_is_unavailable(inv, monkeypatch):
    monkeypatch.setattr(embedder, "embed_query", lambda text: None)
    evidence = retriever.retrieve(inv, "late fee per month")
    assert evidence and all(e["dense_rank"] is None for e in evidence)
    assert "late fee" in evidence[0]["text"]


def test_no_documents_returns_no_evidence(client):
    empty = client.post("/api/investigations", json={}).json()["id"]
    assert retriever.retrieve(empty, "anything") == []
