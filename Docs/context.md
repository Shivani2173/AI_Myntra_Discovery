# Context

Working context for the AI Discovery Engine. Derived from [problemstatement.md](problemstatement.md) and the plan [ai_discovery_engine_4d13c1f6.plan.md](ai_discovery_engine_4d13c1f6.plan.md) (canonical copy also at `c:\Users\Shivani\.cursor\plans\ai_discovery_engine_4d13c1f6.plan.md`).

## What this project is

A **store-first discovery engine** for fashion e-commerce (Myntra / AJIO and peers). It automatically collects public conversations, codes **why wishlisted items are not purchased**, and shows **behavior cards plus corpus percentages** (for example: 18% of analyzed conversations didn’t convert because of size distrust).

It is not a review summarizer and not a sentiment dashboard. The unit of work is **wishlist → not purchased**.

Greenfield repo. Frontend on **Vercel** (Next.js). Backend on **Render** (FastAPI). Data in **Neon** Postgres. All v1 APIs are free.

## Problem we are solving

Teams can see wishlist-to-purchase is weak in internal metrics. They cannot see **which behaviors** cause the leak: bookmark vs real intent, postpone vs abandon, size uncertainty after the product is already chosen, price-watch, OOS, comparison paralysis, off-app research, forgotten list.

Naive approaches fail: sentiment, manual uploads, unbounded “AI search the web,” live-only pipelines that blank when Reddit/YouTube/Gemini are down, re-coding the same text (wasted tokens), or stating “18% of Myntra users didn’t buy” from public chatter.

**Honest number:** “18% didn’t buy because of size” = 18% of **coded wishlist conversations** whose `primary_barrier` is size — labeled *of analyzed conversations*, not live Myntra W2P.

## Primary question

**Why do users add fashion products to a wishlist and then not buy them? What distinct reasons and barriers explain that drop-off?**

Must also inform (as supporting codes, not a second product): motive, remaining uncertainty, postpone triggers, how they compare, what they seek off Myntra/AJIO, role of fit/size/styling/price/reviews/occasion/social proof, bookmark vs intent, inferred segments, unmet needs.

## How data is gathered (no upload)

There is **no CSV or file upload**. One-time keys in Render env; then gather is automatic.

1. **Find (APIs, not Gemini browsing):** Reddit search, YouTube comments on haul/fit videos, Apple App Store RSS for Myntra / AJIO / Nykaa Fashion / Amazon IN. Built-in queries: `wishlist`, `waiting for sale`, `size chart`, `should I buy`, `Myntra return`, `AJIO fit`.
2. **Store** every unit in Neon (`UNIQUE source, source_id` + `content_hash`).
3. **Understand (Gemini):** only rows with `coded_at IS NULL`. Labels primary/secondary barriers, stance, intensity, stage, quotes.
4. **Map behaviors** from stored codes (CPU, **no extra tokens**).

Refresh fetches **new IDs only** (watermarks). If one source is down, keep old rows, log `source_status`, still serve `GET /behaviors` from DB.

**Not in v1:** Play Store, Instagram, TikTok, X, Amazon/Flipkart Q&A, scraping, paid aggregators.

## Barrier taxonomy (seed)

Codes are not mutually exclusive. LLM may add `other_*`; clustering promotes repeats.

| Family | Examples |
|---|---|
| A. Not real intent | `bookmark_inspiration`, `bookmark_compare_later`, `gift_or_other_person`, `low_urgency_maybe` |
| B. Uncertainty after product identified | `fit_size_uncertainty`, `looks_vs_reality`, `styling_wardrobe_fit`, `occasion_timing`, `social_validation` |
| C. Economic / value | `wait_for_price_drop`, `better_price_elsewhere`, `budget_payday`, `value_doubt` |
| D. Risk / reversal | `return_exchange_friction`, `review_trust`, `past_bad_experience`, `counterfeit_or_seller_doubt` |
| E. Choice friction | `too_many_shortlisted`, `missing_compare_tools`, `switched_to_alternative` |
| F. Operational | `oos_after_wishlist`, `delivery_too_slow`, `payment_or_app_friction`, `forgotten_wishlist` |
| G. Off-platform proof | `seeking_external_proof` |

Also on each unit: `primary_barrier` (feeds % didn’t buy, ~100%), `secondary_barriers`, `outcome_stance` (`postpone` \| `abandon` \| `bookmark_only` \| `unclear`), `intensity` 1–5, `w2p_stage`, quote + confidence.

Supporting: `wishlist_motive`, `attribute_role`, `off_platform_info`, `unmet_need`, `segment` (always inferred).

Drop-off path: save → (bookmark **or** evaluate → compare → wait → checkout) → not purchased (blocked, OOS/payment/delivery, or bookmark).

## What the UI shows

Next.js, Myntra-adjacent pink `#E11D48` for accents only. Pages: **Why they didn’t buy**, **Barrier detail**, **Evidence explorer**. Footer: last saved; *% of analyzed conversations, not Myntra conversion.*

**Home:** N conversations, unique voices, overall stance mix; donut/bars of primary reasons; ranked cards with big **% didn’t buy**, N/voices, 1-line behavior, stance mix, source mix, often-with. Chips: bookmark vs intent, fit, price wait, OOS, comparison, off-app research, forgotten list.

**Detail:** % + N, stage, intensity, quotes, overlap %, levers, CSV/quotes download.

**Explorer:** searchable coded units (audit).

Illustrative card: **18% didn’t buy — like the look, don’t trust the size (152 / 847 · 119 voices).** Stance postpone 61% / abandon 24% / bookmark 15%.

If YouTube is down: same stored numbers, banner `Showing stored insights. YouTube unreachable.`

## Stack and env

| Piece | Where |
|---|---|
| Dashboard | Vercel, `NEXT_PUBLIC_API_URL` |
| Gather + Gemini + writes | Render FastAPI, secrets stay on Render (`INGEST_TOKEN` gates gather) |
| DB | Neon `DATABASE_URL` (SQLite only for local optional) |
| LLM | Gemini free on Render; Ollama local only |
| Embeddings | MiniLM / sentence-transformers on Render |

Keys: `REDDIT_*`, `YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `DATABASE_URL`, `INGEST_TOKEN`, `CORS_ORIGINS`.

Limits: YouTube/Gemini quotas, Render free sleep, gather minutes, Reddit may block some cloud IPs (fallback: gather from laptop once; UI still reads Neon).

## Non-negotiables

- No upload UX
- Insights always from Neon; live outage does not blank UI
- Never send the same `source_id` / `content_hash` to Gemini twice
- Refresh = new items only
- Show behavior + quotes **and** corpus % / N / stance mix
- Do not claim official Myntra conversion
- Keep Reddit vs app reviews separable; gold-set on coding quality

## Out of scope (v1)

Internal Myntra telemetry, scraping, paid APIs, Play Store, file upload, re-coding stored text, unconstrained LLM web search, Ollama on Render, Streamlit, secrets in Vercel.
