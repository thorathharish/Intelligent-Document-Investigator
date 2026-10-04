from fastapi import HTTPException

from .. import db


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def require_investigation(investigation_id: str):
    row = db.query_one("SELECT * FROM investigations WHERE id = ?", (investigation_id,))
    if row is None:
        raise api_error(404, "investigation_not_found", "Investigation not found")
    return row


DOCUMENT_FIELDS = "id, filename, ext, status, error_message, page_count, extraction_method, chunk_count"


def list_documents(investigation_id: str) -> list[dict]:
    rows = db.query(
        f"SELECT {DOCUMENT_FIELDS} FROM documents WHERE investigation_id = ? ORDER BY created_at, rowid",
        (investigation_id,),
    )
    return [dict(row) for row in rows]
