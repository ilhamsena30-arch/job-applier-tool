"""Core data models for the job-application agent."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class Experience(BaseModel):
    title: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)


class Education(BaseModel):
    school: str = ""
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""


class Resume(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    website: str = ""
    #: Answers the agent needs for application forms; not on the PDF, so the
    #: user provides them separately (survive re-extraction via resume.json).
    work_authorization: str = ""
    notice_period: str = ""
    salary_expectation: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

    @property
    def years_experience(self) -> int:
        """Rough total years across experience entries (best effort)."""
        total = 0
        for exp in self.experience:
            start, end = exp.start, exp.end
            try:
                sy = int(str(start)[:4])
                ey = int(str(end)[:4]) if end else datetime.now().year
                total += max(0, ey - sy)
            except (ValueError, TypeError):
                continue
        return total


# ---------------------------------------------------------------------------
# Jobs & applications
# ---------------------------------------------------------------------------

class JobSource(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    AGGREGATOR = "aggregator"
    DIRECT_ATS = "direct_ats"
    MANUAL = "manual"


class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    apply_url: str = ""
    source: JobSource = JobSource.MANUAL
    description: str = ""
    easy_apply: bool = False  # LinkedIn Easy Apply / one-click type forms
    external_ats: bool = False  # apply happens on an external ATS site
    raw: dict[str, Any] = Field(default_factory=dict)


class MatchResult(BaseModel):
    score: float = 0.0  # 0-100
    verdict: str = ""  # human-readable summary
    missing_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    suggested_answers: dict[str, str] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class ApplicationStatus(str, Enum):
    QUEUED = "queued"
    MATCHED = "matched"          # scored, awaiting route decision
    APPLYING = "applying"        # form being filled
    APPLIED = "applied"          # success (confirmation page seen)
    PENDING = "pending"          # below threshold -> emailed user
    NOTIFY_ONLY = "notify_only"  # LinkedIn Easy Apply -> emailed link
    AWAITING_REPLY = "awaiting_reply"  # sent pending email, waiting for 4c
    REAPPLYING = "reapplying"    # user answered, filling again
    FAILED = "failed"
    SKIPPED = "skipped"


class Application(BaseModel):
    id: str
    job: Job
    match: MatchResult | None = None
    status: ApplicationStatus = ApplicationStatus.QUEUED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    recording_path: str = ""
    email_sent_at: datetime | None = None
    reply_received_at: datetime | None = None
    notes: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)
