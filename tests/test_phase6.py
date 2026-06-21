"""Phase 6 chat UI integration tests (API contract used by Next.js frontend)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from rag.models import RAGResponse
from rag.postprocessor import RETRIEVAL_MISS_MESSAGE

client = TestClient(app)

EXAMPLE_QUESTIONS = [
    "What is the expense ratio of HDFC Defence Fund Direct Growth?",
    "What is the exit load on HDFC Mid Cap Fund Direct Growth?",
    "Who manages HDFC Large Cap Fund Direct Growth?",
]


def test_ui_constants_match_implementation_plan():
    constants_path = __import__("pathlib").Path(__file__).resolve().parent.parent / "ui" / "lib" / "constants.ts"
    text = constants_path.read_text(encoding="utf-8")
    assert "HDFC Defence Fund Direct Growth" in text
    for question in EXAMPLE_QUESTIONS:
        assert question in text
    assert "Facts-only. No investment advice." in text


def test_factual_chat_returns_source_and_footer():
    with patch("api.routes.chat.answer") as mock_answer:
        mock_answer.return_value = RAGResponse(
            answer="The expense ratio is 0.88%.",
            source_url="https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",
            last_updated_from_sources="2026-06-18",
            disclaimer="Facts-only. No investment advice.",
            refused=False,
        )
        response = client.post("/chat", json={"message": EXAMPLE_QUESTIONS[0]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["source_url"].startswith("https://groww.in/mutual-funds/")
    assert payload["last_updated_from_sources"] == "2026-06-18"
    assert payload["disclaimer"] == "Facts-only. No investment advice."


def test_advisory_chat_returns_refusal_with_educational_link():
    response = client.post("/chat", json={"message": "Should I invest in HDFC Defence Fund?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is True
    assert payload["educational_link"].startswith("https://")
    assert payload["source_url"] is None


def test_comparison_chat_returns_refusal():
    response = client.post("/chat", json={"message": "Compare HDFC Defence and Mid Cap funds"})
    assert response.status_code == 200
    assert response.json()["refused"] is True


def test_empty_message_returns_400():
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 400


def test_generation_failure_returns_503():
    with patch("api.routes.chat.answer", side_effect=RuntimeError("LLM down")):
        response = client.post("/chat", json={"message": EXAMPLE_QUESTIONS[0]})
    assert response.status_code == 503


def test_out_of_context_chat_returns_retrieval_miss_message():
    with patch("api.routes.chat.answer") as mock_answer:
        mock_answer.return_value = RAGResponse(
            answer=RETRIEVAL_MISS_MESSAGE,
            source_url=None,
            last_updated_from_sources="2026-06-18",
            disclaimer="Facts-only. No investment advice.",
            refused=False,
        )
        response = client.post("/chat", json={"message": "What is the weather in Mumbai today?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == RETRIEVAL_MISS_MESSAGE
    assert payload["source_url"] is None
    assert payload["refused"] is False


def test_health_endpoint_for_ui_preflight():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_localhost_3000():
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
