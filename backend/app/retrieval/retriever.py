"""Hybrid retrieval with per-document diversity (LLD section 8.3). BM25 alone if dense search is unavailable."""
import numpy as np

from ..config import settings
from . import embedder
from .index import get_index, tokenize

CANDIDATES = 20
RRF_K = 60


def _bm25_ranking(index, question: str) -> list[int]:
    if index.bm25 is None:
        return []
    scores = index.bm25.get_scores(tokenize(question))
    order = np.argsort(-scores, kind="stable")
    return [int(i) for i in order if scores[i] > 0][:CANDIDATES]


def _dense_ranking(index, question: str) -> list[int]:
    if index.matrix is None:
        return []
    query = embedder.embed_query(question)
    if query is None:
        return []
    scores = index.matrix @ query
    order = np.argsort(-scores, kind="stable")[:CANDIDATES]
    return [index.matrix_rows[int(i)] for i in order]


def retrieve(investigation_id: str, question: str, top_k: int | None = None) -> list[dict]:
    """Return evidence items E1..En for the question, scoped to one investigation."""
    top_k = top_k or settings.top_k
    index = get_index(investigation_id)
    if not index.chunks:
        return []

    bm25 = _bm25_ranking(index, question)
    dense = _dense_ranking(index, question)
    bm25_rank = {position: rank for rank, position in enumerate(bm25, start=1)}
    dense_rank = {position: rank for rank, position in enumerate(dense, start=1)}

    # reciprocal rank fusion over the lists a chunk appears in
    fused: dict[int, float] = {}
    for ranks in (bm25_rank, dense_rank):
        for position, rank in ranks.items():
            fused[position] = fused.get(position, 0.0) + 1.0 / (RRF_K + rank)
    ordered = sorted(fused, key=lambda position: (-fused[position], position))

    # document diversity: the best chunk of every document first (at most top_k documents), then fill by rank
    chosen: list[int] = []
    seen_documents: set[str] = set()
    for position in ordered:
        document_id = index.chunks[position]["document_id"]
        if document_id not in seen_documents and len(chosen) < top_k:
            seen_documents.add(document_id)
            chosen.append(position)
    for position in ordered:
        if len(chosen) >= top_k:
            break
        if position not in chosen:
            chosen.append(position)
    chosen.sort(key=lambda position: (-fused[position], position))

    evidence = []
    for number, position in enumerate(chosen, start=1):
        chunk = index.chunks[position]
        evidence.append(
            {
                "eid": f"E{number}",
                "chunk_id": chunk["id"],
                "document_id": chunk["document_id"],
                "document": chunk["filename"],
                "page": chunk["page"],
                "section": chunk["section"],
                "paragraph": chunk["paragraph_index"],
                "text": chunk["text"],
                "text_hash": chunk["text_hash"],
                "extraction_method": chunk["extraction_method"],
                "ocr_confidence": chunk["ocr_confidence"],
                "fused_score": round(fused[position], 5),
                "dense_rank": dense_rank.get(position),
                "bm25_rank": bm25_rank.get(position),
            }
        )
    return evidence
