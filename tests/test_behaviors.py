from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.behaviors import compute_behavior_map, persist_rollups, rebuild_and_persist
from backend.config import get_settings
from backend.db import init_db, reset_engine, session_scope
from backend.main import app
from backend.models import BehaviorRollup, Code, SourceStatus, Unit
from backend.store import content_hash


def _fresh_db(monkeypatch, tmp_path):
    db_path = (tmp_path / "t.db").resolve().as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EXTRACT_STUB", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("USE_MINILM", "false")
    get_settings.cache_clear()
    reset_engine()
    init_db()
    return session_scope()


def _add_coded(
    db,
    source_id: str,
    *,
    primary: str,
    stance: str = "postpone",
    intensity: int = 3,
    source: str = "reddit",
    secondaries: list[str] | None = None,
    quote: str = "wishlist size chart",
    mechanism: str = "stalls on size",
    relevant: bool = True,
    author: str | None = "a1",
    stage: str = "evaluate",
) -> Unit:
    text = f"{quote} {mechanism} {primary}"
    unit = Unit(
        source=source,
        source_id=source_id,
        content_hash=content_hash(text + source_id),
        text=text,
        author_hash=author,
        relevance_status="relevant" if relevant else "irrelevant",
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    db.add(
        Code(
            unit_id=unit.id,
            payload={
                "relevant": relevant,
                "primary_barrier": primary,
                "secondary_barriers": secondaries or [],
                "outcome_stance": stance,
                "intensity": intensity,
                "w2p_stage": stage,
                "quote": quote,
                "confidence": 0.8,
                "mechanism": mechanism,
                "supporting": {},
            },
            coded_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return unit


def test_primary_shares_sum_to_about_100(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        _add_coded(db, "1", primary="fit_size_uncertainty", intensity=4, secondaries=["looks_vs_reality"])
        _add_coded(db, "2", primary="fit_size_uncertainty", intensity=5, author="a2")
        _add_coded(db, "3", primary="wait_for_price_drop", stance="postpone", intensity=3, author="a3")
        _add_coded(db, "4", primary="bookmark_inspiration", stance="bookmark_only", intensity=2, author="a4")
        result = compute_behavior_map(db)
        assert result["header"]["analyzed"] == 4
        assert abs(result["primary_share_sum"] - 100.0) < 0.2
        shares = {b["id"]: b["didnt_buy_pct"] for b in result["behaviors"]}
        assert shares["fit_size_uncertainty"] == 50.0
        assert shares["wait_for_price_drop"] == 25.0
        assert shares["bookmark_inspiration"] == 25.0
        assert result["behaviors"][0]["id"] == "fit_size_uncertainty"
        often = result["behaviors"][0]["often_with"]
        assert often and often[0]["id"] == "looks_vs_reality"
        assert often[0]["overlap_pct"] == 50.0
    finally:
        db.close()
        reset_engine()
        get_settings.cache_clear()


def test_other_codes_cluster_into_named_emergent(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        _add_coded(
            db,
            "o1",
            primary="other_cod_failed",
            mechanism="COD failed at checkout for wishlist item",
            quote="COD failed again",
        )
        _add_coded(
            db,
            "o2",
            primary="other_cod_issue",
            mechanism="cash on delivery failed for the wishlisted dress",
            quote="COD not working",
            author="a2",
        )
        _add_coded(db, "s1", primary="fit_size_uncertainty", author="a3")
        result = compute_behavior_map(db, include_quotes=True)
        ids = {b["id"] for b in result["behaviors"]}
        assert "fit_size_uncertainty" in ids
        emergent = [b for b in result["behaviors"] if b["emergent"]]
        assert len(emergent) == 1
        assert emergent[0]["n"] == 2
        assert emergent[0]["id"].startswith("other_")
        assert "Emergent" in emergent[0]["family_label"] or emergent[0]["family"] == "other"
        assert emergent[0]["levers"]
        assert emergent[0]["quotes"]
    finally:
        db.close()
        reset_engine()
        get_settings.cache_clear()


def test_gemini_off_endpoints_still_return_rollup(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        _add_coded(db, "1", primary="oos_after_wishlist", stance="abandon", source="youtube")
        _add_coded(db, "2", primary="wait_for_price_drop", source="app_store", author="a2")
        db.add(SourceStatus(source="youtube", status="error", message="quota"))
        db.commit()
        rebuild_and_persist(db)
        assert db.scalar(select(BehaviorRollup).where(BehaviorRollup.slug == "oos_after_wishlist"))
    finally:
        db.close()

    with TestClient(app) as client:
        listed = client.get("/behaviors")
        assert listed.status_code == 200
        body = listed.json()
        assert body["header"]["analyzed"] == 2
        assert abs(body["primary_share_sum"] - 100.0) < 0.2
        assert any(s["source"] == "youtube" and s["status"] == "error" for s in body["header"]["source_status"])
        bid = body["behaviors"][0]["id"]
        detail = client.get(f"/behaviors/{bid}")
        assert detail.status_code == 200
        d = detail.json()
        assert d["quotes"]
        assert d["levers"]
        assert d["often_with"] is not None
        missing = client.get("/behaviors/does-not-exist")
        assert missing.status_code == 404
        units = client.get("/units")
        assert units.status_code == 200
        assert units.json()["total"] == 2
        filtered = client.get("/units", params={"stance": "abandon"})
        assert filtered.json()["total"] == 1
        uid = filtered.json()["units"][0]["id"]
        one = client.get(f"/units/{uid}")
        assert one.status_code == 200
        assert one.json()["code"]["primary_barrier"]
        health = client.get("/health")
        assert health.json()["phase"] == 5

    reset_engine()
    get_settings.cache_clear()


def test_empty_cache_fallback(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        persist_rollups(
            db,
            {
                "caption": "Of analyzed wishlist conversations, not Myntra live conversion.",
                "primary_share_sum": 100.0,
                "header": {"analyzed": 1, "voices": 1, "stance_mix": {}, "source_status": []},
                "behaviors": [
                    {
                        "id": "fit_size_uncertainty",
                        "title": "Like the look, don’t trust the size",
                        "didnt_buy_pct": 100.0,
                        "n": 1,
                        "voices": 1,
                        "intensity": 4.0,
                    }
                ],
            },
        )
    finally:
        db.close()

    with TestClient(app) as client:
        body = client.get("/behaviors").json()
        assert body["from_cache"] is True
        assert body["behaviors"][0]["id"] == "fit_size_uncertainty"

    reset_engine()
    get_settings.cache_clear()
