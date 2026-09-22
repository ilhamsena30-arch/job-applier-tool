"""Batch runner: search -> match -> route -> apply -> track -> email -> replies.

This is what `python -m agent auto` drives. One batch:

  1. Poll the inbox and handle any replies from the user (step 4c).
  2. Run every configured search query across the job boards.
  3. De-duplicate, and skip anything already in the app store.
  4. For each job: match -> route -> apply/notify -> track -> email.
  5. Stop early when the daily rate limit is reached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.config import get_settings
from agent.models import Application, ApplicationStatus, Job, Resume
from agent.orchestrator import Orchestrator
from agent.ratelimit import applied_today, remaining_today
from agent.store import AppStore


@dataclass
class BatchResult:
    searched: int = 0
    seen_before: int = 0
    processed: int = 0
    applied: int = 0
    pending: int = 0
    notify_only: int = 0
    failed: int = 0
    skipped_no_capacity: int = 0
    replies_handled: int = 0
    applications: list[Application] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "Batch complete",
            "=" * 60,
            f"  jobs found            : {self.searched}",
            f"  already seen (skipped): {self.seen_before}",
            f"  processed             : {self.processed}",
            f"    applied             : {self.applied}",
            f"    pending (emailed)   : {self.pending}",
            f"    notify-only         : {self.notify_only}",
            f"    failed              : {self.failed}",
        ]
        if self.skipped_no_capacity:
            lines.append(f"  skipped (daily limit) : {self.skipped_no_capacity}")
        if self.replies_handled:
            lines.append(f"  replies handled       : {self.replies_handled}")
        lines.append("=" * 60)
        return "\n".join(lines)


def _dedupe(jobs: list[Job]) -> list[Job]:
    """Drop duplicate jobs.

    When a job has a URL, the URL is the identity — the same company can post
    the same title in several locations, and those are distinct openings.
    The company+title pair is only used as a fallback when the URL is missing.
    """
    seen_url: set[str] = set()
    seen_pair: set[tuple[str, str]] = set()
    out: list[Job] = []
    for job in jobs:
        url = (job.url or "").strip()
        if url:
            if url in seen_url:
                continue
            seen_url.add(url)
        else:
            pair = (job.company.strip().lower(), job.title.strip().lower())
            if pair in seen_pair:
                continue
            seen_pair.add(pair)
        out.append(job)
    return out


def run_batch(
    orchestrator: Orchestrator | None = None,
    resume: Resume | None = None,
    *,
    queries: list[str] | None = None,
    location: str | None = None,
    limit_per_query: int | None = None,
    handle_replies: bool = True,
    dry_run: bool | None = None,
    log=print,
) -> BatchResult:
    """Run one full batch. Returns a summary of what happened."""
    from agent.resume.extract import load_resume
    from agent.search.registry import search_all

    settings = get_settings()
    # dry_run argument wins; otherwise fall back to AUTO_SUBMIT in .env.
    submit = settings.auto_submit if dry_run is None else not dry_run
    orch = orchestrator or Orchestrator(dry_run=not submit)
    resume = resume or load_resume()
    store = AppStore()
    result = BatchResult()

    queries = queries if queries is not None else settings.queries
    location = location if location is not None else settings.search_location
    limit = limit_per_query if limit_per_query is not None else settings.search_limit

    log(f"Daily applications used: {applied_today(store)}/{settings.daily_rate_limit}")

    # 1. Replies first, so a user answer is acted on before new work starts.
    if handle_replies:
        try:
            from agent.email.receiver import EmailReceiver

            receiver = EmailReceiver()

            def _handle(reply):
                log(f"  reply from {reply.sender}: {reply.subject[:60]}")
                orch.handle_reply(reply)
                result.replies_handled += 1

            receiver.poll(_handle)
        except Exception as exc:  # noqa: BLE001 - inbox trouble must not stop the batch
            log(f"  (skipping inbox poll: {type(exc).__name__}: {exc})")

    # 2. Search.
    known_ids = {a.job.id for a in store.list()}
    known_urls = {a.job.url for a in store.list() if a.job.url}
    found: list[Job] = []
    for query in queries:
        log(f"Searching: {query!r} in {location or 'remote'} ...")
        try:
            jobs = search_all(orch._browser(), query, location, limit_per_board=limit)
        except Exception as exc:  # noqa: BLE001 - one bad board must not stop others
            log(f"  search failed: {type(exc).__name__}: {exc}")
            continue
        log(f"  found {len(jobs)}")
        found.extend(jobs)

    found = _dedupe(found)
    result.searched = len(found)

    # 3/4. Process.
    for job in found:
        if remaining_today(store) <= 0:
            result.skipped_no_capacity += 1
            continue
        if job.id in known_ids or (job.url and job.url in known_urls):
            result.seen_before += 1
            continue

        log(f"→ {job.company} — {job.title}")
        try:
            app = orch.process_job(job, resume)
        except Exception as exc:  # noqa: BLE001 - continue with the next job
            log(f"  failed: {type(exc).__name__}: {exc}")
            result.failed += 1
            continue

        # The orchestrator persists to the store; keep our index in step.
        result.applications.append(app)
        result.processed += 1
        known_ids.add(job.id)

        status = app.status
        if status is ApplicationStatus.APPLIED:
            result.applied += 1
            log(f"  applied (score {app.match.score if app.match else '?'})")
        elif status is ApplicationStatus.NOTIFY_ONLY:
            result.notify_only += 1
            log("  notify-only (Easy Apply) — emailed you the link")
        elif status in (ApplicationStatus.PENDING, ApplicationStatus.AWAITING_REPLY):
            result.pending += 1
            log(f"  pending (score {app.match.score if app.match else '?'}) — emailed you")
        else:
            result.failed += 1
            log(f"  {status.value}")

    return result
