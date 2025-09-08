from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
import os

from ..config import get_settings
from ..crud import list_videos, search_videos
from ..db import get_session
from ..schemas import PaginatedVideos, VideoOut
from ..models import Video
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func

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
    channel: str | None = Query(None, description="Filter by channel title (contains)"),
    sort: str = Query(
        "published_desc",
        description="Sort order for list view",
        regex="^(published_desc|published_asc)$",
    ),
):
    page, per_page = qp
    async with get_session() as session:
        total, items = await list_videos(
            session, page=page, per_page=per_page, channel=channel, sort=sort
        )
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


@router.api_route("/_seed", methods=["POST", "GET"])
async def seed_demo():
    """Insert a few demo videos for local UI preview.

    This endpoint is intended for local development (SQLite). It's idempotent.
    """
    settings = get_settings()
    if not settings.database_url.startswith("sqlite") and os.getenv("ALLOW_DEMO_SEED", "0") != "1":
        raise HTTPException(status_code=400, detail="Seeding only allowed on SQLite dev (set ALLOW_DEMO_SEED=1 to override).")
    async with get_session() as session:
        now = datetime.now(timezone.utc)
        samples = [
            {
                "video_id": "demo-" + suffix,
                "title": title,
                "description": desc,
                "published_at": now - timedelta(days=idx),
                "thumbnails": {"default": {"url": thumb}},
                "channel_id": "demo-ch",
                "channel_title": "Demo Channel",
                "raw_json": {},
            }
            for idx, (suffix, title, desc, thumb) in enumerate(
                [
                    ("1", "Cricket highlights", "Best moments of the match", "https://i.ytimg.com/vi/ysz5S6PUM-U/hqdefault.jpg"),
                    ("2", "How to play cricket", "Beginner tutorial", "https://i.ytimg.com/vi/J---aiyznGQ/hqdefault.jpg"),
                    ("3", "Match analysis", "Deep dive into tactics", "https://i.ytimg.com/vi/oHg5SJYRHA0/hqdefault.jpg"),
                ]
            )
        ]
        # Use existing upsert logic
        from ..crud import upsert_videos
        inserted = await upsert_videos(session, samples)
    return {"status": "ok", "inserted": inserted}


@router.post("/_fetch_now")
async def fetch_now(q: str | None = Query(None, description="Optional search query to fetch now")):
    """Manually fetch latest videos from YouTube and upsert.

    Uses max(published_at) from DB as a starting point; falls back to 7 days.
    Requires YOUTUBE_API_KEYS to be configured.
    """
    settings = get_settings()
    if not settings.youtube_api_keys:
        raise HTTPException(status_code=400, detail="YOUTUBE_API_KEYS not configured.")

    # Determine published_after cutoff(s)
    async with get_session() as session:
        res = await session.execute(select(func.max(Video.published_at)))
        max_ts = res.scalar()
        # Normalize DB timestamp to timezone-aware UTC if it's naive
        if isinstance(max_ts, datetime) and (max_ts.tzinfo is None or max_ts.tzinfo.utcoffset(max_ts) is None):
            max_ts = max_ts.replace(tzinfo=timezone.utc)

    from ..youtube_client import YouTubeClient
    client = YouTubeClient()
    try:
        now_utc = datetime.now(timezone.utc)
        # Try multiple cutoffs to avoid too-tight windows (e.g., demo data near now)
        cutoffs: list[datetime] = []
        if q:
            cutoffs = [
                now_utc - timedelta(days=2),
                now_utc - timedelta(days=7),
                now_utc - timedelta(days=30),
                now_utc - timedelta(days=90),
            ]
        else:
            base = max_ts or (now_utc - timedelta(days=7))
            # Ensure base is timezone-aware UTC
            if isinstance(base, datetime) and (base.tzinfo is None or base.tzinfo.utcoffset(base) is None):
                base = base.replace(tzinfo=timezone.utc)
            # Clamp base to past and provide looser fallbacks
            if base > now_utc:
                base = now_utc - timedelta(days=2)
            cutoffs = [
                base - timedelta(hours=1),
                now_utc - timedelta(days=2),
                now_utc - timedelta(days=7),
                now_utc - timedelta(days=30),
                now_utc - timedelta(days=90),
            ]

        items = []
        tried_cutoff = None
        # Minimal debug: helps check keys presence and cutoff strategy (no secrets)
        try:
            print(f"[fetch_now] q={'set' if q else 'default'}; keys={len(settings.youtube_api_keys)}; tries={len(cutoffs)}")
        except Exception:
            pass
        for co in cutoffs:
            tried_cutoff = co
            items = await client.search_latest(published_after=co, query=q)
            if items:
                break
        # If still nothing, attempt without publishedAfter as a last resort
        if not items:
            tried_cutoff = None
            items = await client.search_latest(published_after=None, query=q, include_published_after=False)
        payloads = YouTubeClient.transform_items(items)
        # Normalize published_at to timezone-aware datetime
        norm: list[dict] = []
        for p in payloads:
            try:
                if isinstance(p.get("published_at"), str):
                    p["published_at"] = datetime.fromisoformat(p["published_at"].replace("Z", "+00:00"))
                norm.append(p)
            except Exception:
                # skip malformed rows
                continue
        from ..crud import upsert_videos
        async with get_session() as session:
            await upsert_videos(session, norm)
        return {
            "status": "ok",
            "fetched": len(items),
            "inserted": len(norm),
            "query": q or get_settings().youtube_query,
            "published_after": tried_cutoff.isoformat().replace("+00:00", "Z") if tried_cutoff else None,
            "last_status": client.last_status_code,
            "last_error": client.last_error,
        }
    finally:
        await client.close()


@router.get("/search", response_model=PaginatedVideos)
async def search(
    q: str = Query(..., min_length=1),
    qp = Depends(_pagination_params),
    channel: str | None = Query(None, description="Filter by channel title (contains)"),
    sort: str = Query(
        "published_desc",
        description="Sort order (applied as a secondary order after relevance)",
        regex="^(published_desc|published_asc)$",
    ),
):
    page, per_page = qp
    async with get_session() as session:
        total, items = await search_videos(
            session, query=q, page=page, per_page=per_page, channel=channel, sort=sort
        )
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
