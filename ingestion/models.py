"""Data models for the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class IngestionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class FundManager:
    name: str
    tenure: str
    education: str
    experience: str
    other_schemes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    source_url: str
    scheme_name: str
    scheme_slug: str
    section_type: str
    ingested_at: datetime
    sequence: int = 1
    manager_name: str | None = None


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk: Chunk
    embedding: tuple[float, ...]
    embedding_model: str
    embedding_model_key: str


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    text: str
    source_url: str
    scheme_name: str
    section_type: str
    score: float
    embedding_model_key: str


@dataclass
class ParsedSection:
    section_type: str
    text: str
    fields: dict[str, str] = field(default_factory=dict)
    managers: list[FundManager] = field(default_factory=list)


@dataclass
class FetchResult:
    url: str
    scheme_name: str
    scheme_slug: str
    html: str
    saved_path: str | None
    status_code: int
    fetched_at: datetime


@dataclass
class SourceIngestionResult:
    url: str
    scheme_name: str
    scheme_slug: str
    status: str
    sections: list[ParsedSection] = field(default_factory=list)
    error: str | None = None
    raw_html_path: str | None = None
    processed_path: str | None = None
    clean_txt_path: str | None = None
    chunks: list[Chunk] = field(default_factory=list)
    chunks_path: str | None = None
    embedded_count: int = 0


@dataclass
class IngestionResult:
    status: IngestionStatus
    started_at: datetime
    completed_at: datetime
    documents_processed: int
    sections_written: int
    chunks_written: int = 0
    corpus_version: str | None = None
    job_id: str | None = None
    source_results: list[SourceIngestionResult] = field(default_factory=list)

    @property
    def sections(self) -> list[ParsedSection]:
        all_sections: list[ParsedSection] = []
        for result in self.source_results:
            if result.status == "success":
                all_sections.extend(result.sections)
        return all_sections

    @property
    def chunks(self) -> list[Chunk]:
        all_chunks: list[Chunk] = []
        for result in self.source_results:
            if result.status == "success":
                all_chunks.extend(result.chunks)
        return all_chunks


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
