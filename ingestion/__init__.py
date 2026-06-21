"""Ingestion pipeline: fetch, parse, normalize, and chunk Groww fund pages."""

from ingestion.chunk_store import load_chunks, save_chunks
from ingestion.chunker import chunk_sections, count_tokens
from ingestion.fetcher import fetch_all_sources, fetch_url, scheme_slug_from_url
from ingestion.embedder import embed_chunks, embed_query, select_embedding_model_key
from ingestion.models import (
    Chunk,
    EmbeddedChunk,
    FetchResult,
    FundManager,
    IngestionResult,
    IngestionStatus,
    ParsedSection,
    SearchResult,
    SourceIngestionResult,
)
from ingestion.normalizer import normalize_section, normalize_sections
from ingestion.parser import parse_html
from ingestion.pipeline import ingest_source, run_ingestion
from ingestion.processed_store import load_clean_text, load_processed_sections, save_processed_sections
from ingestion.url_validator import URLNotAllowlistedError, get_source_for_url, validate_url

__all__ = [
    "Chunk",
    "EmbeddedChunk",
    "FetchResult",
    "FundManager",
    "IngestionResult",
    "IngestionStatus",
    "ParsedSection",
    "SearchResult",
    "SourceIngestionResult",
    "URLNotAllowlistedError",
    "chunk_sections",
    "count_tokens",
    "embed_chunks",
    "embed_query",
    "fetch_all_sources",
    "fetch_url",
    "get_source_for_url",
    "ingest_source",
    "load_chunks",
    "load_clean_text",
    "load_processed_sections",
    "normalize_section",
    "normalize_sections",
    "parse_html",
    "run_ingestion",
    "save_chunks",
    "save_processed_sections",
    "scheme_slug_from_url",
    "select_embedding_model_key",
    "validate_url",
]
