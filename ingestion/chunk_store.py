"""Persist chunked output alongside processed section artifacts."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date
from pathlib import Path

from config.settings import Settings, get_settings
from ingestion.fetcher import scheme_slug_from_url
from ingestion.models import Chunk, SourceIngestionResult

logger = logging.getLogger(__name__)


def chunks_dir(settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    return cfg.project_root / "data" / "processed"


def _dated_chunks_path(scheme_slug: str, processed_on: date | None, settings: Settings) -> Path:
    day = (processed_on or date.today()).isoformat()
    return chunks_dir(settings) / scheme_slug / f"{day}.chunks.json"


def _latest_chunks_path(scheme_slug: str, settings: Settings) -> Path:
    return chunks_dir(settings) / scheme_slug / "chunks.json"


def _flat_chunks_path(scheme_slug: str, settings: Settings) -> Path:
    return chunks_dir(settings) / f"{scheme_slug}.chunks.json"


def chunk_to_dict(chunk: Chunk) -> dict:
    payload = asdict(chunk)
    payload["ingested_at"] = chunk.ingested_at.isoformat()
    return payload


def build_chunks_payload(result: SourceIngestionResult, chunks: list[Chunk]) -> dict:
    return {
        "scheme_name": result.scheme_name,
        "scheme_slug": result.scheme_slug,
        "source_url": result.url,
        "chunk_count": len(chunks),
        "section_types": sorted({chunk.section_type for chunk in chunks}),
        "chunks": [chunk_to_dict(chunk) for chunk in chunks],
    }


def save_chunks(result: SourceIngestionResult, chunks: list[Chunk], *, settings: Settings | None = None) -> str | None:
    if result.status != "success" or not chunks:
        return None

    cfg = settings or get_settings()
    scheme_slug = result.scheme_slug or scheme_slug_from_url(result.url)
    payload = build_chunks_payload(result, chunks)

    dated_path = _dated_chunks_path(scheme_slug, None, cfg)
    latest_path = _latest_chunks_path(scheme_slug, cfg)
    flat_path = _flat_chunks_path(scheme_slug, cfg)
    dated_path.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    dated_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    flat_path.write_text(serialized, encoding="utf-8")

    logger.info("Saved %s chunks for %s to %s", len(chunks), scheme_slug, latest_path)
    return str(latest_path)


def load_chunks(url_or_slug: str, *, settings: Settings | None = None) -> dict | None:
    cfg = settings or get_settings()
    slug = scheme_slug_from_url(url_or_slug) if url_or_slug.startswith("http") else url_or_slug

    latest_path = _latest_chunks_path(slug, cfg)
    if latest_path.exists():
        return json.loads(latest_path.read_text(encoding="utf-8"))

    flat_path = _flat_chunks_path(slug, cfg)
    if flat_path.exists():
        return json.loads(flat_path.read_text(encoding="utf-8"))

    slug_dir = chunks_dir(cfg) / slug
    if not slug_dir.exists():
        return None

    dated_files = sorted(slug_dir.glob("*.chunks.json"), reverse=True)
    if not dated_files:
        return None

    return json.loads(dated_files[0].read_text(encoding="utf-8"))
