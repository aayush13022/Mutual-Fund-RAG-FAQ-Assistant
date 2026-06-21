"""HTTP fetcher for allowlisted Groww fund pages."""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from pathlib import Path

import httpx

from config.settings import Settings, get_settings
from ingestion.models import FetchResult, utc_now
from ingestion.url_validator import get_source_for_url, validate_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DELAY_SECONDS = 1.5


def scheme_slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _raw_html_path(
    project_root: Path,
    scheme_slug: str,
    fetched_on: date | None = None,
) -> Path:
    day = (fetched_on or date.today()).isoformat()
    return project_root / "data" / "raw" / scheme_slug / f"{day}.html"


def fetch_url(
    url: str,
    *,
    settings: Settings | None = None,
    save_html: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> FetchResult:
    """Fetch a single allowlisted fund page."""
    cfg = settings or get_settings()
    normalized_url = validate_url(url, cfg)
    source = get_source_for_url(normalized_url, cfg)
    scheme_slug = scheme_slug_from_url(normalized_url)

    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(normalized_url, headers=headers)
        response.raise_for_status()
        final_url = str(response.url).rstrip("/")
        if not re.match(r"^https://groww\.in/mutual-funds/", final_url):
            raise ValueError(f"Redirected to non-Groww domain: {final_url}")

    saved_path: str | None = None
    if save_html:
        path = _raw_html_path(cfg.project_root, scheme_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(response.text, encoding="utf-8")
        saved_path = str(path)
        logger.info("Saved raw HTML for %s to %s", scheme_slug, saved_path)

    return FetchResult(
        url=normalized_url,
        scheme_name=source.scheme_name,
        scheme_slug=scheme_slug,
        html=response.text,
        saved_path=saved_path,
        status_code=response.status_code,
        fetched_at=utc_now(),
    )


def fetch_all_sources(
    *,
    settings: Settings | None = None,
    save_html: bool = True,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
) -> list[FetchResult]:
    """Fetch all configured corpus sources sequentially with delay."""
    cfg = settings or get_settings()
    results: list[FetchResult] = []

    for index, source in enumerate(cfg.sources):
        if index > 0:
            time.sleep(delay_seconds)
        try:
            results.append(fetch_url(source.url, settings=cfg, save_html=save_html))
        except Exception as exc:
            logger.error("Fetch failed for %s: %s", source.url, exc)
            raise

    return results
