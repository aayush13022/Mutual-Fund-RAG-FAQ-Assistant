"""Section-first chunking for parsed mutual fund sections."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from config.settings import ChunkingConfig, Settings, get_settings
from ingestion.fetcher import scheme_slug_from_url
from ingestion.models import Chunk, FundManager, ParsedSection, utc_now

logger = logging.getLogger(__name__)

ALSO_MANAGES_PATTERN = re.compile(
    r"(?:Also manages:.*|\(\+\d+ more schemes\)\s*)",
    re.IGNORECASE | re.DOTALL,
)


def _get_token_encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        logger.warning("tiktoken unavailable, using character-based token estimate: %s", exc)
        return None


_ENCODER = None


def count_tokens(text: str) -> int:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = _get_token_encoder()
    if _ENCODER is None:
        return max(1, len(text) // 4)
    return len(_ENCODER.encode(text))


def _build_chunk_text(scheme_name: str, section_type: str, body: str) -> str:
    return f"Scheme: {scheme_name}\nSection: {section_type}\n\n{body.strip()}"


def _strip_other_schemes_noise(text: str) -> str:
    return ALSO_MANAGES_PATTERN.sub("", text).strip()


def _manager_to_text(manager: FundManager) -> str:
    lines = [f"Manager: {manager.name}"]
    if manager.tenure:
        lines.append(f"Tenure: {manager.tenure}")
    if manager.education:
        lines.append(f"Education: {manager.education}")
    if manager.experience:
        lines.append(f"Experience: {manager.experience}")
    return "\n".join(lines)


def _split_fund_management_section(section: ParsedSection, config: ChunkingConfig) -> list[str]:
    bodies: list[str] = []

    if section.managers:
        for manager in section.managers:
            bodies.append(_manager_to_text(manager))
    else:
        text = re.sub(r"^Fund management:\s*", "", section.text, flags=re.I).strip()
        parts = re.split(r"(?=Manager \d+:)", text)
        for part in parts:
            cleaned = part.strip()
            if not cleaned:
                continue
            cleaned = re.sub(r"^Manager \d+:\s*", "Manager: ", cleaned)
            cleaned = _strip_other_schemes_noise(cleaned)
            if cleaned:
                bodies.append(cleaned)

    if not bodies:
        bodies.append(_strip_other_schemes_noise(section.text))

    if config.strip_other_schemes_list:
        bodies = [_strip_other_schemes_noise(body) for body in bodies if body.strip()]

    return [body for body in bodies if body.strip()]


def _split_on_paragraphs(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    current: list[str] = []

    for paragraph in paragraphs:
        candidate = "\n\n".join(current + [paragraph])
        if current and count_tokens(candidate) > max_tokens:
            chunks.append("\n\n".join(current))
            if overlap_tokens > 0 and current:
                overlap_parts: list[str] = []
                overlap_count = 0
                for part in reversed(current):
                    overlap_count += count_tokens(part)
                    overlap_parts.insert(0, part)
                    if overlap_count >= overlap_tokens:
                        break
                current = overlap_parts
            else:
                current = []
        current.append(paragraph)

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [text.strip()]


def _chunk_bodies_for_section(section: ParsedSection, config: ChunkingConfig) -> list[str]:
    if section.section_type == "fund_management" and config.fund_management_split == "per_manager":
        return _split_fund_management_section(section, config)

    body = section.text.strip()
    if count_tokens(body) <= config.chunk_size_tokens:
        return [body]

    logger.info(
        "Section %s exceeds %s tokens; applying paragraph fallback split",
        section.section_type,
        config.chunk_size_tokens,
    )
    return _split_on_paragraphs(body, config.chunk_size_tokens, config.chunk_overlap_tokens)


def _make_chunk(
    *,
    chunk_id: str,
    text: str,
    source_url: str,
    scheme_name: str,
    scheme_slug: str,
    section_type: str,
    ingested_at: datetime,
    sequence: int,
    manager_name: str | None = None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        source_url=source_url,
        scheme_name=scheme_name,
        scheme_slug=scheme_slug,
        section_type=section_type,
        ingested_at=ingested_at,
        sequence=sequence,
        manager_name=manager_name,
    )


def chunk_sections(
    sections: list[ParsedSection],
    *,
    scheme_name: str,
    source_url: str,
    settings: Settings | None = None,
    ingested_at: datetime | None = None,
) -> list[Chunk]:
    """Convert parsed sections into embedding-ready chunks."""
    cfg = settings or get_settings()
    config = cfg.chunking
    slug = scheme_slug_from_url(source_url)
    timestamp = ingested_at or utc_now()
    chunks: list[Chunk] = []
    sequence_by_section: dict[str, int] = {}

    for section in sections:
        bodies = _chunk_bodies_for_section(section, config)
        for body in bodies:
            sequence_by_section[section.section_type] = sequence_by_section.get(section.section_type, 0) + 1
            sequence = sequence_by_section[section.section_type]
            chunk_id = f"{slug}-{section.section_type}-{sequence:03d}"
            text = _build_chunk_text(scheme_name, section.section_type, body)

            manager_name = None
            if section.section_type == "fund_management":
                match = re.search(r"^Manager:\s*(.+)$", body, re.MULTILINE)
                if match:
                    manager_name = match.group(1).strip()

            chunks.append(
                _make_chunk(
                    chunk_id=chunk_id,
                    text=text,
                    source_url=source_url,
                    scheme_name=scheme_name,
                    scheme_slug=slug,
                    section_type=section.section_type,
                    ingested_at=timestamp,
                    sequence=sequence,
                    manager_name=manager_name,
                )
            )

    return chunks
