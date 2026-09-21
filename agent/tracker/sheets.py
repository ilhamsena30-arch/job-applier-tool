"""Google Sheets tracker for job applications.

Uses a service account. The sheet must be shared (View/Edit) with the service
account email before writes will succeed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from agent.config import get_settings
from agent.models import Application, ApplicationStatus

HEADER = [
    "id",
    "status",
    "score",
    "company",
    "title",
    "location",
    "url",
    "source",
    "easy_apply",
    "missing_skills",
    "recording_path",
    "created_at",
    "updated_at",
    "email_sent_at",
    "reply_received_at",
    "notes",
]

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class Tracker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._service: Any | None = None

    @property
    def service(self) -> Any:
        if self._service is None:
            creds_file = self.settings.google_credentials
            if not creds_file.exists():
                raise FileNotFoundError(
                    f"Google credentials file not found: {creds_file}"
                )
            creds = service_account.Credentials.from_service_account_file(
                str(creds_file), scopes=_SCOPES
            )
            self._service = build("sheets", "v4", credentials=creds)
        return self._service

    @property
    def sheet_id(self) -> str:
        if not self.settings.spreadsheet_id:
            raise ValueError("SPREADSHEET_ID is not set in .env")
        return self.settings.spreadsheet_id

    def _ensure_header(self) -> None:
        """Create the header row if the sheet is empty."""
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.sheet_id, range="A1:Q1")
            .execute()
        )
        if not result.get("values"):
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range="A1",
                valueInputOption="RAW",
                body={"values": [HEADER]},
            ).execute()

    def upsert(self, app: Application) -> None:
        """Insert or update the row for this application (keyed by id)."""
        self._ensure_header()
        row = _app_to_row(app)
        # Find existing row by id in column A.
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.sheet_id, range="A:A")
            .execute()
        )
        values = result.get("values", [])
        row_index = None
        for i, v in enumerate(values):
            if v and v[0] == app.id:
                row_index = i + 1  # 1-based
                break

        if row_index is None:
            # Append a new row.
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range="A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
        else:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"A{row_index}",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()


def _app_to_row(app: Application) -> list[Any]:
    job = app.job
    match = app.match
    return [
        app.id,
        app.status.value,
        match.score if match else "",
        job.company,
        job.title,
        job.location,
        job.url,
        job.source.value,
        "yes" if job.easy_apply else "no",
        ", ".join(match.missing_skills) if match else "",
        app.recording_path,
        _ts(app.created_at),
        _ts(app.updated_at),
        _ts(app.email_sent_at),
        _ts(app.reply_received_at),
        app.notes,
    ]


def _ts(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


# Keep ApplicationStatus imported for type checks elsewhere.
__all__ = ["ApplicationStatus", "Tracker"]
