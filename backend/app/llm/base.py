"""Provider-independent LLM interface (LLD section 9.1). The investigation engine imports only this."""
from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar

T = TypeVar("T")


class LLMUnavailable(Exception):
    """Network failure, timeout, 5xx, 429 after retry, missing key, or a mock-mode miss."""


class LLMBadOutput(Exception):
    """No parseable / valid JSON after one repair attempt."""


@dataclass
class LLMResult(Generic[T]):
    value: T
    model: str
    latency_ms: int
    from_recording: bool


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, validate: Callable[[dict], T]) -> LLMResult[T]: ...
