from ..config import settings
from .base import LLMBadOutput, LLMClient, LLMResult, LLMUnavailable


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "openrouter":
        from .openrouter import OpenRouterClient

        return OpenRouterClient()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")


__all__ = ["LLMBadOutput", "LLMClient", "LLMResult", "LLMUnavailable", "get_llm_client"]
