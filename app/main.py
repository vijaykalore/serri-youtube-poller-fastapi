from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import os
from .api.videos import router as videos_router
from .poller import BackgroundPoller

app = FastAPI(title="Serri Backend Assignment", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

poller = BackgroundPoller()


@app.on_event("startup")
async def startup_event():
  if os.getenv("DISABLE_POLLER", "0") != "1":
    await poller.start()


@app.on_event("shutdown")
async def shutdown_event():
    await poller.stop()


@app.get("/", response_class=HTMLResponse)
async def index():
    # lightweight static dashboard
    return """
    <html>
      <head>
        <title>Serri — Videos</title>
        <style>
          body { background: #f6f7fb; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 0; padding: 20px; }
          .container { max-width: 960px; margin: 0 auto; }
          h1 { color: #2d313d; }
          .search { display: flex; gap: 8px; margin: 16px 0; }
          input[type=text] { flex: 1; padding: 10px 12px; border-radius: 8px; border: 1px solid #dcdfe6; }
          button { background: #2d7be0; color: white; border: 0; padding: 10px 14px; border-radius: 8px; cursor: pointer; }
          .card { background: #fff; border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,0.06); padding: 16px; display: flex; gap: 16px; margin-bottom: 12px; }
          .thumb { width: 200px; height: 112px; background: #eee; border-radius: 8px; overflow: hidden; }
          .thumb img { width: 100%; height: 100%; object-fit: cover; }
          .title { font-size: 18px; margin: 0 0 6px; }
          .meta { color: #667085; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Serri — Videos</h1>
          <div class="search">
            <input id="q" type="text" placeholder="Search title and description..." />
            <button onclick="load(1)">Search</button>
          </div>
          <div id="list"></div>
        </div>
        <script>
          async function fetchJSON(url){ const r = await fetch(url); return await r.json(); }
          function itemCard(it){
            const th = it.thumbnails?.high?.url || it.thumbnails?.default?.url || '';
            const link = `https://www.youtube.com/watch?v=${it.video_id}`;
            return `
              <div class="card">
                <div class="thumb">${th ? `<a href="${link}" target="_blank"><img src="${th}"/></a>` : ''}</div>
                <div>
                  <h3 class="title"><a href="${link}" target="_blank">${it.title || '(no title)'}</a></h3>
                  <div class="meta">${new Date(it.published_at).toLocaleString()} — ${it.channel_title || ''}</div>
                  <p>${(it.description || '').slice(0, 220)}</p>
                </div>
              </div>`;
          }
          async function load(page){
            const q = document.getElementById('q').value.trim();
            const base = q ? `/api/videos/search?q=${encodeURIComponent(q)}` : '/api/videos';
            const data = await fetchJSON(`${base}&page=${page}&per_page=20`);
            const list = document.getElementById('list');
            list.innerHTML = data.items.map(itemCard).join('');
          }
          load(1);
        </script>
      </body>
    </html>
    """


app.include_router(videos_router)
