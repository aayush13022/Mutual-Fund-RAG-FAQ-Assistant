#!/usr/bin/env python3
"""Phase 6 exit-criteria checks for the chat UI API contract."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from rag.models import RAGResponse

client = TestClient(app)

UI_EXAMPLE_QUESTIONS = [
    "What is the expense ratio of HDFC Defence Fund Direct Growth?",
    "What is the exit load on HDFC Mid Cap Fund Direct Growth?",
    "Who manages HDFC Large Cap Fund Direct Growth?",
]


def check_factual_chat() -> bool:
    with patch("api.routes.chat.answer") as mock_answer:
        mock_answer.return_value = RAGResponse(
            answer="The expense ratio is 0.88%.",
            source_url="https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",
            last_updated_from_sources="2026-06-18",
            disclaimer="Facts-only. No investment advice.",
            refused=False,
        )
        response = client.post("/chat", json={"message": UI_EXAMPLE_QUESTIONS[0]})
    if response.status_code != 200:
        return False
    payload = response.json()
    return (
        payload.get("refused") is False
        and payload.get("source_url", "").startswith("https://groww.in/mutual-funds/")
        and payload.get("last_updated_from_sources") is not None
    )


def check_advisory_refusal() -> bool:
    response = client.post(
        "/chat",
        json={"message": "Should I invest in HDFC Defence Fund?"},
    )
    if response.status_code != 200:
        return False
    payload = response.json()
    return payload.get("refused") is True and payload.get("educational_link") is not None


def check_empty_message() -> bool:
    response = client.post("/chat", json={"message": "   "})
    return response.status_code == 400


def check_api_error() -> bool:
    with patch("api.routes.chat.answer", side_effect=RuntimeError("LLM down")):
        response = client.post("/chat", json={"message": UI_EXAMPLE_QUESTIONS[0]})
    return response.status_code == 503


def main() -> int:
    checks = [
        ("Factual POST /chat returns source + footer", check_factual_chat()),
        ("Advisory POST /chat returns refusal + educational link", check_advisory_refusal()),
        ("Empty message returns 400", check_empty_message()),
        ("Generation failure returns 503", check_api_error()),
    ]

    print("=" * 72)
    print("PHASE 6 CHAT UI — API CONTRACT CHECKS")
    print("=" * 72)

    passed = 0
    for label, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}")
        passed += int(ok)

    print("-" * 72)
    print(f"Result: {passed}/{len(checks)} passed")
    print("-" * 72)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
