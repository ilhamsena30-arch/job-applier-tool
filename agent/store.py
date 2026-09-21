"""Simple JSON-file application store (so replies can re-load the original job)."""

from __future__ import annotations

import json
from pathlib import Path

from agent.config import get_settings
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

    def load(self, app_id: str) -> Application:
        return Application(**json.loads(self._path(app_id).read_text(encoding="utf-8")))

    def list(self) -> list[Application]:
        return [self.load(p.stem) for p in self.dir.glob("*.json")]
