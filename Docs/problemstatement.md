# Problem statement

Source: [ai_discovery_engine_4d13c1f6.plan.md](ai_discovery_engine_4d13c1f6.plan.md)

## One-line problem

**We cannot yet explain, as distinct behaviors with corpus numbers, why fashion products added to a wishlist are not purchased — and we cannot do that on free APIs, without uploads, if sources go offline, or without wasting tokens on the same text twice.**

## Primary question

**Why do users add fashion products to a wishlist and then not buy them? What distinct reasons and barriers explain that drop-off?**

This is about **wishlist → not purchased**, not general review summarization or sentiment.

The engine must:

- Separate **bookmarking** from **failed purchase intent**
- Separate **postpone** from **abandon**
- Describe **behaviors** (what people do and why) **and** show **numbers** (share of analyzed conversations, unique voices, stance mix)
- Surface **emergent** reasons a seed list did not anticipate

## Why it matters

Wishlist-to-purchase conversion is the business metric. A save is not an order. Teams can see the leak in internal metrics; they cannot see **which behaviors** cause it: inspiration bookmark, price-watch, size distrust after the product is already chosen, OOS after save, comparison paralysis, off-app research, forgotten list.

Without a discovery system:

- Sentiment and review summaries are treated as insight
- “% of angry posts” is mistaken for “% of users not converting”
- Opportunity areas cannot be compared against wishlist-to-purchase

## Why a naive approach fails

| Naive approach | Why it fails |
|---|---|
| Sentiment on reviews | Does not split bookmark vs intent, postpone vs abandon, or residual uncertainty after product choice |
| Manual CSV / screenshot upload | Not repeatable; user explicitly does not want uploads |
| LLM “search the web” | Not the same as official Reddit / YouTube / App Store APIs; unbounded and not store-first |
| Live-only pipeline | If Reddit, YouTube, or Gemini is down, the product goes blank |
| Re-code every gather | Same comments burn Gemini tokens again |
| “18% of Myntra users didn’t buy” | Public text is not live W2P; only **% of analyzed wishlist conversations** is honest |

## Problem constraints (from the plan)

1. **Free official APIs only** — Reddit OAuth, YouTube Data API v3, Apple App Store RSS. No scrapers, SerpAPI, DataForSEO, or Play Store (no free official third-party review API).
2. **No file upload** — gather is automatic from a built-in query list.
3. **Store-first** — fetch → save raw text → code new rows only → UI always reads Neon. APIs down must not blank the dashboard.
4. **Code once** — unique `(source, source_id)` and `content_hash`; Gemini only when `coded_at IS NULL`.
5. **Numbers with an honest denominator** — “18% didn’t buy because of size” means 18% of **coded wishlist conversations** whose `primary_barrier` is size, plus N and unique voices — not Myntra’s live conversion rate.

## Barrier space the problem must cover

Reasons users don’t buy from wishlist (seed taxonomy; not mutually exclusive):

- **A. Not real intent** — inspiration bookmark, compare-later parking lot, gift for someone else, low urgency
- **B. Uncertainty after the product is identified** — fit/size, looks vs reality, styling/wardrobe, occasion, social validation
- **C. Economic / value** — wait for sale, better price elsewhere, payday, value vs MRP
- **D. Risk / reversal** — returns hassle, review trust, past bad order, seller doubt
- **E. Choice friction** — too many shortlisted, no compare tools, switched to another product
- **F. Operational** — OOS after wishlist, slow delivery, payment/app friction, forgotten list
- **G. Off-platform proof still missing** — YouTube / Reddit / Instagram / friends before converting the save

Each conversation also needs a **primary barrier** (for % didn’t buy, summing to ~100%), secondary barriers, stance (postpone / abandon / bookmark / unclear), intensity, and stage (`save → evaluate → compare → wait → checkout-fail`).

## What “solved” looks like

A Next.js UI on **Vercel**, FastAPI on **Render**, data in **Neon**, that after automatic gather shows:

- Header: N conversations, unique voices, overall bookmark / postpone / abandon mix
- Donut or bars of **primary reasons** totaling ~100% of the analyzed set
- Ranked **behavior cards**: big **% didn’t buy**, N / voices, what they do, stance mix, source mix, often-with
- Detail: quotes, overlap %, possible levers
- Explorer: audit trail of coded units
- If YouTube (or another source) is down: same stored cards, banner that insights are from last save

Illustrative headline (format, not live data): **18% didn’t buy — like the look, don’t trust the size (152 / 847 conversations).** Caption: of analyzed wishlist conversations, not Myntra live conversion.

## Out of scope (v1)

Internal Myntra telemetry, scraping, paid APIs, Play Store, file upload, re-coding stored text, unconstrained LLM web search, Ollama on Render. Corpus % is in scope; claiming it is official Myntra W2P is not.

## Bias (part of the problem, not a footnote)

Public chatter over-represents loud, English, complaint-heavy users. The product must show % of **this dataset**, keep Reddit vs app reviews separable, and never present the numbers as a Myntra user panel.
