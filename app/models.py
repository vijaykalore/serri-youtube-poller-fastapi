from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, Index, JSON, Text, func, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Video(Base):
    __tablename__ = "videos"

    # Use Integer PK to support SQLite AUTOINCREMENT semantics
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(Text, unique=True, index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), index=True)
    thumbnails: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    channel_id: Mapped[str | None] = mapped_column(Text)
    channel_title: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_videos_published_at_desc", "published_at", postgresql_using="btree"),
        {"sqlite_autoincrement": True},
    )
