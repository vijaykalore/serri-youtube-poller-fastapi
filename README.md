# Serri — YouTube poller backend (FastAPI)

I built a small service that keeps pulling the latest YouTube videos for a query (e.g. "cricket"), stores them, and lets you list and search them. It runs in Docker, has a background poller, a couple of APIs, and a simple dashboard.

Reviewer note: if you just want to try it quickly, copy `.env.example` to `.env`, then run `docker compose up -d --build` and open http://localhost:8000. Full details below.

Author: Vijay Kalore · Email: vijaykalore.ds@gmail.com · Date: September 8, 2025

---

## How to run the server

### Option A — Docker Compose (recommended)
1) Create `.env` from the template and (optionally) add your YouTube API keys for live data.

```powershell
copy .env.example .env
# Edit .env and set YOUTUBE_API_KEYS=KEY1,KEY2 (optional for live data)
```

2) Start the stack (Postgres + API/UI):

```powershell
docker compose up -d --build
```

Open:
- UI: http://localhost:8000
- API docs: http://localhost:8000/docs

### Option B — Local, SQLite (no Docker)

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements-sqlite.txt
$env:DATABASE_URL = "sqlite+aiosqlite:///./dev.db"; $env:DISABLE_POLLER = "1"
copy .env.example .env   # optional; edit keys/query later
uvicorn app.main:app --reload
```

### Option C — Local, PostgreSQL

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/serri_videos"
uvicorn app.main:app --reload
```

If you have Anaconda on PATH and the reloader fights your venv, use `scripts\run_dev.ps1`.

---

## How to test the API (PowerShell examples)

Seed demo rows (handy without keys):
```powershell
Invoke-RestMethod http://localhost:8000/api/videos/_seed -Method POST | ConvertTo-Json -Depth 3
```

List videos (paginated, newest first):
```powershell
Invoke-RestMethod "http://localhost:8000/api/videos?page=1&per_page=5" -Method GET | ConvertTo-Json -Depth 4
```

Search by title/description:
```powershell
Invoke-RestMethod "http://localhost:8000/api/videos/search?q=how%20play&page=1&per_page=5" -Method GET | ConvertTo-Json -Depth 4
```

Fetch now from YouTube (shows quota info if blocked):
```powershell
Invoke-RestMethod http://localhost:8000/api/videos/_fetch_now -Method POST | ConvertTo-Json -Depth 5
```

---

## Expected output (shape and examples)

- GET /api/videos returns:

```json
{
  "total": 3,
  "page": 1,
  "per_page": 20,
  "items": [
	 {
		"video_id": "demo-2",
		"title": "How to play cricket",
		"description": "Beginner tutorial",
		"published_at": "2025-09-07T08:23:41.704467Z",
		"thumbnails": { "default": { "url": "..." } },
		"channel_id": "demo-ch",
		"channel_title": "Demo Channel"
	 }
  ]
}
```

- GET /api/videos/search?q=how%20play returns relevant matches for reordered words (e.g., "How to play cricket").

- POST /api/videos/_fetch_now returns something like:

```json
{
  "status": "ok",
  "fetched": 0,
  "inserted": 0,
  "query": "cricket",
  "published_after": null,
  "last_status": 403,
  "last_error": "The request cannot be completed because you have exceeded your quota."
}
```

If you add valid keys and quota is available, `fetched`/`inserted` will be > 0 and the new rows will appear in `/api/videos` immediately.

---

## Live data and private keys

- Put your own keys in `.env` as:

```
YOUTUBE_API_KEYS=KEY1,KEY2,KEY3
YOUTUBE_QUERY=cricket
```

- The background poller runs every `POLL_INTERVAL` seconds (default 10) and calls YouTube with `publishedAfter` anchored to the latest stored item. If a key hits quota (403/429), it is rotated out for a cooldown and the next key is tried.

- The manual fetch endpoint (`/_fetch_now`) is for demonstrations; it tries a few safe time windows and, if empty, does one last request without `publishedAfter` to avoid showing “nothing”. The background poller always uses `publishedAfter` per the spec.

Keep keys private. Don’t commit `.env` — only `.env.example` is in the repo.

---

## How I solved the assignment (short write-up)

1) Framework and shape
	- FastAPI + async SQLAlchemy 2.x for clean async I/O.
	- Postgres in Docker Compose for full-text and trigram search; SQLite fallback for local/tests.

2) Background poller
	- A small async loop (10s interval) calling YouTube Search: `type=video&order=date&publishedAfter=<last_seen>`.
	- Upserts by `video_id` (idempotent) and advances `last_seen` to the latest `published_at` we observed.

3) Data model and indexes
	- Table `videos(video_id, title, description, published_at, thumbnails, channel_id, channel_title, raw_json)` with indexes on `published_at` and unique `video_id`.
	- On Postgres, enable pg_trgm (for similarity) and use FTS (to_tsvector/websearch_to_tsquery) in queries.

4) Search
	- Combine FTS + trigram similarity + ILIKE to handle partial matches and word reordering (e.g., "tea how" matches "How to make tea?").
	- Sort primarily by relevance, secondarily by `published_at` (configurable asc/desc).

5) API keys rotation
	- Accept multiple keys via `YOUTUBE_API_KEYS`. On 403/429, mark a key exhausted for ~10 minutes, switch to the next, and use exponential backoff.

6) Docker & DX
	- Multi-stage Dockerfile; docker-compose with health-checked Postgres; schema bootstrap on startup; read-only source mount for quick iteration.
	- A small Tailwind dashboard at `/` with search, pagination, and buttons for “Fetch now” and “Seed demo”.

7) Tests & CI
	- Tests run in SQLite mode by default; a GitHub Actions workflow installs deps and runs `pytest -q` on push/PR.

---

## Endpoints quick reference

- GET `/api/videos?page=1&per_page=20&channel=&sort=published_desc`
- GET `/api/videos/search?q=how%20play&page=1&per_page=20&sort=published_desc`
- POST `/api/videos/_fetch_now`
- POST `/api/videos/_seed` (enabled for local/dev)

Environment variables (see `.env.example`):

- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/serri_videos`
- `YOUTUBE_API_KEYS=KEY1,KEY2`
- `YOUTUBE_QUERY=cricket`
- `POLL_INTERVAL=10`
- `PAGE_SIZE_DEFAULT=20`
- `APP_HOST=0.0.0.0`, `APP_PORT=8000`
- `LOG_LEVEL=info`

---

## Troubleshooting

- Quota errors: `/_fetch_now` will show `last_status=403` and a message. Add more keys or try later; the poller resumes automatically.
- Postgres similarity() missing: make sure pg_trgm is enabled (this repo enables it on startup for Postgres).
- Port already in use: change `APP_PORT` in `.env` or stop the conflicting process.

---

## License & author

MIT License — see `LICENSE`.

Author: Vijay Kalore (vijaykalore.ds@gmail.com)
