from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Video


async def upsert_videos(session: AsyncSession, videos: list[dict]) -> int:
    """Insert videos idempotently based on unique video_id.

    Returns number of records inserted (ignores duplicates).
    """
    if not videos:
        return 0

    # Normalize input dicts to model columns
    cleaned = []
    for v in videos:
        cleaned.append(
            {
                "video_id": v.get("video_id"),
                "title": v.get("title"),
                "description": v.get("description"),
                "channel_title": v.get("channel_title"),
                "channel_id": v.get("channel_id"),
                "published_at": v.get("published_at"),
                "thumbnails": v.get("thumbnails"),
                "raw_json": v.get("raw_json"),
            }
        )

    if not cleaned:
        return 0

    dialect_name = session.bind.dialect.name if session.bind is not None else ""
    if dialect_name == "postgresql":
        stmt = (
            pg_insert(Video.__table__)
            .values(cleaned)
            .on_conflict_do_nothing(index_elements=[Video.video_id])
            .returning(Video.video_id)
        )
        result = await session.execute(stmt)
        inserted_ids = result.scalars().all()
        return len(inserted_ids)
    else:
        # SQLite: pre-check existing and bulk insert only new ones
        ids = [v["video_id"] for v in cleaned]
        existing = (
            await session.execute(
                select(Video.video_id).where(Video.video_id.in_(ids))
            )
        ).scalars().all()
        existing_set = set(existing)
        to_insert = [v for v in cleaned if v["video_id"] not in existing_set]
        if not to_insert:
            return 0
        await session.execute(Video.__table__.insert(), to_insert)
        return len(to_insert)


async def list_videos(
    session: AsyncSession,
    *,
    page: int,
    per_page: int,
    channel: str | None = None,
    sort: str = "published_desc",
) -> tuple[int, Sequence[Video]]:
    where = []
    if channel:
        like = f"%{channel}%"
        where.append(Video.channel_title.ilike(like))
    stmt_total = select(func.count()).select_from(Video)
    if where:
        stmt_total = stmt_total.where(and_(*where))
    total = await session.scalar(stmt_total)

    order_clause = Video.published_at.desc()
    if sort == "published_asc":
        order_clause = Video.published_at.asc()

    stmt_items = select(Video)
    if where:
        stmt_items = stmt_items.where(and_(*where))
    stmt_items = stmt_items.order_by(order_clause).offset((page - 1) * per_page).limit(per_page)

    items = (await session.execute(stmt_items)).scalars().all()
    return int(total or 0), items


async def search_videos(
    session: AsyncSession,
    *,
    query: str,
    page: int,
    per_page: int,
    channel: str | None = None,
    sort: str = "published_desc",
) -> tuple[int, Sequence[Video]]:
    dialect_name = session.bind.dialect.name if session.bind is not None else ""
    if dialect_name == "postgresql":
        # Full-text search with fallback to trigram similarity and ILIKE for stopwords/partials
        ts_match = text(
            "(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')) \u0040\u0040 websearch_to_tsquery('english', :q))"
        )
        like_param = f"%{query}%"
        # Dynamic trigram threshold: len<=4 -> 0.2 (typo friendly), len<=6 -> 0.25, else 0.3
        qlen = len(query)
        sim_threshold = 0.2 if qlen <= 4 else (0.25 if qlen <= 6 else 0.3)
        trigram_match = text(
            "(similarity(coalesce(title,''), :q) >= :simth OR similarity(coalesce(description,''), :q) >= :simth)"
        )
        ilike_match = or_(Video.title.ilike(like_param), Video.description.ilike(like_param))
        or_group = or_(ts_match, trigram_match, ilike_match)
        where_clause = or_group
        if channel:
            like = f"%{channel}%"
            where_clause = and_(where_clause, Video.channel_title.ilike(like))

        total_stmt = select(func.count()).select_from(Video).where(where_clause)
        total_res = await session.execute(total_stmt.params(q=query, simth=sim_threshold))
        total = total_res.scalar() or 0

        # Relevance: combine ts_rank + trigram similarity; fallbacks get lower but non-zero score
        score_expr = text(
            "(0.6 * ts_rank(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')), websearch_to_tsquery('english', :q)) + "
            "0.2 * similarity(coalesce(title,''), :q) + 0.2 * similarity(coalesce(description,''), :q))"
        )
        published_order = text("published_at ASC" if sort == "published_asc" else "published_at DESC")
        items = (
            await session.execute(
                select(Video)
                .where(where_clause)
                .order_by(text(f"{score_expr.text} DESC"), published_order)
                .offset((page - 1) * per_page)
                .limit(per_page)
                .params(q=query, simth=sim_threshold)
            )
        ).scalars().all()

        # Fallback for very short queries (typos like "crik"): do a fuzzy pass in Python
        if (total == 0) and query.strip() and len(query) <= 4:
            import difflib
            # Pull recent window
            window_rows = (
                await session.execute(
                    select(Video).order_by(Video.published_at.desc()).limit(500)
                )
            ).scalars().all()
            ql = " ".join(query.lower().split())
            def score(v: Video) -> float:
                hay = f"{v.title or ''} {v.description or ''}".lower()
                hay = " ".join(hay.split())
                return float(difflib.SequenceMatcher(None, ql, hay).ratio())
            ranked = sorted(window_rows, key=lambda v: (-score(v), (v.published_at or datetime.min).timestamp() if sort != "published_asc" else -(v.published_at or datetime.min).timestamp()))
            # Filter by a minimal score to avoid random matches
            filtered = [v for v in ranked if score(v) >= 0.18]
            total = len(filtered)
            start = (page - 1) * per_page
            items = filtered[start:start + per_page]
    else:
        # Fallback to SQLite: tokenized ILIKE filter + optional fuzzy ranking using difflib
        import difflib

        terms = [t for t in query.split() if t]
        had_terms = bool(terms)
        cond = None
        for t in terms:
            like = f"%{t}%"
            term_cond = or_(Video.title.ilike(like), Video.description.ilike(like))
            cond = term_cond if cond is None else (cond & term_cond)
        cond = cond if cond is not None else text("1=1")
        if channel:
            ch_like = f"%{channel}%"
            ch_cond = Video.channel_title.ilike(ch_like)
            cond = and_(cond, ch_cond)

        # Count total matches for proper pagination metadata
        total_count = await session.scalar(select(func.count()).select_from(Video).where(cond))

        # Pull a window and, if query present, rank in Python for fuzzy matches
        candidate_rows = (
            await session.execute(
                select(Video)
                .where(cond)
                .order_by(Video.published_at.desc())
                .limit(500)  # safety window
            )
        ).scalars().all()

    # If no candidates found (likely a typo), optionally broaden to recent window
        broadened_total = None
        if not candidate_rows and query.strip():
            candidate_rows = (
                await session.execute(
                    select(Video)
                    .order_by(Video.published_at.desc())
                    .limit(1000)
                )
            ).scalars().all()
            broadened_total = len(candidate_rows)

        if query.strip() and candidate_rows:
            ql = query.lower()

            def score(v: Video) -> float:
                hay = f"{v.title or ''} {v.description or ''}".lower()
                # Token-ish normalization: collapse whitespace
                hay = " ".join(hay.split())
                qn = " ".join(ql.split())
                return float(difflib.SequenceMatcher(None, qn, hay).ratio())

            def sort_key(v: Video):
                sc = score(v)
                pa = v.published_at or datetime.min
                try:
                    ts = pa.timestamp()
                except Exception:
                    ts = 0.0
                # Primary: higher score first; Secondary: published_at per requested order
                if sort == "published_asc":
                    return (-sc, ts)
                else:
                    return (-sc, -ts)

            ranked = sorted(candidate_rows, key=sort_key)
            total = total_count if had_terms and broadened_total is None else len(ranked)
            start = (page - 1) * per_page
            items = ranked[start:start + per_page]
        else:
            # No RapidFuzz: simple contains filter and date order
            total = total_count
        order_clause = Video.published_at.desc() if sort != "published_asc" else Video.published_at.asc()
        items = (
                await session.execute(
                    select(Video)
                    .where(cond)
            .order_by(order_clause)
                    .offset((page - 1) * per_page)
                    .limit(per_page)
                )
            ).scalars().all()

    return int(total or 0), items
