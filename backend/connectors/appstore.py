from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.connectors import Envelope, FetchResult
from backend.store import author_hash

RSS = "https://itunes.apple.com/in/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"


class AppStoreConnector:
    name = "app_store"

    def __init__(self, app_ids: dict[str, str], pages_per_app: int) -> None:
        self.app_ids = app_ids
        self.pages_per_app = max(1, pages_per_app)

    def fetch(self, watermark_cursor: str | None, watermark_extra: dict | None) -> FetchResult:
        extra = dict(watermark_extra or {})
        envelopes: list[Envelope] = []
        newest = watermark_cursor or ""

        with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "ai-discovery-engine/0.1"}) as client:
            for slug, app_id in self.app_ids.items():
                url = RSS.format(app_id=app_id)
                headers = {}
                etag = extra.get(f"etag_{slug}")
                if etag:
                    headers["If-None-Match"] = etag
                resp = client.get(url, headers=headers)
                if resp.status_code == 304:
                    continue
                resp.raise_for_status()
                if resp.headers.get("etag"):
                    extra[f"etag_{slug}"] = resp.headers["etag"]
                extra[f"fetched_{slug}"] = datetime.now(timezone.utc).isoformat()
                payload = resp.json()
                entries = payload.get("feed", {}).get("entry") or []
                if isinstance(entries, dict):
                    entries = [entries]
                for entry in entries[1:]:
                    cid = (entry.get("id") or {}).get("label")
                    content = (entry.get("content") or {}).get("label") or ""
                    title = (entry.get("title") or {}).get("label") or ""
                    updated = (entry.get("updated") or {}).get("label") or ""
                    author = ((entry.get("author") or {}).get("name") or {}).get("label")
                    text = f"{title}\n{content}".strip()
                    if not cid or len(text) < 8:
                        continue
                    if watermark_cursor and updated <= watermark_cursor:
                        continue
                    if updated > newest:
                        newest = updated
                    created_at = None
                    if updated:
                        try:
                            created_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                        except ValueError:
                            created_at = None
                    envelopes.append(
                        Envelope(
                            source="app_store",
                            source_id=str(cid),
                            text=text[:8000],
                            url=f"https://apps.apple.com/app/id{app_id}",
                            author_hash=author_hash(author),
                            created_at=created_at,
                            parent_context={"app": slug, "app_id": app_id},
                        )
                    )

        return FetchResult(
            envelopes=envelopes,
            watermark_cursor=newest or watermark_cursor,
            watermark_extra=extra,
        )
