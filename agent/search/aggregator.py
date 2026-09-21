"""Aggregator-based job search.

This adapter uses a headful browser to query job aggregators / Google Jobs-style
listings and extract normalized Job records. Board-specific selectors live here
so the rest of the system stays independent of page markup.
"""

from __future__ import annotations

import hashlib

from agent.models import Job, JobSource
from agent.search.base import JobSearchAdapter

# Board-specific extraction is intentionally generic: a real deployment uses the
# browser layer to read search-result cards. Keeping the extraction contract
# small makes it easy to add Indeed/LinkedIn/ATS-specific selectors later.
_SEARCH_URLS = {
    "indeed": "https://www.indeed.com/jobs?q={query}&l={location}",
    "linkedin": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}",
}


class AggregatorSearch(JobSearchAdapter):
    """Search job boards through a browser (delegated by the orchestrator)."""

    def __init__(self, browser) -> None:
        self._browser = browser

    def search(self, query: str, location: str = "", limit: int = 20) -> list[Job]:
        jobs: list[Job] = []
        # The browser layer provides a generic "read list page" primitive;
        # adapters describe how to map cards to jobs.
        for board, url_tpl in _SEARCH_URLS.items():
            url = url_tpl.format(query=query, location=location or "remote")
            cards = self._browser.scrape_job_cards(url, board, limit=limit)
            for card in cards:
                jobs.append(_card_to_job(board, card))
        return jobs


def _card_to_job(board: str, card: dict) -> Job:
    url = card.get("url", "")
    source = JobSource.INDEED if board == "indeed" else JobSource.LINKEDIN
    return Job(
        id=hashlib.sha1(url.encode()).hexdigest()[:16],
        title=card.get("title", ""),
        company=card.get("company", ""),
        location=card.get("location", ""),
        url=url,
        apply_url=card.get("apply_url", url),
        source=source,
        description=card.get("description", ""),
        easy_apply=bool(card.get("easy_apply", False)),
        external_ats=bool(card.get("external_ats", False)),
    )
