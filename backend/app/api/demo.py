"""Health endpoint and the demo seed (LLD section 6)."""
import hashlib
import importlib.util
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks

from .. import db
from ..config import REPO_ROOT, settings
from ..ingestion import ocr
from ..retrieval import embedder
from ..schemas import HealthResponse, SeedRequest
from . import api_error
from .documents import store_files
from .investigations import get_investigation

router = APIRouter()

DEMO_DIR = REPO_ROOT / "demo_docs"


def _state(module: str, status: str) -> str:
    return status if importlib.util.find_spec(module) is not None else "unavailable"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        llm_mode=settings.llm_mode,
        model=settings.openrouter_model,
        embedder=_state("fastembed", embedder.status()),
        ocr=_state("rapidocr_onnxruntime", ocr.status()),
    )


@router.post("/demo/seed")
def seed_demo(body: SeedRequest, background: BackgroundTasks) -> dict:
    """Open a demo investigation preloaded with a bundled document set.

    The set is described by demo_docs/set_<x>/manifest.json; files go through the normal upload path.
    Seeding again returns the existing investigation for that set instead of creating a duplicate.
    """
    folder = DEMO_DIR / f"set_{body.set.strip().lower()}"
    manifest_path = folder / "manifest.json"
    if not body.set.strip().isalnum() or not manifest_path.is_file():
        raise api_error(400, "unknown_demo_set", "Unknown demo set")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [(name, (folder / name).read_bytes()) for name in manifest["files"]]
    wanted = sorted(hashlib.sha256(data).hexdigest() for _, data in files)

    for row in db.query(
        "SELECT id FROM investigations WHERE title = ? ORDER BY created_at DESC, rowid DESC", (manifest["title"],)
    ):
        documents = db.query("SELECT sha256, status FROM documents WHERE investigation_id = ?", (row["id"],))
        if sorted(d["sha256"] for d in documents) == wanted and all(d["status"] != "failed" for d in documents):
            return get_investigation(row["id"])

    investigation_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO investigations (id, title, created_at) VALUES (?, ?, ?)",
        (investigation_id, manifest["title"], datetime.now(timezone.utc).isoformat()),
    )
    store_files(investigation_id, files, background)
    return get_investigation(investigation_id)
