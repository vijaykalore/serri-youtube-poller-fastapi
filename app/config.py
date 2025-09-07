from __future__ import annotations

import os
from functools import lru_cache
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from a local .env if present
load_dotenv()


class Settings(BaseModel):
    author: str = "Vijay Kalore"
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/serri_videos"
    )
    youtube_api_keys: list[str] = (
        [k.strip() for k in os.getenv("YOUTUBE_API_KEYS", "").split(",") if k.strip()]
    )
    youtube_query: str = os.getenv("YOUTUBE_QUERY", "cricket")
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "10"))
    page_size_default: int = int(os.getenv("PAGE_SIZE_DEFAULT", "20"))
    page_size_max: int = 100
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "info")


@lru_cache
def get_settings() -> Settings:
    return Settings()
