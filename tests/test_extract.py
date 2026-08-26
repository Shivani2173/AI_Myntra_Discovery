from __future__ import annotations

import json

from sqlalchemy import func, select

from backend.config import get_settings
from backend.db import init_db, reset_engine, session_scope
from backend.extract import run_extract
from backend.llm import StubClient
from backend.models import Code, Unit
from backend.store import content_hash


def _fresh_db(monkeypatch, tmp_path):
    db_path = (tmp_path / "t.db").resolve().as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EXTRACT_STUB", "1")
    monkeypatch.setenv("USE_MINILM", "false")
    get_settings.cache_clear()
    reset_engine()
    init_db()
    return session_scope()


def _add_unit(db, source_id: str, text: str, source: str = "reddit") -> Unit:
    unit = Unit(
        source=source,
        source_id=source_id,
        content_hash=content_hash(text),
        text=text,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


WISH = (
    "I added this Myntra dress to my wishlist but I don't trust the size chart "
    "so I will not buy until I know the fit."
)


def test_second_extract_does_not_increase_llm_calls(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        _add_unit(db, "1", WISH)
        client = StubClient()
        first = run_extract(db, client)
        assert first["llm_calls"] == 1
        assert first["coded"] == 1
        assert db.scalar(select(func.count()).select_from(Code)) == 1
        second = run_extract(db, client)
        assert second["llm_calls"] == 0
        assert second["coded"] == 0
        assert db.scalar(select(func.count()).select_from(Code)) == 1
    finally:
        db.close()
        reset_engine()
        get_settings.cache_clear()


def test_same_content_hash_copies_code_without_llm(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        _add_unit(db, "a", WISH, source="reddit")
        client = StubClient()
        run_extract(db, client)
        _add_unit(db, "b", WISH, source="youtube")
        again = run_extract(db, client)
        assert again["copied_hash"] == 1
        assert again["llm_calls"] == 0
        assert db.scalar(select(func.count()).select_from(Code)) == 2
    finally:
        db.close()
        reset_engine()
        get_settings.cache_clear()


def test_codes_are_never_updated(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        unit = _add_unit(db, "1", WISH)
        run_extract(db, StubClient())
        code = db.scalar(select(Code).where(Code.unit_id == unit.id))
        original = json.dumps(code.payload, sort_keys=True)
        run_extract(db, StubClient())
        db.refresh(code)
        assert json.dumps(code.payload, sort_keys=True) == original
        assert db.scalar(select(func.count()).select_from(Code)) == 1
    finally:
        db.close()
        reset_engine()
        get_settings.cache_clear()


class _BadThenGood:
    name = "flaky"
    calls = 0

    def complete(self, unit_text: str, parent_context: dict | None) -> str:
        self.calls += 1
        if "FAILJSON" in unit_text:
            return "this is not json {"
        return StubClient().complete(unit_text, parent_context)


def test_invalid_json_fails_row_not_job(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        _add_unit(
            db,
            "bad",
            "FAILJSON I added this Myntra dress to my wishlist but size chart is wrong.",
        )
        _add_unit(db, "good", WISH)
        client = _BadThenGood()
        result = run_extract(db, client)
        assert result["failed_rows"] == 1
        assert result["coded"] == 1
        assert result["llm_calls"] >= 3  # original + 2 retries on the bad row, plus good row
        assert db.scalar(select(func.count()).select_from(Code)) == 1
        bad = db.scalar(select(Unit).where(Unit.source_id == "bad"))
        assert bad.extract_error
    finally:
        db.close()
        reset_engine()
        get_settings.cache_clear()


def test_irrelevant_skips_llm(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    try:
        _add_unit(db, "x", "The weather in Goa is nice this week and I like mangoes a lot.")
        client = StubClient()
        result = run_extract(db, client)
        assert result["filtered_irrelevant"] == 1
        assert result["llm_calls"] == 0
        assert db.scalar(select(func.count()).select_from(Code)) == 0
    finally:
        db.close()
        reset_engine()
        get_settings.cache_clear()
