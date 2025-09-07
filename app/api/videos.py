from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..crud import list_videos, search_videos
from ..db import get_session
from ..schemas import PaginatedVideos, VideoOut

router = APIRouter(prefix="/api/videos", tags=["videos"])


async def _pagination_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(None, ge=1),
):
    settings = get_settings()
    if per_page is None:
        per_page = settings.page_size_default
    per_page = min(per_page, settings.page_size_max)
    return page, per_page


@router.get("", response_model=PaginatedVideos)
async def get_videos(
    qp = Depends(_pagination_params),
):
    page, per_page = qp
    async with get_session() as session:
        total, items = await list_videos(session, page=page, per_page=per_page)
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "next_page": page + 1 if page * per_page < total else None,
        "prev_page": page - 1 if page > 1 else None,
        "items": [
            VideoOut(
                video_id=i.video_id,
                title=i.title,
                description=i.description,
                published_at=i.published_at,
                thumbnails=i.thumbnails,
                channel_id=i.channel_id,
                channel_title=i.channel_title,
            )
            for i in items
        ],
    }


@router.get("/search", response_model=PaginatedVideos)
async def search(
    q: str = Query(..., min_length=1),
    qp = Depends(_pagination_params),
):
    page, per_page = qp
    async with get_session() as session:
        total, items = await search_videos(session, query=q, page=page, per_page=per_page)
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "next_page": page + 1 if page * per_page < total else None,
        "prev_page": page - 1 if page > 1 else None,
        "items": [
            VideoOut(
                video_id=i.video_id,
                title=i.title,
                description=i.description,
                published_at=i.published_at,
                thumbnails=i.thumbnails,
                channel_id=i.channel_id,
                channel_title=i.channel_title,
            )
            for i in items
        ],
    }
