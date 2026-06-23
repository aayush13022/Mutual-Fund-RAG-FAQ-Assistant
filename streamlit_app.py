"""Mutual Fund FAQ Assistant — Streamlit UI + in-process RAG backend."""

from __future__ import annotations

import base64
from pathlib import Path

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

LOGO_PATH = str(Path(__file__).parent / "assets" / "groww-logo.png")

_CUSTOM_CSS = """
<style>
:root {
    --groww-teal: #00d09c;
    --groww-blue: #5367ff;
}

/* Tighten top padding and widen content a touch */
.block-container {
    padding-top: 2.2rem;
    max-width: 920px;
}

/* Brand header */
.mf-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 4px;
}
.mf-header img {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    box-shadow: 0 4px 18px rgba(83, 103, 255, 0.35);
}
.mf-title {
    font-size: 1.6rem;
    font-weight: 700;
    line-height: 1.1;
    margin: 0;
    background: linear-gradient(90deg, var(--groww-blue), var(--groww-teal));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.mf-badge {
    display: inline-block;
    margin-top: 4px;
    padding: 2px 10px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    color: var(--groww-teal);
    background: rgba(0, 208, 156, 0.12);
    border: 1px solid rgba(0, 208, 156, 0.35);
    border-radius: 999px;
}

/* Disclaimer banner */
.mf-disclaimer {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    margin: 10px 0 18px 0;
    font-size: 0.86rem;
    color: #ffd9a8;
    background: rgba(255, 170, 60, 0.10);
    border: 1px solid rgba(255, 170, 60, 0.30);
    border-radius: 12px;
}

/* Info cards on the welcome screen */
.mf-card {
    padding: 16px 18px;
    background: var(--secondary-background-color, #151c30);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    height: 100%;
}
.mf-card h4 {
    margin: 0 0 10px 0;
    font-size: 0.95rem;
    color: #cdd6ff;
}
.mf-card ul {
    margin: 0;
    padding-left: 18px;
}
.mf-card li {
    margin-bottom: 6px;
    font-size: 0.88rem;
    color: #e6ebff;
}

/* Buttons */
.stButton > button {
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.10);
    font-weight: 500;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    border-color: var(--groww-teal);
    color: var(--groww-teal);
}

/* Chat bubbles */
[data-testid="stChatMessage"] {
    border-radius: 14px;
    padding: 2px 6px;
}

/* Footer note */
.mf-footer {
    margin-top: 22px;
    text-align: center;
    font-size: 0.78rem;
    color: #7c87a8;
}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def _render_header() -> None:
    try:
        encoded = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode()
        logo_html = f'<img src="data:image/png;base64,{encoded}" alt="Groww logo" />'
    except OSError:
        logo_html = ""

    st.markdown(
        f"""
        <div class="mf-header">
            {logo_html}
            <div>
                <p class="mf-title">Mutual Fund FAQ Assistant</p>
                <span class="mf-badge">HDFC · 5 schemes · Source: Groww</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    st.markdown(f"#### {WELCOME_MESSAGE}")

    schemes_items = "".join(f"<li>{scheme}</li>" for scheme in SUPPORTED_SCHEMES)
    ask_items = "".join(f"<li>{topic}</li>" for topic, _ in ASK_TOPICS)

    schemes_col, ask_col = st.columns(2)
    with schemes_col:
        st.markdown(
            f'<div class="mf-card"><h4>📂 Supported schemes</h4>'
            f"<ul>{schemes_items}</ul></div>",
            unsafe_allow_html=True,
        )
    with ask_col:
        st.markdown(
            f'<div class="mf-card"><h4>💡 What you can ask</h4>'
            f"<ul>{ask_items}</ul></div>",
            unsafe_allow_html=True,
        )

    st.write("")
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
    page_icon = LOGO_PATH if Path(LOGO_PATH).exists() else "💬"
    st.set_page_config(
        page_title="Mutual Fund FAQ Assistant",
        page_icon=page_icon,
        layout="centered",
        initial_sidebar_state="expanded",
    )

    if Path(LOGO_PATH).exists():
        st.logo(LOGO_PATH, size="large")

    _inject_css()
    _init_session_state()
    _warmup_stack()

    conv = _current_conversation()

    header_col, home_col = st.columns([0.78, 0.22])
    with header_col:
        _render_header()
    with home_col:
        if conv["messages"]:
            st.button(
                "← Back to home",
                key="home-button",
                on_click=_start_new_chat,
                use_container_width=True,
            )

    st.markdown(
        f'<div class="mf-disclaimer">⚠️ <strong>Disclaimer:</strong>&nbsp;{DISCLAIMER}</div>',
        unsafe_allow_html=True,
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

    st.markdown(f'<div class="mf-footer">{FOOTER_NOTE}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
