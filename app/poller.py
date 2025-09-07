from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from .config import get_settings
from .crud import upsert_videos
from .db import get_session
from .youtube_client import YouTubeClient


class BackgroundPoller:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._client = YouTubeClient()
        self._running = False

    async def start(self):
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._client.close()

    async def _run(self):
        settings = get_settings()
        poll_interval = settings.poll_interval
        last_after = datetime.now(timezone.utc)
        while self._running:
            try:
                items = await self._client.search_latest(published_after=last_after)
                transformed = YouTubeClient.transform_items(items)
                # Convert published_at to datetime
                for t in transformed:
                    if isinstance(t.get("published_at"), str):
                        t["published_at"] = datetime.fromisoformat(t["published_at"].replace("Z", "+00:00"))
                inserted = 0
                if transformed:
                    async with get_session() as session:
                        inserted = await upsert_videos(session, transformed)
                # Advance last_after to max published_at we saw (avoid missing newer)
                if transformed:
                    max_dt = max([t["published_at"] for t in transformed if t.get("published_at")])
                    if max_dt and max_dt > last_after:
                        last_after = max_dt
            except Exception:
                # Swallow to keep loop alive; logs could be added here
                pass
            await asyncio.sleep(poll_interval)
