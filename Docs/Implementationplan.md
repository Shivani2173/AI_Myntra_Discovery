# Implementation plan

Ordered build for v1. Sources: [ai_discovery_engine_4d13c1f6.plan.md](ai_discovery_engine_4d13c1f6.plan.md), [Architecture.md](Architecture.md).

**Done when:** Vercel shows behavior cards + corpus % from Neon; gather is incremental; Gemini never sees the same `source_id` / `content_hash` twice; live API outage does not blank the UI.

Do not build: uploads, Play Store, scrapers, Streamlit, Ollama on Render, secrets in the Vercel client bundle.

## Layout to create

```
backend/                 FastAPI, connectors, pipeline, taxonomy, CLI
web/                    Next.js (Vercel)
configs/default.yaml    queries, app IDs, quota caps
eval/gold_set.jsonl     gold labels
.env.example
render.yaml
Docs/                   already present
```

Local DB may be SQLite via `DATABASE_URL`. Production is Neon Postgres.

---

## Phase 0 — Scaffold

**Goal:** Empty app boots locally; schema exists; no live APIs required.

- Python 3.11+ FastAPI app: `/health`, settings from `.env`
- SQLAlchemy/SQLModel (or equivalent) tables:
  - `units` — unique `(source, source_id)`, `content_hash`, `last_seen_at`, text envelope
  - `codes` — JSON, `coded_at`
  - `source_watermarks`, `source_status`
  - optional `behavior_rollups`
- Migrations (Alembic or create-all for v1)
- Next.js app in `web/` with three routes (home, detail, explorer) and stub data
- `.env.example`: `DATABASE_URL`, `INGEST_TOKEN`, `CORS_ORIGINS`, Reddit, YouTube, Gemini (optional locally)
- `configs/default.yaml`: query list, app IDs, small quota caps
- CLI: `python -m backend.cli health`

**Exit:** `GET /health` 200; Next.js renders shell; Postgres/SQLite creates tables.

---

## Phase 1 — Connectors (incremental gather)

**Goal:** Pull public text into `units` without coding.

- Shared `SourceConnector` → same envelope (`source`, `source_id`, `url`, `author_hash`, `created_at`, `text`, `parent_context`)
- Reddit (PRAW), YouTube Data API v3, App Store RSS (Myntra, AJIO, Nykaa Fashion, Amazon IN)
- Upsert by `(source, source_id)`; bump `last_seen_at` on re-fetch; **no delete** on failure
- Watermarks: Reddit after-id, YouTube page token, RSS etag/date
- If one connector throws: write `source_status`, continue others
- `POST /jobs/gather` + `GET /jobs/{id}` background; require `INGEST_TOKEN`
- First-run caps from config (small)

**Exit:** Job fills `units`; second run inserts ~0 duplicates; killing YouTube still saves Reddit + RSS.

---

## Phase 2 — Taxonomy + Gemini extract (code once)

**Goal:** Label new rows only; persist codes forever.

- Taxonomy module: families A–G, Pydantic schema (`primary_barrier`, `secondary_barriers`, `outcome_stance`, `intensity`, `w2p_stage`, quotes, supporting codes)
- Cheap relevance filter on **new** `units` only
- Gemini Flash (Ollama if no key, **local only**)
- Skip Gemini when `coded_at` set **or** `content_hash` / near-dup embedding matches a coded unit
- Never update `codes` except schema migration
- MiniLM for near-dup (batch-capped for Render RAM)

**Exit:** Re-running extract does not increase Gemini calls on the same corpus; invalid JSON retries then fails the row, not the job.

---

## Phase 3 — Behavior map + numbers

**Goal:** `GET /behaviors` is CPU-only from `codes`.

- Roll up `primary_barrier` → `% didn’t buy`, N, unique voices, stance mix, source mix, mean intensity
- Co-occurrence from `secondary_barriers`
- Cluster `other_*` into named emergent behaviors
- Sort by primary % then intensity
- Caption fields: “of analyzed wishlist conversations”
- `GET /behaviors`, `GET /behaviors/{id}` (quotes, overlaps, levers stubs), `GET /units`

**Exit:** With Gemini mocked off, endpoints still return last rollup. Percents of primary barriers ~100%.

---

## Phase 4 — UI

**Goal:** Vercel UI matches the plan’s sample output.

- Home: N, voices, overall stance; donut/bars; ranked cards (`18% didn’t buy…`); chips; source_status banner; **Refresh** → `POST /jobs/gather` + poll
- Paint stored data **first**; auto-gather only if DB empty
- Detail: % + N, stage, quotes, overlap %, levers, download quotes/CSV
- Explorer: search table of units
- Accent `#E11D48`; footer caption; **no** file input
- CORS: Vercel origin

**Exit:** Browser walkthrough of home → detail → explorer; YouTube-down banner with data still visible.

---

## Phase 5 — Eval + deploy

**Goal:** Quality gate + hosted stack.

- `eval/gold_set.jsonl`: relevance, `outcome_stance`, `primary_barrier` (start ~80–120)
- Script: precision/recall vs Gemini codes
- `render.yaml`: `uvicorn`, health check, env list
- Neon `DATABASE_URL` on Render
- Vercel: `web/`, `NEXT_PUBLIC_API_URL`
- README: keys, first gather, quota, Reddit IP fallback (laptop gather, UI on Vercel)
- Optional GitHub Action to ping gather (Render free has no cron)

**Exit:** Deployed UI loads insights after Render sleep; gather from empty Neon works; gold-set script runs in CI or locally.

---

## Suggested order of work

```text
Phase 0 scaffold
    → Phase 1 connectors
        → Phase 2 extract (can stub Gemini with fixtures)
            → Phase 3 rollup API
                → Phase 4 UI (can use fixture JSON until 3 is ready)
                    → Phase 5 gold-set + Render/Vercel/Neon
```

Phase 4 can start against mocked `/behaviors` in parallel with Phase 3.

## Definition of v1 done

| Criterion | Check |
|---|---|
| Store-first | Stop Reddit/YouTube/Gemini; UI still shows last cards |
| Code once | Same unit gathered twice → 0 extra Gemini calls |
| Incremental | Watermarks; only new IDs fetched |
| Output | Behavior + quotes + % / N / stance mix, labeled as corpus |
| No upload | No file inputs in `web/` |
| Hosting | Vercel + Render + Neon; secrets on Render |

## Risks (handle in the phase named)

| Risk | Phase | Mitigation |
|---|---|---|
| YouTube quota | 1 | Caps in `configs/default.yaml` |
| Render 512MB / MiniLM | 2 | Small model, small batches |
| Reddit blocks Render IPs | 1, 5 | CLI gather locally; Neon still serves UI |
| Gemini JSON drift | 2, 5 | Pydantic + gold-set |
| Empty first gather failure | 4 | Error empty state; do not pretend data exists |
