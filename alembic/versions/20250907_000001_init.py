"""init videos table

Revision ID: 20250907_000001
Revises: 
Create Date: 2025-09-07 00:00:01

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250907_000001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        'videos',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('video_id', sa.Text(), nullable=False, unique=True),
        sa.Column('title', sa.Text()),
        sa.Column('description', sa.Text()),
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), index=True),
        sa.Column('thumbnails', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('channel_id', sa.Text()),
        sa.Column('channel_title', sa.Text()),
        sa.Column('raw_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_videos_published_at_desc', 'videos', ['published_at'])
    # Full text search index
    op.execute("CREATE INDEX IF NOT EXISTS idx_videos_fts ON videos USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')))")
    # Trigram indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_videos_title_trgm ON videos USING GIN (title gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_videos_description_trgm ON videos USING GIN (description gin_trgm_ops)")


def downgrade() -> None:
    op.drop_index('idx_videos_description_trgm', table_name='videos')
    op.drop_index('idx_videos_title_trgm', table_name='videos')
    op.drop_index('idx_videos_fts', table_name='videos')
    op.drop_index('idx_videos_published_at_desc', table_name='videos')
    op.drop_table('videos')
