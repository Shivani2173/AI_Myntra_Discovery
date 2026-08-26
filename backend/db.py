from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import ROOT, get_settings
from backend.models import Base

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    if ":///" not in url:
        return
    raw = url.split("sqlite:///")[-1]
    if raw in {":memory:", ""}:
        return
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        settings = get_settings()
        _ensure_sqlite_dir(settings.database_url)
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, connect_args=connect_args)
        SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def reset_engine() -> None:
    global _engine, SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    SessionLocal = None


def _add_column_if_missing(engine: Engine, table: str, column: str, ddl: str) -> None:
    url = str(engine.url)
    with engine.begin() as conn:
        if url.startswith("sqlite"):
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            names = {row[1] for row in rows}
            if column not in names:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        else:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {ddl}"))


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _add_column_if_missing(engine, "units", "relevance_status", "relevance_status VARCHAR(32)")
    _add_column_if_missing(engine, "units", "extract_error", "extract_error TEXT")
    _add_column_if_missing(engine, "units", "embedding", "embedding JSON")


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_db() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def session_scope() -> Session:
    if SessionLocal is None:
        get_engine()
    assert SessionLocal is not None
    return SessionLocal()
