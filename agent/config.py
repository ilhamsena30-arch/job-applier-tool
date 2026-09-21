"""Configuration loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the `agent` package directory.
ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All runtime settings. Values come from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- DeepSeek LLM ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_reasoning_model: str = "deepseek-v4-pro"

    # ---- Gmail ----
    gmail_user: str = ""
    gmail_app_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993

    # ---- Google Sheets ----
    google_credentials_file: str = "credentials.json"
    spreadsheet_id: str = ""

    # ---- Data paths ----
    resume_pdf_path: str = "data/resume.pdf"
    resume_json_path: str = "data/resume.json"
    recordings_dir: str = "recordings"

    # ---- Behaviour ----
    confidence_threshold: float = 75.0
    daily_rate_limit: int = 10
    headed: bool = True

    # ---- Convenience helpers ----
    @property
    def resume_pdf(self) -> Path:
        p = Path(self.resume_pdf_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def resume_json(self) -> Path:
        p = Path(self.resume_json_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def recordings(self) -> Path:
        p = Path(self.recordings_dir)
        return p if p.is_absolute() else ROOT / p

    @property
    def google_credentials(self) -> Path:
        p = Path(self.google_credentials_file)
        return p if p.is_absolute() else ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
