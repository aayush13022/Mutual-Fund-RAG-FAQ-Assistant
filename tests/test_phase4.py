"""Phase 4 RAG generation tests (prompts, post-processor, generator with mock LLM)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from config.settings import get_settings, load_settings
from ingestion.embedder import _get_embedding_provider_cached
from ingestion.models import Chunk
from rag.generator import answer
from rag.llm import MockLLMProvider, _get_llm_provider_cached
from rag.models import RetrievedChunk
from rag.postprocessor import (
    RETRIEVAL_MISS_MESSAGE,
    build_rag_response,
    count_sentences,
    retrieval_miss_response,
    truncate_to_max_sentences,
)
from rag.prompts import SYSTEM_PROMPT, build_context_block, build_user_prompt
from storage.indexer import index_chunks
from storage.metadata_store import MetadataStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent

GOLDEN_CASES = [
    ("What is the expense ratio of HDFC Defence Fund Direct Growth?", ["0.88"]),
    ("What is the minimum SIP for HDFC Gold ETF Fund of Fund?", ["100"]),
    ("What is the exit load on HDFC Mid Cap Fund Direct Growth?", ["1%"]),
    ("What is the benchmark of HDFC Large Cap Fund Direct Growth?", ["NIFTY 100"]),
    ("What is the risk classification of HDFC Small Cap Fund Direct Growth?", ["Very High"]),
    ("Who manages HDFC Defence Fund Direct Growth?", ["Manager"]),
    ("Since when has the fund manager been managing HDFC Defence Fund?", ["Apr 2025", "Tenure"]),
    ("What is the educational background of the HDFC Defence Fund manager?", ["Education"]),
    ("What is the work experience of the fund manager of HDFC Defence Fund?", ["Experience"]),
    ("Who manages HDFC Large Cap Fund Direct Growth?", ["Manager", "Rahul"]),
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
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("METADATA_DB_PATH", str(tmp_path / "metadata.db"))
    monkeypatch.setenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.0")
    get_settings.cache_clear()
    _get_embedding_provider_cached.cache_clear()
    _get_llm_provider_cached.cache_clear()
    settings = load_settings()
    index_chunks(_load_all_chunks(), settings=settings, triggered_by="test")
    yield settings
    get_settings.cache_clear()
    _get_embedding_provider_cached.cache_clear()
    _get_llm_provider_cached.cache_clear()


def test_system_prompt_enforces_facts_only_rules():
    assert "facts-only" in SYSTEM_PROMPT.lower()
    assert "3" in SYSTEM_PROMPT
    assert "investment advice" in SYSTEM_PROMPT.lower()


def test_build_context_block_includes_scheme_and_section():
    chunk = RetrievedChunk(
        chunk_id="demo",
        text="Scheme: Demo\nSection: expense_ratio\n\nExpense ratio: 1%",
        source_url="https://groww.in/mutual-funds/demo",
        scheme_name="Demo Fund",
        section_type="expense_ratio",
        score=1.0,
    )
    context = build_context_block([chunk])
    assert "Demo Fund" in context
    assert "expense_ratio" in context


def test_truncate_to_max_sentences():
    text = "One. Two. Three. Four."
    assert truncate_to_max_sentences(text, max_sentences=3) == "One. Two. Three."


def test_count_sentences():
    assert count_sentences("First. Second! Third?") == 3


def test_build_rag_response_sets_source_and_footer_fields():
    chunk = RetrievedChunk(
        chunk_id="demo",
        text="body",
        source_url="https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",
        scheme_name="HDFC Defence Fund Direct Growth",
        section_type="expense_ratio",
        score=1.0,
    )
    response = build_rag_response(
        "Answer one. Answer two. Answer three. Answer four.",
        top_chunk=chunk,
        last_updated_from_sources="2026-06-18",
    )
    assert count_sentences(response.answer) == 3
    assert response.source_url == chunk.source_url
    assert response.last_updated_from_sources == "2026-06-18"
    assert response.refused is False


def test_retrieval_miss_response_has_no_source():
    response = retrieval_miss_response(last_updated_from_sources="2026-06-18")
    assert response.answer == RETRIEVAL_MISS_MESSAGE
    assert response.source_url is None


def test_answer_retrieval_miss_skips_llm(indexed_settings):
    mock_llm = MockLLMProvider()
    with patch("rag.generator.retrieve", return_value=[]):
        response = answer("unknown topic", settings=indexed_settings, llm=mock_llm)
    assert response.answer == RETRIEVAL_MISS_MESSAGE
    assert response.source_url is None


def test_answer_retrieval_failure_returns_miss(indexed_settings):
    with patch("rag.generator.retrieve", side_effect=RuntimeError("embedder down")):
        response = answer("What is the weather in Mumbai?", settings=indexed_settings)
    assert response.answer == RETRIEVAL_MISS_MESSAGE
    assert response.source_url is None


def test_answer_with_mock_llm_returns_allowlisted_source(indexed_settings):
    response = answer(
        "What is the expense ratio of HDFC Defence Fund Direct Growth?",
        settings=indexed_settings,
        llm=MockLLMProvider(),
    )
    assert "0.88" in response.answer
    assert response.source_url == "https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth"
    assert response.last_updated_from_sources is not None
    assert count_sentences(response.answer) <= 3


@pytest.mark.parametrize("question,keywords", GOLDEN_CASES)
def test_golden_questions_with_mock_llm(question, keywords, indexed_settings):
    response = answer(question, settings=indexed_settings, llm=MockLLMProvider())
    lowered = response.answer.lower()
    assert any(keyword.lower() in lowered for keyword in keywords), response.answer
    assert response.source_url and response.source_url.startswith("https://groww.in/mutual-funds/")
    assert response.last_updated_from_sources
    assert count_sentences(response.answer) <= 3


def test_metadata_last_updated_available(indexed_settings):
    metadata = MetadataStore(settings=indexed_settings)
    assert metadata.get_last_updated_from_sources() is not None
