# UI — Mutual Fund FAQ Assistant (Phase 6)

Next.js frontend matching the **Compliance-First Dark** Stitch design.

## Prerequisites

- Node.js 18+
- FastAPI backend running on `http://localhost:8000`

## Setup

```bash
cd ui
npm install
cp .env.local.example .env.local   # optional — override API URL
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | unset | Local dev only — direct calls to FastAPI (`http://localhost:8000`) |
| `API_URL` | — | Vercel production — powers `/api` proxy to Railway |

## Features

- Sticky disclaimer banner (always visible)
- Welcome block with 5 supported HDFC schemes
- 3 example question chips (auto-send on click)
- User / bot chat bubbles (factual + refusal states)
- Source link + last-updated footer on factual answers
- Loading spinner and error retry
- Responsive layout (mobile + desktop)

## Run with backend

```bash
# Terminal 1 — API
uvicorn api.main:app --reload --port 8000

# Terminal 2 — UI
cd ui && npm run dev
```

## Verify Phase 6 exit criteria

```bash
# API contract checks (no browser required)
python scripts/test_chat_ui.py

# Full pytest suite including Phase 6
pytest tests/test_phase6.py -q
```

Manual browser checks at http://localhost:3000:

1. Welcome + disclaimer + 3 example chips visible on load
2. Click example chip → factual answer with Groww source link
3. Ask "Should I invest in HDFC Defence?" → refusal + AMFI link
