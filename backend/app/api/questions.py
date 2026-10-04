"""Question and run-history endpoints (LLD section 6)."""
import json

from fastapi import APIRouter

from .. import db
from ..investigation.orchestrator import run_investigation
from ..schemas import QuestionRequest
from . import api_error, require_investigation

router = APIRouter()

MAX_QUESTION_CHARS = 500


@router.post("/investigations/{investigation_id}/questions")
def ask_question(investigation_id: str, body: QuestionRequest, debug: int = 0) -> dict:
    require_investigation(investigation_id)
    question = " ".join(body.question.split())
    if not question:
        raise api_error(400, "empty_question", "Please enter a question")
    if len(question) > MAX_QUESTION_CHARS:
        raise api_error(400, "question_too_long", f"Questions are limited to {MAX_QUESTION_CHARS} characters")
    return run_investigation(investigation_id, question, fresh=body.fresh, debug=bool(debug))


@router.get("/investigations/{investigation_id}/runs")
def list_runs(investigation_id: str) -> list[dict]:
    require_investigation(investigation_id)
    rows = db.query(
        "SELECT result_json FROM runs WHERE investigation_id = ? ORDER BY created_at, rowid", (investigation_id,)
    )
    return [json.loads(row["result_json"]) for row in rows]
