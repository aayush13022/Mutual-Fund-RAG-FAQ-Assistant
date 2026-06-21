"""Post-processing for generated answers."""

from __future__ import annotations

import re

from config.settings import Settings, get_settings
from rag.models import RAGResponse, RetrievedChunk

DISCLAIMER = "Facts-only. No investment advice."
RETRIEVAL_MISS_MESSAGE = "I could not find this information in my sources."
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def count_sentences(text: str) -> int:
    cleaned = text.strip()
    if not cleaned:
        return 0
    return len(SENTENCE_SPLIT_PATTERN.split(cleaned))


def truncate_to_max_sentences(text: str, max_sentences: int = 3) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    sentences = SENTENCE_SPLIT_PATTERN.split(cleaned)
    if len(sentences) <= max_sentences:
        return cleaned
    return " ".join(sentences[:max_sentences]).strip()


def build_rag_response(
    answer: str,
    *,
    top_chunk: RetrievedChunk | None,
    last_updated_from_sources: str | None,
    refused: bool = False,
    educational_link: str | None = None,
) -> RAGResponse:
    trimmed = truncate_to_max_sentences(answer)
    if RETRIEVAL_MISS_MESSAGE.lower() in trimmed.lower():
        return RAGResponse(
            answer=RETRIEVAL_MISS_MESSAGE,
            source_url=None,
            last_updated_from_sources=last_updated_from_sources,
            disclaimer=DISCLAIMER,
            refused=refused,
            educational_link=educational_link,
        )

    source_url = top_chunk.source_url if top_chunk else None
    return RAGResponse(
        answer=trimmed,
        source_url=source_url,
        last_updated_from_sources=last_updated_from_sources,
        disclaimer=DISCLAIMER,
        refused=refused,
        educational_link=educational_link,
    )


def retrieval_miss_response(
    *,
    last_updated_from_sources: str | None,
    settings: Settings | None = None,
) -> RAGResponse:
    _ = settings or get_settings()
    return RAGResponse(
        answer=RETRIEVAL_MISS_MESSAGE,
        source_url=None,
        last_updated_from_sources=last_updated_from_sources,
        disclaimer=DISCLAIMER,
        refused=False,
    )
