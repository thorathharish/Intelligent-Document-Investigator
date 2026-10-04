"""One key=value line per pipeline stage on stdout (LLD section 17)."""
import sys
from datetime import datetime, timezone


def _fmt(value) -> str:
    text = str(value)
    if " " in text or "=" in text:
        return '"' + text.replace('"', "'") + '"'
    return text


def log_stage(stage: str, level: str = "INFO", **fields) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [f"ts={ts}", f"level={level}", f"stage={stage}"]
    parts += [f"{key}={_fmt(value)}" for key, value in fields.items() if value is not None]
    print(" ".join(parts), file=sys.stdout, flush=True)
