"""Phase 0 tests for configuration and API health."""

from fastapi.testclient import TestClient

from api.main import app
from config.settings import EXPECTED_SOURCE_COUNT, REQUIRED_SECTIONS, load_settings


def test_load_settings_returns_five_sources():
    settings = load_settings()
    assert len(settings.sources) == EXPECTED_SOURCE_COUNT
    assert settings.amc == "HDFC Mutual Fund"


def test_sections_match_required_section_types():
    settings = load_settings()
    assert set(settings.sections) == set(REQUIRED_SECTIONS)


def test_allowlisted_urls_are_unique():
    settings = load_settings()
    urls = [source.url for source in settings.sources]
    assert len(urls) == len(set(urls))
    assert all(url.startswith("https://groww.in/mutual-funds/") for url in urls)


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
