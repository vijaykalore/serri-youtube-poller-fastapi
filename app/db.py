from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_Session: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine, _Session
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
        _Session = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _Session
    if _Session is None:
        _get_engine()
    assert _Session is not None
    return _Session


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_for_testing(metadata) -> None:
    """Create tables for non-PostgreSQL testing environments (e.g., SQLite).

    In production we rely on Alembic migrations instead.
    """
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def drop_all_for_testing(metadata) -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
