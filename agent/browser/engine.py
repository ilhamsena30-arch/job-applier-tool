"""Browser engine wrapper.

Strategy (per decision: "borrow AIHawk's anti-detect engine"):
  1. If `invisible_playwright` (AIHawk) is installed, use it — far lower ban risk.
  2. Otherwise, fall back to plain Playwright (Chromium).

Both expose the same interface, so the apply engine doesn't care which is active.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.config import get_settings


@dataclass
class BrowserOptions:
    headed: bool | None = None
    record_dir: Path | None = None
    user_agent: str | None = None
    proxy: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Browser:
    """A headful (visible) browser used for searching and form-filling."""

    def __init__(self, options: BrowserOptions | None = None) -> None:
        self.options = options or BrowserOptions()
        self.settings = get_settings()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._aihawk = False

    # -- lifecycle ----------------------------------------------------------

    def launch(self) -> "Browser":
        headed = (
            self.options.headed
            if self.options.headed is not None
            else self.settings.headed
        )
        record_dir = self.options.record_dir or self.settings.recordings
        record_dir = Path(record_dir)
        record_dir.mkdir(parents=True, exist_ok=True)

        # Prefer the AIHawk anti-detect engine if available.
        try:
            import invisible_playwright  # noqa: F401

            self._aihawk = True
        except ImportError:
            self._aihawk = False

        if self._aihawk:
            # AIHawk mirrors Playwright's API.
            self._browser = invisible_playwright.launch(
                headless=not headed,
                proxy=self.options.proxy,
                **self.options.extra,
            )
            self._page = self._get_page_from(self._browser)
        else:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=not headed)
            self._context = self._browser.new_context(
                record_video_dir=str(record_dir),
                record_video_size={"width": 1280, "height": 720},
                user_agent=self.options.user_agent,
            )
            self._page = self._context.new_page()
        return self

    def _get_page_from(self, obj: Any) -> Any:
        """Return a page from an AIHawk browser/context/page object."""
        if hasattr(obj, "goto") and hasattr(obj, "fill"):
            return obj  # already a page
        if hasattr(obj, "new_page"):
            return obj.new_page()
        if hasattr(obj, "pages"):
            pages = obj.pages()
            if pages:
                return pages[0]
            return obj.new_page()
        raise RuntimeError("Could not obtain a page from the AIHawk engine.")

    @property
    def page(self) -> Any:
        if self._page is None:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    def close(self) -> None:
        try:
            if self._context is not None and hasattr(self._context, "close"):
                self._context.close()
        finally:
            if self._playwright is not None and hasattr(self._playwright, "stop"):
                self._playwright.stop()

    # -- primitives ---------------------------------------------------------

    def goto(self, url: str) -> Any:
        return self.page.goto(url)

    def fill(self, selector: str, value: str) -> None:
        self.page.fill(selector, value)

    def click(self, selector: str) -> None:
        self.page.click(selector)

    def content(self) -> str:
        return self.page.content()

    def screenshot(self, path: Path) -> None:
        self.page.screenshot(path=str(path))

    def scrape_job_cards(self, url: str, board: str, limit: int = 20) -> list[dict]:
        """Generic job-card scraper: navigates and extracts card data.

        Board-specific selectors are provided inline; this can be extended with
        dedicated adapter modules per board as needed.
        """
        self.goto(url)
        try:
            self.page.wait_for_load_state("networkidle")
        except Exception:
            pass

        selectors = {
            "indeed": "div.job_seen_beacon",
            "linkedin": "li.jobs-search-results__list-item",
        }
        sel = selectors.get(board)
        if sel is None:
            return []

        cards = self.page.locator(sel).all()[:limit]
        out: list[dict] = []
        for card in cards:
            try:
                text = card.inner_text()
            except Exception:
                continue
            # Extract likely title/company by line heuristics.
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            title = lines[0] if lines else ""
            company = lines[1] if len(lines) > 1 else ""
            href = ""
            try:
                href = card.locator("a").first.get_attribute("href") or ""
            except Exception:
                pass
            out.append(
                {
                    "title": title,
                    "company": company,
                    "location": "",
                    "url": href,
                    "apply_url": href,
                    "description": text,
                    "easy_apply": "easy apply" in text.lower(),
                    "external_ats": False,
                }
            )
        return out
