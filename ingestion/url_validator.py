"""Allowlist validation for corpus source URLs."""

from __future__ import annotations

from config.settings import Settings, get_settings


class URLNotAllowlistedError(ValueError):
    """Raised when a URL is not present in the configured corpus."""


def validate_url(url: str, settings: Settings | None = None) -> str:
    """Validate and return a normalized allowlisted URL."""
    cfg = settings or get_settings()
    normalized = url.strip().rstrip("/")
    allowlisted = {source.url.rstrip("/") for source in cfg.sources}

    if normalized not in allowlisted:
        raise URLNotAllowlistedError(
            f"URL is not allowlisted: {url}. "
            f"Only {len(allowlisted)} configured Groww fund pages are permitted."
        )
    return normalized


def get_source_for_url(url: str, settings: Settings | None = None):
    cfg = settings or get_settings()
    normalized = url.strip().rstrip("/")
    for source in cfg.sources:
        if source.url.rstrip("/") == normalized:
            return source
    raise URLNotAllowlistedError(f"No source config found for URL: {url}")
