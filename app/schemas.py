from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class VideoBase(BaseModel):
    video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    published_at: Optional[datetime] = None
    thumbnails: Optional[dict[str, Any]] = None
    channel_id: Optional[str] = None
    channel_title: Optional[str] = None


class VideoOut(VideoBase):
    pass


class PaginatedVideos(BaseModel):
    total: int
    page: int
    per_page: int
    next_page: int | None
    prev_page: int | None
    items: list[VideoOut]
