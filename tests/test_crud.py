import asyncio
from datetime import datetime, timezone, timedelta
import pytest

from app.crud import upsert_videos, list_videos
from app.db import get_session


@pytest.mark.asyncio
async def test_upsert_idempotent_and_sorted_listing():
    v1 = {
        "video_id": "vid-1",
        "title": "How to make tea?",
        "description": "Short desc",
        "published_at": datetime.now(timezone.utc) - timedelta(days=1),
        "thumbnails": {"default": {"url": "http://x"}},
        "channel_id": "c1",
        "channel_title": "Ch1",
        "raw_json": {"k": 1},
    }
    v2 = {
        "video_id": "vid-2",
        "title": "How to cook pasta",
        "description": "Yum",
        "published_at": datetime.now(timezone.utc),
        "thumbnails": {"default": {"url": "http://y"}},
        "channel_id": "c2",
        "channel_title": "Ch2",
        "raw_json": {"k": 2},
    }
    async with get_session() as s:
        c1 = await upsert_videos(s, [v1, v2])
        c2 = await upsert_videos(s, [v1, v2])
        assert c1 >= 1
        assert c2 == 0  # second insert should be idempotent (no duplicates)
        total, items = await list_videos(s, page=1, per_page=10)
        assert total >= 2
        # sorted desc by published_at
        assert items[0].video_id == "vid-2"
