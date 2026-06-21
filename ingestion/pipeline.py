"""Ingestion pipeline orchestration (fetch → parse → normalize → chunk → embed)."""

from __future__ import annotations

import logging
import uuid

from config.settings import Settings, get_settings
from ingestion.chunk_store import save_chunks
from ingestion.chunker import chunk_sections
from ingestion.fetcher import fetch_url, scheme_slug_from_url
from ingestion.models import Chunk, IngestionResult, IngestionStatus, SourceIngestionResult, utc_now
from ingestion.normalizer import normalize_sections
from ingestion.parser import parse_html
from ingestion.processed_store import save_processed_sections
from ingestion.url_validator import get_source_for_url, validate_url
from storage.indexer import index_chunks, update_source_results_with_embedding_counts

logger = logging.getLogger(__name__)


def _resolve_html(url: str, html: str | None, settings: Settings) -> tuple[str, str | None]:
    if html is not None:
        return html, None

    fetch = fetch_url(url, settings=settings, save_html=True)
    return fetch.html, fetch.saved_path


def _load_cached_html(url: str, settings: Settings) -> str | None:
    slug = scheme_slug_from_url(url)
    flat_file = settings.project_root / "data" / "raw" / f"{slug}.html"
    if flat_file.exists():
        return flat_file.read_text(encoding="utf-8")

    raw_dir = settings.project_root / "data" / "raw" / slug
    if not raw_dir.exists():
        return None

    html_files = sorted(raw_dir.glob("*.html"), reverse=True)
    if not html_files:
        return None

    return html_files[0].read_text(encoding="utf-8")


def ingest_source(
    url: str,
    *,
    settings: Settings | None = None,
    html: str | None = None,
    use_cache: bool = False,
    save_html: bool = True,
    save_processed: bool = True,
    persist_chunks: bool = True,
) -> SourceIngestionResult:
    cfg = settings or get_settings()
    scheme_slug = scheme_slug_from_url(url)

    try:
        normalized_url = validate_url(url, cfg)
        source = get_source_for_url(normalized_url, cfg)
        scheme_slug = scheme_slug_from_url(normalized_url)
        page_html = html
        raw_html_path: str | None = None

        if page_html is None and use_cache:
            page_html = _load_cached_html(normalized_url, cfg)
            if page_html:
                raw_dir = cfg.project_root / "data" / "raw" / scheme_slug
                html_files = sorted(raw_dir.glob("*.html"), reverse=True)
                raw_html_path = str(html_files[0]) if html_files else None

        if page_html is None:
            fetch = fetch_url(normalized_url, settings=cfg, save_html=save_html)
            page_html = fetch.html
            raw_html_path = fetch.saved_path
        elif save_html and raw_html_path is None:
            _, raw_html_path = _resolve_html(normalized_url, page_html, cfg)

        sections = parse_html(page_html, scheme_name=source.scheme_name, source_url=normalized_url)
        sections = normalize_sections(sections)
        ingested_at = utc_now()
        chunks = chunk_sections(
            sections,
            scheme_name=source.scheme_name,
            source_url=normalized_url,
            settings=cfg,
            ingested_at=ingested_at,
        )

        result = SourceIngestionResult(
            url=normalized_url,
            scheme_name=source.scheme_name,
            scheme_slug=scheme_slug,
            status="success",
            sections=sections,
            chunks=chunks,
            raw_html_path=raw_html_path,
        )
        if save_processed:
            processed_path, clean_txt_path = save_processed_sections(result, settings=cfg)
            result.processed_path = processed_path
            result.clean_txt_path = clean_txt_path
        if persist_chunks:
            result.chunks_path = save_chunks(result, chunks, settings=cfg)
        return result
    except Exception as exc:
        logger.exception("Ingestion failed for %s", url)
        return SourceIngestionResult(
            url=url.rstrip("/"),
            scheme_name=scheme_slug,
            scheme_slug=scheme_slug,
            status="failed",
            error=str(exc),
        )


def run_ingestion(
    *,
    settings: Settings | None = None,
    urls: list[str] | None = None,
    use_cache: bool = False,
    save_html: bool = True,
    save_processed: bool = True,
    persist_chunks: bool = True,
    embed: bool = False,
    triggered_by: str = "manual",
    job_id: str | None = None,
    record_run: bool = True,
) -> IngestionResult:
    """Run fetch/parse/normalize/chunk for one or more allowlisted URLs."""
    cfg = settings or get_settings()
    started_at = utc_now()
    target_urls = urls or [source.url for source in cfg.sources]
    run_id = job_id or str(uuid.uuid4())

    source_results: list[SourceIngestionResult] = []
    for url in target_urls:
        source_results.append(
            ingest_source(
                url,
                settings=cfg,
                use_cache=use_cache,
                save_html=save_html,
                save_processed=save_processed,
                persist_chunks=persist_chunks,
            )
        )

    successes = [result for result in source_results if result.status == "success"]
    sections_written = sum(len(result.sections) for result in successes)
    all_chunks: list[Chunk] = []
    for result in successes:
        all_chunks.extend(result.chunks)

    if not successes:
        status = IngestionStatus.FAILED
    elif len(successes) < len(source_results):
        status = IngestionStatus.PARTIAL
    else:
        status = IngestionStatus.SUCCESS

    corpus_version: str | None = None
    if embed and all_chunks:
        try:
            ingestion = IngestionResult(
                status=status,
                started_at=started_at,
                completed_at=utc_now(),
                documents_processed=len(successes),
                sections_written=sections_written,
                chunks_written=len(all_chunks),
                job_id=run_id,
                source_results=source_results,
            )
            corpus_version = index_chunks(
                all_chunks,
                settings=cfg,
                triggered_by=triggered_by,
                ingestion_result=ingestion,
                job_id=run_id,
                record_run=record_run,
            )
            update_source_results_with_embedding_counts(source_results, all_chunks)
        except Exception as exc:
            logger.exception("Embedding/indexing failed")
            status = IngestionStatus.FAILED if not successes else IngestionStatus.PARTIAL
            for result in source_results:
                if result.status == "success":
                    result.error = f"Embedding failed: {exc}"

    return IngestionResult(
        status=status,
        started_at=started_at,
        completed_at=utc_now(),
        documents_processed=len(successes),
        sections_written=sections_written,
        chunks_written=len(all_chunks),
        corpus_version=corpus_version,
        job_id=run_id,
        source_results=source_results,
    )
