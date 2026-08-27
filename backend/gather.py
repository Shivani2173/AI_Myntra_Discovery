from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.connectors.appstore import AppStoreConnector
from backend.models import GatherJob, SourceWatermark, Unit
from backend.pipeline_config import load_pipeline_config
from backend.extract import run_extract
from backend.store import save_status, save_watermark, upsert_envelope


def _log(msg: str) -> None:
    print(msg, flush=True)


def run_gather(session: Session) -> dict:
    cfg = load_pipeline_config()
    caps = cfg.get("quota_caps") or {}
    app_ids = cfg.get("app_store_rss_ids") or {}

    connectors = [
        AppStoreConnector(app_ids, int(caps.get("app_store_pages_per_app") or 1)),
    ]

    summary: dict = {"inserted": 0, "updated": 0, "sources": {}}

    for connector in connectors:
        name = connector.name
        wm = session.get(SourceWatermark, name)
        cursor = wm.cursor if wm else None
        extra = wm.extra if wm else None
        _log(f"[gather] {name}…")
        try:
            result = connector.fetch(cursor, extra)
            if result.skipped:
                save_status(session, name, "skipped", result.skipped)
                summary["sources"][name] = {"status": "skipped", "message": result.skipped}
                session.commit()
                _log(f"[gather] {name}: skipped ({result.skipped})")
                continue
            inserted = 0
            updated = 0
            for env in result.envelopes:
                action = upsert_envelope(session, env)
                if action == "inserted":
                    inserted += 1
                else:
                    updated += 1
            save_watermark(session, name, result.watermark_cursor, result.watermark_extra)
            save_status(session, name, "ok", f"inserted={inserted} updated={updated}")
            session.commit()
            summary["inserted"] += inserted
            summary["updated"] += updated
            summary["sources"][name] = {"status": "ok", "inserted": inserted, "updated": updated}
            _log(f"[gather] {name}: ok inserted={inserted} updated={updated}")
        except Exception as exc:
            session.rollback()
            save_status(session, name, "error", str(exc)[:500])
            session.commit()
            summary["sources"][name] = {
                "status": "error",
                "message": str(exc)[:500],
                "trace": traceback.format_exc()[-400:],
            }
            _log(f"[gather] {name}: error — {str(exc)[:200]}")

    total = session.scalar(select(func.count()).select_from(Unit)) or 0
    summary["units_total"] = int(total)
    _log(f"[gather] done. units_total={total}")
    return summary


def create_job(session: Session) -> GatherJob:
    job = GatherJob(id=str(uuid.uuid4()), status="queued")
    session.add(job)
    session.commit()
    return job


def execute_job(session: Session, job_id: str) -> None:
    job = session.get(GatherJob, job_id)
    if job is None:
        return
    job.status = "running"
    job.updated_at = datetime.now(timezone.utc)
    session.commit()
    try:
        result = run_gather(session)
        result["extract"] = run_extract(session)
        job = session.get(GatherJob, job_id)
        if job:
            job.status = "done"
            job.result = result
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as exc:
        job = session.get(GatherJob, job_id)
        if job:
            job.status = "error"
            job.error = str(exc)[:1000]
            job.updated_at = datetime.now(timezone.utc)
            session.commit()


def execute_extract_job(session: Session, job_id: str) -> None:
    job = session.get(GatherJob, job_id)
    if job is None:
        return
    job.status = "running"
    job.updated_at = datetime.now(timezone.utc)
    session.commit()
    try:
        result = run_extract(session)
        job = session.get(GatherJob, job_id)
        if job:
            job.status = "done"
            job.result = {"extract": result}
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as exc:
        job = session.get(GatherJob, job_id)
        if job:
            job.status = "error"
            job.error = str(exc)[:1000]
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
