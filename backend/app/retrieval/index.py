"""Per-investigation in-memory search index, rebuilt from SQLite when the chunks change (LLD section 8.2)."""
import re
import threading
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from .. import db
from .embedder import EMBED_DIM

_TOKEN = re.compile(r"[a-z0-9]+")
_lock = threading.Lock()
_cache: dict[str, "Index"] = {}


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Index:
    signature: tuple
    chunks: list[dict]              # chunk rows joined with the document filename
    bm25: BM25Okapi | None
    matrix: np.ndarray | None       # rows = chunks that have an embedding
    matrix_rows: list[int]          # matrix row -> position in `chunks`


def _signature(investigation_id: str) -> tuple:
    row = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(MAX(c.rowid), 0) AS last FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE c.investigation_id = ? AND d.status = 'ready'",
        (investigation_id,),
    )
    return (row["n"], row["last"])


def get_index(investigation_id: str) -> Index:
    signature = _signature(investigation_id)
    with _lock:
        cached = _cache.get(investigation_id)
        if cached is not None and cached.signature == signature:
            return cached

        rows = db.query(
            "SELECT c.id, c.document_id, d.filename, c.ordinal, c.page, c.section, c.paragraph_index, c.text,"
            " c.text_hash, c.extraction_method, c.ocr_confidence, c.embedding"
            " FROM chunks c JOIN documents d ON d.id = c.document_id"
            " WHERE c.investigation_id = ? AND d.status = 'ready' ORDER BY d.created_at, d.rowid, c.ordinal",
            (investigation_id,),
        )
        chunks, vectors, matrix_rows = [], [], []
        for position, row in enumerate(rows):
            chunk = dict(row)
            embedding = chunk.pop("embedding")
            chunks.append(chunk)
            if embedding is not None and len(embedding) == EMBED_DIM * 4:
                vectors.append(np.frombuffer(embedding, dtype=np.float32))
                matrix_rows.append(position)

        index = Index(
            signature=signature,
            chunks=chunks,
            bm25=BM25Okapi([tokenize(c["text"]) or ["_"] for c in chunks]) if chunks else None,
            matrix=np.vstack(vectors) if vectors else None,
            matrix_rows=matrix_rows,
        )
        _cache[investigation_id] = index
        return index
