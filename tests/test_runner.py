"""Tests for the batch runner and daily rate limiting."""

from datetime import UTC, datetime

from agent.models import Application, ApplicationStatus, Job, JobSource
from agent.ratelimit import (
    COUNTED_STATUSES,
    _local_day,
    applied_today,
    remaining_today,
)
from agent.runner import BatchResult, _dedupe


def _job(url: str, company: str = "Acme", title: str = "SDET") -> Job:
    return Job(
        id=url or f"{company}:{title}",
        title=title,
        company=company,
        url=url,
        source=JobSource.MANUAL,
    )


# ---------------------------------------------------------------- dedupe

def test_dedupe_by_url():
    jobs = [_job("https://a"), _job("https://a"), _job("https://b")]
    assert len(_dedupe(jobs)) == 2


def test_dedupe_by_company_title_when_url_blank():
    jobs = [_job("", "Acme", "SDET"), _job("", "Acme", "SDET"), _job("", "Beta", "SDET")]
    assert len(_dedupe(jobs)) == 2


def test_dedupe_is_case_insensitive_on_pair():
    jobs = [_job("", "Acme", "SDET"), _job("", "acme", "sdet")]
    assert len(_dedupe(jobs)) == 1


def test_dedupe_preserves_order():
    jobs = [_job("https://a"), _job("https://b"), _job("https://a")]
    out = _dedupe(jobs)
    assert [j.url for j in out] == ["https://a", "https://b"]


# ------------------------------------------------------------ rate limit

def test_counted_statuses_are_submissions():
    assert ApplicationStatus.APPLIED in COUNTED_STATUSES
    assert ApplicationStatus.NOTIFY_ONLY in COUNTED_STATUSES
    # A queued/failed job must not consume quota.
    assert ApplicationStatus.QUEUED not in COUNTED_STATUSES
    assert ApplicationStatus.FAILED not in COUNTED_STATUSES


def test_local_day_handles_naive_and_aware():
    naive = datetime(2026, 9, 22, 12, 0)  # noqa: DTZ001 - naive input is the case under test
    aware = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    assert _local_day(naive).year == 2026
    assert _local_day(aware).year == 2026


def test_applied_today_counts_only_today(tmp_path):
    from agent.store import AppStore

    store = AppStore(directory=tmp_path)
    today = datetime.now(UTC)

    fresh = Application(id="a1", job=_job("https://x"), status=ApplicationStatus.APPLIED)
    fresh.updated_at = today
    store.save(fresh)

    # A job counted yesterday must not reduce today's capacity.
    old = Application(id="a2", job=_job("https://y"), status=ApplicationStatus.APPLIED)
    old.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    store.save(old)

    queued = Application(id="a3", job=_job("https://z"), status=ApplicationStatus.QUEUED)
    queued.updated_at = today
    store.save(queued)

    assert applied_today(store) == 1
    assert remaining_today(store) >= 0


def test_remaining_today_never_negative(tmp_path, monkeypatch):
    from agent.store import AppStore

    store = AppStore(directory=tmp_path)
    from agent.config import get_settings

    monkeypatch.setattr(get_settings(), "daily_rate_limit", 0)
    assert remaining_today(store) == 0


# ---------------------------------------------------------- batch result

def test_batch_summary_mentions_counts():
    r = BatchResult(searched=10, seen_before=3, processed=7, applied=5)
    text = r.summary()
    assert "jobs found" in text
    assert "10" in text
    assert "applied" in text


def test_batch_summary_hides_zero_extras():
    r = BatchResult(searched=1, processed=1, applied=1)
    text = r.summary()
    assert "daily limit" not in text
    assert "replies handled" not in text


def test_batch_summary_shows_limit_skips():
    r = BatchResult(skipped_no_capacity=4)
    assert "skipped (daily limit) : 4" in r.summary()
