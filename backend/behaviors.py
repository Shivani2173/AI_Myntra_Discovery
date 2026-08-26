"""CPU-only behavior map from stored codes. Never calls Gemini."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.embeddings import cosine, embed_batch
from backend.models import BehaviorRollup, Code, SourceStatus, Unit
from backend.taxonomy import ALLOWED_SEED, FAMILY_LABELS, SEED_BARRIERS

CORPUS_CAPTION = "Of analyzed wishlist conversations, not Myntra live conversion."
HEADER_SLUG = "_header"
OTHER_CLUSTER_THRESHOLD = 0.82
QUOTE_LIMIT = 8
OFTEN_WITH_LIMIT = 5

BARRIER_TITLES: dict[str, str] = {
    "bookmark_inspiration": "Wishlist is a lookbook, not a cart",
    "bookmark_compare_later": "Saved to compare later, not to buy now",
    "gift_or_other_person": "Wishlist is for someone else",
    "low_urgency_maybe": "Low urgency — maybe later",
    "fit_size_uncertainty": "Like the look, don’t trust the size",
    "looks_vs_reality": "Photos don’t match what arrives",
    "styling_wardrobe_fit": "Not sure it works with the wardrobe",
    "occasion_timing": "Waiting for the right occasion",
    "social_validation": "Waiting for social proof before buying",
    "wait_for_price_drop": "Waiting for a “real” discount",
    "better_price_elsewhere": "Saw a better price elsewhere",
    "budget_payday": "Waiting for payday / budget",
    "value_doubt": "Not convinced the price is worth it",
    "return_exchange_friction": "Returns and exchanges feel too hard",
    "review_trust": "Don’t trust the reviews",
    "past_bad_experience": "Past bad experience blocks the buy",
    "counterfeit_or_seller_doubt": "Worried about seller or authenticity",
    "too_many_shortlisted": "Too many items shortlisted",
    "missing_compare_tools": "Can’t compare the shortlist cleanly",
    "switched_to_alternative": "Bought a different product instead",
    "oos_after_wishlist": "Went out of stock after the save",
    "delivery_too_slow": "Delivery would miss the occasion",
    "payment_or_app_friction": "Checkout or app friction",
    "forgotten_wishlist": "Wishlist went stale / forgotten",
    "seeking_external_proof": "Still seeking proof off the app",
}

FAMILY_OF: dict[str, str] = {
    code: family for family, codes in SEED_BARRIERS.items() for code in codes
}

LEVERS_BY_FAMILY: dict[str, list[str]] = {
    "A": [
        "Separate inspiration saves from purchase-intent lists",
        "Prompt “buying for when?” at save time",
        "Don’t treat bookmark-heavy users as failed conversion",
    ],
    "B": [
        "Real-body / similar-body photos on PDP",
        "Size confidence (chart that matches reviews)",
        "Easier reverse pickup so fit risk feels reversible",
    ],
    "C": [
        "Honest discount vs MRP, not token 10% off",
        "Price-drop alerts that feel trustworthy",
        "Payday / budget reminders without spam",
    ],
    "D": [
        "Clearer return windows and reverse pickup",
        "Review authenticity cues",
        "Seller / authenticity badges on fashion",
    ],
    "E": [
        "Shortlist compare (fit, price, delivery side by side)",
        "Cap or cluster an oversized wishlist",
        "Show why this item vs the alternative they mentioned",
    ],
    "F": [
        "Back-in-stock for wishlisted SKU/size",
        "Occasion-aware delivery promise",
        "Checkout / COD friction audit",
    ],
    "G": [
        "Surface haul / fit content on PDP",
        "Friend or community proof without leaving the app",
    ],
    "other": [
        "Investigate this emergent theme with product/UX (stub lever)",
    ],
}

SOURCE_LABELS = {
    "reddit": "Reddit",
    "youtube": "YouTube",
    "app_store": "App Store",
}

PRESET_CHIPS = [
    {"id": "bookmark_inspiration", "label": "Bookmark vs intent"},
    {"id": "fit_size_uncertainty", "label": "Fit & size"},
    {"id": "wait_for_price_drop", "label": "Waiting for price"},
    {"id": "oos_after_wishlist", "label": "Out of stock"},
    {"id": "too_many_shortlisted", "label": "Comparison paralysis"},
    {"id": "seeking_external_proof", "label": "Off-app research"},
    {"id": "forgotten_wishlist", "label": "Forgotten list"},
]


@dataclass
class CodedRow:
    unit: Unit
    code: Code
    payload: dict[str, Any]
    primary: str
    secondaries: list[str]
    stance: str
    intensity: int
    stage: str
    quote: str
    confidence: float
    mechanism: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def humanize_barrier(code: str) -> str:
    if code in BARRIER_TITLES:
        return BARRIER_TITLES[code]
    raw = code[6:] if code.startswith("other_") else code
    words = raw.replace("_", " ").strip()
    if not words:
        return "Other (unnamed)"
    return words[:1].upper() + words[1:]


def family_for(code: str) -> str:
    if code in FAMILY_OF:
        return FAMILY_OF[code]
    return "other"


def levers_for(code: str) -> list[str]:
    return list(LEVERS_BY_FAMILY.get(family_for(code), LEVERS_BY_FAMILY["other"]))


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if x]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def load_coded_rows(session: Session) -> list[CodedRow]:
    rows = session.execute(select(Unit, Code).join(Code, Code.unit_id == Unit.id)).all()
    out: list[CodedRow] = []
    for unit, code in rows:
        payload = code.payload if isinstance(code.payload, dict) else None
        if not payload:
            continue
        if payload.get("relevant") is False:
            continue
        if unit.relevance_status == "irrelevant":
            continue
        primary = str(payload.get("primary_barrier") or "").strip()
        if not primary:
            continue
        try:
            intensity = int(payload.get("intensity") or 3)
        except (TypeError, ValueError):
            intensity = 3
        intensity = min(5, max(1, intensity))
        try:
            confidence = float(payload.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        stance = str(payload.get("outcome_stance") or "unclear")
        stage = str(payload.get("w2p_stage") or "evaluate")
        quote = str(payload.get("quote") or "").strip()
        mechanism = str(payload.get("mechanism") or "").strip()
        out.append(
            CodedRow(
                unit=unit,
                code=code,
                payload=payload,
                primary=primary,
                secondaries=_as_list(payload.get("secondary_barriers")),
                stance=stance,
                intensity=intensity,
                stage=stage,
                quote=quote,
                confidence=confidence,
                mechanism=mechanism,
            )
        )
    return out


def _emergent_stem(primary: str) -> str:
    if not primary.startswith("other_"):
        return primary
    rest = primary[6:]
    first = rest.split("_")[0]
    return f"other_{first}" if first else primary


def _cluster_other(rows: list[CodedRow]) -> dict[int, str]:
    """Map unit.id → behavior id. Seed codes stay as-is; other_* may merge."""
    mapping: dict[int, str] = {}
    others = [r for r in rows if r.primary not in ALLOWED_SEED]
    seeds = [r for r in rows if r.primary in ALLOWED_SEED]
    for r in seeds:
        mapping[r.unit.id] = r.primary
    if not others:
        return mapping

    bags: dict[str, list[CodedRow]] = defaultdict(list)
    for r in others:
        bags[_emergent_stem(r.primary)].append(r)

    settings = get_settings()
    stems = list(bags.keys())
    texts = [
        " ".join(f"{r.primary} {r.mechanism} {r.quote}" for r in bags[stem])
        for stem in stems
    ]
    vectors = embed_batch(texts, model_name="all-MiniLM-L6-v2", use_minilm=settings.use_minilm)

    parent = {stem: stem for stem in stems}
    for i, stem_i in enumerate(stems):
        for j, stem_j in enumerate(stems):
            if j <= i:
                continue
            if cosine(vectors[i], vectors[j]) >= OTHER_CLUSTER_THRESHOLD:
                root_i, root_j = parent[stem_i], parent[stem_j]
                keep, drop = (root_i, root_j) if root_i <= root_j else (root_j, root_i)
                for stem in stems:
                    if parent[stem] == drop:
                        parent[stem] = keep

    merged: dict[str, list[CodedRow]] = defaultdict(list)
    for stem, group in bags.items():
        merged[parent[stem]].extend(group)

    for stem, group in merged.items():
        slugs = [_emergent_stem(r.primary) for r in group]
        canonical = Counter(slugs).most_common(1)[0][0]
        for r in group:
            mapping[r.unit.id] = canonical
    return mapping


def _source_key(source: str) -> str:
    return source if source in SOURCE_LABELS else source


def _pick_quotes(group: list[CodedRow]) -> list[dict[str, Any]]:
    ranked = sorted(group, key=lambda r: (-r.confidence, -r.intensity, r.unit.id))
    seen: set[str] = set()
    quotes: list[dict[str, Any]] = []
    for r in ranked:
        text = r.quote or (r.unit.text or "")[:180]
        key = text.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        quotes.append(
            {
                "text": text[:500],
                "unit_id": r.unit.id,
                "source": r.unit.source,
                "url": r.unit.url,
                "confidence": round(r.confidence, 3),
            }
        )
        if len(quotes) >= QUOTE_LIMIT:
            break
    return quotes


def _mode(values: list[str], fallback: str) -> str:
    if not values:
        return fallback
    return Counter(values).most_common(1)[0][0]


def _card_for(
    behavior_id: str,
    group: list[CodedRow],
    analyzed: int,
    include_quotes: bool,
) -> dict[str, Any]:
    n = len(group)
    voices = {r.unit.author_hash or f"{r.unit.source}:{r.unit.source_id}" for r in group}
    stance = Counter(r.stance for r in group)
    sources = Counter(_source_key(r.unit.source) for r in group)
    intensity = round(sum(r.intensity for r in group) / n, 1) if n else 0.0
    co: Counter[str] = Counter()
    for r in group:
        for s in r.secondaries:
            if s and s != behavior_id:
                co[s] += 1
    often = [
        {
            "id": slug,
            "title": humanize_barrier(slug),
            "overlap_pct": pct(count, n),
        }
        for slug, count in co.most_common(OFTEN_WITH_LIMIT)
    ]
    mechanisms = [r.mechanism for r in group if r.mechanism]
    card: dict[str, Any] = {
        "id": behavior_id,
        "title": humanize_barrier(behavior_id),
        "family": family_for(behavior_id),
        "family_label": FAMILY_LABELS.get(family_for(behavior_id), "Emergent / uncategorized"),
        "emergent": behavior_id not in ALLOWED_SEED,
        "didnt_buy_pct": pct(n, analyzed),
        "n": n,
        "voices": len(voices),
        "mechanism": _mode(mechanisms, humanize_barrier(behavior_id)),
        "intensity": intensity,
        "w2p_stage": _mode([r.stage for r in group], "evaluate"),
        "stance_mix": {
            "postpone": pct(stance.get("postpone", 0), n),
            "abandon": pct(stance.get("abandon", 0), n),
            "bookmark_only": pct(stance.get("bookmark_only", 0), n),
            "unclear": pct(stance.get("unclear", 0), n),
        },
        "source_mix": {k: pct(v, n) for k, v in sorted(sources.items())},
        "often_with": often,
        "caption": CORPUS_CAPTION,
    }
    if include_quotes:
        card["quotes"] = _pick_quotes(group)
        card["levers"] = levers_for(behavior_id)
        card["unit_ids"] = [r.unit.id for r in group]
    return card


def source_status_payload(session: Session) -> list[dict[str, Any]]:
    statuses = session.scalars(select(SourceStatus)).all()
    return [
        {
            "source": s.source,
            "status": s.status,
            "message": s.message,
            "checked_at": s.checked_at.isoformat() if s.checked_at else None,
        }
        for s in statuses
    ]


def compute_behavior_map(session: Session, *, include_quotes: bool = False) -> dict[str, Any]:
    rows = load_coded_rows(session)
    analyzed = len(rows)
    voices = {r.unit.author_hash or f"{r.unit.source}:{r.unit.source_id}" for r in rows}
    overall_stance = Counter(r.stance for r in rows)
    last_coded = max((r.code.coded_at for r in rows if r.code.coded_at), default=None)
    computed_at = _now().isoformat()

    header = {
        "analyzed": analyzed,
        "voices": len(voices),
        "stance_mix": {
            "postpone": pct(overall_stance.get("postpone", 0), analyzed),
            "abandon": pct(overall_stance.get("abandon", 0), analyzed),
            "bookmark_only": pct(overall_stance.get("bookmark_only", 0), analyzed),
            "unclear": pct(overall_stance.get("unclear", 0), analyzed),
        },
        "source_status": source_status_payload(session),
        "last_coded_at": last_coded.isoformat() if last_coded else None,
        "computed_at": computed_at,
        "caption": CORPUS_CAPTION,
        "chips": PRESET_CHIPS,
    }

    if analyzed == 0:
        return {
            "caption": CORPUS_CAPTION,
            "from_cache": False,
            "header": header,
            "behaviors": [],
            "primary_share_sum": 0.0,
        }

    group_of = _cluster_other(rows)
    grouped: dict[str, list[CodedRow]] = defaultdict(list)
    for r in rows:
        grouped[group_of[r.unit.id]].append(r)

    behaviors = [
        _card_for(bid, group, analyzed, include_quotes=include_quotes)
        for bid, group in grouped.items()
    ]
    behaviors.sort(key=lambda b: (-b["didnt_buy_pct"], -b["intensity"], b["id"]))
    share_sum = round(sum(b["didnt_buy_pct"] for b in behaviors), 1)
    return {
        "caption": CORPUS_CAPTION,
        "from_cache": False,
        "header": header,
        "behaviors": behaviors,
        "primary_share_sum": share_sum,
    }


def persist_rollups(session: Session, payload: dict[str, Any]) -> None:
    session.execute(delete(BehaviorRollup))
    header = dict(payload.get("header") or {})
    header["caption"] = payload.get("caption", CORPUS_CAPTION)
    header["primary_share_sum"] = payload.get("primary_share_sum", 0.0)
    session.add(
        BehaviorRollup(
            slug=HEADER_SLUG,
            title="header",
            primary_share=0.0,
            payload=header,
            computed_at=_now(),
        )
    )
    for card in payload.get("behaviors") or []:
        full = dict(card)
        session.add(
            BehaviorRollup(
                slug=str(card["id"]),
                title=str(card.get("title") or card["id"]),
                primary_share=float(card.get("didnt_buy_pct") or 0.0),
                payload=full,
                computed_at=_now(),
            )
        )
    session.commit()


def load_cached_map(session: Session) -> dict[str, Any] | None:
    rows = session.scalars(select(BehaviorRollup)).all()
    if not rows:
        return None
    header_row = next((r for r in rows if r.slug == HEADER_SLUG), None)
    behaviors = [dict(r.payload) for r in rows if r.slug != HEADER_SLUG and isinstance(r.payload, dict)]
    behaviors.sort(key=lambda b: (-float(b.get("didnt_buy_pct") or 0), -float(b.get("intensity") or 0), b.get("id") or ""))
    header = dict(header_row.payload) if header_row and isinstance(header_row.payload, dict) else {}
    return {
        "caption": header.get("caption", CORPUS_CAPTION),
        "from_cache": True,
        "header": header,
        "behaviors": behaviors,
        "primary_share_sum": float(header.get("primary_share_sum") or sum(float(b.get("didnt_buy_pct") or 0) for b in behaviors)),
    }


def rebuild_and_persist(session: Session) -> dict[str, Any]:
    payload = compute_behavior_map(session, include_quotes=True)
    persist_rollups(session, payload)
    payload["from_cache"] = False
    return payload


def behaviors_list_response(session: Session) -> dict[str, Any]:
    live = compute_behavior_map(session, include_quotes=False)
    if live["header"]["analyzed"] > 0:
        return live
    cached = load_cached_map(session)
    if cached and cached.get("behaviors"):
        return cached
    return live


def behavior_detail_response(session: Session, behavior_id: str) -> dict[str, Any] | None:
    live = compute_behavior_map(session, include_quotes=True)
    cards = live.get("behaviors") or []
    if live["header"]["analyzed"] == 0:
        cached = load_cached_map(session)
        if cached:
            live = cached
            cards = live.get("behaviors") or []
    for card in cards:
        if card.get("id") == behavior_id:
            detail = dict(card)
            if "quotes" not in detail:
                # Cached list cards may omit quotes; recompute live with quotes if possible.
                live_full = compute_behavior_map(session, include_quotes=True)
                for c in live_full.get("behaviors") or []:
                    if c.get("id") == behavior_id:
                        detail = c
                        live = live_full
                        break
                else:
                    detail["quotes"] = []
                    detail["levers"] = levers_for(behavior_id)
            detail["header"] = live["header"]
            detail["caption"] = live.get("caption", CORPUS_CAPTION)
            return detail
    return None


def units_list_response(
    session: Session,
    *,
    q: str | None = None,
    source: str | None = None,
    stance: str | None = None,
    barrier: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    rows = load_coded_rows(session)
    group_of = _cluster_other(rows) if rows else {}
    needle = (q or "").strip().lower()
    items: list[dict[str, Any]] = []
    for r in rows:
        bid = group_of.get(r.unit.id, r.primary)
        if source and r.unit.source != source:
            continue
        if stance and r.stance != stance:
            continue
        if barrier and bid != barrier and r.primary != barrier:
            continue
        blob = " ".join(
            [
                r.unit.text or "",
                r.quote,
                r.primary,
                r.mechanism,
            ]
        ).lower()
        if needle and needle not in blob:
            continue
        items.append(
            {
                "id": r.unit.id,
                "source": r.unit.source,
                "source_id": r.unit.source_id,
                "url": r.unit.url,
                "created_at": r.unit.created_at.isoformat() if r.unit.created_at else None,
                "snippet": (r.quote or (r.unit.text or ""))[:240],
                "primary_barrier": r.primary,
                "behavior_id": bid,
                "behavior_title": humanize_barrier(bid),
                "outcome_stance": r.stance,
                "intensity": r.intensity,
                "w2p_stage": r.stage,
                "confidence": round(r.confidence, 3),
            }
        )
    total = len(items)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    page = items[offset : offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "caption": CORPUS_CAPTION,
        "units": page,
    }


def unit_detail_response(session: Session, unit_id: int) -> dict[str, Any] | None:
    unit = session.get(Unit, unit_id)
    if unit is None:
        return None
    code = session.scalar(select(Code).where(Code.unit_id == unit.id))
    payload = code.payload if code and isinstance(code.payload, dict) else None
    return {
        "id": unit.id,
        "source": unit.source,
        "source_id": unit.source_id,
        "url": unit.url,
        "created_at": unit.created_at.isoformat() if unit.created_at else None,
        "last_seen_at": unit.last_seen_at.isoformat() if unit.last_seen_at else None,
        "text": unit.text,
        "parent_context": unit.parent_context,
        "relevance_status": unit.relevance_status,
        "extract_error": unit.extract_error,
        "content_hash": unit.content_hash,
        "coded_at": code.coded_at.isoformat() if code and code.coded_at else None,
        "code": payload,
        "caption": CORPUS_CAPTION,
    }
