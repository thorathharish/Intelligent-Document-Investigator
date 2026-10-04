"""Tolerant JSON extraction from model replies (LLD section 9.2)."""
import json
import re

_FENCE = re.compile(r"```(?:json)?", re.IGNORECASE)


def extract_json(text: str) -> dict:
    """Return the outermost JSON object in `text`. Raises ValueError if there is none."""
    if not text or not text.strip():
        raise ValueError("empty reply")
    cleaned = _FENCE.sub("", text)
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object found")

    depth = 0
    in_string = False
    escaped = False
    end = -1
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise ValueError("JSON object is not closed")

    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg} at position {exc.pos}") from exc
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    return data
