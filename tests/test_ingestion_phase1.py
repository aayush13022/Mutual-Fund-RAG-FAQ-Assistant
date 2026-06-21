"""Phase 1 ingestion tests (fetcher, parser, normalizer, URL validator)."""

import json
from pathlib import Path

import pytest

from config.settings import EXPECTED_SOURCE_COUNT, REQUIRED_SECTIONS, load_settings
from ingestion.fetcher import scheme_slug_from_url
from ingestion.normalizer import normalize_sections
from ingestion.parser import parse_html
from ingestion.pipeline import ingest_source
from ingestion.processed_store import load_clean_text, load_processed_sections
from ingestion.url_validator import URLNotAllowlistedError, validate_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFENCE_HTML = PROJECT_ROOT / "data" / "raw" / "hdfc-defence-fund-direct-growth" / "2026-06-17.html"
DEFENCE_URL = "https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth"


@pytest.fixture
def defence_html() -> str:
    if DEFENCE_HTML.exists():
        return DEFENCE_HTML.read_text(encoding="utf-8")
    flat = PROJECT_ROOT / "data" / "raw" / "hdfc-defence-fund-direct-growth.html"
    if flat.exists():
        return flat.read_text(encoding="utf-8")
    pytest.skip("Defence fund HTML fixture not available")


def test_validate_url_rejects_unknown():
    with pytest.raises(URLNotAllowlistedError):
        validate_url("https://groww.in/mutual-funds/some-other-fund")


def test_validate_url_accepts_corpus_url():
    settings = load_settings()
    assert validate_url(settings.sources[0].url) == settings.sources[0].url.rstrip("/")


def test_scheme_slug_from_url():
    assert scheme_slug_from_url(DEFENCE_URL) == "hdfc-defence-fund-direct-growth"


def test_parser_extracts_nine_sections_for_defence(defence_html):
    sections = parse_html(
        defence_html,
        scheme_name="HDFC Defence Fund Direct Growth",
        source_url=DEFENCE_URL,
    )
    sections = normalize_sections(sections)
    types = {section.section_type for section in sections}
    assert types == set(REQUIRED_SECTIONS)


def test_defence_expense_ratio_section(defence_html):
    sections = normalize_sections(
        parse_html(defence_html, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    )
    expense = next(section for section in sections if section.section_type == "expense_ratio")
    assert "0.88%" in expense.text


def test_defence_fund_management_has_managers(defence_html):
    sections = normalize_sections(
        parse_html(defence_html, scheme_name="HDFC Defence Fund Direct Growth", source_url=DEFENCE_URL)
    )
    mgmt = next(section for section in sections if section.section_type == "fund_management")
    assert len(mgmt.managers) >= 1
    assert any(manager.name for manager in mgmt.managers)


@pytest.mark.parametrize(
    "slug",
    [
        "hdfc-mid-cap-fund-direct-growth",
        "hdfc-large-cap-fund-direct-growth",
        "hdfc-small-cap-fund-direct-growth",
        "hdfc-gold-etf-fund-of-fund-direct-plan-growth",
        "hdfc-defence-fund-direct-growth",
    ],
)
def test_cached_html_parses_all_five_schemes(slug):
    flat = PROJECT_ROOT / "data" / "raw" / f"{slug}.html"
    dated_dir = PROJECT_ROOT / "data" / "raw" / slug
    if flat.exists():
        html = flat.read_text(encoding="utf-8")
    elif dated_dir.exists():
        html = sorted(dated_dir.glob("*.html"), reverse=True)[0].read_text(encoding="utf-8")
    else:
        pytest.skip(f"No cached HTML for {slug}")

    settings = load_settings()
    source = next(s for s in settings.sources if slug in s.url)
    sections = normalize_sections(parse_html(html, scheme_name=source.scheme_name, source_url=source.url))
    assert len(sections) >= 8
    assert "expense_ratio" in {s.section_type for s in sections}
    assert "fund_management" in {s.section_type for s in sections}


def test_ingest_source_writes_processed_json_and_clean_txt():
    settings = load_settings()
    result = ingest_source(DEFENCE_URL, settings=settings, use_cache=True, save_html=False)
    assert result.status == "success"
    assert result.processed_path is not None
    assert result.clean_txt_path is not None
    processed = Path(result.processed_path)
    clean_txt = Path(result.clean_txt_path)
    assert processed.exists()
    assert clean_txt.exists()
    payload = json.loads(processed.read_text(encoding="utf-8"))
    assert payload["section_count"] == len(REQUIRED_SECTIONS)
    assert set(payload["section_types"]) == set(REQUIRED_SECTIONS)
    clean_content = clean_txt.read_text(encoding="utf-8")
    assert "=== overview ===" in clean_content
    assert "=== fund_management ===" in clean_content
    assert "HDFC Defence Fund Direct Growth" in clean_content


def test_load_clean_text_from_slug():
    settings = load_settings()
    ingest_source(DEFENCE_URL, settings=settings, use_cache=True, save_html=False)
    content = load_clean_text("hdfc-defence-fund-direct-growth", settings=settings)
    assert content is not None
    assert "=== expense_ratio ===" in content


def test_load_processed_sections_from_slug():
    settings = load_settings()
    ingest_source(DEFENCE_URL, settings=settings, use_cache=True, save_html=False)
    payload = load_processed_sections("hdfc-defence-fund-direct-growth", settings=settings)
    assert payload is not None
    assert payload["scheme_slug"] == "hdfc-defence-fund-direct-growth"


def test_ingest_source_uses_cache_for_defence():
    settings = load_settings()
    result = ingest_source(DEFENCE_URL, settings=settings, use_cache=True, save_html=False)
    assert result.status == "success"
    assert len(result.sections) == len(REQUIRED_SECTIONS)


def test_corpus_has_five_sources():
    assert len(load_settings().sources) == EXPECTED_SOURCE_COUNT
