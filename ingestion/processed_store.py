"""Persist parsed and normalized sections to data/processed/."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from config.settings import Settings, get_settings
from ingestion.fetcher import scheme_slug_from_url
from ingestion.models import ParsedSection, SourceIngestionResult, utc_now

logger = logging.getLogger(__name__)

SECTION_ORDER = (
    "overview",
    "expense_ratio",
    "exit_load",
    "minimum_investment",
    "benchmark",
    "tax",
    "fund_management",
    "investment_objective",
    "fund_house",
)


def processed_dir(settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    return cfg.project_root / "data" / "processed"


def _dated_processed_path(scheme_slug: str, processed_on: date | None, settings: Settings) -> Path:
    day = (processed_on or date.today()).isoformat()
    return processed_dir(settings) / scheme_slug / f"{day}.json"


def _latest_processed_path(scheme_slug: str, settings: Settings) -> Path:
    return processed_dir(settings) / f"{scheme_slug}.json"


def _dated_clean_txt_path(scheme_slug: str, processed_on: date | None, settings: Settings) -> Path:
    day = (processed_on or date.today()).isoformat()
    return processed_dir(settings) / scheme_slug / f"{day}.clean.txt"


def _latest_clean_txt_path(scheme_slug: str, settings: Settings) -> Path:
    return processed_dir(settings) / scheme_slug / "clean.txt"


def _flat_clean_txt_path(scheme_slug: str, settings: Settings) -> Path:
    return processed_dir(settings) / f"{scheme_slug}.clean.txt"


def build_clean_text(result: SourceIngestionResult, *, processed_at: datetime | None = None) -> str:
    """Build a human-readable plain-text export of parsed sections."""
    timestamp = processed_at or utc_now()
    sections_by_type = {section.section_type: section for section in result.sections}

    lines = [
        f"Scheme: {result.scheme_name}",
        f"Source: {result.url}",
        f"Processed: {timestamp.isoformat()}",
        f"Sections: {len(result.sections)}",
        "",
    ]

    for section_type in SECTION_ORDER:
        section = sections_by_type.get(section_type)
        if section is None:
            continue
        lines.append(f"=== {section_type} ===")
        lines.append(section.text.strip())
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_clean_text_from_payload(payload: dict) -> str:
    """Build clean text from a saved processed JSON payload."""
    lines = [
        f"Scheme: {payload.get('scheme_name', '')}",
        f"Source: {payload.get('source_url', '')}",
        f"Processed: {payload.get('processed_at', '')}",
        f"Sections: {payload.get('section_count', 0)}",
        "",
    ]

    sections_by_type = {
        section["section_type"]: section for section in payload.get("sections", [])
    }
    for section_type in SECTION_ORDER:
        section = sections_by_type.get(section_type)
        if section is None:
            continue
        lines.append(f"=== {section_type} ===")
        lines.append(str(section.get("text", "")).strip())
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def section_to_dict(section: ParsedSection) -> dict:
    payload = {
        "section_type": section.section_type,
        "text": section.text,
        "fields": section.fields,
    }
    if section.managers:
        payload["managers"] = [asdict(manager) for manager in section.managers]
    return payload


def build_processed_payload(result: SourceIngestionResult, *, processed_at: datetime | None = None) -> dict:
    timestamp = processed_at or utc_now()
    return {
        "scheme_name": result.scheme_name,
        "scheme_slug": result.scheme_slug,
        "source_url": result.url,
        "processed_at": timestamp.isoformat(),
        "raw_html_path": result.raw_html_path,
        "section_count": len(result.sections),
        "section_types": [section.section_type for section in result.sections],
        "sections": [section_to_dict(section) for section in result.sections],
    }


def save_processed_sections(
    result: SourceIngestionResult,
    *,
    settings: Settings | None = None,
    processed_on: date | None = None,
) -> tuple[str | None, str | None]:
    """Write parsed sections to data/processed/ as JSON and clean.txt."""
    if result.status != "success" or not result.sections:
        return None, None

    cfg = settings or get_settings()
    scheme_slug = result.scheme_slug or scheme_slug_from_url(result.url)
    processed_at = utc_now()
    payload = build_processed_payload(result, processed_at=processed_at)
    clean_text = build_clean_text(result, processed_at=processed_at)

    dated_path = _dated_processed_path(scheme_slug, processed_on, cfg)
    latest_path = _latest_processed_path(scheme_slug, cfg)
    dated_clean_path = _dated_clean_txt_path(scheme_slug, processed_on, cfg)
    latest_clean_path = _latest_clean_txt_path(scheme_slug, cfg)
    flat_clean_path = _flat_clean_txt_path(scheme_slug, cfg)
    dated_path.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    dated_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    dated_clean_path.write_text(clean_text, encoding="utf-8")
    latest_clean_path.write_text(clean_text, encoding="utf-8")
    flat_clean_path.write_text(clean_text, encoding="utf-8")

    logger.info(
        "Saved processed sections for %s to %s and %s",
        scheme_slug,
        latest_path,
        latest_clean_path,
    )
    return str(latest_path), str(latest_clean_path)


def load_processed_sections(
    url_or_slug: str,
    *,
    settings: Settings | None = None,
    use_latest: bool = True,
) -> dict | None:
    """Load processed JSON for a scheme slug or URL."""
    cfg = settings or get_settings()
    slug = scheme_slug_from_url(url_or_slug) if url_or_slug.startswith("http") else url_or_slug

    if use_latest:
        latest_path = _latest_processed_path(slug, cfg)
        if latest_path.exists():
            return json.loads(latest_path.read_text(encoding="utf-8"))

    slug_dir = processed_dir(cfg) / slug
    if not slug_dir.exists():
        return None

    dated_files = sorted(slug_dir.glob("*.json"), reverse=True)
    if not dated_files:
        return None

    return json.loads(dated_files[0].read_text(encoding="utf-8"))


def load_clean_text(
    url_or_slug: str,
    *,
    settings: Settings | None = None,
    use_latest: bool = True,
) -> str | None:
    """Load clean.txt for a scheme slug or URL."""
    cfg = settings or get_settings()
    slug = scheme_slug_from_url(url_or_slug) if url_or_slug.startswith("http") else url_or_slug

    if use_latest:
        latest_clean = _latest_clean_txt_path(slug, cfg)
        if latest_clean.exists():
            return latest_clean.read_text(encoding="utf-8")
        flat_clean = _flat_clean_txt_path(slug, cfg)
        if flat_clean.exists():
            return flat_clean.read_text(encoding="utf-8")

    slug_dir = processed_dir(cfg) / slug
    if not slug_dir.exists():
        return None

    dated_clean_files = sorted(slug_dir.glob("*.clean.txt"), reverse=True)
    if dated_clean_files:
        return dated_clean_files[0].read_text(encoding="utf-8")

    payload = load_processed_sections(slug, settings=cfg, use_latest=use_latest)
    if payload is None:
        return None

    return build_clean_text_from_payload(payload)
