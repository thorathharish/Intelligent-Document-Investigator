"""Recording store behind the live / replay / mock modes (LLD section 9.3)."""
import hashlib
import json
from datetime import datetime, timezone

from ..config import settings


def recording_key(system: str, user: str) -> str:
    return hashlib.sha256((system + "\n---\n" + user).encode("utf-8")).hexdigest()


def _path(key: str):
    return settings.recordings_dir / f"{key}.json"


def load(key: str) -> dict | None:
    path = _path(key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save(key: str, model: str, system: str, user: str, raw_response: str) -> None:
    settings.recordings_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "system": system,
        "user": user,
        "raw_response": raw_response,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _path(key).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
