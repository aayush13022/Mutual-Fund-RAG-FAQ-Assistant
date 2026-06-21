"""Chunker and end-to-end Phase 1 pipeline tests."""

import json
from pathlib import Path

import pytest

from config.settings import REQUIRED_SECTIONS, load_settings
from ingestion.chunk_store import load_chunks
from ingestion.chunker import chunk_sections, count_tokens
from ingestion.normalizer import normalize_sections
from ingestion.parser import parse_html
from ingestion.pipeline import ingest_source, run_ingestion

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFENCE_URL = "https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth"

EXPECTED_CHUNK_COUNTS = {
    "hdfc-defence-fund-direct-growth": 11,
    "hdfc-mid-cap-fund-direct-growth": 10,
    "hdfc-large-cap-fund-direct-growth": 10,
    "hdfc-small-cap-fund-direct-growth": 10,
    "hdfc-gold-etf-fund-of-fund-direct-plan-growth": 10,
}


def _load_html(slug: str) -> str:
    flat = PROJECT_ROOT / "data" / "raw" / f"{slug}.html"
    dated_dir = PROJECT_ROOT / "data" / "raw" / slug
    if flat.exists():
        return flat.read_text(encoding="utf-8")
    if dated_dir.exists():
        return sorted(dated_dir.glob("*.html"), reverse=True)[0].read_text(encoding="utf-8")
    pytest.skip(f"No cached HTML for {slug}")


def test_count_tokens_returns_positive_integer():
    assert count_tokens("Expense ratio (direct plan): 0.88%") >= 1


def test_defence_chunking_produces_eleven_chunks():
    html = _load_html("hdfc-defence-fund-direct-growth")
    sections = normalize_sections(
        parse_html(html, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    )
    chunks = chunk_sections(sections, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    assert len(chunks) == 11
    assert len({chunk.section_type for chunk in chunks}) == len(REQUIRED_SECTIONS)
    fm_chunks = [chunk for chunk in chunks if chunk.section_type == "fund_management"]
    assert len(fm_chunks) == 3
    assert all(chunk.manager_name for chunk in fm_chunks)
    assert all("Also manages" not in chunk.text for chunk in fm_chunks)


def test_defence_expense_ratio_chunk_content():
    html = _load_html("hdfc-defence-fund-direct-growth")
    sections = normalize_sections(
        parse_html(html, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    )
    chunks = chunk_sections(sections, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    expense = next(chunk for chunk in chunks if chunk.section_type == "expense_ratio")
    assert "0.88%" in expense.text
    assert expense.chunk_id == "hdfc-defence-fund-direct-growth-expense_ratio-001"


def test_chunks_have_context_header():
    html = _load_html("hdfc-defence-fund-direct-growth")
    sections = normalize_sections(
        parse_html(html, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    )
    chunks = chunk_sections(sections, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    for chunk in chunks:
        assert chunk.text.startswith("Scheme:")
        assert "\nSection:" in chunk.text


@pytest.mark.parametrize("slug,expected_count", list(EXPECTED_CHUNK_COUNTS.items()))
def test_all_schemes_meet_chunk_count_targets(slug, expected_count):
    settings = load_settings()
    source = next(item for item in settings.sources if slug in item.url)
    html = _load_html(slug)
    sections = normalize_sections(parse_html(html, scheme_name=source.scheme_name, source_url=source.url))
    chunks = chunk_sections(sections, scheme_name=source.scheme_name, source_url=source.url)
    assert len(chunks) == expected_count
    assert len(chunks) >= 10


def test_run_ingestion_writes_chunk_artifacts():
    settings = load_settings()
    result = run_ingestion(settings=settings, use_cache=True, save_html=False)
    assert result.status.value in {"success", "partial"}
    assert result.chunks_written == sum(EXPECTED_CHUNK_COUNTS.values())
    defence = next(
        item for item in result.source_results if item.scheme_slug == "hdfc-defence-fund-direct-growth"
    )
    assert len(defence.chunks) == 11
    assert defence.chunks_path is not None
    payload = json.loads(Path(defence.chunks_path).read_text(encoding="utf-8"))
    assert payload["chunk_count"] == 11


def test_load_chunks_from_slug():
    settings = load_settings()
    ingest_source(DEFENCE_URL, settings=settings, use_cache=True, save_html=False)
    payload = load_chunks("hdfc-defence-fund-direct-growth", settings=settings)
    assert payload is not None
    assert payload["chunk_count"] == 11


def test_partial_failure_when_one_url_invalid():
    settings = load_settings()
    good = settings.sources[0].url
    result = run_ingestion(
        settings=settings,
        urls=[good, "https://groww.in/mutual-funds/not-a-real-fund"],
        use_cache=True,
        save_html=False,
    )
    assert result.status.value == "partial"
    assert result.documents_processed == 1
    assert result.chunks_written == EXPECTED_CHUNK_COUNTS[good.rstrip("/").split("/")[-1]]


def test_ingest_rejects_invalid_url():
    result = ingest_source("https://groww.in/mutual-funds/invalid-fund", use_cache=True, save_html=False)
    assert result.status == "failed"
    assert result.error
