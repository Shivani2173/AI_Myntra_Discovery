"""Code new units once. Never rewrite codes. Skip Gemini on hash / near-dup hits."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pydantic import ValidationError

from backend.behaviors import rebuild_and_persist
from backend.config import get_settings
from backend.embeddings import cosine, embed_one
from backend.llm import ExtractClient, LlmError, parse_extracted, resolve_client
from backend.models import Code, Unit
from backend.pipeline_config import load_pipeline_config
from backend.relevance import is_relevant
from backend.store import save_status

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_cfg() -> dict:
    cfg = load_pipeline_config().get("extract") or {}
    return {
        "max_units": int(cfg.get("max_units_per_run") or 40),
        "retries": int(cfg.get("json_retries") or 2),
        "near_dup": float(cfg.get("near_dup_threshold") or 0.92),
        "minilm_model": str(cfg.get("minilm_model") or "all-MiniLM-L6-v2"),
        "pause_seconds": float(cfg.get("llm_pause_seconds") or 13),
    }


def insert_code_once(session: Session, unit: Unit, payload: dict) -> str:
    existing = session.scalar(select(Code.id).where(Code.unit_id == unit.id))
    if existing is not None:
        return "exists"
    session.add(Code(unit_id=unit.id, payload=payload, coded_at=_now()))
    unit.extract_error = None
    return "inserted"


def _coded_units(session: Session) -> list[tuple[Unit, Code]]:
    rows = session.execute(select(Unit, Code).join(Code, Code.unit_id == Unit.id)).all()
    return [(u, c) for u, c in rows]


def _copy_from_hash(unit: Unit, coded: list[tuple[Unit, Code]]) -> dict | None:
    for other, code in coded:
        if other.id == unit.id:
            continue
        if other.content_hash == unit.content_hash:
            payload = dict(code.payload)
            payload["_meta"] = {
                "origin": "copied",
                "reason": "content_hash",
                "from_unit_id": other.id,
            }
            return payload
    return None


def _copy_from_near_dup(
    unit: Unit,
    coded: list[tuple[Unit, Code]],
    embedding: list[float],
    threshold: float,
) -> dict | None:
    best: tuple[float, Unit, Code] | None = None
    for other, code in coded:
        if other.id == unit.id or not other.embedding:
            continue
        score = cosine(embedding, other.embedding)
        if score >= threshold and (best is None or score > best[0]):
            best = (score, other, code)
    if best is None:
        return None
    score, other, code = best
    payload = dict(code.payload)
    payload["_meta"] = {
        "origin": "copied",
        "reason": "near_dup",
        "from_unit_id": other.id,
        "similarity": round(score, 4),
    }
    return payload


_RETRY_IN = re.compile(r"retry in ([0-9]+(?:\.[0-9]+)?)", re.I)


def _quota_hit(message: str) -> bool:
    lower = message.lower()
    return "429" in message or "quota" in lower or "rate-limit" in lower


def _retry_wait_seconds(message: str, fallback: float = 30.0) -> float:
    match = _RETRY_IN.search(message)
    if match:
        return min(90.0, float(match.group(1)) + 2.0)
    return fallback


def _call_with_retries(client: ExtractClient, unit: Unit, retries: int) -> tuple[dict | None, str | None, int]:
    last_err = None
    attempts = 0
    for attempt in range(retries + 1):
        attempts += 1
        try:
            raw = client.complete(unit.text, unit.parent_context)
            parsed = parse_extracted(raw)
            return parsed.model_dump(mode="json"), None, attempts
        except (LlmError, ValueError, TypeError, ValidationError) as exc:
            last_err = str(exc)[:400]
            log.warning("extract row %s attempt %s failed: %s", unit.id, attempt + 1, last_err)
            if "no longer available" in last_err.lower() or ("404" in last_err and "model" in last_err.lower()):
                break
            if _quota_hit(last_err):
                wait = _retry_wait_seconds(last_err)
                log.warning("Gemini quota hit; waiting %.0fs then retrying once", wait)
                time.sleep(wait)
                break
    if last_err and _quota_hit(last_err):
        attempts += 1
        try:
            raw = client.complete(unit.text, unit.parent_context)
            parsed = parse_extracted(raw)
            return parsed.model_dump(mode="json"), None, attempts
        except (LlmError, ValueError, TypeError, ValidationError) as exc:
            last_err = str(exc)[:400]
            log.warning("extract row %s still failing after wait: %s", unit.id, last_err)
    return None, last_err, attempts


def run_extract(session: Session, client: ExtractClient | None = None) -> dict:
    settings = get_settings()
    cfg = _extract_cfg()
    resolved = resolve_client(settings, client)

    summary: dict = {
        "llm_provider": resolved.name if resolved else None,
        "llm_calls": 0,
        "filtered_irrelevant": 0,
        "filtered_relevant": 0,
        "skipped_already_coded": 0,
        "copied_hash": 0,
        "copied_near_dup": 0,
        "coded": 0,
        "failed_rows": 0,
        "skipped_no_llm": 0,
        "quota_stopped": False,
        "errors": [],
    }

    pending_rel = session.scalars(select(Unit).where(Unit.relevance_status.is_(None))).all()
    for unit in pending_rel:
        if is_relevant(unit.text):
            unit.relevance_status = "relevant"
            summary["filtered_relevant"] += 1
        else:
            unit.relevance_status = "irrelevant"
            summary["filtered_irrelevant"] += 1
    session.commit()

    if resolved is None:
        save_status(
            session,
            "extract",
            "skipped",
            "Set GEMINI_API_KEY in .env (Ollama is not running on this machine)",
        )
        session.commit()
        summary["message"] = (
            "No Gemini key and Ollama is not running. Add GEMINI_API_KEY to .env "
            "from https://aistudio.google.com/apikey then run: python -m backend.cli extract"
        )
        summary["skipped_no_llm"] = int(
            session.scalar(
                select(func.count()).select_from(Unit).where(Unit.relevance_status == "relevant")
            )
            or 0
        )
        rollup = rebuild_and_persist(session)
        summary["behaviors"] = len(rollup.get("behaviors") or [])
        summary["analyzed"] = (rollup.get("header") or {}).get("analyzed", 0)
        return summary

    candidates = session.scalars(
        select(Unit)
        .where(Unit.relevance_status == "relevant")
        .where(Unit.id.not_in(select(Code.unit_id)))
        .order_by(Unit.id)
        .limit(cfg["max_units"])
    ).all()

    coded = _coded_units(session)
    summary["skipped_already_coded"] = int(
        session.scalar(
            select(func.count())
            .select_from(Unit)
            .join(Code, Code.unit_id == Unit.id)
            .where(Unit.relevance_status == "relevant")
        )
        or 0
    )

    for unit in candidates:
        if session.scalar(select(Code.id).where(Code.unit_id == unit.id)):
            continue

        copied = _copy_from_hash(unit, coded)
        if copied:
            insert_code_once(session, unit, copied)
            summary["copied_hash"] += 1
            session.commit()
            coded = _coded_units(session)
            continue

        embedding = embed_one(
            unit.text,
            model_name=cfg["minilm_model"],
            use_minilm=settings.use_minilm,
        )
        unit.embedding = embedding

        copied = _copy_from_near_dup(unit, coded, embedding, cfg["near_dup"])
        if copied:
            insert_code_once(session, unit, copied)
            summary["copied_near_dup"] += 1
            session.commit()
            coded = _coded_units(session)
            continue

        payload, err, attempts = _call_with_retries(resolved, unit, cfg["retries"])
        summary["llm_calls"] += attempts
        if payload is None:
            unit.extract_error = err
            summary["failed_rows"] += 1
            summary["errors"].append({"unit_id": unit.id, "error": err})
            session.commit()
            if err and _quota_hit(err):
                summary["quota_stopped"] = True
                summary["message"] = (
                    "Gemini free-tier limit reached (5 requests / window). "
                    "Wait about 1 minute, then run: python -m backend.cli extract"
                )
                break
            continue

        payload["_meta"] = {"origin": "llm", "provider": resolved.name}
        if payload.get("relevant") is False:
            unit.relevance_status = "irrelevant"
        insert_code_once(session, unit, payload)
        summary["coded"] += 1
        session.commit()
        coded = _coded_units(session)
        if resolved.name == "gemini" and cfg["pause_seconds"] > 0:
            time.sleep(cfg["pause_seconds"])

    save_status(
        session,
        "extract",
        "ok",
        (
            f"llm_calls={summary['llm_calls']} coded={summary['coded']} "
            f"copied_hash={summary['copied_hash']} near_dup={summary['copied_near_dup']} "
            f"failed_rows={summary['failed_rows']}"
        ),
    )
    session.commit()
    rollup = rebuild_and_persist(session)
    summary["behaviors"] = len(rollup.get("behaviors") or [])
    summary["analyzed"] = (rollup.get("header") or {}).get("analyzed", 0)
    return summary
