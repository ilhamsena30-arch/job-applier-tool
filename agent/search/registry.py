"""Search orchestration: run all enabled board adapters and merge results.

This is the entrypoint the orchestrator uses for the "auto-search" leg of the
workflow (find jobs -> match -> apply/notify).
"""

from __future__ import annotations

from agent.browser.engine import Browser
from agent.models import Job
from agent.search.base import JobSearchAdapter
from agent.search.indeed import IndeedSearch
from agent.search.linkedin import LinkedInSearch


def build_adapters(browser: Browser) -> list[JobSearchAdapter]:
    """Return the default set of board adapters sharing one browser."""
    return [
        LinkedInSearch(browser),
        IndeedSearch(browser),
    ]


def search_all(
    browser: Browser,
    query: str,
    location: str = "",
    limit_per_board: int = 10,
) -> list[Job]:
    """Search every enabled board and return a de-duplicated job list."""
    seen: set[str] = set()
    jobs: list[Job] = []
    for adapter in build_adapters(browser):
        for job in adapter.search(query, location, limit=limit_per_board):
            key = job.url or f"{job.company}:{job.title}"
            if key in seen:
                continue
            seen.add(key)
            jobs.append(job)
    return jobs
