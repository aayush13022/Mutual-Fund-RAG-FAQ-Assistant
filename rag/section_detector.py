"""Detect which corpus section a user query is asking about."""

from __future__ import annotations

from config.settings import Settings, get_settings


def detect_section_hint(query: str, settings: Settings | None = None) -> str | None:
    """Return section_type when query keywords match, else None."""
    cfg = settings or get_settings()
    query_lower = query.lower()
    hits: list[tuple[int, str]] = []

    for section_type, keywords in cfg.retrieval.section_keywords.items():
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in query_lower:
                hits.append((len(keyword), section_type))

    if not hits:
        return None

    return max(hits, key=lambda item: item[0])[1]
