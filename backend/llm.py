"""Gemini Flash, or Ollama on a laptop when no Gemini key is set."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Protocol

import httpx

from backend.config import Settings
from backend.taxonomy import ExtractedCode, taxonomy_prompt_block

log = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


class LlmError(Exception):
    pass


class ExtractClient(Protocol):
    name: str

    def complete(self, unit_text: str, parent_context: dict | None) -> str:
        """Return raw model text that should contain JSON."""


def _strip_json(raw: str) -> str:
    text = (raw or "").strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def parse_extracted(raw: str) -> ExtractedCode:
    payload = json.loads(_strip_json(raw))
    if not isinstance(payload, dict):
        raise ValueError("model output is not a JSON object")
    return ExtractedCode.model_validate(payload)


def build_prompt(unit_text: str, parent_context: dict | None) -> str:
    ctx = ""
    if parent_context:
        ctx = "\nParent/thread context (JSON): " + json.dumps(parent_context, default=str)[:800]
    return (
        "You label public fashion-shopping conversations about why people add items "
        "to a wishlist (or shortlist) and then do not buy.\n\n"
        f"{taxonomy_prompt_block()}\n\n"
        "If the text is not about fashion shopping, wishlists, fit, price, returns, "
        "or buying clothes/apps like Myntra/AJIO, set relevant=false and still fill "
        "the other fields with your best guess (primary_barrier may be other_offtopic).\n"
        "If the text IS about fashion shopping but states no reason for delaying, "
        "avoiding, or not completing a purchase — e.g. a plain positive review with no "
        "hesitation, friction, or unmet need — also set relevant=false and use "
        "primary_barrier=other_no_barrier. Do not invent a barrier that isn't there.\n"
        "quote must be a short span copied from the user text.\n"
        "Respond with a single JSON object only, keys: relevant, primary_barrier, "
        "secondary_barriers, outcome_stance, intensity, w2p_stage, quote, confidence, "
        "mechanism, supporting (object with wishlist_motive, attribute_role, "
        "off_platform_info, unmet_need, segment).\n\n"
        f"Conversation text:\n{unit_text[:4000]}{ctx}"
    )


class GeminiClient:
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, unit_text: str, parent_context: dict | None) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LlmError("google-genai is not installed") from exc
        client = genai.Client(api_key=self.api_key)
        prompt = build_prompt(unit_text, parent_context)
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            raise LlmError(str(exc)[:500]) from exc
        text = getattr(response, "text", None)
        if not text:
            raise LlmError("Gemini returned empty text")
        return text


class GroqClient:
    name = "groq"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, unit_text: str, parent_context: dict | None) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": build_prompt(unit_text, parent_context)}],
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise LlmError(str(exc)[:500]) from exc
        choices = data.get("choices") or []
        if not choices:
            raise LlmError("Groq returned no choices")
        return (choices[0].get("message") or {}).get("content") or ""


class FallbackClient:
    """Try `primary`; on any LlmError from it, retry the same call on `secondary`.

    Different vendors have independent rate limits, so a quota hit on one
    doesn't have to stall a run — it just shifts that call to the other.
    """

    def __init__(self, primary: ExtractClient, secondary: ExtractClient) -> None:
        self.primary = primary
        self.secondary = secondary
        self.name = f"{primary.name}+{secondary.name}"

    def complete(self, unit_text: str, parent_context: dict | None) -> str:
        try:
            return self.primary.complete(unit_text, parent_context)
        except LlmError as exc:
            log.warning("%s failed, falling back to %s: %s", self.primary.name, self.secondary.name, exc)
            return self.secondary.complete(unit_text, parent_context)


class OllamaClient:
    name = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, unit_text: str, parent_context: dict | None) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "user",
                    "content": build_prompt(unit_text, parent_context),
                }
            ],
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                res = client.post(f"{self.base_url}/api/chat", json=payload)
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise LlmError(f"Ollama request failed: {exc}") from exc
        return (data.get("message") or {}).get("content") or ""


class StubClient:
    """Deterministic coder for tests / EXTRACT_STUB=1. Not used in production."""

    name = "stub"

    def __init__(self, raw_override: str | None = None) -> None:
        self.raw_override = raw_override
        self.calls = 0

    def complete(self, unit_text: str, parent_context: dict | None) -> str:
        self.calls += 1
        if self.raw_override is not None:
            return self.raw_override
        text = (unit_text or "").lower()
        primary = "fit_size_uncertainty"
        stance = "postpone"
        stage = "evaluate"
        if "sale" in text or "price" in text or "coupon" in text:
            primary = "wait_for_price_drop"
            stance = "postpone"
            stage = "wait"
        elif "inspiration" in text or "mood board" in text:
            primary = "bookmark_inspiration"
            stance = "bookmark_only"
            stage = "save"
        elif "stock" in text or "oos" in text:
            primary = "oos_after_wishlist"
            stance = "abandon"
            stage = "checkout-fail"
        snippet = (unit_text or "wishlist")[:180]
        return json.dumps(
            {
                "relevant": True,
                "primary_barrier": primary,
                "secondary_barriers": [],
                "outcome_stance": stance,
                "intensity": 3,
                "w2p_stage": stage,
                "quote": snippet,
                "confidence": 0.7,
                "mechanism": f"stub: {primary}",
                "supporting": {
                    "wishlist_motive": "inferred from keywords",
                    "attribute_role": None,
                    "off_platform_info": None,
                    "unmet_need": None,
                    "segment": "inferred unknown",
                },
            }
        )


def ollama_allowed() -> bool:
    return not os.environ.get("RENDER")


def _ollama_reachable(base_url: str) -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            res = client.get(f"{base_url.rstrip('/')}/api/tags")
            return res.status_code < 500
    except Exception:
        return False


def resolve_client(settings: Settings, override: ExtractClient | None = None) -> ExtractClient | None:
    if override is not None:
        return override
    if settings.extract_stub:
        return StubClient()
    gemini_key = (settings.gemini_api_key or "").strip()
    groq_key = (settings.groq_api_key or "").strip()
    if gemini_key and groq_key:
        return FallbackClient(
            GeminiClient(gemini_key, settings.gemini_model),
            GroqClient(groq_key, settings.groq_model),
        )
    if gemini_key:
        return GeminiClient(gemini_key, settings.gemini_model)
    if groq_key:
        return GroqClient(groq_key, settings.groq_model)
    if ollama_allowed() and settings.ollama_base_url and _ollama_reachable(settings.ollama_base_url):
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    return None
