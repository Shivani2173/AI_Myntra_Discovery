from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.config import Settings
from backend.connectors import Envelope, FetchResult
from backend.store import author_hash

SEARCH = "https://www.googleapis.com/youtube/v3/search"
COMMENTS = "https://www.googleapis.com/youtube/v3/commentThreads"


class YouTubeConnector:
    name = "youtube"

    def __init__(self, settings: Settings, queries: list[str], video_cap: int, comments_cap: int) -> None:
        self.settings = settings
        self.queries = queries
        self.video_cap = video_cap
        self.comments_cap = comments_cap

    def fetch(self, watermark_cursor: str | None, watermark_extra: dict | None) -> FetchResult:
        if not self.settings.youtube_api_key:
            return FetchResult(skipped="YOUTUBE_API_KEY not set")

        extra = dict(watermark_extra or {})
        envelopes: list[Envelope] = []
        newest = watermark_cursor or ""

        with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)) as client:
            video_ids: list[tuple[str, str]] = []
            queries = self.queries or []
            # Give every query a fair share of the cap so a run doesn't exhaust the
            # whole budget on the first query and never reach the rest of the list.
            per_query_cap = max(1, -(-self.video_cap // len(queries))) if queries else self.video_cap
            for query in queries:
                if len(video_ids) >= self.video_cap:
                    break
                take = min(per_query_cap, self.video_cap - len(video_ids))
                params = {
                    "part": "snippet",
                    "type": "video",
                    "maxResults": min(5, take),
                    "q": query,
                    "key": self.settings.youtube_api_key,
                    "order": "date",
                }
                page = extra.get(f"search_{query}")
                if page:
                    params["pageToken"] = page
                resp = client.get(SEARCH, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get("nextPageToken"):
                    extra[f"search_{query}"] = data["nextPageToken"]
                taken = 0
                for item in data.get("items", []):
                    if taken >= take:
                        break
                    vid = item.get("id", {}).get("videoId")
                    title = item.get("snippet", {}).get("title", "")
                    if vid:
                        video_ids.append((vid, title))
                        taken += 1

            for vid, title in video_ids[: self.video_cap]:
                params = {
                    "part": "snippet",
                    "videoId": vid,
                    "maxResults": min(100, self.comments_cap),
                    "textFormat": "plainText",
                    "key": self.settings.youtube_api_key,
                }
                cpage = extra.get(f"comments_{vid}")
                if cpage:
                    params["pageToken"] = cpage
                # Per-video cursor: a video seen for the first time this run has no
                # cutoff, so its older comments still count as new-to-us. Only videos
                # we've already paged through before are filtered against their own
                # last-seen comment timestamp (never the global cursor — that wrongly
                # discarded genuinely new comments on newly discovered videos).
                video_cursor = extra.get(f"newest_{vid}")
                resp = client.get(COMMENTS, params=params)
                if resp.status_code == 403:
                    continue
                resp.raise_for_status()
                data = resp.json()
                if data.get("nextPageToken"):
                    extra[f"comments_{vid}"] = data["nextPageToken"]
                video_newest = video_cursor or ""
                for item in data.get("items", []):
                    sn = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    text = (sn.get("textDisplay") or "").strip()
                    cid = item.get("id")
                    if not cid or len(text) < 8:
                        continue
                    published = sn.get("publishedAt") or ""
                    if video_cursor and published <= video_cursor:
                        continue
                    if published > video_newest:
                        video_newest = published
                    if published > newest:
                        newest = published
                    created_at = None
                    if published:
                        created_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    envelopes.append(
                        Envelope(
                            source="youtube",
                            source_id=str(cid),
                            text=text[:8000],
                            url=f"https://www.youtube.com/watch?v={vid}",
                            author_hash=author_hash(sn.get("authorDisplayName")),
                            created_at=created_at,
                            parent_context={"video_id": vid, "video_title": title},
                        )
                    )
                if video_newest:
                    extra[f"newest_{vid}"] = video_newest

        return FetchResult(
            envelopes=envelopes,
            watermark_cursor=newest or watermark_cursor,
            watermark_extra=extra,
        )
