#!/usr/bin/env python3
"""CLI to validate Phase 3 retrieval against the 11-query test matrix."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import configure_logging, load_settings
from rag.retriever import retrieve

TEST_CASES = [
    {
        "query": "expense ratio HDFC Defence Fund",
        "section": "expense_ratio",
        "scheme_contains": "Defence",
    },
    {
        "query": "Who manages HDFC Mid Cap Fund?",
        "section": "fund_management",
        "scheme_contains": "Mid Cap",
    },
    {
        "query": "exit load HDFC Small Cap",
        "section": "exit_load",
        "scheme_contains": "Small Cap",
    },
    {
        "query": "benchmark HDFC Large Cap",
        "section": "benchmark",
        "scheme_contains": "Large Cap",
    },
    {
        "query": "minimum SIP gold ETF fund",
        "section": "minimum_investment",
        "scheme_contains": "Gold ETF",
    },
    {
        "query": "education of Defence fund manager",
        "section": "fund_management",
        "scheme_contains": "Defence",
    },
    {
        "query": "tax implication HDFC Defence",
        "section": "tax",
        "scheme_contains": "Defence",
    },
    {
        "query": "investment objective HDFC Defence",
        "section": "investment_objective",
        "scheme_contains": "Defence",
    },
    {
        "query": "NAV of HDFC Mid Cap",
        "section": "overview",
        "scheme_contains": "Mid Cap",
    },
    {
        "query": "expense ratio",
        "multi_scheme": True,
        "section": "expense_ratio",
    },
    {
        "query": "expense ratio HDFC Defence",
        "section": "expense_ratio",
        "scheme_contains": "Defence",
        "exclude_schemes": ["Mid Cap", "Large Cap"],
    },
]


def _evaluate(case: dict, results) -> tuple[bool, str]:
    if not results:
        return False, "no results"

    top = results[0]
    if case.get("multi_scheme"):
        schemes = {item.scheme_name for item in results}
        if len(schemes) < 2:
            return False, f"expected multiple schemes, got {schemes}"
        if top.section_type != case["section"]:
            return False, f"expected section {case['section']}, got {top.section_type}"
        return True, f"schemes={len(schemes)} top={top.section_type}"

    if top.section_type != case["section"]:
        return False, f"expected section {case['section']}, got {top.section_type}"

    scheme_needle = case.get("scheme_contains")
    if scheme_needle and scheme_needle.lower() not in top.scheme_name.lower():
        return False, f"expected scheme containing {scheme_needle!r}, got {top.scheme_name!r}"

    for excluded in case.get("exclude_schemes", []):
        for item in results:
            if excluded.lower() in item.scheme_name.lower():
                return False, f"found excluded scheme {item.scheme_name}"

    return True, f"{top.section_type} | {top.scheme_name} | score={top.score:.3f} | tier={top.retrieval_tier}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run retrieval test matrix.")
    parser.add_argument("--query", help="Run a single query instead of the full matrix")
    args = parser.parse_args()

    configure_logging()
    load_settings()

    if args.query:
        results = retrieve(args.query)
        for item in results:
            print(
                f"{item.score:.3f} | {item.retrieval_tier:8} | "
                f"{item.section_type:22} | {item.scheme_name}"
            )
        return 0

    passed = 0
    print("=" * 72)
    print("RETRIEVAL TEST MATRIX")
    print("=" * 72)

    for index, case in enumerate(TEST_CASES, start=1):
        results = retrieve(case["query"])
        ok, detail = _evaluate(case, results)
        status = "PASS" if ok else "FAIL"
        print(f"\n{index:02d}. [{status}] {case['query']}")
        print(f"    {detail}")
        if results:
            print(f"    top: {results[0].scheme_name} / {results[0].section_type}")
        passed += int(ok)

    print("\n" + "-" * 72)
    print(f"Result: {passed}/{len(TEST_CASES)} passed")
    print("-" * 72)
    return 0 if passed == len(TEST_CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
