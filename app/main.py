from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import os
from .api.videos import router as videos_router
from .poller import BackgroundPoller
from .db import get_session_maker
from .db import create_all_for_testing, ensure_pg_extensions
from .db import Base
from .config import get_settings
import app.models  # ensure models are registered on Base.metadata

app = FastAPI(title="Serri Backend Assignment", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

poller = BackgroundPoller()
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
async def startup_event():
  # Bootstrap schema on first run to avoid 500s (guarded for safety)
  try:
    settings = get_settings()
    # On Postgres, enable required extensions (e.g., pg_trgm for similarity())
    await ensure_pg_extensions()
    if os.getenv("BOOTSTRAP_DB", "1") == "1":
      await create_all_for_testing(Base.metadata)
  except Exception:
    # Ignore startup schema errors; API will surface errors if any persist
    pass
  if os.getenv("DISABLE_POLLER", "0") != "1":
    await poller.start()


@app.on_event("shutdown")
async def shutdown_event():
    await poller.stop()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
  return templates.TemplateResponse("index.html", {"request": request})


app.include_router(videos_router)
