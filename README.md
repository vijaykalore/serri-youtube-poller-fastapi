# Serri — YouTube Poller Backend

Reviewer quick note: For fastest review, see SUBMISSION.md for a condensed run/validate guide. TL;DR — copy .env.example to .env, then `docker compose up -d --build`, open http://localhost:8000.

Author: Vijay kalore · Email: vijaykalore.ds2gmail.com · Role: Candidate — Backend Engineer · Company: Serri

A Dockerized FastAPI service that continuously polls the YouTube Data v3 Search API for the latest videos for a predefined query, stores them with indexes, and exposes:
- A paginated list API sorted by published datetime (desc)
- A search API on title + description with partial/reordered match support
- An optional dashboard to browse/search videos

Submission date: September 8, 2025

## Quick start (Docker Compose)

1. Copy env and edit variables:
   
	```bash
	cp .env.example .env
	```

2. Start services:
   
	```bash
	docker-compose up --build
	```

App: http://localhost:8000 · OpenAPI docs: http://localhost:8000/docs

### Build a Docker image locally

```powershell
# Build and tag with your Docker Hub username
docker build -t vijaykalore/serri-backend:latest .

# Optional: if Docker Hub CDN is temporarily unreachable on your network,
# use an alternative mirror by overriding the base image ARG
docker build --build-arg PYTHON_IMAGE=python:3.11-bookworm -t vijaykalore/serri-backend:latest .

# Run the image (expects a Postgres URL; easiest via docker compose)
docker run --rm -p 8000:8000 --env-file .env vijaykalore/serri-backend:latest

# Push to Docker Hub after login
docker login
docker push vijaykalore/serri-backend:latest
```

## Local (without Docker)

Two options:

1) SQLite (easiest; Windows/Python 3.13 friendly)

```powershell
# 1) Create and activate a virtual environment
python -m venv .venv
. .\.venv\Scripts\Activate.ps1

# 2) Install SQLite-friendly dependencies
pip install -r requirements-sqlite.txt

# 3) Use SQLite dev DB and disable the background poller while developing
$env:DATABASE_URL = "sqlite+aiosqlite:///./dev.db"; $env:DISABLE_POLLER = "1"

# 4) Provide YouTube API config via .env (recommended)
#    Copy the example and edit keys/query inside the file
copy .env.example .env

# 5) Run the app
uvicorn app.main:app --reload
```

Notes:
- If you prefer to avoid editing a file, you can set env vars directly in your shell:
	- `$env:YOUTUBE_API_KEYS = "KEY1,KEY2"`
	- `$env:YOUTUBE_QUERY = "cricket"`
- On Windows with Anaconda on PATH, prefer the helper script to force the project venv: `scripts\run_dev.ps1`.

2) PostgreSQL (full features)

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/serri_videos"
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Tip: If you have Anaconda on PATH, uvicorn may spawn the reloader under Anaconda. Use the helper script to force the venv:

```powershell
scripts\run_dev.ps1
```

## Endpoints

- GET /api/videos?page=1&per_page=20 — list stored videos (desc by published_at)
- GET /api/videos/search?q=tea how&page=1&per_page=20 — search by title+description
- POST /api/videos/_fetch_now — fetch latest from YouTube immediately
- POST /api/videos/_seed — seed demo rows (SQLite dev only)

Optional filters and sorting:
- `channel` — filter by channel title (contains, case-insensitive)
- `sort` — `published_desc` (default) or `published_asc`

Example:

```bash
curl "http://localhost:8000/api/videos?page=1&per_page=5"
curl "http://localhost:8000/api/videos/search?q=cric mat&page=1&per_page=5"
curl "http://localhost:8000/api/videos?channel=ESPN&sort=published_asc&page=1&per_page=6"
```

## Environment variables

See `.env.example`

- DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/serri_videos
- YOUTUBE_API_KEYS=KEY1,KEY2
- YOUTUBE_QUERY=cricket
- POLL_INTERVAL=10
- PAGE_SIZE_DEFAULT=20
- APP_HOST=0.0.0.0
- APP_PORT=8000
- LOG_LEVEL=info

## Data model

Table: `videos`

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

- PostgreSQL: Full Text Search (to_tsvector/websearch_to_tsquery) + pg_trgm similarity for partial/typo/reordered matches.
- SQLite (local/tests): tokenized ILIKE filter plus fuzzy ranking in Python to handle reordered words and minor typos.

Trade-offs: FTS is powerful and fast at scale; trigram helps partials. SQLite fallback is simpler and good for dev.

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

Notes: Tests default to SQLite and disable the poller. Set `DATABASE_URL` to Postgres to run against Postgres.

## Dashboard

- Available at the root path `/`.
- Tailwind-based UI with a vibrant gradient background, search with keyboard shortcut (Ctrl/Cmd+K), pagination, “Fetch now,” and a “Seed demo” button for instant local data.


## Submission

Preferred stack: Python + FastAPI. Send the repo link to wasil@serri.club.
## Author

- Name: Vijay kalore
- Email: vijaykalore.ds@gmail.com
- Company: Serri

Delivery note: This submission was prepared by Vijay kalore for the Serri hiring assignment.
