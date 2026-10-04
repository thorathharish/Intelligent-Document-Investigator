"""Checkpoint 1 smoke test: run the analyst prompt on two tiny passages against candidate models.

Usage (from repo root, venv active):
  python scripts/llm_smoke.py --list                 list free models currently on OpenRouter
  python scripts/llm_smoke.py                        test openrouter/free + up to 3 free candidates
  python scripts/llm_smoke.py --models a b c         test the given model ids
  python scripts/llm_smoke.py --json-mode ...        send response_format=json_object
"""
import argparse
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import settings  # noqa: E402
from app.investigation.prompts import SYSTEM_PROMPT, build_user_message  # noqa: E402
from app.llm.base import LLMBadOutput, LLMUnavailable  # noqa: E402
from app.llm.openrouter import OpenRouterClient  # noqa: E402
from app.schemas import validate_analyst_output  # noqa: E402

QUESTION = "Are the payment terms consistent across the documents?"
EVIDENCE = [
    {
        "eid": "E1",
        "document": "Agreement.pdf",
        "page": 2,
        "section": "4.2 Payment Terms",
        "text": "4.2 Payment Terms. The Customer shall pay each undisputed invoice within thirty (30) days "
        "of the invoice date.",
    },
    {
        "eid": "E2",
        "document": "Invoice.pdf",
        "page": 1,
        "section": None,
        "text": "Invoice INV-2041. Total due: USD 48,500. Payment due within 45 days of the invoice date.",
    },
]
PREFERRED = ["llama-3.3-70b", "gemini", "deepseek", "qwen", "mistral", "gemma"]


def free_models() -> list[str]:
    response = httpx.get(f"{settings.openrouter_base_url}/models", timeout=30)
    response.raise_for_status()
    return sorted(m["id"] for m in response.json().get("data", []) if m["id"].endswith(":free"))


def default_candidates() -> list[str]:
    available = free_models()
    picked: list[str] = []
    for keyword in PREFERRED:
        match = next((m for m in available if keyword in m and m not in picked), None)
        if match:
            picked.append(match)
        if len(picked) == 3:
            break
    return ["openrouter/free"] + picked


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def test_model(model: str, json_mode: bool) -> dict:
    client = OpenRouterClient(model=model, fallback_models=[], mode="live", supports_json_mode=json_mode)
    user = build_user_message(QUESTION, EVIDENCE)
    texts = {item["eid"]: item["text"] for item in EVIDENCE}
    row = {"model": model, "request": "fail", "json": "no", "claims": 0, "exact": "-", "values": "", "s": 0.0, "error": ""}
    started = time.monotonic()
    try:
        result = client.complete_json(SYSTEM_PROMPT, user, validate_analyst_output)
    except LLMUnavailable as exc:
        row["error"] = str(exc)[:110]
        return row
    except LLMBadOutput as exc:
        row.update(request="ok", error=str(exc)[:110])
        return row
    finally:
        row["s"] = round(time.monotonic() - started, 1)

    if result.from_recording:
        row["error"] = "live call failed (see log above); a recording was returned instead"
        return row

    claims = result.value.claims
    exact = sum(1 for c in claims if c.quote and c.quote in texts.get(c.evidence, ""))
    loose = sum(1 for c in claims if c.quote and _norm(c.quote) in _norm(texts.get(c.evidence, "")))
    row.update(
        request="ok",
        json="yes",
        claims=len(claims),
        exact=f"{exact}/{len(claims)} (loose {loose})",
        values=", ".join(f"{c.evidence}={c.value}" for c in claims)[:60],
        model=result.model,
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--json-mode", action="store_true")
    args = parser.parse_args()

    if args.list:
        print("\n".join(free_models()))
        return
    if not settings.openrouter_api_key:
        sys.exit("OPENROUTER_API_KEY is not set in backend/.env")

    models = args.models or default_candidates()
    print(f"json_mode={args.json_mode}  models={models}\n")
    rows = [test_model(m, args.json_mode) for m in models]
    header = f"{'model':<52} {'request':<8} {'json':<5} {'claims':<7} {'quotes exact':<18} {'sec':<6} values / error"
    print("\n" + header + "\n" + "-" * len(header))
    for r in rows:
        print(
            f"{r['model']:<52} {r['request']:<8} {r['json']:<5} {r['claims']:<7} {r['exact']:<18} "
            f"{r['s']:<6} {r['values'] or r['error']}"
        )


if __name__ == "__main__":
    main()
