import json
import logging
import threading
import traceback
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth import require_ingest_token
from backend.behaviors import (
    behavior_detail_response,
    behaviors_list_response,
    unit_detail_response,
    units_list_response,
)
from backend.config import get_settings
from backend.csv_seed import run_import_csv
from backend.db import get_db, init_db, ping_db, session_scope
from backend.extract import run_extract
from backend.gather import create_job, execute_extract_job, execute_job
from backend.models import Code, GatherJob, SourceStatus, Unit
from backend.store import save_status

log = logging.getLogger(__name__)


def _seed_default_data() -> None:
    """Import the bundled curated CSV and code it, in the background, on every boot.

    Runs off the ASGI event loop so it never delays startup or /health. Safe to
    run every boot: upsert_envelope dedupes on (source, source_id).
    """
    db = session_scope()
    try:
        result = run_import_csv(db)
        run_extract(db)
        save_status(db, "csv_seed", "ok", json.dumps(result)[:500])
        db.commit()
    except Exception as exc:
        db.rollback()
        log.error("csv_seed failed: %s\n%s", exc, traceback.format_exc())
        try:
            save_status(db, "csv_seed", "error", str(exc)[:500])
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    threading.Thread(target=_seed_default_data, daemon=True).start()
    yield


app = FastAPI(title="AI Discovery Engine", version="0.1.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _health_payload() -> dict:
    ping_db()
    return {"status": "ok", "phase": 5}


def _run_job(job_id: str) -> None:
    db = session_scope()
    try:
        execute_job(db, job_id)
    finally:
        db.close()


def _run_extract_job(job_id: str) -> None:
    db = session_scope()
    try:
        execute_extract_job(db, job_id)
    finally:
        db.close()


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(_health_payload())


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    payload = _health_payload()
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Discovery engine API</title></head>
<body style="font-family:sans-serif;padding:2rem">
  <h1>API is running</h1>
  <p>Phase 5 health check:</p>
  <pre style="font-size:1.25rem">{json.dumps(payload)}</pre>
  <p>JSON: <a href="/health">/health</a> · Docs: <a href="/docs">/docs</a></p>
  <p>Reads: <a href="/behaviors">/behaviors</a> · <a href="/units">/units</a> · <a href="/units/stats">/units/stats</a></p>
  <p>Gather (needs X-Ingest-Token): POST /jobs/gather · extract: POST /jobs/extract</p>
</body>
</html>"""


@app.post("/jobs/gather", dependencies=[Depends(require_ingest_token)])
def start_gather(background: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    job = create_job(db)
    background.add_task(_run_job, job.id)
    return {"job_id": job.id, "status": job.status}


@app.post("/jobs/extract", dependencies=[Depends(require_ingest_token)])
def start_extract(background: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    job = create_job(db)
    background.add_task(_run_extract_job, job.id)
    return {"job_id": job.id, "status": job.status}


@app.get("/jobs/{job_id}", dependencies=[Depends(require_ingest_token)])
def job_status(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(GatherJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "result": job.result,
        "error": job.error,
    }


def _stats_payload(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(Unit)) or 0
    codes = db.scalar(select(func.count()).select_from(Code)) or 0
    by_source = db.execute(select(Unit.source, func.count()).group_by(Unit.source)).all()
    statuses = db.scalars(select(SourceStatus)).all()
    return {
        "units_total": int(total),
        "codes_total": int(codes),
        "by_source": {row[0]: int(row[1]) for row in by_source},
        "source_status": [
            {"source": s.source, "status": s.status, "message": s.message} for s in statuses
        ],
    }


@app.get("/behaviors")
def list_behaviors(db: Session = Depends(get_db)) -> dict:
    return behaviors_list_response(db)


@app.get("/behaviors/{behavior_id}")
def behavior_detail(behavior_id: str, db: Session = Depends(get_db)) -> dict:
    detail = behavior_detail_response(db, behavior_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="behavior not found")
    return detail


@app.get("/units")
def list_units(
    q: str | None = None,
    source: str | None = None,
    stance: str | None = None,
    barrier: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    return units_list_response(
        db,
        q=q,
        source=source,
        stance=stance,
        barrier=barrier,
        limit=limit,
        offset=offset,
    )


@app.get("/units/stats.json")
def unit_stats_json(db: Session = Depends(get_db)) -> dict:
    return _stats_payload(db)


@app.get("/units/stats", response_class=HTMLResponse)
def unit_stats_page(db: Session = Depends(get_db)) -> str:
    data = _stats_payload(db)
    rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in data["by_source"].items()
    ) or "<tr><td colspan='2'>No units yet. Run: python -m backend.cli gather</td></tr>"
    status_rows = "".join(
        f"<tr><td>{s['source']}</td><td>{s['status']}</td><td>{s['message'] or ''}</td></tr>"
        for s in data["source_status"]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Gather stats</title></head>
<body style="font-family:sans-serif;padding:2rem">
  <h1>Stored conversations</h1>
  <p style="font-size:1.5rem"><strong>{data['units_total']}</strong> units · <strong>{data['codes_total']}</strong> codes</p>
  <h2>By source</h2>
  <table border="1" cellpadding="8" cellspacing="0">
    <tr><th>Source</th><th>Count</th></tr>
    {rows}
  </table>
  <h2>Last gather status</h2>
  <table border="1" cellpadding="8" cellspacing="0">
    <tr><th>Source</th><th>Status</th><th>Message</th></tr>
    {status_rows}
  </table>
  <p>JSON: <a href="/units/stats.json">/units/stats.json</a> · <a href="/">Home</a></p>
</body>
</html>"""


@app.get("/units/{unit_id}")
def unit_detail(unit_id: int, db: Session = Depends(get_db)) -> dict:
    detail = unit_detail_response(db, unit_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="unit not found")
    return detail
