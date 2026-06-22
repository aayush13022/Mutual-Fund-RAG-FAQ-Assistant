"""Persist chat conversations to disk so history survives restarts."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rag.models import RAGResponse

HISTORY_PATH = Path(os.getenv("CHAT_HISTORY_PATH", "data/chat_history.json"))

_TITLE_MAX = 50


def _serialize_message(message: dict) -> dict:
    out: dict = {"role": message["role"], "content": message.get("content", "")}
    if message.get("error"):
        out["error"] = True
    response = message.get("response")
    if isinstance(response, RAGResponse):
        out["response"] = asdict(response)
    return out


def _deserialize_message(data: dict) -> dict:
    message: dict = {"role": data["role"], "content": data.get("content", "")}
    if data.get("error"):
        message["error"] = True
    response = data.get("response")
    if response:
        message["response"] = RAGResponse(**response)
    return message


def new_conversation() -> dict:
    """Create an empty conversation with a unique id and timestamp."""
    return {
        "id": uuid.uuid4().hex,
        "title": "New chat",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "messages": [],
    }


def conversation_title(message: str) -> str:
    """Derive a short conversation title from the first user message."""
    text = " ".join(message.strip().split())
    if not text:
        return "New chat"
    return text[:_TITLE_MAX] + ("…" if len(text) > _TITLE_MAX else "")


def load_conversations() -> list[dict]:
    """Load saved conversations from disk; return [] if missing or unreadable."""
    if not HISTORY_PATH.exists():
        return []
    try:
        raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []

    conversations: list[dict] = []
    for conv in raw:
        try:
            conversations.append(
                {
                    "id": conv["id"],
                    "title": conv.get("title", "New chat"),
                    "created_at": conv.get("created_at", ""),
                    "messages": [
                        _deserialize_message(m) for m in conv.get("messages", [])
                    ],
                }
            )
        except (KeyError, TypeError):
            continue
    return conversations


def save_conversations(conversations: list[dict]) -> None:
    """Persist conversations to disk atomically. Empty conversations are skipped."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = [
        {
            "id": conv["id"],
            "title": conv.get("title", "New chat"),
            "created_at": conv.get("created_at", ""),
            "messages": [_serialize_message(m) for m in conv["messages"]],
        }
        for conv in conversations
        if conv.get("messages")
    ]

    tmp = HISTORY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(HISTORY_PATH)
