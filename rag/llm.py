"""LLM providers for answer generation (Groq default, mock for tests)."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> str:
        raise NotImplementedError


class GroqLLMProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _client_instance(self):
        if self._client is None:
            from openai import OpenAI

            if not self._settings.groq_api_key:
                raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
            self._client = OpenAI(
                api_key=self._settings.groq_api_key,
                base_url=GROQ_BASE_URL,
            )
        return self._client

    def chat(self, messages: list[dict[str, str]]) -> str:
        client = self._client_instance()
        response = client.chat.completions.create(
            model=self._settings.llm.model,
            messages=messages,
            temperature=self._settings.llm.temperature,
            max_tokens=self._settings.llm.max_tokens,
        )
        content = response.choices[0].message.content or ""
        return content.strip()


class MockLLMProvider(LLMProvider):
    """Deterministic provider for tests — summarizes context without external API calls."""

    _CHUNK_PATTERN = re.compile(
        r"\[Chunk \d+ \| .*?\]\n(.*?)(?=\n\[Chunk |\Z)",
        re.DOTALL,
    )

    @classmethod
    def _extract_bodies(cls, context: str) -> list[str]:
        bodies: list[str] = []
        for match in cls._CHUNK_PATTERN.finditer(context):
            chunk_text = match.group(1).strip()
            if "\n\n" in chunk_text:
                body = chunk_text.split("\n\n", 1)[1].strip()
            else:
                body = chunk_text
            if body:
                bodies.append(body.replace("\n", " "))
        return bodies

    def chat(self, messages: list[dict[str, str]]) -> str:
        user_content = messages[-1]["content"]
        context_match = re.search(r"Context:\n(.*)\n\nQuestion:", user_content, re.DOTALL)
        if not context_match:
            return "I could not find this information in my sources."

        bodies = self._extract_bodies(context_match.group(1))
        if not bodies:
            return "I could not find this information in my sources."

        question = user_content.split("Question:", 1)[-1].strip().lower()
        if any(token in question for token in ("manager", "manages", "who manage")):
            return " ".join(bodies[:2])[:500]
        return bodies[0][:400]


@lru_cache
def _get_llm_provider_cached(provider: str) -> LLMProvider:
    if provider == "mock":
        return MockLLMProvider()
    return GroqLLMProvider(get_settings())


def get_llm_provider(provider: str | None = None) -> LLMProvider:
    cfg = get_settings()
    selected = (provider or cfg.llm.provider).lower()
    if selected == "groq" and not cfg.groq_api_key:
        logger.warning(
            "GROQ_API_KEY is not set; falling back to mock LLM provider. "
            "Set GROQ_API_KEY in .env or use LLM_PROVIDER=mock explicitly."
        )
        selected = "mock"
    return _get_llm_provider_cached(selected)
