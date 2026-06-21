#!/usr/bin/env python3
"""Manual parser validation for all 5 configured HDFC schemes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import REQUIRED_SECTIONS, load_settings
from ingestion.fetcher import scheme_slug_from_url
from ingestion.pipeline import ingest_source

REQUIRED_CHECKS = {
    "expense_ratio": ("expense_ratio", "expense"),
    "exit_load": ("exit_load", "exit load"),
    "minimum_investment": ("minimum_investment", "sip"),
    "fund_management": ("fund_management", "manager"),
    "benchmark": ("benchmark", "benchmark"),
    "tax": ("tax", "tax"),
    "investment_objective": ("investment_objective", "objective"),
    "fund_house": ("fund_house", "fund house"),
    "overview": ("overview", "scheme"),
}


def _preview(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def validate_scheme(url: str | None = None, *, use_cache: bool = True, save_html: bool = False) -> dict:
    settings = load_settings()
    target_urls = [url] if url else [source.url for source in settings.sources]
    report = {
        "schemes_validated": 0,
        "schemes_passed": 0,
        "schemes_failed": 0,
        "details": [],
    }

    for target_url in target_urls:
        result = ingest_source(target_url, settings=settings, use_cache=use_cache, save_html=save_html)
        slug = scheme_slug_from_url(target_url)
        section_types = {section.section_type for section in result.sections}
        missing = sorted(REQUIRED_SECTIONS - section_types)

        scheme_report = {
            "scheme_name": result.scheme_name,
            "scheme_slug": slug,
            "url": result.url,
            "status": result.status,
            "sections_found": len(result.sections),
            "section_types": sorted(section_types),
            "missing_sections": missing,
            "error": result.error,
            "processed_path": result.processed_path,
            "clean_txt_path": result.clean_txt_path,
            "sections": [],
            "checks": {},
        }

        if result.status == "success":
            report["schemes_validated"] += 1
            for section in result.sections:
                scheme_report["sections"].append(
                    {
                        "section_type": section.section_type,
                        "preview": _preview(section.text),
                        "fields": section.fields,
                        "manager_count": len(section.managers),
                    }
                )

            for check_name, (section_type, keyword) in REQUIRED_CHECKS.items():
                matching = next((s for s in result.sections if s.section_type == section_type), None)
                passed = matching is not None and keyword.lower() in matching.text.lower()
                scheme_report["checks"][check_name] = passed

            passed = not missing and all(scheme_report["checks"].values())
            scheme_report["passed"] = passed
            if passed:
                report["schemes_passed"] += 1
            else:
                report["schemes_failed"] += 1
        else:
            scheme_report["passed"] = False
            report["schemes_failed"] += 1

        report["details"].append(scheme_report)

    return report


def print_report(report: dict) -> None:
    print("=" * 72)
    print("PARSER VALIDATION REPORT — 5 HDFC SCHEMES")
    print("=" * 72)

    for detail in report["details"]:
        status = "PASS" if detail.get("passed") else "FAIL"
        print(f"\n[{status}] {detail['scheme_name']}")
        print(f"  URL: {detail['url']}")
        if detail.get("processed_path"):
            print(f"  Processed JSON: {detail['processed_path']}")
        if detail.get("clean_txt_path"):
            print(f"  Clean text: {detail['clean_txt_path']}")
        print(f"  Sections: {detail.get('sections_found', 0)}/9")
        if detail.get("missing_sections"):
            print(f"  Missing: {', '.join(detail['missing_sections'])}")
        if detail.get("error"):
            print(f"  Error: {detail['error']}")

        for section in detail.get("sections", []):
            managers = f" ({section['manager_count']} managers)" if section["section_type"] == "fund_management" else ""
            print(f"  - {section['section_type']}{managers}: {section['preview']}")

        if detail.get("checks"):
            failed_checks = [name for name, ok in detail["checks"].items() if not ok]
            if failed_checks:
                print(f"  Failed checks: {', '.join(failed_checks)}")

    print("\n" + "-" * 72)
    print(
        f"Summary: {report['schemes_passed']}/{len(report['details'])} schemes passed | "
        f"{report['schemes_failed']} failed"
    )
    print("-" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Groww parser output for corpus schemes.")
    parser.add_argument("--url", help="Validate a single allowlisted URL")
    parser.add_argument("--fetch", action="store_true", help="Fetch live HTML instead of using cache")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--output", help="Write JSON report to file")
    args = parser.parse_args()

    use_cache = not args.fetch
    save_html = args.fetch

    if args.url:
        target_urls = [args.url]
    else:
        settings = load_settings()
        target_urls = [source.url for source in settings.sources]

    report = {
        "schemes_validated": 0,
        "schemes_passed": 0,
        "schemes_failed": 0,
        "details": [],
    }

    for target_url in target_urls:
        single = validate_scheme(target_url, use_cache=use_cache, save_html=save_html)
        report["details"].extend(single["details"])
    report["schemes_validated"] = sum(1 for d in report["details"] if d["status"] == "success")
    report["schemes_passed"] = sum(1 for d in report["details"] if d.get("passed"))
    report["schemes_failed"] = len(report["details"]) - report["schemes_passed"]

    if args.json or args.output:
        payload = json.dumps(report, indent=2)
        if args.output:
            Path(args.output).write_text(payload, encoding="utf-8")
            print(f"Wrote report to {args.output}")
        if args.json:
            print(payload)
    else:
        print_report(report)

    return 0 if report["schemes_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
