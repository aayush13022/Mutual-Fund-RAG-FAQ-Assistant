"""Text normalization for parsed fund sections."""

from __future__ import annotations

import re

from ingestion.models import ParsedSection

NOISE_PATTERNS = [
    r"View details",
    r"Scheme Information Document\(SID\)",
    r"Understand terms",
    r"MF Calculator",
    r"Invest in a few minutes with the following steps:",
]


def normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_noise(text: str) -> str:
    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.I)
    return normalize_whitespace(cleaned)


def normalize_section(section: ParsedSection) -> ParsedSection:
    """Return a cleaned copy of a parsed section."""
    cleaned_fields = {
        key: strip_noise(value) if isinstance(value, str) else value
        for key, value in section.fields.items()
    }
    return ParsedSection(
        section_type=section.section_type,
        text=strip_noise(section.text),
        fields=cleaned_fields,
        managers=section.managers,
    )


def normalize_sections(sections: list[ParsedSection]) -> list[ParsedSection]:
    return [normalize_section(section) for section in sections]
