"""Local embeddings with fastembed (LLD section 8.1). Lazy singleton behind a lock."""
import threading

import numpy as np

from ..config import settings
from ..logging_utils import log_stage

EMBED_DIM = 384
BATCH_SIZE = 32

_lock = threading.Lock()
_model = None
_failed = False


def _get_model():
    global _model, _failed
    if _model is None and not _failed:
        try:
            from fastembed import TextEmbedding

            _model = TextEmbedding(settings.embed_model)
        except Exception as exc:
            _failed = True
            log_stage("embed", level="WARN", error=f"{type(exc).__name__}: {exc}"[:200])
    return _model


def status() -> str:
    return "unavailable" if _failed else "ok"


def _normalise(vector) -> np.ndarray:
    v = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(v))
    return v / norm if norm > 0 else v


def passage_text(filename: str, section: str | None, text: str) -> str:
    return f"{filename} — {section or ''}\n{text}"


def embed_query(text: str) -> np.ndarray | None:
    with _lock:
        model = _get_model()
        if model is None:
            return None
        try:
            return _normalise(next(iter(model.query_embed(text))))
        except Exception as exc:
            log_stage("embed", level="WARN", error=f"{type(exc).__name__}: {exc}"[:200])
            return None


def embed_passages(texts: list[str]) -> list[np.ndarray] | None:
    """Return one L2-normalised float32 vector per text, or None if the embedder is unavailable."""
    with _lock:
        model = _get_model()
        if model is None:
            return None
        try:
            return [_normalise(v) for v in model.embed(texts, batch_size=BATCH_SIZE)]
        except Exception as exc:
            log_stage("embed", level="WARN", error=f"{type(exc).__name__}: {exc}"[:200])
            return None
