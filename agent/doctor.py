"""Setup diagnostics: `python -m agent doctor`.

Checks every prerequisite the agent needs and reports exactly what is missing,
so misconfiguration is caught before it surfaces as a confusing runtime error.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from agent.config import ROOT, get_settings


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class Check:
    name: str
    status: Status
    detail: str = ""
    fix: str = ""


@dataclass
class DoctorReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> None:
        self.checks.append(check)

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.FAIL]

    @property
    def warned(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.WARN]

    @property
    def ok(self) -> bool:
        return not self.failed


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_python() -> Check:
    import sys

    v = sys.version_info
    if v >= (3, 11):
        return Check("Python version", Status.OK, f"{v.major}.{v.minor}.{v.micro}")
    return Check(
        "Python version",
        Status.FAIL,
        f"{v.major}.{v.minor}.{v.micro} (need >= 3.11)",
        "Install Python 3.11+ and recreate the venv.",
    )


def check_package(module: str, label: str, fix: str) -> Check:
    try:
        mod = __import__(module)
        version = getattr(mod, "__version__", "")
        return Check(label, Status.OK, version or "installed")
    except ImportError:
        return Check(label, Status.FAIL, "not installed", fix)


def check_playwright_browser() -> Check:
    """Chromium is only needed for the Playwright fallback engine."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return Check("Chromium (fallback)", Status.SKIP, "playwright not installed")
    try:
        pw = sync_playwright().start()
        path = pw.chromium.executable_path
        pw.stop()
    except Exception as exc:  # noqa: BLE001 - any failure means "not resolvable"
        return Check(
            "Chromium (fallback)",
            Status.WARN,
            f"could not resolve ({exc})",
            "Optional: python -m playwright install chromium",
        )
    if path and Path(path).exists():
        return Check("Chromium (fallback)", Status.OK, "installed")
    return Check(
        "Chromium (fallback)",
        Status.WARN,
        "binary not found",
        "Optional: python -m playwright install chromium",
    )


def check_aihawk_engine() -> Check:
    """The AIHawk anti-detect Firefox is the default engine."""
    try:
        from invisible_playwright import InvisiblePlaywright  # noqa: F401
    except ImportError:
        return Check(
            "AIHawk engine (default)",
            Status.FAIL,
            "invisible-playwright not installed",
            "pip install -r requirements.txt",
        )
    try:
        from invisible_playwright._engine import resolve_executable

        path = resolve_executable(None)
    except Exception as exc:  # noqa: BLE001 - any failure means "not fetched yet"
        return Check(
            "AIHawk engine (default)",
            Status.WARN,
            f"binary not fetched ({exc})",
            "python -m invisible_playwright fetch",
        )
    if path and Path(path).exists():
        return Check("AIHawk engine (default)", Status.OK, str(path.name))
    return Check(
        "AIHawk engine (default)",
        Status.WARN,
        "binary not found",
        "python -m invisible_playwright fetch",
    )


def check_env_file() -> Check:
    path = ROOT / ".env"
    if path.exists():
        return Check(".env file", Status.OK, str(path))
    return Check(
        ".env file",
        Status.FAIL,
        "missing",
        "cp .env.example .env  (then fill it in)",
    )


def check_deepseek() -> Check:
    s = get_settings()
    if s.deepseek_api_key and s.deepseek_api_key.startswith("sk-"):
        return Check("DeepSeek API key", Status.OK, f"...{s.deepseek_api_key[-6:]}")
    return Check(
        "DeepSeek API key",
        Status.FAIL,
        "not set",
        "Get a key at https://platform.deepseek.com and set DEEPSEEK_API_KEY",
    )


def check_gmail() -> Check:
    s = get_settings()
    if s.gmail_user and s.gmail_app_password:
        return Check("Gmail credentials", Status.OK, s.gmail_user)
    return Check(
        "Gmail credentials",
        Status.FAIL,
        "not set",
        "Set GMAIL_USER + GMAIL_APP_PASSWORD (16-char App Password, needs 2FA)",
    )


def check_google_sheets() -> list[Check]:
    out: list[Check] = []
    s = get_settings()
    creds = s.google_credentials
    if creds.exists():
        out.append(Check("Google credentials file", Status.OK, creds.name))
    else:
        out.append(
            Check(
                "Google credentials file",
                Status.FAIL,
                f"missing: {creds}",
                "Create a service-account key in Google Cloud Console -> save as credentials.json",
            )
        )

    if s.spreadsheet_id:
        out.append(Check("Spreadsheet ID", Status.OK, s.spreadsheet_id[:12] + "..."))
    else:
        out.append(
            Check(
                "Spreadsheet ID",
                Status.FAIL,
                "not set",
                "Set SPREADSHEET_ID from the sheet URL (and share the sheet with the service account)",
            )
        )
    return out


def check_resume() -> list[Check]:
    out: list[Check] = []
    s = get_settings()
    if s.resume_pdf.exists():
        kb = s.resume_pdf.stat().st_size // 1024
        out.append(Check("Resume PDF", Status.OK, f"{s.resume_pdf.name} ({kb} KB)"))
    else:
        out.append(
            Check(
                "Resume PDF",
                Status.FAIL,
                f"missing: {s.resume_pdf_path}",
                "Put your resume at data/resume.pdf",
            )
        )

    if s.resume_json.exists():
        out.append(Check("Resume JSON", Status.OK, s.resume_json.name))
    else:
        out.append(
            Check(
                "Resume JSON",
                Status.FAIL,
                "not generated yet",
                "python -m agent extract",
            )
        )
    return out


def check_port(host: str = "127.0.0.1", port: int = 8000) -> Check:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:
            return Check(
                f"Dashboard port {port}",
                Status.WARN,
                "in use",
                "The dashboard auto-picks the next free port; or stop the other process.",
            )
    return Check(f"Dashboard port {port}", Status.OK, "free")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all() -> DoctorReport:
    report = DoctorReport()

    report.add(check_python())
    report.add(check_package("pydantic", "pydantic", "pip install -r requirements.txt"))
    report.add(check_package("fastapi", "fastapi", "pip install -r requirements.txt"))
    report.add(
        check_package(
            "openai", "openai (DeepSeek client)", "pip install -r requirements.txt"
        )
    )
    report.add(check_package("pymupdf", "pymupdf (PDF)", "pip install -r requirements.txt"))
    report.add(check_aihawk_engine())
    report.add(check_playwright_browser())

    report.add(check_env_file())
    report.add(check_deepseek())
    report.add(check_gmail())
    for c in check_google_sheets():
        report.add(c)
    for c in check_resume():
        report.add(c)
    report.add(check_port())

    return report


_SYMBOL = {
    Status.OK: "[ OK ]",
    Status.WARN: "[WARN]",
    Status.FAIL: "[FAIL]",
    Status.SKIP: "[SKIP]",
}


def format_report(report: DoctorReport) -> str:
    lines = ["Setup check", "=" * 60]
    for c in report.checks:
        line = f"{_SYMBOL[c.status]} {c.name}"
        if c.detail:
            line += f" — {c.detail}"
        lines.append(line)
        if c.status is Status.FAIL and c.fix:
            lines.append(f"         fix: {c.fix}")

    lines.append("=" * 60)
    n_fail, n_warn = len(report.failed), len(report.warned)
    if n_fail == 0 and n_warn == 0:
        lines.append("All checks passed. You're ready to go.")
    elif n_fail == 0:
        lines.append(f"Ready to go, with {n_warn} warning(s).")
    else:
        lines.append(f"{n_fail} problem(s) to fix, {n_warn} warning(s).")
    return "\n".join(lines)
