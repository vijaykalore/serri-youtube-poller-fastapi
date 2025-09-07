from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Optional

import httpx

from .config import get_settings

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


class APIKeyRotator:
    def __init__(self, keys: list[str]):
        self._queue: Deque[tuple[str, float]] = deque()
        now = time.monotonic()
        for k in keys:
            self._queue.append((k, now))
        self.cooldown_seconds = 600  # 10 minutes cooldown when exhausted

    def next_key(self) -> Optional[str]:
        if not self._queue:
            return None
        key, last_used = self._queue[0]
        return key

    def rotate(self) -> Optional[str]:
        if not self._queue:
            return None
        k, _ = self._queue.popleft()
        self._queue.append((k, time.monotonic()))
        return k

    def mark_exhausted(self):
        if not self._queue:
            return
        k, _ = self._queue.popleft()
        # Put it back with a future timestamp indicating cooldown
        self._queue.append((k, time.monotonic() + self.cooldown_seconds))

    def pop_available(self) -> Optional[str]:
        if not self._queue:
            return None
        # rotate until we find available one
        for _ in range(len(self._queue)):
            k, ready_at = self._queue[0]
            if time.monotonic() >= ready_at:
                return k
            self._queue.rotate(-1)
        return None


class YouTubeClient:
    def __init__(self):
        settings = get_settings()
        self.query = settings.youtube_query
        self.key_rotator = APIKeyRotator(settings.youtube_api_keys or [])
        self.client = httpx.AsyncClient(timeout=20)
        self.last_polled_at: datetime = datetime.now(timezone.utc)

    async def close(self):
        await self.client.aclose()

    async def search_latest(self, *, published_after: Optional[datetime] = None) -> list[dict[str, Any]]:
        """Fetch latest videos since published_after using key rotation and backoff.
        Returns raw items list from YouTube API.
        """
        params = {
            "part": "snippet",
            "type": "video",
            "order": "date",
            "q": self.query,
            "maxResults": 50,
        }
        if published_after is None:
            published_after = self.last_polled_at
        params["publishedAfter"] = published_after.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        backoff = 1.0
        for attempt in range(5):
            key = self.key_rotator.pop_available()
            if not key:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            params["key"] = key
            try:
                resp = await self.client.get(YOUTUBE_SEARCH_URL, params=params)
                if resp.status_code in (403, 429):
                    self.key_rotator.mark_exhausted()
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                return items
            except httpx.HTTPStatusError as e:
                if 500 <= e.response.status_code < 600:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
                raise
            except httpx.RequestError:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
        return []

    @staticmethod
    def transform_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for it in items:
            if it.get("id", {}).get("kind") != "youtube#video":
                continue
            vid = it.get("id", {}).get("videoId")
            snip = it.get("snippet", {})
            out.append(
                {
                    "video_id": vid,
                    "title": snip.get("title"),
                    "description": snip.get("description"),
                    "published_at": snip.get("publishedAt"),
                    "thumbnails": snip.get("thumbnails"),
                    "channel_id": snip.get("channelId"),
                    "channel_title": snip.get("channelTitle"),
                    "raw_json": it,
                }
            )
        return out
