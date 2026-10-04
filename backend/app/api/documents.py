"""Document upload and status endpoints (LLD section 6)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from .. import db
from ..config import settings
from ..ingestion.pipeline import process_document
from ..ingestion.validate import ValidationError, validate_file
from . import DOCUMENT_FIELDS, api_error, list_documents, require_investigation

router = APIRouter()


@router.post("/investigations/{investigation_id}/documents")
def upload_documents(
    investigation_id: str,
    background: BackgroundTasks,
    files: list[UploadFile] = File(default=[]),
) -> dict:
    require_investigation(investigation_id)
    if not files:
        raise api_error(400, "no_files", "No files were uploaded")
    if len(files) > settings.max_files:
        raise api_error(400, "too_many_files", f"Upload at most {settings.max_files} files at a time")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    accepted_ids, rejected = [], []
    for upload in files:
        filename = (upload.filename or "unnamed").replace("\\", "/").rsplit("/", 1)[-1]
        data = upload.file.read()
        try:
            ext, sha256 = validate_file(filename, data)
        except ValidationError as exc:
            rejected.append({"filename": filename, "reason": str(exc)})
            continue

        document_id = str(uuid.uuid4())
        existing = db.query_one(
            "SELECT stored_path FROM documents WHERE investigation_id = ? AND sha256 = ?"
            " AND status NOT IN ('failed', 'duplicate')",
            (investigation_id, sha256),
        )
        if existing is not None:
            status, stored_path = "duplicate", existing["stored_path"]
        else:
            status = "queued"
            path = settings.uploads_dir / f"{document_id}.{ext}"
            path.write_bytes(data)
            stored_path = str(path)

        db.execute(
            "INSERT INTO documents (id, investigation_id, filename, ext, stored_path, sha256, size_bytes,"
            " status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                document_id,
                investigation_id,
                filename,
                ext,
                stored_path,
                sha256,
                len(data),
                status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        accepted_ids.append(document_id)
        if status == "queued":
            background.add_task(process_document, document_id)

    accepted = [
        dict(db.query_one(f"SELECT {DOCUMENT_FIELDS} FROM documents WHERE id = ?", (document_id,)))
        for document_id in accepted_ids
    ]
    return {"accepted": accepted, "rejected": rejected}


@router.get("/investigations/{investigation_id}/documents")
def get_documents(investigation_id: str) -> list[dict]:
    require_investigation(investigation_id)
    return list_documents(investigation_id)
