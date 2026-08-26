"""Seed barrier taxonomy (families A–G) and the persisted Gemini JSON schema."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SEED_BARRIERS: dict[str, tuple[str, ...]] = {
    "A": (
        "bookmark_inspiration",
        "bookmark_compare_later",
        "gift_or_other_person",
        "low_urgency_maybe",
    ),
    "B": (
        "fit_size_uncertainty",
        "looks_vs_reality",
        "styling_wardrobe_fit",
        "occasion_timing",
        "social_validation",
    ),
    "C": (
        "wait_for_price_drop",
        "better_price_elsewhere",
        "budget_payday",
        "value_doubt",
    ),
    "D": (
        "return_exchange_friction",
        "review_trust",
        "past_bad_experience",
        "counterfeit_or_seller_doubt",
    ),
    "E": (
        "too_many_shortlisted",
        "missing_compare_tools",
        "switched_to_alternative",
    ),
    "F": (
        "oos_after_wishlist",
        "delivery_too_slow",
        "payment_or_app_friction",
        "forgotten_wishlist",
    ),
    "G": ("seeking_external_proof",),
}

FAMILY_LABELS = {
    "A": "Wishlist was not real purchase intent",
    "B": "Uncertainty after the product is already identified",
    "C": "Economic and value barriers",
    "D": "Risk, trust, and reversal cost",
    "E": "Choice and comparison friction",
    "F": "Operational / product availability",
    "G": "Off-platform information still missing",
}

ALLOWED_SEED = tuple(code for codes in SEED_BARRIERS.values() for code in codes)


class OutcomeStance(str, Enum):
    postpone = "postpone"
    abandon = "abandon"
    bookmark_only = "bookmark_only"
    unclear = "unclear"


W2PStage = Literal["save", "evaluate", "compare", "wait", "checkout-fail"]


class SupportingCodes(BaseModel):
    wishlist_motive: str | None = Field(
        default=None,
        description="intent vs bookmark vs price-watch",
    )
    attribute_role: str | None = Field(
        default=None,
        description="fit, size, styling, price, reviews, occasion, social proof",
    )
    off_platform_info: str | None = Field(
        default=None,
        description="what they still seek outside the app before converting",
    )
    unmet_need: str | None = Field(
        default=None,
        description="repeated ask with no adequate PDP/UX answer",
    )
    segment: str | None = Field(
        default=None,
        description="inferred category / price tier / occasion; always treated as inferred",
    )


class ExtractedCode(BaseModel):
    """JSON persisted on codes.payload. Never rewritten after insert."""

    relevant: bool = True
    primary_barrier: str
    secondary_barriers: list[str] = Field(default_factory=list)
    outcome_stance: OutcomeStance
    intensity: int = Field(ge=1, le=5)
    w2p_stage: W2PStage
    quote: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    mechanism: str = Field(
        min_length=1,
        max_length=240,
        description="one line: what the person does and why they don't buy",
    )
    supporting: SupportingCodes = Field(default_factory=SupportingCodes)

    @field_validator("primary_barrier")
    @classmethod
    def _primary_ok(cls, value: str) -> str:
        return _normalize_barrier(value, required=True)

    @field_validator("secondary_barriers")
    @classmethod
    def _secondaries_ok(cls, values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in values:
            code = _normalize_barrier(raw, required=False)
            if code and code not in seen:
                seen.add(code)
                out.append(code)
        return out


def _normalize_barrier(value: str, *, required: bool) -> str:
    code = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not code:
        if required:
            raise ValueError("primary_barrier is required")
        return ""
    if code in ALLOWED_SEED:
        return code
    if code.startswith("other_") and len(code) > 6 and code.replace("_", "").isalnum():
        return code
    if required:
        raise ValueError(f"unknown primary_barrier: {value}")
    return f"other_{code}" if not code.startswith("other_") else code


def taxonomy_prompt_block() -> str:
    lines = ["Seed barrier codes (not mutually exclusive; you may add other_* labels):"]
    for family, codes in SEED_BARRIERS.items():
        lines.append(f"{family}. {FAMILY_LABELS[family]}: {', '.join(codes)}")
    lines.append(
        "Also set: primary_barrier (one main reason), secondary_barriers, "
        "outcome_stance (postpone|abandon|bookmark_only|unclear), intensity 1-5, "
        "w2p_stage (save|evaluate|compare|wait|checkout-fail), quote from the text, "
        "confidence 0-1, mechanism (one sentence), supporting codes."
    )
    return "\n".join(lines)
