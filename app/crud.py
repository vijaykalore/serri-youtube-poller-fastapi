from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select, func, or_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Video


async def upsert_videos(session: AsyncSession, videos: list[dict]) -> int:
    """Insert videos idempotently based on unique video_id.

    Returns number of records inserted (ignores duplicates).
    """
    if not videos:
        return 0

    dialect_name = session.bind.dialect.name if session.bind is not None else ""
    if dialect_name == "postgresql":
        stmt = (
            pg_insert(Video)
            .values(videos)
            .on_conflict_do_nothing(index_elements=[Video.video_id])
        )
        res = await session.execute(stmt)
    else:
        # Fallback naive upsert for tests (SQLite). Filter out duplicates first.
        existing_ids = set(
            (
                await session.execute(
                    select(Video.video_id).where(
                        Video.video_id.in_([v["video_id"] for v in videos if v.get("video_id")])
                    )
                )
            ).scalars().all()
        )
        to_insert = [v for v in videos if v.get("video_id") and v["video_id"] not in existing_ids]
        res = await session.execute(Video.__table__.insert(), to_insert) if to_insert else type("obj", (), {"rowcount": 0})()
    # rowcount may be -1 depending on dialect; do a count afterwards for reliability if needed
    return res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0


async def list_videos(
    session: AsyncSession, *, page: int, per_page: int
) -> tuple[int, Sequence[Video]]:
    total = await session.scalar(select(func.count()).select_from(Video))
    items = (
        await session.execute(
            select(Video).order_by(Video.published_at.desc()).offset((page - 1) * per_page).limit(per_page)
        )
    ).scalars().all()
    return int(total or 0), items


async def search_videos(
    session: AsyncSession, *, query: str, page: int, per_page: int
) -> tuple[int, Sequence[Video]]:
    dialect_name = session.bind.dialect.name if session.bind is not None else ""
    if dialect_name == "postgresql":
        # Use full-text search + trigram when available (PostgreSQL)
        where_clause = text(
            "(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')) @@ websearch_to_tsquery('english', :q))"
        )
        total_stmt = select(func.count()).select_from(Video).where(where_clause)
        total_res = await session.execute(total_stmt.params(q=query))
        total = total_res.scalar() or 0
        order_expr = text(
            "(0.6 * ts_rank(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')), websearch_to_tsquery('english', :q)) + "
            "0.2 * similarity(coalesce(title,''), :q) + 0.2 * similarity(coalesce(description,''), :q)) DESC, published_at DESC"
        )
        items = (
            await session.execute(
                select(Video)
                .where(where_clause)
                .order_by(order_expr)
                .offset((page - 1) * per_page)
                .limit(per_page)
                .params(q=query)
            )
        ).scalars().all()
    else:
        # Fallback to ILIKE contains search
        like = f"%{query}%"
        total = await session.scalar(
            select(func.count()).select_from(Video).where(
                or_(Video.title.ilike(like), Video.description.ilike(like))
            )
        )
        items = (
            await session.execute(
                select(Video)
                .where(or_(Video.title.ilike(like), Video.description.ilike(like)))
                .order_by(Video.published_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).scalars().all()

    return int(total or 0), items
