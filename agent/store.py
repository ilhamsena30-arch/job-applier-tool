"""Simple JSON-file application store (so replies can re-load the original job)."""

from __future__ import annotations

import json
from pathlib import Path

from agent.config import get_settings
from agent.identity import canonical_job_key
from agent.models import Application


class AppStore:
    def __init__(self, directory: Path | None = None) -> None:
        settings = get_settings()
        self.dir = directory or (settings.recordings / "apps")
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, app_id: str) -> Path:
        return self.dir / f"{app_id}.json"

    def save(self, app: Application) -> None:
        self._path(app.id).write_text(app.model_dump_json(indent=2), encoding="utf-8")
        # Prune on write so duplicates can never re-accumulate (see dedupe()).
        self.dedupe(protect_id=app.id)

    def dedupe(self, protect_id: str | None = None) -> int:
        """Delete older records sharing a canonical job key; return how many.

        Job-board URLs carry per-visit tracking parameters, so the same opening
        was once stored repeatedly. Keep only the newest record per canonical
        key; the just-saved record (`protect_id`) always wins ties.
        """
        apps = self.list()
        newest: dict[str, tuple[str, float]] = {}
        for app in apps:
            key = canonical_job_key(app.job.url, app.job.company, app.job.title)
            stamp = (app.updated_at or app.created_at).timestamp()
            if protect_id and app.id == protect_id:
                stamp = float("inf")
            current = newest.get(key)
            if current is None or stamp > current[1]:
                newest[key] = (app.id, stamp)
        keep = {app_id for app_id, _ in newest.values()}
        removed = 0
        for app in apps:
            if app.id not in keep:
                self._path(app.id).unlink(missing_ok=True)
                removed += 1
        return removed

    def load(self, app_id: str) -> Application:
        return Application(**json.loads(self._path(app_id).read_text(encoding="utf-8")))

    def list(self) -> list[Application]:
        return [self.load(p.stem) for p in self.dir.glob("*.json")]
