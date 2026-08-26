# AI Discovery Engine

Store-first wishlist → purchase barrier insights. Connectors find public text; Gemini labels new rows once; the UI reads corpus % from the database (no live APIs required on read).

## Stack

| Piece | Host | Notes |
|---|---|---|
| `web/` | **Vercel** | Next.js; only `NEXT_PUBLIC_API_URL` + server `INGEST_TOKEN` |
| `backend/` | **Render** | FastAPI gather + extract + `/behaviors` |
| DB | **Neon** Postgres | `DATABASE_URL` on Render (SQLite OK locally) |

Secrets stay on Render. Never put YouTube / Gemini keys in the Vercel client bundle.

## Local setup

### 1. Python API

```powershell
cd AI_DIscovery_Engine_Myntra
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
pip install .
copy .env.example .env
```

Fill `.env` (see below). Then:

```powershell
python -m backend.cli health
uvicorn backend.main:app --reload --port 8000
```

### 2. Next.js UI

```powershell
cd web
copy .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 — cards load from `GET /behaviors`.

`web/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
INGEST_TOKEN=change-me
```

`INGEST_TOKEN` must match the backend (used only by Next `/api/refresh` proxy).

## Keys

| Env | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | Render / local | Neon Postgres or `sqlite:///./data/app.db` |
| `INGEST_TOKEN` | Render + `web/.env.local` | Gate `POST /jobs/gather` |
| `CORS_ORIGINS` | Render | Your Vercel origin, e.g. `https://….vercel.app` |
| `GEMINI_API_KEY` | Render | Code new units (Flash) |
| `YOUTUBE_API_KEY` | Render | Comments (quota-capped in `configs/default.yaml`) |
| `NEXT_PUBLIC_API_URL` | Vercel | Render API URL |

Optional local: Ollama if Gemini empty (`OLLAMA_*`). Not used on Render (`RENDER=true`).

## First gather

```powershell
python -m backend.cli gather
```

Or from the UI: **Refresh insights** (proxies to gather + extract). First run is capped small. Later runs are incremental (watermarks + skip already-coded).

```powershell
python -m backend.cli extract
python -m backend.cli behaviors
```

## Quotas

- YouTube: keep `quota_caps` low in `configs/default.yaml`.
- Gemini free tier: extract pauses between calls; if quota hits, re-run `extract` later. Old codes stay served.

## Deploy

### Neon

1. Create a free Postgres project.
2. Copy the connection string as `DATABASE_URL` (use SSL).

### Render

1. New Web Service from this repo (or Blueprint with `render.yaml`).
2. Set env vars listed in `render.yaml` (`sync: false` → fill in dashboard).
3. Health check: `/health`.
4. After deploy, hit `POST /jobs/gather` once with `X-Ingest-Token` (or use the GitHub Action).

### Vercel

1. Import repo; **Root Directory** = `web`.
2. Env: `NEXT_PUBLIC_API_URL=https://<your-render>.onrender.com`
3. Env: `INGEST_TOKEN=<same as Render>`
4. On Render, set `CORS_ORIGINS` to your Vercel URL.

Render free sleeps — first request after idle is slow; data still loads from Neon.

## Eval (gold set)

```powershell
python eval/build_gold_set.py
python -m eval.score --predict stub    # CI / no Gemini
python -m eval.score --predict db      # vs codes already in DB
python -m eval.score --predict llm     # live Gemini/Ollama (uses quota)
```

Gold labels: `relevant`, `outcome_stance`, `primary_barrier` (~100 rows in `eval/gold_set.jsonl`).

CI: `.github/workflows/eval.yml`.

## Optional scheduled gather

`.github/workflows/gather.yml` — every 12h + manual. Repo secrets: `API_URL`, `INGEST_TOKEN`.

## Phase checklist

| Phase | Status |
|---|---|
| 0 Scaffold | Done |
| 1 Connectors | Done |
| 2 Taxonomy + extract | Done |
| 3 Behavior map API | Done |
| 4 UI | Done |
| 5 Eval + deploy | Config + scripts in repo; you wire Neon/Render/Vercel |

## Honest limits

Corpus % = share of **analyzed wishlist conversations**, not live Myntra W2P. Public chatter is biased. No file upload, no Play Store connector, no scraping.
