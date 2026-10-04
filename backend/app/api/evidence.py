"""Evidence inspection endpoints (LLD section 6): passage context and the rendered source page."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from .. import db
from . import api_error

router = APIRouter()

PAGE_DPI = 110
MAX_QUOTE_CHARS = 300


def _brief(row) -> dict | None:
    if row is None:
        return None
    return {"id": row["id"], "text": row["text"], "page": row["page"], "section": row["section"]}


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str) -> dict:
    """A passage with the passages just before and after it in the same document."""
    chunk = db.query_one("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
    if chunk is None:
        raise api_error(404, "chunk_not_found", "Passage not found")

    def neighbour(offset: int):
        return db.query_one(
            "SELECT * FROM chunks WHERE document_id = ? AND ordinal = ?", (chunk["document_id"], chunk["ordinal"] + offset)
        )

    return {"chunk": _brief(chunk), "prev": _brief(neighbour(-1)), "next": _brief(neighbour(1))}


@router.get("/documents/{document_id}/pages/{page}/image")
def page_image(document_id: str, page: int, q: str = ""):
    """The source page as a PNG. For PDF pages with a text layer the quote is highlighted."""
    document = db.query_one("SELECT ext, stored_path, status FROM documents WHERE id = ?", (document_id,))
    if document is None or not Path(document["stored_path"]).is_file():
        raise api_error(404, "document_not_found", "Document not found")

    if document["ext"] in ("png", "jpg"):
        if page != 1:
            raise api_error(404, "page_out_of_range", "This document has one page")
        return FileResponse(document["stored_path"], media_type="image/png" if document["ext"] == "png" else "image/jpeg")
    if document["ext"] != "pdf":
        raise api_error(404, "page_out_of_range", "This document has no pages")

    import pymupdf

    with pymupdf.open(document["stored_path"]) as pdf:
        if page < 1 or page > len(pdf):
            raise api_error(404, "page_out_of_range", "Page not found")
        pdf_page = pdf[page - 1]
        quote = " ".join(q.split())[:MAX_QUOTE_CHARS]
        if quote:
            rects = pdf_page.search_for(quote) or pdf_page.search_for(quote[:60])
            for rect in rects:
                pdf_page.add_highlight_annot(rect)
        png = pdf_page.get_pixmap(dpi=PAGE_DPI).tobytes("png")
    return Response(content=png, media_type="image/png")
