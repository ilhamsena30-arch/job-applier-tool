"""FastAPI dashboard: live status + recordings list + apply-by-URL."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent.config import get_settings
from agent.models import Job, JobSource
from agent.orchestrator import Orchestrator
from agent.resume.extract import load_resume
from agent.store import AppStore

app = FastAPI(title="Job Applier Agent", version="0.1.0")


class ApplyRequest(BaseModel):
    url: str
    title: str = ""
    company: str = ""
    description: str = ""
    easy_apply: bool = False


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    settings = get_settings()
    store = AppStore()
    apps = store.list()
    rows = "".join(
        f"<tr><td>{a.status.value}</td><td>{a.job.company}</td><td>{a.job.title}</td>"
        f"<td>{a.match.score if a.match else ''}</td><td>{a.job.url[:60]}</td></tr>"
        for a in apps
    )
    recordings = "".join(
        f"<li><a href='/recordings/{p.name}'>{p.name}</a></li>"
        for p in sorted(Path(settings.recordings).glob("*.webm"))
    )
    return f"""<!doctype html><html><head><title>Job Agent</title>
<style>body{{font-family:system-ui;margin:2rem}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:6px 10px}}</style></head><body>
<h1>Job Applier Agent</h1>
<p>Threshold: {settings.confidence_threshold}/100 · Daily limit: {settings.daily_rate_limit}</p>
<h2>Applications</h2>
<table><tr><th>Status</th><th>Company</th><th>Title</th><th>Score</th><th>URL</th></tr>{rows or "<tr><td colspan=5>No applications yet.</td></tr>"}</table>
<h2>Recordings</h2><ul>{recordings or "<li>None</li>"}</ul>
<h2>Apply to a URL</h2>
<form action="/apply" method="post">
<input name="url" placeholder="https://..." style="width:400px" required>
<input name="title" placeholder="Title"><input name="company" placeholder="Company">
<label><input type="checkbox" name="easy_apply"> Easy Apply</label>
<button type="submit">Apply</button></form>
</body></html>"""


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
