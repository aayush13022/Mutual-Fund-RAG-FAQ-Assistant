"""Mutual Fund FAQ Assistant — Streamlit UI + in-process RAG backend."""

from __future__ import annotations

import streamlit as st

from config.settings import configure_logging, get_settings
from rag.models import RAGResponse
from rag.warmup import warmup_rag_stack
from stapp.chat_handler import ChatError, handle_message
from stapp.constants import (
    ASK_TOPICS,
    CANNOT_ASK,
    DISCLAIMER,
    EXAMPLE_QUESTIONS,
    FOOTER_NOTE,
    SUPPORTED_SCHEMES,
    WELCOME_MESSAGE,
)
from stapp.history import (
    conversation_title,
    load_conversations,
    new_conversation,
    save_conversations,
)

configure_logging()


def _init_session_state() -> None:
    if "conversations" not in st.session_state:
        st.session_state.conversations = load_conversations()
    if "current_id" not in st.session_state or not _conversation_exists(
        st.session_state.current_id
    ):
        _start_new_chat()


def _conversation_exists(conversation_id: str) -> bool:
    return any(c["id"] == conversation_id for c in st.session_state.conversations)


def _current_conversation() -> dict:
    for conv in st.session_state.conversations:
        if conv["id"] == st.session_state.current_id:
            return conv
    conv = new_conversation()
    st.session_state.conversations.insert(0, conv)
    st.session_state.current_id = conv["id"]
    return conv


def _start_new_chat() -> None:
    conv = new_conversation()
    st.session_state.conversations.insert(0, conv)
    st.session_state.current_id = conv["id"]


def _switch_conversation(conversation_id: str) -> None:
    st.session_state.current_id = conversation_id


def _clear_history() -> None:
    st.session_state.conversations = []
    save_conversations(st.session_state.conversations)
    _start_new_chat()


@st.cache_resource(show_spinner="Loading assistant models…")
def _warmup_stack() -> bool:
    warmup_rag_stack(get_settings())
    return True


def _render_assistant_message(response: RAGResponse) -> None:
    if response.refused:
        st.warning(response.answer)
        if response.educational_link:
            st.link_button("Learn more at AMFI", response.educational_link)
        return

    st.markdown(response.answer)

    if response.source_url:
        st.caption("Factual data")
        st.link_button("View source on Groww", response.source_url)
        if response.last_updated_from_sources:
            st.caption(f"Last updated from sources: {response.last_updated_from_sources}")

    st.caption(response.disclaimer)


def _process_question(question: str) -> None:
    conv = _current_conversation()
    conv["messages"].append({"role": "user", "content": question})
    if conv["title"] == "New chat":
        conv["title"] = conversation_title(question)

    try:
        response = handle_message(question)
        conv["messages"].append(
            {"role": "assistant", "content": response.answer, "response": response}
        )
    except ChatError as exc:
        conv["messages"].append(
            {"role": "assistant", "content": str(exc), "error": True}
        )

    save_conversations(st.session_state.conversations)


def _render_sidebar() -> None:
    with st.sidebar:
        st.header("Chats")
        st.button(
            "➕ New chat",
            key="new-chat",
            on_click=_start_new_chat,
            use_container_width=True,
        )

        saved = [c for c in st.session_state.conversations if c.get("messages")]
        if saved:
            st.caption("Previous chats")
            for conv in saved:
                is_current = conv["id"] == st.session_state.current_id
                st.button(
                    ("• " if is_current else "") + conv["title"],
                    key=f"conv-{conv['id']}",
                    on_click=_switch_conversation,
                    args=(conv["id"],),
                    use_container_width=True,
                    type="primary" if is_current else "secondary",
                )
            st.divider()
            st.button(
                "🗑 Clear all history",
                key="clear-history",
                on_click=_clear_history,
                use_container_width=True,
            )
        else:
            st.caption("No previous chats yet.")


def _render_welcome() -> None:
    st.markdown(WELCOME_MESSAGE)

    schemes_col, ask_col = st.columns(2)
    with schemes_col:
        st.markdown("**Supported schemes**")
        for scheme in SUPPORTED_SCHEMES:
            st.markdown(f"- {scheme}")
    with ask_col:
        st.markdown("**What you can ask about each fund**")
        for topic, _ in ASK_TOPICS:
            st.markdown(f"- {topic}")

    with st.expander("See sample questions for each topic"):
        for topic, sample in ASK_TOPICS:
            st.markdown(f"- **{topic}** — _{sample}_")
        st.markdown("**I can't help with** (facts only):")
        for item in CANNOT_ASK:
            st.markdown(f"- {item}")

    st.markdown("**Try an example**")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for col, question in zip(cols, EXAMPLE_QUESTIONS, strict=True):
        if col.button(question, key=f"example-{question}", use_container_width=True):
            _process_question(question)
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Mutual Fund FAQ Assistant",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _init_session_state()
    _warmup_stack()

    st.warning(f"**Disclaimer:** {DISCLAIMER}")

    conv = _current_conversation()

    header_col, home_col = st.columns([0.8, 0.2])
    with header_col:
        st.title("Mutual Fund FAQ Assistant")
        st.caption("HDFC · 5 schemes")
    with home_col:
        if conv["messages"]:
            st.button(
                "← Back to home",
                key="home-button",
                on_click=_start_new_chat,
                use_container_width=True,
            )

    _render_sidebar()

    if not conv["messages"]:
        _render_welcome()

    for message in conv["messages"]:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            elif message.get("error"):
                st.error(message["content"])
            else:
                response = message.get("response")
                if isinstance(response, RAGResponse):
                    _render_assistant_message(response)
                else:
                    st.markdown(message["content"])

    if prompt := st.chat_input("Ask a factual question about an HDFC scheme…"):
        _process_question(prompt)
        st.rerun()

    st.caption(FOOTER_NOTE)


if __name__ == "__main__":
    main()
