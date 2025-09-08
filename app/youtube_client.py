from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone, timedelta
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
        self.last_status_code = None
        self.last_error = None
    # Note: we don't store last_polled_at here; callers pass published_after or we use a safe recent default.

    async def close(self):
        await self.client.aclose()

    async def search_latest(self, *, published_after: Optional[datetime] = None, query: Optional[str] = None, include_published_after: bool = True) -> list[dict[str, Any]]:
        """Fetch latest videos since published_after using key rotation and backoff.
        Returns raw items list from YouTube API.
        """
        # If no keys configured, skip external call gracefully
        if not self.key_rotator._queue:
            return []
        params = {
            "part": "snippet",
            "type": "video",
            "order": "date",
            "q": (query or self.query),
            "maxResults": 50,
        }
        if include_published_after:
            if published_after is None:
                # Default to a small recent window to avoid 'cached old' or empty results on first call
                published_after = datetime.now(timezone.utc) - timedelta(days=2)
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
                self.last_status_code = resp.status_code
                self.last_error = None
                if resp.status_code in (403, 429):
                    # Capture error body if present
                    try:
                        err = resp.json().get("error", {})
                        msg = err.get("message") or (err.get("errors", [{}])[0].get("reason"))
                        if msg:
                            self.last_error = str(msg)
                    except Exception:
                        pass
                    self.key_rotator.mark_exhausted()
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                return items
            except httpx.HTTPStatusError as e:
                try:
                    self.last_status_code = e.response.status_code
                    # Try to extract structured YouTube error message
                    try:
                        err = e.response.json().get("error", {})
                        msg = err.get("message") or (err.get("errors", [{}])[0].get("reason"))
                        self.last_error = str(msg) if msg else f"HTTP {e.response.status_code}"
                    except Exception:
                        self.last_error = f"HTTP {e.response.status_code}"
                except Exception:
                    self.last_error = "HTTP error"
                if 500 <= e.response.status_code < 600:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
                raise
            except httpx.RequestError as e:
                self.last_error = f"Request error: {type(e).__name__}"
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
