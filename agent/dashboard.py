"""FastAPI dashboard: live video stream + status + recordings + apply-by-URL."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from agent import livestream
from agent.config import get_settings
from agent.models import Job, JobSource
from agent.orchestrator import Orchestrator
from agent.resume.extract import load_resume
from agent.store import AppStore

app = FastAPI(title="Job Applier Agent", version="0.2.0")


class ApplyRequest(BaseModel):
    url: str
    title: str = ""
    company: str = ""
    description: str = ""
    easy_apply: bool = False


# ---------------------------------------------------------------------------
# Live video stream (MJPEG)
# ---------------------------------------------------------------------------

@app.get("/stream")
def stream(fps: float = 3.0) -> StreamingResponse:
    """MJPEG live video of the active browser."""
    return StreamingResponse(
        livestream.mjpeg_stream(fps=fps),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/demo/start")
def demo_start() -> dict:
    """Launch a shared demo browser and register it as the stream source."""
    from agent.browser.engine import Browser, BrowserOptions

    def _run():
        browser = Browser(BrowserOptions(headed=False)).launch()
        livestream.set_active_browser(browser)
        try:
            browser.goto("https://example.com")
            import time

            for url in (
                "https://www.indeed.com/",
                "https://www.indeed.com/jobs?q=python+developer&l=remote",
            ):
                browser.goto(url)
                browser.page.wait_for_timeout(4000)
            time.sleep(120)
        finally:
            livestream.clear_active_browser(browser)
            browser.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "demo started", "stream": "/stream"}


@app.get("/demo/stop")
def demo_stop() -> dict:
    livestream.clear_active_browser()
    return {"status": "stopped"}


# ---------------------------------------------------------------------------
# Status page
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    settings = get_settings()
    store = AppStore()
    apps = store.list()
    rows = "".join(
        f"<tr><td>{a.status.value}</td><td>{a.job.company}</td><td>{a.job.title}</td>"
        f"<td>{a.match.score if a.match else ''}</td>"
        f"<td>{a.job.url[:60]}</td></tr>"
        for a in apps
    )
    recordings = "".join(
        f"<li><a href='/recordings/{p.name}'>{p.name}</a></li>"
        for p in sorted(Path(settings.recordings).glob("*.webm"))
    )
    return f"""<!doctype html><html><head><title>Job Agent</title>
<style>
body{{font-family:system-ui;margin:2rem;background:#0f1115;color:#e6e6e6}}
h1,h2{{color:#fff}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #2a2e3a;padding:6px 10px;text-align:left}}
th{{background:#1a1d27}}
a{{color:#7aa2f7}}
.video-wrap{{border:1px solid #2a2e3a;background:#000;max-width:1280px;margin:1rem 0}}
.video-wrap img{{width:100%;display:block}}
button{{background:#3b82f6;color:#fff;border:0;padding:8px 14px;
border-radius:6px;cursor:pointer;margin-right:8px}}
button:hover{{background:#2563eb}}
</style></head><body>
<h1>Job Applier Agent</h1>
<p>Threshold: {settings.confidence_threshold}/100 ·
Daily limit: {settings.daily_rate_limit}</p>

<h2>Live browser</h2>
<p>
  <button onclick="fetch('/demo/start')">Start demo browser</button>
  <button onclick="fetch('/demo/stop')">Stop</button>
  <span style="color:#888">Streams the browser the agent is driving (or the demo).</span>
</p>
<div class="video-wrap"><img src="/stream" alt="Live browser stream"></div>

<h2>Applications</h2>
<table>
<tr><th>Status</th><th>Company</th><th>Title</th><th>Score</th><th>URL</th></tr>
{rows or "<tr><td colspan=5>No applications yet.</td></tr>"}
</table>
<h2>Recordings</h2><ul>{recordings or "<li>None</li>"}</ul>

<h2>Apply to a URL</h2>
<form action="/apply" method="post">
<input name="url" placeholder="https://..." style="width:400px" required>
<input name="title" placeholder="Title"><input name="company" placeholder="Company">
<label><input type="checkbox" name="easy_apply"> Easy Apply</label>
<button type="submit">Apply</button></form>
</body></html>"""


# ---------------------------------------------------------------------------
# Apply (registers the browser so the stream follows the real application)
# ---------------------------------------------------------------------------

@app.post("/apply")
def apply_url(req: ApplyRequest) -> dict:
    resume = load_resume()
    orch = Orchestrator()
    job = Job(
        id=f"web-{abs(hash(req.url)) % 10**12}",
        title=req.title or "Unknown title",
        company=req.company or "Unknown company",
        url=req.url,
        apply_url=req.url,
        source=JobSource.MANUAL,
        description=req.description,
        easy_apply=req.easy_apply,
    )
    app = orch.process_job(job, resume)
    return {
        "id": app.id,
        "status": app.status.value,
        "score": app.match.score if app.match else None,
    }
