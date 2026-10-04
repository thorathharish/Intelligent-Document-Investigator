"""process_document: extract -> clean -> chunk -> embed -> store (LLD section 7.6)."""
import time
import traceback
import uuid
from pathlib import Path

from .. import db
from ..logging_utils import log_stage
from ..retrieval import embedder
from . import IngestionError
from .chunk import chunk_pages
from .clean import clean_pages
from .extract import extract


def set_status(document_id: str, status: str, error_message: str | None = None) -> None:
    db.execute("UPDATE documents SET status = ?, error_message = ? WHERE id = ?", (status, error_message, document_id))


def process_document(document_id: str) -> None:
    doc = db.query_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if doc is None or doc["status"] != "queued":
        return
    started = time.monotonic()
    try:
        set_status(document_id, "extracting")
        pages, page_count = extract(Path(doc["stored_path"]), doc["ext"])
        chunks = chunk_pages(clean_pages(pages))
        if not chunks:
            raise IngestionError("No readable text found")

        set_status(document_id, "indexing")
        vectors = embedder.embed_passages(
            [embedder.passage_text(doc["filename"], c["section"], c["text"]) for c in chunks]
        )

        conn = db.get_conn()
        conn.executemany(
            "INSERT INTO chunks (id, document_id, investigation_id, ordinal, page, section, paragraph_index,"
            " text, text_hash, extraction_method, ocr_confidence, embedding)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    str(uuid.uuid4()),
                    document_id,
                    doc["investigation_id"],
                    c["ordinal"],
                    c["page"],
                    c["section"],
                    c["paragraph_index"],
                    c["text"],
                    c["text_hash"],
                    c["extraction_method"],
                    c["ocr_confidence"],
                    vectors[i].tobytes() if vectors is not None else None,
                )
                for i, c in enumerate(chunks)
            ],
        )
        methods = {c["extraction_method"] for c in chunks}
        method = "mixed" if len(methods) > 1 else methods.pop()
        conn.execute(
            "UPDATE documents SET status = 'ready', error_message = NULL, page_count = ?, chunk_count = ?,"
            " extraction_method = ? WHERE id = ?",
            (page_count, len(chunks), method, document_id),
        )
        conn.commit()
        log_stage(
            "ingest",
            doc=document_id,
            inv=doc["investigation_id"],
            status="ready",
            pages=page_count,
            chunks=len(chunks),
            method=method,
            embedded=vectors is not None,
            ms=int((time.monotonic() - started) * 1000),
        )
    except Exception as exc:
        db.get_conn().rollback()
        message = str(exc) if isinstance(exc, IngestionError) else "Could not read this file"
        set_status(document_id, "failed", message)
        log_stage(
            "ingest",
            level="WARN",
            doc=document_id,
            inv=doc["investigation_id"],
            status="failed",
            error=f"{type(exc).__name__}: {exc}"[:200],
        )
        if not isinstance(exc, IngestionError):
            traceback.print_exc()
