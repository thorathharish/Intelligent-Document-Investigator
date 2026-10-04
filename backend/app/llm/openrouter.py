"""OpenRouter adapter (LLD section 9.2).

Failure chain for one logical call:
primary model -> retry primary once -> fallback model(s) -> recorded run if one exists -> error
(the caller turns the error into evidence-only mode).
"""
import threading
import time
from typing import Callable, TypeVar

import httpx

from ..config import settings
from ..logging_utils import log_stage
from . import recorder
from .base import LLMBadOutput, LLMResult, LLMUnavailable
from .json_utils import extract_json

T = TypeVar("T")

_call_lock = threading.Lock()
_last_call_at = 0.0


class _AttemptFailed(Exception):
    def __init__(self, detail: str, retryable: bool, retry_after: float | None = None):
        super().__init__(detail)
        self.retryable = retryable
        self.retry_after = retry_after


class OpenRouterClient:
    def __init__(
        self,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        mode: str | None = None,
        supports_json_mode: bool | None = None,
        http_client: httpx.Client | None = None,
    ):
        self.model = model or settings.openrouter_model
        self.fallback_models = settings.openrouter_fallback_models if fallback_models is None else fallback_models
        self.mode = mode or settings.llm_mode
        self.supports_json_mode = (
            settings.llm_supports_json_mode if supports_json_mode is None else supports_json_mode
        )
        self._http = http_client or httpx.Client(timeout=settings.llm_timeout_s)

    # --- public -----------------------------------------------------------------

    def complete_json(self, system: str, user: str, validate: Callable[[dict], T]) -> LLMResult[T]:
        key = recorder.recording_key(system, user)

        if self.mode in ("replay", "mock"):
            recorded = self._from_recording(key, validate)
            if recorded is not None:
                return recorded
            if self.mode == "mock":
                raise LLMUnavailable("mock mode: no recording for this prompt")

        try:
            return self._call_network(key, system, user, validate)
        except (LLMUnavailable, LLMBadOutput) as exc:
            recorded = self._from_recording(key, validate)
            if recorded is not None:
                log_stage("llm", level="WARN", status="recording_after_failure", error=type(exc).__name__)
                return recorded
            raise

    # --- recording --------------------------------------------------------------

    def _from_recording(self, key: str, validate: Callable[[dict], T]) -> LLMResult[T] | None:
        rec = recorder.load(key)
        if rec is None:
            return None
        try:
            value = validate(extract_json(rec.get("raw_response", "")))
        except Exception:
            return None
        return LLMResult(value=value, model=rec.get("model", "recording"), latency_ms=0, from_recording=True)

    # --- network ----------------------------------------------------------------

    def _call_network(self, key: str, system: str, user: str, validate: Callable[[dict], T]) -> LLMResult[T]:
        if not settings.openrouter_api_key:
            raise LLMUnavailable("OPENROUTER_API_KEY is not set")

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        started = time.monotonic()
        last_error = "no attempt made"

        # primary, one retry of the primary (only for retryable failures), then each fallback once
        plan = [(self.model, True)] + [(m, False) for m in self.fallback_models]
        for model, may_retry in plan:
            attempts = 2 if may_retry else 1
            for attempt in range(attempts):
                try:
                    content = self._post(model, messages)
                except _AttemptFailed as exc:
                    last_error = f"{model}: {exc}"
                    log_stage("llm", level="WARN", model=model, attempt=attempt + 1, error=str(exc))
                    if exc.retryable and attempt + 1 < attempts:
                        time.sleep(min(exc.retry_after if exc.retry_after is not None else 4.0, 10.0))
                        continue
                    break
                value, raw = self._parse_or_repair(model, messages, content, validate)
                latency_ms = int((time.monotonic() - started) * 1000)
                recorder.save(key, model, system, user, raw)
                log_stage("llm", model=model, ms=latency_ms, status="ok")
                return LLMResult(value=value, model=model, latency_ms=latency_ms, from_recording=False)

        raise LLMUnavailable(last_error)

    def _parse_or_repair(self, model: str, messages: list[dict], content: str, validate: Callable[[dict], T]):
        try:
            return validate(extract_json(content)), content
        except Exception as first_error:
            log_stage("llm", level="WARN", model=model, status="repair", error=str(first_error)[:200])
            repair_messages = messages + [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": f"Your reply was not valid. Problem: {first_error}. "
                    "Reply with the corrected JSON only.",
                },
            ]
            try:
                repaired = self._post(model, repair_messages)
                return validate(extract_json(repaired)), repaired
            except Exception as second_error:
                raise LLMBadOutput(f"{model}: {second_error}") from second_error

    def _post(self, model: str, messages: list[dict]) -> str:
        """One HTTP request. Returns message content or raises _AttemptFailed."""
        global _last_call_at
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": settings.llm_max_tokens,
        }
        if self.supports_json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "X-Title": "Document Investigator",
        }

        with _call_lock:
            wait = settings.llm_min_gap_s - (time.monotonic() - _last_call_at)
            if wait > 0:
                time.sleep(wait)
            try:
                response = self._http.post(
                    f"{settings.openrouter_base_url}/chat/completions", json=body, headers=headers
                )
            except httpx.TimeoutException as exc:
                raise _AttemptFailed("timeout", retryable=True) from exc
            except httpx.HTTPError as exc:
                raise _AttemptFailed(f"network error: {type(exc).__name__}", retryable=True) from exc
            finally:
                _last_call_at = time.monotonic()

        if response.status_code != 200:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise _AttemptFailed(
                f"HTTP {response.status_code}: {_error_text(response)}",
                retryable=retryable,
                retry_after=_retry_after(response),
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise _AttemptFailed("response body is not JSON", retryable=True) from exc
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            code = err.get("code") if isinstance(err, dict) else None
            message = err.get("message") if isinstance(err, dict) else str(err)
            retryable = code == 429 or (isinstance(code, int) and code >= 500)
            raise _AttemptFailed(f"provider error {code}: {str(message)[:200]}", retryable=retryable)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise _AttemptFailed("response has no message content", retryable=True) from exc
        if not content or not str(content).strip():
            raise _AttemptFailed("empty content", retryable=True)
        return str(content)


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None


def _error_text(response: httpx.Response) -> str:
    try:
        err = response.json().get("error", {})
        message = err.get("message") if isinstance(err, dict) else str(err)
        return str(message)[:200]
    except Exception:
        return response.text[:200]
