# Streamlit App — Mutual Fund FAQ Assistant

Single Python app that combines the **UI and RAG backend** (no separate FastAPI or Next.js).

## Run locally

```bash
# From repo root — API keys and corpus paths in .env
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501).

Ensure the FastAPI backend is **not** required — chat calls `rag.generator.answer()` in-process.

## Environment

Same as the FastAPI backend (see `.env.example`):

| Variable | Required | Notes |
|----------|----------|-------|
| `GROQ_API_KEY` | Yes | LLM generation |
| `EMBEDDING_PROVIDER` | Yes | `bge` or `openai` |
| `CHROMA_PERSIST_DIR` | Yes | `./data/chroma` locally |
| `METADATA_DB_PATH` | Yes | `./data/metadata.db` locally |

## Deploy on Streamlit Community Cloud

1. [share.streamlit.io](https://share.streamlit.io) → **Create app** → pick the repo
   (`aayush13022/rag-demo-1`), branch `main`, **main file** `streamlit_app.py`.
2. **Advanced settings → Secrets**: add at least `GROQ_API_KEY = "gsk_..."`
   (TOML format). Other config has sensible defaults; local `./data/...` paths work.
3. Deploy. Health endpoint: `/_stcore/health`.

> **Stale build / `ImportError` after a push:** Streamlit Community Cloud can cache a
> previous checkout. If you see an import error for symbols that exist in the repo, open
> **Manage app → ⋮ → Reboot app** (or **Clear cache**), or push a new commit to force a
> clean re-clone.

> **Memory:** the app loads a local BGE embedding model. Keep `BGE_KEEP_SINGLE_MODEL=true`.
> If the instance runs out of memory, deploy on Railway (≥ 2 GB) instead, or switch to
> `EMBEDDING_PROVIDER=openai` (needs `OPENAI_API_KEY`).

## Deploy on Railway

The repo `Procfile` and `railway.toml` start Streamlit:

```bash
streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
```

Health check: `/_stcore/health`

Use the same Railway env vars as the FastAPI deployment (Groq key, Chroma paths, volume mount at `/data`).

## Architecture

```text
Browser → Streamlit (streamlit_app.py)
              → stapp/chat_handler.py  (guardrails)
              → rag/generator.py         (retrieve + LLM)
```

The old **Next.js + FastAPI** stack under `ui/` and `api/` is kept for reference but is no longer the default deploy path.

## Features

- Disclaimer banner
- Welcome block + 5 supported schemes
- 3 example question buttons
- Chat history with source links and refusal handling
- Dark theme (`.streamlit/config.toml`)
