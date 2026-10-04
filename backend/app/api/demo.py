"""Health endpoint. The demo seed endpoint is added at Checkpoint 7."""
import importlib.util

from fastapi import APIRouter

from ..config import settings
from ..schemas import HealthResponse

router = APIRouter()


def _available(module: str) -> str:
    return "ok" if importlib.util.find_spec(module) is not None else "unavailable"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        llm_mode=settings.llm_mode,
        model=settings.openrouter_model,
        embedder=_available("fastembed"),
        ocr=_available("rapidocr_onnxruntime"),
    )
