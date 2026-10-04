"""Settings loaded from backend/.env (LLD section 3)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


def _str(key: str, default: str) -> str:
    value = os.getenv(key)
    return value.strip() if value and value.strip() else default


def _bool(key: str, default: bool) -> bool:
    return _str(key, str(default)).lower() in {"1", "true", "yes", "on"}


def _list(key: str) -> list[str]:
    return [item.strip() for item in _str(key, "").split(",") if item.strip()]


def _path(key: str, default: str) -> Path:
    path = Path(_str(key, default))
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = field(default_factory=lambda: _str("LLM_PROVIDER", "openrouter"))
    openrouter_api_key: str = field(default_factory=lambda: _str("OPENROUTER_API_KEY", ""), repr=False)
    openrouter_base_url: str = field(
        default_factory=lambda: _str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    )
    openrouter_model: str = field(default_factory=lambda: _str("OPENROUTER_MODEL", "openrouter/free"))
    openrouter_fallback_models: list[str] = field(default_factory=lambda: _list("OPENROUTER_FALLBACK_MODELS"))
    llm_mode: str = field(default_factory=lambda: _str("LLM_MODE", "live").lower())
    llm_supports_json_mode: bool = field(default_factory=lambda: _bool("LLM_SUPPORTS_JSON_MODE", False))
    llm_supports_vision: bool = field(default_factory=lambda: _bool("LLM_SUPPORTS_VISION", False))
    llm_timeout_s: float = field(default_factory=lambda: float(_str("LLM_TIMEOUT_S", "45")))
    llm_min_gap_s: float = field(default_factory=lambda: float(_str("LLM_MIN_GAP_S", "3")))
    llm_max_tokens: int = field(default_factory=lambda: int(_str("LLM_MAX_TOKENS", "2000")))
    prompt_version: str = field(default_factory=lambda: _str("PROMPT_VERSION", "1"))
    embed_model: str = field(default_factory=lambda: _str("EMBED_MODEL", "BAAI/bge-small-en-v1.5"))
    top_k: int = field(default_factory=lambda: int(_str("TOP_K", "10")))
    max_file_mb: int = field(default_factory=lambda: int(_str("MAX_FILE_MB", "20")))
    max_files: int = field(default_factory=lambda: int(_str("MAX_FILES", "10")))
    data_dir: Path = field(default_factory=lambda: _path("DATA_DIR", "./data"))
    enable_timeline: bool = field(default_factory=lambda: _bool("ENABLE_TIMELINE", False))
    enable_graph: bool = field(default_factory=lambda: _bool("ENABLE_GRAPH", False))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def recordings_dir(self) -> Path:
        return self.data_dir / "llm_recordings"


settings = Settings()
