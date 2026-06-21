#!/usr/bin/env python3
"""CLI for the ingestion pipeline (Phase 1 parse/chunk + Phase 2 embed/index)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import configure_logging, load_settings
from ingestion.pipeline import ingest_source, run_ingestion
from ingestion.url_validator import URLNotAllowlistedError


def _print_source_summary(result) -> None:
    print(f"\n{result.scheme_name}")
    print(f"  status: {result.status}")
    print(f"  sections: {len(result.sections)}")
    print(f"  chunks: {len(result.chunks)}")
    if result.embedded_count:
        print(f"  embedded: {result.embedded_count}")
    if result.processed_path:
        print(f"  processed: {result.processed_path}")
    if result.clean_txt_path:
        print(f"  clean.txt: {result.clean_txt_path}")
    if result.chunks_path:
        print(f"  chunks.json: {result.chunks_path}")
    if result.error:
        print(f"  error: {result.error}")
    for chunk in result.chunks[:2]:
        print(f"  - {chunk.chunk_id}: {chunk.text[:80].replace(chr(10), ' ')}...")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ingestion for Groww HDFC fund pages.")
    parser.add_argument("--url", help="Ingest a single allowlisted URL")
    parser.add_argument("--full", action="store_true", help="Ingest all 5 configured sources")
    parser.add_argument("--dry-run", action="store_true", help="Parse and chunk without saving artifacts")
    parser.add_argument("--use-cache", action="store_true", help="Use cached raw HTML from data/raw/")
    parser.add_argument("--embed", action="store_true", help="Embed chunks and index into ChromaDB (Phase 2)")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    configure_logging()
    settings = load_settings()

    if not args.url and not args.full:
        parser.error("Provide --url or --full")

    use_cache = args.use_cache or args.dry_run
    save_html = not args.dry_run
    persist = not args.dry_run

    try:
        if args.url:
            if args.embed:
                batch = run_ingestion(
                    settings=settings,
                    urls=[args.url],
                    use_cache=use_cache,
                    save_html=save_html,
                    save_processed=persist,
                    persist_chunks=persist,
                    embed=True,
                    triggered_by="cli",
                )
                results = batch.source_results
            else:
                result = ingest_source(
                    args.url,
                    settings=settings,
                    use_cache=use_cache,
                    save_html=save_html,
                    save_processed=persist,
                    persist_chunks=persist,
                )
                batch = None
                results = [result]
        else:
            batch = run_ingestion(
                settings=settings,
                use_cache=use_cache,
                save_html=save_html,
                save_processed=persist,
                persist_chunks=persist,
                embed=args.embed,
                triggered_by="cli",
            )
            results = batch.source_results
    except URLNotAllowlistedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "status": batch.status.value if batch else results[0].status,
            "documents_processed": batch.documents_processed if batch else int(results[0].status == "success"),
            "sections_written": batch.sections_written if batch else len(results[0].sections),
            "chunks_written": batch.chunks_written if batch else len(results[0].chunks),
            "corpus_version": batch.corpus_version if batch else None,
            "job_id": batch.job_id if batch else None,
            "sources": [
                {
                    "scheme_name": result.scheme_name,
                    "url": result.url,
                    "status": result.status,
                    "sections": len(result.sections),
                    "chunks": len(result.chunks),
                    "embedded_count": result.embedded_count,
                    "chunks_path": result.chunks_path,
                    "error": result.error,
                }
                for result in results
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        title = "INGESTION + EMBED" if args.embed else "INGESTION"
        print("=" * 72)
        print(title)
        print("=" * 72)
        for result in results:
            _print_source_summary(result)
        if batch:
            print("\n" + "-" * 72)
            print(
                f"Summary: status={batch.status.value} | "
                f"documents={batch.documents_processed} | "
                f"sections={batch.sections_written} | "
                f"chunks={batch.chunks_written}"
            )
            if batch.corpus_version:
                print(f"Corpus version: {batch.corpus_version}")
            print("-" * 72)

    failed = sum(1 for result in results if result.status != "success")
    return 1 if failed == len(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
