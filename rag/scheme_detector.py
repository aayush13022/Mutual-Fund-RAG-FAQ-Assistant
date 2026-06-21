"""Detect which allowlisted HDFC scheme a user query refers to."""

from __future__ import annotations

from config.settings import Settings, get_settings


def detect_scheme(query: str, settings: Settings | None = None) -> str | None:
    """Return canonical scheme_name when query mentions a fund, else None."""
    cfg = settings or get_settings()
    query_lower = query.lower()
    matches: list[tuple[int, str]] = []

    for source in cfg.sources:
        scheme_lower = source.scheme_name.lower()
        if scheme_lower in query_lower:
            matches.append((len(source.scheme_name), source.scheme_name))
        for alias in source.aliases:
            alias_lower = alias.lower()
            if alias_lower in query_lower:
                matches.append((len(alias), source.scheme_name))

    if not matches:
        return None

    return max(matches, key=lambda item: item[0])[1]
