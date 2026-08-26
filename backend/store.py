from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.connectors import Envelope
from backend.models import SourceStatus, SourceWatermark, Unit


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def author_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:32]


def upsert_envelope(session: Session, env: Envelope) -> str:
    now = datetime.now(timezone.utc)
    hashed = content_hash(env.text)
    row = session.scalar(
        select(Unit).where(Unit.source == env.source, Unit.source_id == env.source_id)
    )
    if row is None:
        session.add(
            Unit(
                source=env.source,
                source_id=env.source_id,
                content_hash=hashed,
                url=env.url,
                author_hash=env.author_hash,
                text=env.text,
                parent_context=env.parent_context,
                created_at=env.created_at,
                last_seen_at=now,
            )
        )
        return "inserted"
    row.last_seen_at = now
    row.content_hash = hashed
    row.text = env.text
    row.url = env.url or row.url
    row.parent_context = env.parent_context or row.parent_context
    return "updated"


def save_watermark(session: Session, source: str, cursor: str | None, extra: dict | None) -> None:
    row = session.get(SourceWatermark, source)
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(SourceWatermark(source=source, cursor=cursor, extra=extra, updated_at=now))
        return
    row.cursor = cursor
    row.extra = extra
    row.updated_at = now


def save_status(session: Session, source: str, status: str, message: str | None = None) -> None:
    row = session.get(SourceStatus, source)
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(SourceStatus(source=source, status=status, message=message, checked_at=now))
        return
    row.status = status
    row.message = message
    row.checked_at = now
