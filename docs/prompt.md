# Google Stitch Design Prompt — Mutual Fund FAQ Assistant (Chat UI)

Use this document as the full design brief when generating frontend mockups in **Google Stitch** for Phase 6 of this project.

**References:** [architecture.md](./architecture.md) §9, [implementation-plan.md](./implementation-plan.md) Phase 6, [problemStatement.md](./problemStatement.md)

---

## Product summary

Design a **minimal, mobile-first chat interface** for the **Mutual Fund FAQ Assistant** — a facts-only Q&A web app for **5 HDFC mutual fund schemes** on Groww.

The app answers **objective, verifiable questions only** (expense ratio, exit load, minimum SIP, benchmark, fund managers, etc.). It must **never** feel like a trading or advisory product. Tone: **trustworthy, calm, compliance-first** — like a financial help desk, not a fintech growth app.

**Tech context (for layout only):** Static HTML/JS or React frontend calling `POST /chat` on a FastAPI backend. No login, no accounts, no portfolio.

---

## Design goals

1. **Compliance visible at all times** — disclaimer always on screen
2. **Source transparency** — every bot answer shows one clickable source link + “last updated” date
3. **Low cognitive load** — welcome, 3 example questions, simple chat thread
4. **Clear refusal state** — advisory/comparison questions get a distinct visual treatment + educational link
5. **Responsive** — works on mobile (375px) and desktop (1280px)

---

## Screens to design

Design **one main screen** with these **states**:

| State | When |
|-------|------|
| **Empty / welcome** | First load, no messages yet |
| **Loading** | User sent a message, waiting for API |
| **Factual answer** | Successful response with source |
| **Refusal** | Investment advice / comparison blocked |
| **Error** | API offline or 503 timeout |
| **Retrieval miss** | “Could not find in sources” (still 200 OK) |

Optional: **mobile** and **desktop** variants of the same screen.

---

## Page structure (top → bottom)

```
┌─────────────────────────────────────────────┐
│ STICKY DISCLAIMER BANNER (always visible)   │
├─────────────────────────────────────────────┤
│ App title + short subtitle                  │
│ Welcome message                             │
│ “Supported schemes” — list of 5 fund names  │
│                                             │
│ [Example chip 1] [Example chip 2] [Chip 3]  │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ CHAT THREAD (scrollable)                │ │
│ │   User bubble (right)                   │ │
│ │   Bot card (left) — answer + metadata   │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [ Text input........................ ] [Send]│
└─────────────────────────────────────────────┘
```

---

## Required UI elements

### 1. Sticky disclaimer banner

- **Copy:** `Facts-only. No investment advice.`
- Always visible; do not hide on scroll
- Subtle but distinct (e.g. soft amber or neutral info bar)

### 2. Header

- **Title:** `Mutual Fund FAQ Assistant`
- **Subtitle:** `HDFC Mutual Fund · 5 schemes`
- Optional small badge: `Source-backed answers`

### 3. Welcome block

Shown before or above the first message.

- **Copy:**  
  `Ask factual questions about 5 HDFC mutual fund schemes. I provide source-backed answers only — no investment advice.`

### 4. Supported schemes list

Display all 5 (compact list or chips):

1. HDFC Mid Cap Fund Direct Growth
2. HDFC Large Cap Fund Direct Growth
3. HDFC Small Cap Fund Direct Growth
4. HDFC Gold ETF Fund of Fund Direct Plan Growth
5. HDFC Defence Fund Direct Growth

### 5. Example question chips (3, clickable)

1. `What is the expense ratio of HDFC Defence Fund Direct Growth?`
2. `What is the exit load on HDFC Mid Cap Fund Direct Growth?`
3. `Who manages HDFC Large Cap Fund Direct Growth?`

**Behavior:** tap → fills input and sends (design as tappable pills/chips).

### 6. Chat input + Send

- Placeholder: `Type your question...`
- Send button disabled while loading
- Max ~500 characters visually; multiline OK

### 7. Message bubbles

**User message (right-aligned)**

- Short question text
- Timestamp optional

**Bot — factual answer card (left-aligned)**

Must show:

- Answer text (≤3 sentences)
- **Source link** — e.g. `View source on Groww` (opens new tab)
- **Footer:** `Last updated from sources: 2026-06-18` (date from API)
- Small disclaimer repeat optional inside card

**Bot — refusal card (left-aligned, different style)**

- **Answer:**  
  `I can only answer factual questions about mutual fund schemes. I cannot provide investment advice or recommend funds.`
- **Button/link:** `Learn about investing responsibly` → AMFI educational page
- No source URL on refusals
- Visual: muted/warning tone (not error red)

**Bot — error state**

- Friendly copy: `Something went wrong. Please try again.`
- Retry button

**Bot — loading state**

- Typing indicator or skeleton in bot bubble area

---

## API response shapes (for accurate UI)

### Factual success (`refused: false`)

```json
{
  "answer": "The expense ratio of HDFC Defence Fund Direct Growth is 0.88%.",
  "source_url": "https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",
  "last_updated_from_sources": "2026-06-18",
  "disclaimer": "Facts-only. No investment advice.",
  "refused": false
}
```

### Refusal (`refused: true`)

```json
{
  "answer": "I can only answer factual questions about mutual fund schemes. I cannot provide investment advice or recommend funds.",
  "educational_link": "https://www.amfiindia.com/investor/knowledge-center-info",
  "disclaimer": "Facts-only. No investment advice.",
  "refused": true
}
```

### Retrieval miss (still success UI, no source)

- **Answer:** `I could not find this information in my sources.`
- No `source_url`

---

## Visual direction

**Do:**

- Clean fintech-adjacent but **not** flashy
- Plenty of whitespace
- Readable body text (16px+ on mobile)
- Accessible contrast (WCAG AA)
- Distinct colors for: user bubble, bot answer, bot refusal, loading, error
- HDFC-adjacent trust palette OK (deep blue + white + neutral grays) — no official HDFC branding required

**Do not:**

- Stock charts, NAV graphs, buy/sell CTAs
- Portfolio dashboards, login screens, KYC flows
- “Recommend a fund” or comparison UI
- Dark patterns that hide the disclaimer
- More than one source link per answer

---

## Interaction details

| Action | Behavior |
|--------|----------|
| Click example chip | Auto-send that question |
| Send while loading | Disable input + show spinner |
| Double Send | Prevent duplicate requests (debounce) |
| Source link | Opens Groww URL in new tab |
| Long answer | Wrap text; no truncation needed (API caps at 3 sentences) |
| Mobile keyboard | Input stays visible; chat scrolls to latest message |

---

## Edge cases to reflect in design

- Empty input → no send (or inline validation hint)
- API 503 → error card + retry
- Refusal without `educational_link` → still show refusal text gracefully
- Very long scheme names → wrap in supported schemes list
- Special characters in user messages → normal text rendering

---

## Deliverables requested from Stitch

1. **Desktop chat screen** — welcome + example chips + 1 factual answer + 1 refusal in thread
2. **Mobile chat screen** — same content, stacked layout
3. **Component specs:** disclaimer bar, example chip, user bubble, bot answer card, bot refusal card, loading state, error state
4. **Color + typography tokens** (primary, surface, text, success/info/warning/error)
5. **Spacing system** for chat bubbles and cards

---

## Reference copy (exact strings)

| Element | Text |
|---------|------|
| Disclaimer | `Facts-only. No investment advice.` |
| Welcome | `Ask factual questions about 5 HDFC mutual fund schemes. I provide source-backed answers only — no investment advice.` |
| Input placeholder | `Type your question...` |
| Send button | `Send` |
| Source link label | `View source on Groww` |
| Last updated prefix | `Last updated from sources:` |
| Educational CTA | `Learn about investing responsibly` |
| Loading | `Finding an answer...` |
| Error | `Something went wrong. Please try again.` |
| Retry | `Retry` |

---

## Out of scope for this design

- Admin / ingestion dashboard
- Settings page
- Auth / user profile
- Charts, calculators, fund comparison tables
- Multi-language UI (English only for MVP)

---

## Success criteria

A developer should be able to implement `ui/index.html`, `ui/app.js`, and `ui/style.css` directly from your designs without guessing layout, states, or copy.

---

## Short prompt (paste into Stitch quick-generate)

> Design a mobile-first chat UI for a **facts-only Mutual Fund FAQ Assistant** (HDFC, 5 Groww schemes). Sticky top banner: “Facts-only. No investment advice.” Welcome text, list of 5 fund names, 3 clickable example question chips. Scrollable chat: user bubbles right, bot cards left. Bot factual card: answer (≤3 sentences), “View source on Groww” link, “Last updated from sources” date. Bot refusal card: different muted style, no source, CTA “Learn about investing responsibly”. Loading spinner, error + retry. Calm trust palette (blue/white/gray), no charts or buy/sell. Desktop + mobile. Compliance-first, minimal, accessible.
