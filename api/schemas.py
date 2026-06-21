"""Pydantic schemas for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    answer: str
    source_url: str | None = None
    last_updated_from_sources: str | None = None
    disclaimer: str
    refused: bool
    educational_link: str | None = None


class SourceStatus(BaseModel):
    url: str
    scheme_name: str
    last_success_at: str | None = None
    last_status: str | None = None


class IngestionRunStatus(BaseModel):
    job_id: str
    triggered_by: str | None = None
    status: str | None = None
    documents_processed: int | None = None
    chunks_written: int | None = None
    started_at: str | None = None
    completed_at: str | None = None


class CorpusStatusResponse(BaseModel):
    active_version: str | None = None
    embedding_provider: str | None = None
    last_updated_from_sources: str | None = None
    last_ingestion: IngestionRunStatus | None = None
    sources: list[SourceStatus] = Field(default_factory=list)


class IngestRunResponse(BaseModel):
    status: str
    job_id: str | None = None
    documents_processed: int = 0
    chunks_written: int = 0
    corpus_version: str | None = None
