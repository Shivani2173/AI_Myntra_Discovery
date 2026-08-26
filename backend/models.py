from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_units_source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    author_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    parent_context: Mapped[dict | None] = mapped_column(JSON().with_variant(SQLITE_JSON, "sqlite"), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    relevance_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    extract_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON().with_variant(SQLITE_JSON, "sqlite"), nullable=True)

    code: Mapped["Code | None"] = relationship(back_populates="unit")


class Code(Base):
    __tablename__ = "codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), unique=True)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(SQLITE_JSON, "sqlite"))
    coded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    unit: Mapped[Unit] = relationship(back_populates="code")


class SourceWatermark(Base):
    __tablename__ = "source_watermarks"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON().with_variant(SQLITE_JSON, "sqlite"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SourceStatus(Base):
    __tablename__ = "source_status"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GatherJob(Base):
    __tablename__ = "gather_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    result: Mapped[dict | None] = mapped_column(JSON().with_variant(SQLITE_JSON, "sqlite"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BehaviorRollup(Base):
    __tablename__ = "behavior_rollups"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    primary_share: Mapped[float] = mapped_column(default=0.0)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(SQLITE_JSON, "sqlite"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
