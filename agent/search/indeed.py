"""Indeed job-search adapter.

Drives Indeed's public search via the browser and normalizes result cards.
Indeed also has bot detection; keep pacing conservative and use the anti-detect
engine when available.
"""

from __future__ import annotations

import hashlib

from agent.browser.engine import Browser
from agent.models import Job, JobSource
from agent.search.base import JobSearchAdapter

_SEARCH_URL = "https://www.indeed.com/jobs?q={query}&l={location}"

_CARD_SELECTOR = "div.job_seen_beacon"
# Title is the card's primary job link. Indeed has used <h2> and <h3> over time,
# so we find the anchor that is a job link (/rc/clk or /viewjob) instead.
_TITLE_LINK_SELECTOR = "a[href*='/rc/clk'], a[href*='/viewjob'], a[href*='/jobs/viewjob']"
_COMPANY_SELECTOR = "span[data-testid='company-name']"
_LOCATION_SELECTOR = "div[data-testid='text-location']"


class IndeedSearch(JobSearchAdapter):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    def search(self, query: str, location: str = "", limit: int = 20) -> list[Job]:
        url = _SEARCH_URL.format(
            query=query.replace(" ", "+"),
            location=(location or "remote").replace(" ", "+"),
        )
        self._warm_up()
        self._browser.goto(url)
        self._browser.page.wait_for_timeout(2500)

        # If a security check blocked us, retry once after a pause.
        if self._is_blocked():
            self._browser.page.wait_for_timeout(5000)
            self._browser.goto(url)
            self._browser.page.wait_for_timeout(2500)

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

    def _warm_up(self) -> None:
        """Land on the homepage first; direct search hits the bot wall more often."""
        try:
            self._browser.goto("https://www.indeed.com/")
            self._browser.page.wait_for_timeout(2000)
        except Exception:
            pass

    def _is_blocked(self) -> bool:
        try:
            title = self._browser.page.title().lower()
            return "security check" in title or "tunggu" in title
        except Exception:
            return False

    def _parse_card(self, card) -> Job | None:
        try:
            link_el = card.locator(_TITLE_LINK_SELECTOR).first
            title = link_el.inner_text().strip()
            url = link_el.get_attribute("href") or ""
        except Exception:
            return None

        company = _safe_text(card, _COMPANY_SELECTOR)
        location = _safe_text(card, _LOCATION_SELECTOR)
        card_text = _safe_text(card, None)

        easy_apply = "easily apply" in card_text.lower() or "easy apply" in card_text.lower()

        if url and not url.startswith("http"):
            url = "https://www.indeed.com" + url

        return Job(
            id=hashlib.sha1(url.encode()).hexdigest()[:16],
            title=title,
            company=company,
            location=location,
            url=url,
            apply_url=url,
            source=JobSource.INDEED,
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
