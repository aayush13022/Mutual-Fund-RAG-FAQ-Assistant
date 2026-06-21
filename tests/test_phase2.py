"""Phase 2 tests: embeddings, ChromaDB vector store, metadata, and pipeline indexing."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from config.settings import get_settings, load_settings
from ingestion.chunker import chunk_sections
from ingestion.embedder import (
    MODEL_DIMENSIONS,
    _get_embedding_provider_cached,
    embed_chunks,
    embed_query,
    get_embedding_provider,
    select_embedding_model_key,
)
from ingestion.models import Chunk, utc_now
from ingestion.normalizer import normalize_sections
from ingestion.parser import parse_html
from ingestion.pipeline import run_ingestion
from storage.indexer import index_chunks
from storage.metadata_store import MetadataStore
from storage.vector_store import VectorStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFENCE_URL = "https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth"
DEFENCE_SLUG = "hdfc-defence-fund-direct-growth"


def _load_html(slug: str) -> str:
    flat = PROJECT_ROOT / "data" / "raw" / f"{slug}.html"
    dated_dir = PROJECT_ROOT / "data" / "raw" / slug
    if flat.exists():
        return flat.read_text(encoding="utf-8")
    if dated_dir.exists():
        return sorted(dated_dir.glob("*.html"), reverse=True)[0].read_text(encoding="utf-8")
    pytest.skip(f"No cached HTML for {slug}")


def _defence_chunks():
    html = _load_html(DEFENCE_SLUG)
    sections = normalize_sections(
        parse_html(html, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    )
    return chunk_sections(
        sections,
        scheme_name="HDFC Defence Fund Direct Growth",
        source_url=DEFENCE_URL,
    )


@pytest.fixture
def hash_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("METADATA_DB_PATH", str(tmp_path / "metadata.db"))
    get_settings.cache_clear()
    _get_embedding_provider_cached.cache_clear()
    settings = load_settings()
    yield settings
    get_settings.cache_clear()
    _get_embedding_provider_cached.cache_clear()


def test_select_embedding_model_key_routes_by_section_type(hash_settings):
    cfg = hash_settings.embeddings
    expense = Chunk(
        chunk_id="test-expense",
        text="Expense ratio (direct plan): 0.88%",
        source_url=DEFENCE_URL,
        scheme_name="HDFC Defence Fund Direct Growth",
        scheme_slug=DEFENCE_SLUG,
        section_type="expense_ratio",
        ingested_at=utc_now(),
    )
    overview = replace(expense, chunk_id="test-overview", section_type="overview", text="A" * 400)
    assert select_embedding_model_key(expense, cfg) == "small"
    assert select_embedding_model_key(overview, cfg) == "large"


def test_embed_chunks_produces_correct_dimensions(hash_settings):
    chunks = _defence_chunks()
    embedded = embed_chunks(chunks, settings=hash_settings)
    assert len(embedded) == len(chunks)
    for item in embedded:
        expected_dim = MODEL_DIMENSIONS[item.embedding_model_key]
        assert len(item.embedding) == expected_dim


def test_index_chunks_publishes_dual_collections(hash_settings):
    chunks = _defence_chunks()
    version = index_chunks(chunks, settings=hash_settings, triggered_by="test")
    assert version == "v1"

    store = VectorStore(settings=hash_settings)
    assert store.count(version=version, model_key="small") == 4
    assert store.count(version=version, model_key="large") == 7
    assert store.count(version=version) == 11

    metadata = MetadataStore(settings=hash_settings)
    info = metadata.get_corpus_version()
    assert info is not None
    assert info.active_version == "v1"
    assert info.embedding_provider == "hash"
    assert info.last_updated_from_sources is not None


def test_blue_green_swap_replaces_active_version(hash_settings):
    chunks = _defence_chunks()
    first = index_chunks(chunks, settings=hash_settings, triggered_by="test")
    second = index_chunks(chunks, settings=hash_settings, triggered_by="test")
    assert first == "v1"
    assert second == "v2"

    store = VectorStore(settings=hash_settings)
    assert store.active_version() == "v2"
    assert store.count() == 11

    metadata = MetadataStore(settings=hash_settings)
    assert metadata.get_corpus_version().active_version == "v2"
    assert metadata.next_corpus_version() == "v3"


def test_search_returns_relevant_expense_ratio_chunk(hash_settings):
    chunks = _defence_chunks()
    index_chunks(chunks, settings=hash_settings, triggered_by="test")

    store = VectorStore(settings=hash_settings)
    query_small = embed_query("expense ratio HDFC Defence", model_key="small", settings=hash_settings)
    query_large = embed_query("expense ratio HDFC Defence", model_key="large", settings=hash_settings)
    results = store.search_all(
        {"small": query_small, "large": query_large},
        top_k=3,
        scheme_filter="HDFC Defence Fund Direct Growth",
    )
    assert results
    assert any(result.section_type == "expense_ratio" for result in results)
    assert all(result.scheme_name == "HDFC Defence Fund Direct Growth" for result in results)


def test_run_ingestion_with_embed_indexes_defence_fund(hash_settings):
    result = run_ingestion(
        settings=hash_settings,
        urls=[DEFENCE_URL],
        use_cache=True,
        save_html=False,
        save_processed=False,
        persist_chunks=False,
        embed=True,
        triggered_by="test",
    )
    assert result.status.value == "success"
    assert result.corpus_version == "v1"
    assert result.chunks_written == 11
    assert result.source_results[0].embedded_count == 11

    metadata = MetadataStore(settings=hash_settings)
    with metadata._connect() as connection:
        row = connection.execute(
            "SELECT status, chunks_written FROM ingestion_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row["status"] == "success"
    assert row["chunks_written"] == 11
