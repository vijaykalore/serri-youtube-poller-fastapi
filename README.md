# Serri — Backend Assignment

> Author: Vijay Kalore · Role: Candidate — Backend Engineer · Company: Serri

This repository contains a Dockerized FastAPI backend that continuously polls the YouTube Data v3 Search API for the latest videos for a configurable search query and stores them in a PostgreSQL database. It exposes endpoints to list and search videos with pagination and a minimal dashboard.

Submission prepared by Vijay Kalore for Serri hiring assignment (September 7, 2025).

## Quick start (Docker Compose)

1. Copy env and edit variables:
   
	```bash
	cp .env.example .env
	```

2. Start services:
   
	```bash
	docker-compose up --build
	```

App will be available at http://localhost:8000 and API at http://localhost:8000/api/videos

## Local (without Docker)

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/serri_videos
alembic upgrade head
uvicorn app.main:app --reload
```

## Endpoints

- GET /api/videos?page=1&per_page=20
- GET /api/videos/search?q=tea how&page=1&per_page=20

Example curl:

```bash
curl http://localhost:8000/api/videos?page=1&per_page=5
curl "http://localhost:8000/api/videos/search?q=cric mat&page=1&per_page=5"
```

## Environment variables

See .env.example

- DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/serri_videos
- YOUTUBE_API_KEYS=KEY1,KEY2
- YOUTUBE_QUERY=cricket
- POLL_INTERVAL=10
- PAGE_SIZE_DEFAULT=20
- APP_HOST=0.0.0.0
- APP_PORT=8000
- LOG_LEVEL=info

## Data model

Table: videos

- id bigint PK
- video_id text unique indexed
- title text
- description text
- published_at timestamptz indexed (DESC)
- thumbnails jsonb
- channel_id text
- channel_title text
- raw_json jsonb
- created_at timestamptz default now()
- updated_at timestamptz default now()

Indexes created by Alembic migration:

- idx_videos_published_at_desc (btree on published_at)
- GIN on to_tsvector('english', title || ' ' || description)
- pg_trgm GIN on title, description

## Search strategy

- Primary: PostgreSQL Full Text Search (to_tsvector/websearch_to_tsquery) + pg_trgm similarity for partials and reordered words.
- Fallback (in tests/SQLite): ILIKE search over title/description.

Trade-offs: FTS is robust for linguistic tokenization and ranking; trigram boosts partial matches. It adds write-time/index costs and requires pg_trgm extension.

## Background fetcher

- Polls YouTube Search API every POLL_INTERVAL seconds (default 10s).
- Uses publishedAfter=last_seen to avoid cached results.
- Stores unique videos by video_id (idempotent upsert) and captures thumbnails and raw snippet JSON.
- API key rotation: supply multiple keys via YOUTUBE_API_KEYS. On 403/429, a key is marked exhausted for 10 minutes and the next available is tried with exponential backoff.

## Scaling notes

- Split poller into a separate worker Deployment or CronJob (K8s), or Celery beat with Redis.
- Use a job queue (Redis/RabbitMQ) for resilient retries and backpressure.
- Horizontal scale API behind a load balancer; DB connection pool tuning; add read replicas for heavy search.
- Rotate and shard API keys; add observability (metrics/logs/traces) and circuit breakers.

## Running tests

```bash
pytest -q
```

Notes: tests default to SQLite and disable the poller; Postgres-only features are mocked/fallbacks.

## Author

- Vijay Kalore — Candidate, Backend Engineer
- Company: Serri

Delivery note: This submission was prepared by Vijay Kalore for Serri hiring assignment.
