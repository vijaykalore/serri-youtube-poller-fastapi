# Serri Assignment Submission

This repository implements the required YouTube poller backend with:

- Background async polling every POLL_INTERVAL seconds (default 10s)
- PostgreSQL + SQLAlchemy async, fallback to SQLite for local/tests
- GET /api/videos (paginated, published_at desc)
- GET /api/videos/search (title+description with partial/reordered matches)
- Dockerfile and docker-compose for app + Postgres
- Optional Tailwind dashboard at /
- Multiple YouTube API keys supported (rotation + cooldown)

## How reviewers can run

Option A: Docker Compose

1) Copy env: `.env.example` to `.env` and edit YouTube keys.
2) Start: `docker compose up -d --build`
3) UI: http://localhost:8000  |  API docs: http://localhost:8000/docs

Option B: Local (SQLite)

1) `python -m venv .venv && . .venv/Scripts/activate`
2) `pip install -r requirements-sqlite.txt`
3) `set DATABASE_URL=sqlite+aiosqlite:///./dev.db` and `set DISABLE_POLLER=1`
4) `uvicorn app.main:app --reload`

## Validation

- Seed demo data: POST /api/videos/_seed or UI button "Seed demo"
- List: GET /api/videos
- Search: GET /api/videos/search?q=how%20play
- Manual fetch: POST /api/videos/_fetch_now (shows last_status/last_error)

Notes: If YouTube quota is exceeded, fetching returns last_status=403 and last_error with message. Add more keys to `YOUTUBE_API_KEYS` or try later.
