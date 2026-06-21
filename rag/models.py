"""Data models for the retrieval and generation layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    source_url: str
    scheme_name: str
    section_type: str
    score: float
    embedding_model_key: str = ""
    retrieval_tier: str = "semantic"


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    source_url: str | None
    last_updated_from_sources: str | None
    disclaimer: str
    refused: bool
    educational_link: str | None = None
