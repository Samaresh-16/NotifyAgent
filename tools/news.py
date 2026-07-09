from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.models import Event


class HackerNewsTool:
    name = "hacker_news"

    def __init__(
        self,
        *,
        limit: int = 10,
        timeout_seconds: float = 10.0,
        api_url: str = "https://hn.algolia.com/api/v1/search_by_date?tags=front_page",
    ) -> None:
        self.limit = limit
        self.timeout_seconds = timeout_seconds
        self.api_url = api_url

    def collect(self) -> list[Event]:
        import httpx

        response = httpx.get(self.api_url, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits", [])
        return [self._event_from_hit(hit) for hit in hits[: self.limit]]

    def _event_from_hit(self, hit: dict[str, Any]) -> Event:
        created_at = hit.get("created_at")
        timestamp = self._parse_timestamp(created_at)
        title = hit.get("title") or hit.get("story_title") or "Untitled Hacker News item"
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        points = hit.get("points")
        author = hit.get("author", "unknown")
        comments = hit.get("num_comments")
        summary = f"By {author}"
        if points is not None:
            summary += f", {points} points"
        if comments is not None:
            summary += f", {comments} comments"

        return Event(
            id=str(hit.get("objectID") or url),
            source=self.name,
            title=str(title),
            summary=summary,
            url=str(url),
            timestamp=timestamp,
        )

    def _parse_timestamp(self, value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
