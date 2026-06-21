#!/usr/bin/env python3
"""Golden-test harness for Phase 4 RAG generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import configure_logging, load_settings
from rag.generator import answer
from rag.postprocessor import count_sentences

GOLDEN_CASES = [
    {
        "question": "What is the expense ratio of HDFC Defence Fund Direct Growth?",
        "keywords": ["0.88"],
    },
    {
        "question": "What is the minimum SIP for HDFC Gold ETF Fund of Fund?",
        "keywords": ["100"],
    },
    {
        "question": "What is the exit load on HDFC Mid Cap Fund Direct Growth?",
        "keywords": ["1%"],
    },
    {
        "question": "What is the benchmark of HDFC Large Cap Fund Direct Growth?",
        "keywords": ["NIFTY 100"],
    },
    {
        "question": "What is the risk classification of HDFC Small Cap Fund Direct Growth?",
        "keywords": ["Very High"],
    },
    {
        "question": "Who manages HDFC Defence Fund Direct Growth?",
        "keywords": ["Manager", "Priya"],
    },
    {
        "question": "Since when has the fund manager been managing HDFC Defence Fund?",
        "keywords": ["Apr 2025", "Tenure"],
    },
    {
        "question": "What is the educational background of the HDFC Defence Fund manager?",
        "keywords": ["Education", "B.E", "PGDBM"],
    },
    {
        "question": "What is the work experience of the fund manager of HDFC Defence Fund?",
        "keywords": ["Experience", "years"],
    },
    {
        "question": "Who manages HDFC Large Cap Fund Direct Growth?",
        "keywords": ["Manager", "Rahul"],
    },
]


def _passes_keywords(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run golden generation tests.")
    parser.add_argument("--question", help="Run one question instead of all 10")
    parser.add_argument(
        "--provider",
        default=None,
        help="LLM provider override (groq or mock). Defaults to env/config.",
    )
    args = parser.parse_args()

    configure_logging()
    settings = load_settings()

    if args.provider:
        import os

        os.environ["LLM_PROVIDER"] = args.provider
        from config.settings import get_settings
        from rag.llm import _get_llm_provider_cached

        get_settings.cache_clear()
        _get_llm_provider_cached.cache_clear()
        settings = load_settings()

    cases = GOLDEN_CASES
    if args.question:
        cases = [{"question": args.question, "keywords": []}]

    passed = 0
    print("=" * 72)
    print("GOLDEN GENERATION TESTS")
    print("=" * 72)

    for index, case in enumerate(cases, start=1):
        question = case["question"]
        response = answer(question, settings=settings)
        sentence_count = count_sentences(response.answer)
        keyword_ok = True if not case["keywords"] else _passes_keywords(response.answer, case["keywords"])
        format_ok = (
            sentence_count <= 3
            and response.source_url is not None
            and response.source_url.startswith("https://groww.in/mutual-funds/")
            and response.last_updated_from_sources is not None
            and not response.refused
        )
        ok = keyword_ok and format_ok
        status = "PASS" if ok else "FAIL"
        print(f"\n{index:02d}. [{status}] {question}")
        print(f"    answer: {response.answer}")
        print(f"    source: {response.source_url}")
        print(f"    updated: {response.last_updated_from_sources}")
        print(f"    sentences: {sentence_count}")
        if not keyword_ok:
            print(f"    missing keywords: {case['keywords']}")
        passed += int(ok)

    print("\n" + "-" * 72)
    print(f"Result: {passed}/{len(cases)} passed (target ≥ 8/10)")
    print("-" * 72)
    return 0 if passed >= max(8, len(cases)) or (len(cases) == 1 and passed == 1) else 1


if __name__ == "__main__":
    raise SystemExit(main())
