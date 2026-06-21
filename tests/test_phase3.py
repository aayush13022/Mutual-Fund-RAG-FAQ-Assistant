"""Phase 3 retrieval tests: scheme detection, section hints, tiered retriever."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from config.settings import get_settings, load_settings
from ingestion.embedder import _get_embedding_provider_cached
from ingestion.models import Chunk
from rag.retriever import retrieve
from rag.scheme_detector import detect_scheme
from rag.section_detector import detect_section_hint
from storage.indexer import index_chunks

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RETRIEVAL_CASES = [
    ("expense ratio HDFC Defence Fund", "expense_ratio", "Defence"),
    ("Who manages HDFC Mid Cap Fund?", "fund_management", "Mid Cap"),
    ("exit load HDFC Small Cap", "exit_load", "Small Cap"),
    ("benchmark HDFC Large Cap", "benchmark", "Large Cap"),
    ("minimum SIP gold ETF fund", "minimum_investment", "Gold ETF"),
    ("education of Defence fund manager", "fund_management", "Defence"),
    ("tax implication HDFC Defence", "tax", "Defence"),
    ("investment objective HDFC Defence", "investment_objective", "Defence"),
    ("NAV of HDFC Mid Cap", "overview", "Mid Cap"),
]


def _chunk_from_dict(payload: dict) -> Chunk:
    return Chunk(
        chunk_id=payload["chunk_id"],
        text=payload["text"],
        source_url=payload["source_url"],
        scheme_name=payload["scheme_name"],
        scheme_slug=payload["scheme_slug"],
        section_type=payload["section_type"],
        ingested_at=datetime.fromisoformat(payload["ingested_at"]),
        sequence=payload.get("sequence", 1),
        manager_name=payload.get("manager_name"),
    )


def _load_all_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    processed_dir = PROJECT_ROOT / "data" / "processed"
    for path in sorted(processed_dir.glob("*/chunks.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        chunks.extend(_chunk_from_dict(item) for item in payload["chunks"])
    if not chunks:
        pytest.skip("Processed chunk fixtures not available")
    return chunks


@pytest.fixture
def indexed_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("METADATA_DB_PATH", str(tmp_path / "metadata.db"))
    monkeypatch.setenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.0")
    get_settings.cache_clear()
    _get_embedding_provider_cached.cache_clear()
    settings = load_settings()
    index_chunks(_load_all_chunks(), settings=settings, triggered_by="test")
    yield settings
    get_settings.cache_clear()
    _get_embedding_provider_cached.cache_clear()


@pytest.mark.parametrize(
    "query,expected_scheme",
    [
        ("expense ratio HDFC Defence Fund", "HDFC Defence Fund Direct Growth"),
        ("Who manages HDFC Mid Cap Fund?", "HDFC Mid Cap Fund Direct Growth"),
        ("minimum SIP gold ETF fund", "HDFC Gold ETF Fund of Fund Direct Plan Growth"),
        ("benchmark HDFC Large Cap", "HDFC Large Cap Fund Direct Growth"),
    ],
)
def test_detect_scheme(query, expected_scheme, indexed_settings):
    assert detect_scheme(query, indexed_settings) == expected_scheme


@pytest.mark.parametrize(
    "query,expected_section",
    [
        ("expense ratio HDFC Defence Fund", "expense_ratio"),
        ("Who manages HDFC Mid Cap Fund?", "fund_management"),
        ("fund management of HDFC Large Cap Fund Direct Growth", "fund_management"),
        ("exit load HDFC Small Cap", "exit_load"),
        ("NAV of HDFC Mid Cap", "overview"),
        ("tax implication HDFC Defence", "tax"),
    ],
)
def test_detect_section_hint(query, expected_section, indexed_settings):
    assert detect_section_hint(query, indexed_settings) == expected_section


@pytest.mark.parametrize("query,expected_section,scheme_needle", RETRIEVAL_CASES)
def test_retrieve_matrix(query, expected_section, scheme_needle, indexed_settings):
    results = retrieve(query, settings=indexed_settings)
    assert results, f"No results for query: {query}"
    top = results[0]
    assert top.section_type == expected_section
    assert scheme_needle.lower() in top.scheme_name.lower()


def test_retrieve_expense_ratio_without_scheme_returns_multiple_funds(indexed_settings):
    results = retrieve("expense ratio", settings=indexed_settings)
    assert results
    schemes = {item.scheme_name for item in results}
    assert len(schemes) >= 2
    assert results[0].section_type == "expense_ratio"


def test_retrieve_defence_expense_ratio_excludes_other_cap_funds(indexed_settings):
    results = retrieve("expense ratio HDFC Defence", settings=indexed_settings)
    assert results
    assert results[0].section_type == "expense_ratio"
    assert "Defence" in results[0].scheme_name
    for item in results:
        assert "Mid Cap" not in item.scheme_name
        assert "Large Cap" not in item.scheme_name


def test_tier1_metadata_used_for_single_section_queries(indexed_settings):
    results = retrieve("benchmark HDFC Large Cap", settings=indexed_settings)
    assert results
    assert results[0].retrieval_tier == "metadata"
    assert results[0].section_type == "benchmark"


def test_tier1_metadata_used_for_fund_management(indexed_settings):
    results = retrieve(
        "fund management of HDFC Large Cap Fund Direct Growth",
        settings=indexed_settings,
    )
    assert results
    assert all(item.retrieval_tier == "metadata" for item in results)
    assert all(item.section_type == "fund_management" for item in results)
