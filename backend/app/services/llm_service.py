"""LLM providers.

Concrete providers conform to `LLMProvider` and are selected via
settings.LLM_PROVIDER. Streaming is first-class so the chat endpoint
can yield tokens to the client as they arrive.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from functools import lru_cache

from app.config import get_settings


class LLMProvider(ABC):
    """Chat-completion LLM interface."""

    @abstractmethod
    async def generate(self, messages: list[dict]) -> str:
        """Single-shot completion. `messages` is OpenAI-style [{role, content}]."""
        ...

    @abstractmethod
    def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yields token / text fragments as they arrive."""
        ...


class GroqProvider(LLMProvider):
    """Groq async client. Free tier, very fast inference."""

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ):
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to backend/.env "
                "(get a free key at https://console.groq.com)."
            )
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def generate(self, messages: list[dict]) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=False,
        )
        return resp.choices[0].message.content or ""

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        async for chunk in resp:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


@lru_cache
def get_llm() -> LLMProvider:
    """Factory: returns the configured LLM provider (cached singleton)."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()

    if provider == "groq":
        return GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.MODEL_NAME,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}. Supported: groq"
    )
