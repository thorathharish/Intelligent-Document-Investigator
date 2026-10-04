"""Evidence inspection endpoints: passage context and the rendered source page."""
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def seeded(client):
    investigation = client.post("/api/demo/seed", json={"set": "A"}).json()
    return {d["filename"]: d for d in client.get(f"/api/investigations/{investigation['id']}/documents").json()}


def test_chunk_context_returns_neighbours(client, seeded):
    agreement = seeded["Master_Services_Agreement.pdf"]["id"]
    chunks = db.query("SELECT id, ordinal, text FROM chunks WHERE document_id = ? ORDER BY ordinal", (agreement,))
    middle = client.get(f"/api/chunks/{chunks[5]['id']}").json()
    assert middle["chunk"]["text"] == chunks[5]["text"] and middle["chunk"]["page"] == 2
    assert middle["prev"]["id"] == chunks[4]["id"] and middle["next"]["id"] == chunks[6]["id"]
    assert client.get(f"/api/chunks/{chunks[0]['id']}").json()["prev"] is None
    assert client.get("/api/chunks/nope").json()["error"]["code"] == "chunk_not_found"


def test_pdf_page_image_highlights_the_quote(client, seeded):
    agreement = seeded["Master_Services_Agreement.pdf"]["id"]
    plain = client.get(f"/api/documents/{agreement}/pages/2/image")
    marked = client.get(f"/api/documents/{agreement}/pages/2/image",
                        params={"q": "pay each undisputed invoice within thirty (30) days of the invoice date"})
    assert plain.status_code == marked.status_code == 200
    assert plain.headers["content-type"] == marked.headers["content-type"] == "image/png"
    assert plain.content[:4] == b"\x89PNG" and plain.content != marked.content  # the highlight changes the render
    width = pymupdf.Pixmap(marked.content).width
    assert abs(width - 595 / 72 * 110) <= 2


def test_page_image_errors_and_image_documents(client, seeded):
    agreement = seeded["Master_Services_Agreement.pdf"]["id"]
    assert client.get(f"/api/documents/{agreement}/pages/9/image").json()["error"]["code"] == "page_out_of_range"
    assert client.get("/api/documents/nope/pages/1/image").json()["error"]["code"] == "document_not_found"
    policy = seeded["Vendor_Payment_Policy.docx"]["id"]
    assert client.get(f"/api/documents/{policy}/pages/1/image").status_code == 404
    scan = client.get(f"/api/documents/{seeded['Invoice_INV-2041.png']['id']}/pages/1/image")
    assert scan.status_code == 200 and scan.content[:4] == b"\x89PNG"
