"""Import curated evidence rows from a bundled CSV as permanent, default units.

Unlike backend/connectors/*, this reads a file shipped in the repo instead of a
live API, so it never needs a network call and is safe to re-run on every boot
(upsert_envelope dedupes on source+source_id).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from sqlalchemy.orm import Session

from backend.connectors import Envelope
from backend.store import upsert_envelope

DEFAULT_CSV_PATH = Path(__file__).parent / "seed_data" / "myntra_wishlist_evidence.csv"

SOURCE_SLUG_MAP = {
    "news/industry": "news",
    "india today": "news",
    "reddit": "reddit",
    "linkedin": "linkedin",
    "medium": "medium",
    "youtube": "youtube",
    "app store": "app_store",
    "instagram": "instagram",
    "facebook": "facebook",
    "general e-commerce": "web_research",
    "general fashion": "web_research",
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "web_research"


def _source_slug(source_type: str) -> str:
    return SOURCE_SLUG_MAP.get(source_type.strip().lower(), _slugify(source_type))


def run_import_csv(session: Session, path: Path | str = DEFAULT_CSV_PATH) -> dict:
    path = Path(path)
    summary: dict = {"inserted": 0, "updated": 0, "rows_total": 0, "path": str(path)}
    if not path.exists():
        summary["skipped"] = f"csv not found: {path}"
        return summary

    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            record_id = (row.get("record_id") or "").strip()
            evidence = (row.get("original_evidence") or "").strip()
            if not record_id or not evidence:
                continue
            summary["rows_total"] += 1
            title = (row.get("title") or "").strip()
            # Some rows only say "wishlist" in the title, not the evidence
            # snippet itself; fold it in so the relevance filter (which only
            # looks at unit.text) and the LLM both see it.
            text = f"{title}. {evidence}" if title else evidence
            env = Envelope(
                source=_source_slug(row.get("source_type") or ""),
                source_id=record_id,
                text=text,
                url=(row.get("url") or "").strip() or None,
                parent_context={
                    "title": row.get("title"),
                    "source_name": row.get("source_name"),
                    "hypothesis_link": row.get("hypothesis_link"),
                    "notes": row.get("notes"),
                },
            )
            action = upsert_envelope(session, env)
            summary["inserted" if action == "inserted" else "updated"] += 1
    session.commit()
    return summary
