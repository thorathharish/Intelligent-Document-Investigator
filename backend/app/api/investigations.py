"""Investigation workspace endpoints (LLD section 6)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from .. import db
from ..schemas import InvestigationCreate
from . import list_documents, require_investigation

router = APIRouter()


@router.post("/investigations")
def create_investigation(body: InvestigationCreate | None = None) -> dict:
    title = (body.title or "").strip() if body else ""
    investigation = {
        "id": str(uuid.uuid4()),
        "title": title or "Untitled investigation",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.execute(
        "INSERT INTO investigations (id, title, created_at) VALUES (?, ?, ?)",
        (investigation["id"], investigation["title"], investigation["created_at"]),
    )
    return investigation


@router.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: str) -> dict:
    row = require_investigation(investigation_id)
    runs = db.query(
        "SELECT id, question, state, created_at FROM runs WHERE investigation_id = ? ORDER BY created_at",
        (investigation_id,),
    )
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "documents": list_documents(investigation_id),
        "runs": [dict(r) for r in runs],
    }
