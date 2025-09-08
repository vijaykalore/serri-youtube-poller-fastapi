from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient

from app.main import app
from app.db import get_session
from app.crud import upsert_videos


@pytest.mark.asyncio
async def test_list_videos_empty():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/videos")
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["items"] == []


@pytest.mark.asyncio
async def test_list_endpoint_returns_paginated_items():
    # Seed a couple of videos
    async with get_session() as s:
        await upsert_videos(
            s,
            [
                {
                    "video_id": "seed-1",
                    "title": "Cricket highlights",
                    "description": "Best moments",
                    "published_at": datetime.now(timezone.utc) - timedelta(days=2),
                    "thumbnails": {},
                    "channel_id": "cA",
                    "channel_title": "Sports",
                    "raw_json": {},
                },
                {
                    "video_id": "seed-2",
                    "title": "How to play cricket",
                    "description": "Tutorial",
                    "published_at": datetime.now(timezone.utc) - timedelta(days=1),
                    "thumbnails": {},
                    "channel_id": "cB",
                    "channel_title": "Coach",
                    "raw_json": {},
                },
            ],
        )

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/videos", params={"page": 1, "per_page": 1})
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and data["per_page"] == 1
        assert data["items"][0]["video_id"] == "seed-2"
