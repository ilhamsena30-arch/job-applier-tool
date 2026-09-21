"""LinkedIn job-search adapter.

Drives LinkedIn's public job search via the browser and normalizes the result
cards into `Job` models. Uses the AIHawk anti-detect engine when available.

NOTE: LinkedIn is bot-hostile. Use a dedicated low-value account, keep the
rate conservative, and never auto-submit Easy Apply (handled by the
orchestrator's notify-only policy).
"""

from __future__ import annotations

import hashlib

from agent.browser.engine import Browser
from agent.models import Job, JobSource
from agent.search.base import JobSearchAdapter

_SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}"

# Card selectors (LinkedIn changes these; keep them grouped for easy fixing).
_CARD_SELECTOR = "li.jobs-search-results__list-item"
_TITLE_SELECTOR = "a.job-card-list__title"
_COMPANY_SELECTOR = "span.job-card-container__primary-description"
_LOCATION_SELECTOR = "li.job-card-container__metadata-item"


class LinkedInSearch(JobSearchAdapter):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    def search(self, query: str, location: str = "", limit: int = 20) -> list[Job]:
        url = _SEARCH_URL.format(
            query=query.replace(" ", "%20"),
            location=(location or "remote").replace(" ", "%20"),
        )
        # Warm-up: land on the jobs page first, then run the search.
        self._browser.goto("https://www.linkedin.com/jobs/")
        self._browser.page.wait_for_timeout(2000)
        self._browser.goto(url)
        self._browser.page.wait_for_timeout(2500)  # let cards render

        cards = self._browser.page.locator(_CARD_SELECTOR).all()
        jobs: list[Job] = []
        for card in cards[:limit]:
            try:
                job = self._parse_card(card)
            except Exception:
                continue
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card) -> Job | None:
        try:
            link_el = card.locator(_TITLE_SELECTOR).first
            title = link_el.inner_text().strip()
            url = link_el.get_attribute("href") or ""
        except Exception:
            return None

        company = _safe_text(card, _COMPANY_SELECTOR)
        location = _safe_text(card, _LOCATION_SELECTOR)
        card_text = _safe_text(card, None)

        # Easy Apply detection: LinkedIn shows an "Easy Apply" tag.
        easy_apply = "easy apply" in card_text.lower()

        if url and not url.startswith("http"):
            url = "https://www.linkedin.com" + url

        return Job(
            id=hashlib.sha1(url.encode()).hexdigest()[:16],
            title=title,
            company=company,
            location=location,
            url=url,
            apply_url=url,
            source=JobSource.LINKEDIN,
            description="",
            easy_apply=easy_apply,
            external_ats=not easy_apply and bool(url),
            raw={"card_text": card_text},
        )


def _safe_text(card, selector: str | None) -> str:
    try:
        if selector:
            return card.locator(selector).first.inner_text().strip()
        return card.inner_text().strip()
    except Exception:
        return ""
