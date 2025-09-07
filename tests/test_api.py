import asyncio
import os
import json
from httpx import AsyncClient
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/serri_videos")

from app.main import app  # noqa: E402


@pytest.mark.asyncio
async def test_list_videos_empty():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/videos")
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["items"] == []
