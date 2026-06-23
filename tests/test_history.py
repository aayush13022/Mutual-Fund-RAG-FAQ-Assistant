"""Tests for Streamlit chat history persistence."""

from __future__ import annotations

import pytest

from rag.models import RAGResponse


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_HISTORY_PATH", str(tmp_path / "chat_history.json"))
    import stapp.history as history_module

    return history_module


def test_new_conversation_has_unique_ids(history):
    a = history.new_conversation()
    b = history.new_conversation()
    assert a["id"] != b["id"]
    assert a["title"] == "New chat"
    assert a["messages"] == []


def test_conversation_title_truncates(history):
    short = history.conversation_title("Expense ratio?")
    assert short == "Expense ratio?"
    long = history.conversation_title("x" * 80)
    assert long.endswith("…")
    assert len(long) == 51


def test_save_and_load_round_trip(history):
    response = RAGResponse(
        answer="1.2%",
        source_url="https://groww.in/example",
        last_updated_from_sources="2026-06-22",
        disclaimer="Facts-only. No investment advice.",
        refused=False,
    )
    conv = history.new_conversation()
    conv["title"] = "Expense ratio"
    conv["messages"] = [
        {"role": "user", "content": "What is the expense ratio?"},
        {"role": "assistant", "content": "1.2%", "response": response},
    ]

    history.save_conversations([conv])
    loaded = history.load_conversations()

    assert len(loaded) == 1
    assert loaded[0]["title"] == "Expense ratio"
    restored = loaded[0]["messages"][1]["response"]
    assert isinstance(restored, RAGResponse)
    assert restored.answer == "1.2%"
    assert restored.source_url == "https://groww.in/example"


def test_empty_conversations_are_skipped(history):
    empty = history.new_conversation()
    history.save_conversations([empty])
    assert history.load_conversations() == []


def test_load_missing_file_returns_empty(history):
    assert history.load_conversations() == []
