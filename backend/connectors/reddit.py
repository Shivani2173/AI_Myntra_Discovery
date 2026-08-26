from __future__ import annotations

from datetime import datetime, timezone

from backend.config import Settings
from backend.connectors import Envelope, FetchResult
from backend.store import author_hash


class RedditConnector:
    name = "reddit"

    def __init__(self, settings: Settings, queries: list[str], thread_cap: int) -> None:
        self.settings = settings
        self.queries = queries
        self.thread_cap = thread_cap

    def fetch(self, watermark_cursor: str | None, watermark_extra: dict | None) -> FetchResult:
        if not self.settings.reddit_client_id or not self.settings.reddit_client_secret:
            return FetchResult(skipped="REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set")

        import praw

        min_utc = float(watermark_cursor) if watermark_cursor else 0.0
        reddit = praw.Reddit(
            client_id=self.settings.reddit_client_id,
            client_secret=self.settings.reddit_client_secret,
            user_agent=self.settings.reddit_user_agent,
        )
        reddit.read_only = True

        envelopes: list[Envelope] = []
        max_utc = min_utc
        remaining = self.thread_cap
        for query in self.queries:
            if remaining <= 0:
                break
            for post in reddit.subreddit("all").search(query, sort="new", limit=min(25, remaining)):
                created = float(getattr(post, "created_utc", 0) or 0)
                if created <= min_utc:
                    continue
                max_utc = max(max_utc, created)
                title = (post.title or "").strip()
                body = (getattr(post, "selftext", None) or "").strip()
                text = f"{title}\n{body}".strip()
                if len(text) < 20:
                    continue
                created_at = datetime.fromtimestamp(created, tz=timezone.utc)
                envelopes.append(
                    Envelope(
                        source="reddit",
                        source_id=str(post.id),
                        text=text[:8000],
                        url=f"https://www.reddit.com{post.permalink}",
                        author_hash=author_hash(str(getattr(post, "author", "") or "")),
                        created_at=created_at,
                        parent_context={"query": query, "subreddit": str(post.subreddit)},
                    )
                )
                remaining -= 1
                if remaining <= 0:
                    break

        cursor = str(max_utc) if max_utc > min_utc else watermark_cursor
        return FetchResult(envelopes=envelopes, watermark_cursor=cursor, watermark_extra=watermark_extra)
