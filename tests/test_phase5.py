"""Phase 5 API and guardrail tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from rag.guardrails import (
    AMFI_EDUCATIONAL_LINK,
    QueryType,
    build_refusal_response,
    classify,
    should_refuse,
)
from rag.models import RAGResponse

client = TestClient(app)


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Should I invest in HDFC Defence Fund?", QueryType.ADVISORY),
        ("Is it good to buy HDFC Mid Cap?", QueryType.ADVISORY),
        ("Which fund is better, Defence or Mid Cap?", QueryType.COMPARISON),
        ("Compare HDFC Large Cap and Small Cap", QueryType.COMPARISON),
        ("What returns will I get in 5 years?", QueryType.PERFORMANCE_CALC),
        ("Calculate returns for HDFC Defence", QueryType.PERFORMANCE_CALC),
        ("Who manages HDFC Defence Fund?", QueryType.FUND_MANAGEMENT),
        ("fund management of HDFC Large Cap Fund Direct Growth", QueryType.FUND_MANAGEMENT),
        ("What is the expense ratio of HDFC Defence?", QueryType.FACTUAL),
    ],
)
def test_classify(message, expected):
    assert classify(message) == expected


def test_should_refuse_for_advisory_and_comparison():
    assert should_refuse(QueryType.ADVISORY) is True
    assert should_refuse(QueryType.COMPARISON) is True
    assert should_refuse(QueryType.PERFORMANCE_CALC) is True
    assert should_refuse(QueryType.FACTUAL) is False
    assert should_refuse(QueryType.FUND_MANAGEMENT) is False


def test_refusal_response_has_educational_link():
    response = build_refusal_response()
    assert response.refused is True
    assert response.educational_link == AMFI_EDUCATIONAL_LINK
    assert "investment advice" in response.answer.lower()


def test_chat_refuses_advisory_query():
    response = client.post("/chat", json={"message": "Should I invest in HDFC Defence Fund?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is True
    assert payload["educational_link"] == AMFI_EDUCATIONAL_LINK
    assert payload["source_url"] is None


def test_chat_refuses_comparison_query():
    response = client.post("/chat", json={"message": "Compare HDFC Defence and Mid Cap funds"})
    assert response.status_code == 200
    assert response.json()["refused"] is True


@patch("api.routes.chat.answer")
def test_chat_factual_query_returns_answer(mock_answer):
    mock_answer.return_value = RAGResponse(
        answer="The expense ratio is 0.88%.",
        source_url="https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",
        last_updated_from_sources="2026-06-18",
        disclaimer="Facts-only. No investment advice.",
        refused=False,
    )
    response = client.post(
        "/chat",
        json={"message": "What is the expense ratio of HDFC Defence Fund Direct Growth?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["source_url"].startswith("https://groww.in/mutual-funds/")
    assert payload["last_updated_from_sources"] == "2026-06-18"
    mock_answer.assert_called_once()


@patch("api.routes.chat.answer", side_effect=RuntimeError("LLM down"))
def test_chat_returns_503_on_generation_failure(mock_answer):
    response = client.post(
        "/chat",
        json={"message": "What is the expense ratio of HDFC Defence Fund Direct Growth?"},
    )
    assert response.status_code == 503


def test_chat_rejects_empty_message():
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 400


def test_corpus_status_endpoint():
    response = client.get("/corpus/status")
    assert response.status_code == 200
    payload = response.json()
    assert "active_version" in payload
    assert "sources" in payload
    assert isinstance(payload["sources"], list)


@patch("api.routes.ingest.run_ingestion")
def test_ingest_run_endpoint(mock_run):
    from ingestion.models import IngestionResult, IngestionStatus, utc_now

    mock_run.return_value = IngestionResult(
        status=IngestionStatus.SUCCESS,
        started_at=utc_now(),
        completed_at=utc_now(),
        documents_processed=5,
        sections_written=45,
        chunks_written=51,
        corpus_version="v2",
        job_id="job-123",
    )
    response = client.post("/ingest/run")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["corpus_version"] == "v2"
    assert payload["chunks_written"] == 51
