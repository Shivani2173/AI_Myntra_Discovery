from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class Envelope:
    source: str
    source_id: str
    text: str
    url: str | None = None
    author_hash: str | None = None
    created_at: datetime | None = None
    parent_context: dict | None = None


@dataclass
class FetchResult:
    envelopes: list[Envelope] = field(default_factory=list)
    watermark_cursor: str | None = None
    watermark_extra: dict | None = None
    skipped: str | None = None


class SourceConnector(Protocol):
    name: str

    def fetch(self, watermark_cursor: str | None, watermark_extra: dict | None) -> FetchResult: ...
