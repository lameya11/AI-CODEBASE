"""LLM client interface with OpenAI, Anthropic, and NoOp implementations."""
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract LLM client."""

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict],
    ) -> tuple[str, str]:
        """
        Send a completion request.

        Args:
            system:   System prompt.
            messages: List of {"role": "user"|"assistant", "content": str}.

        Returns:
            (answer_text, model_name)
        """
        ...

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True if a real LLM is configured and callable."""
        ...


class NoOpLLMClient(LLMClient):
    """Fallback when no LLM key is configured."""

    def complete(self, system: str, messages: list[dict]) -> tuple[str, str]:
        return (
            "No LLM API key is configured. Showing the most relevant code sections instead.",
            "none",
        )

    @property
    def is_configured(self) -> bool:
        return False


class OpenAILLMClient(LLMClient):
    """OpenAI chat completion client."""

    MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str) -> None:
        import openai  # type: ignore
        self._client = openai.OpenAI(api_key=api_key)

    def complete(self, system: str, messages: list[dict]) -> tuple[str, str]:
        formatted = [{"role": "system", "content": system}] + messages
        response = self._client.chat.completions.create(
            model=self.MODEL,
            messages=formatted,
            temperature=0.1,
        )
        return response.choices[0].message.content or "", self.MODEL

    @property
    def is_configured(self) -> bool:
        return True


class AnthropicLLMClient(LLMClient):
    """Anthropic Claude client."""

    MODEL = "claude-3-haiku-20240307"

    def __init__(self, api_key: str) -> None:
        import anthropic  # type: ignore
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, system: str, messages: list[dict]) -> tuple[str, str]:
        response = self._client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return response.content[0].text, self.MODEL

    @property
    def is_configured(self) -> bool:
        return True


def get_llm_client() -> LLMClient:
    """Return the appropriate LLM client based on settings."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai" and settings.OPENAI_API_KEY:
        try:
            return OpenAILLMClient(settings.OPENAI_API_KEY)
        except Exception as exc:
            logger.warning("Failed to initialize OpenAI client: %s", exc)

    if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        try:
            return AnthropicLLMClient(settings.ANTHROPIC_API_KEY)
        except Exception as exc:
            logger.warning("Failed to initialize Anthropic client: %s", exc)

    return NoOpLLMClient()
