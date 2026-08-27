"""Cheap keyword relevance filter — runs on unfiltered units only, not Gemini."""

from __future__ import annotations

import re

from backend.models import Unit

# Specific enough to the "wishlisted it, then didn't buy" behavior to stand on their own.
_STRONG_TERMS = (
    "wishlist",
    "wish list",
    "wishlisted",
    "wish-list",
    "wish-listed",
    "wish-lists",
    "shortlist",
    "shortlisted",
    "save for later",
    "saved it",
    "added to bag",
    "add to bag",
    "should i buy",
    "should i get",
    "waiting for sale",
    "price drop",
    "size chart",
    "size issue",
    "doesn't fit",
    "doesnt fit",
    "too small",
    "too big",
    "out of stock",
    "oos",
    "fake review",
    "better price",
    "not worth",
    "try and buy",
    "try then return",
    "haul",
)

# Common enough in plain positive reviews (e.g. "easy returns", "love this app") that they
# need a friction/hesitation cue nearby to count as signal instead of noise.
_WEAK_TERMS = (
    "cart",
    "return",
    "exchange",
    "myntra",
    "ajio",
    "nykaa",
    "delivery",
    "checkout",
    "cod",
    "coupon",
    "compare",
)

_FRICTION_CUES = (
    "issue",
    "problem",
    "hard",
    "difficult",
    "slow",
    "late",
    "delay",
    "damaged",
    "wrong size",
    "poor",
    "bad",
    "worst",
    "fake",
    "refund",
    "denied",
    "rejected",
    "stuck",
    "confus",
    "unsure",
    "doubt",
    "hesitant",
    "still deciding",
    "not sure",
    "disappoint",
    "hassle",
    "frustrat",
    "cancel",
    "fail",
    "wait",
    "didn't buy",
    "didnt buy",
    "not buying",
    "expensive",
    "overpriced",
)

_STRONG_PATTERN = re.compile("|".join(re.escape(t) for t in _STRONG_TERMS), re.IGNORECASE)
_WEAK_PATTERN = re.compile("|".join(re.escape(t) for t in _WEAK_TERMS), re.IGNORECASE)
_FRICTION_PATTERN = re.compile("|".join(re.escape(t) for t in _FRICTION_CUES), re.IGNORECASE)


def is_relevant(text: str) -> bool:
    if not text or len(text.strip()) < 20:
        return False
    if _STRONG_PATTERN.search(text):
        return True
    return bool(_WEAK_PATTERN.search(text) and _FRICTION_PATTERN.search(text))


def needs_relevance_pass(unit: Unit) -> bool:
    return not unit.relevance_status
