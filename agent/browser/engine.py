"""Browser engine wrapper.

Strategy (per decision: "borrow AIHawk's anti-detect engine"):
  1. Default (`auto`): prefer the AIHawk anti-detect engine (invisible-playwright),
     fall back to plain Playwright Chromium if it is not installed.
  2. `aihawk`: require the AIHawk engine.
  3. `playwright`: plain Playwright Chromium.

The AIHawk engine is a context manager returning a patched Firefox browser
(lower ban risk). We keep the context manager alive for the wrapper's lifetime
and create pages via `browser.new_page()`.
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
    seed: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Browser:
    """A headful (visible) browser used for searching and form-filling."""

    def __init__(self, options: BrowserOptions | None = None) -> None:
        self.options = options or BrowserOptions()
        self.settings = get_settings()
        self._playwright = None          # plain Playwright manager
        self._browser = None             # AIHawk browser OR Playwright browser
        self._context = None             # Playwright context (fallback path)
        self._page = None
        self._aihawk = None              # the InvisiblePlaywright context manager

    # -- lifecycle ----------------------------------------------------------

    def launch(self) -> Browser:
        engine = self.settings.browser_engine.lower()
        use_aihawk = self._resolve_engine(engine)

        if use_aihawk:
            self._launch_aihawk()
        else:
            self._launch_playwright()
        return self

    def _resolve_engine(self, engine: str) -> bool:
        """Decide which engine to use based on config + availability."""
        if engine == "playwright":
            return False
        try:
            import invisible_playwright  # noqa: F401

            available = True
        except ImportError:
            available = False

        if engine == "aihawk" and not available:
            raise RuntimeError(
                "BROWSER_ENGINE=aihawk but invisible-playwright is not installed. "
                "Run: pip install invisible-playwright"
            )
        return available  # "auto" -> prefer AIHawk if present

    def _launch_aihawk(self) -> None:
        from invisible_playwright import InvisiblePlaywright

        headed = self.options.headed if self.options.headed is not None else self.settings.headed
        proxy = self.options.proxy
        proxy_dict = None
        if proxy:
            # AIHawk accepts a dict, e.g. {"server": "socks5://host:port"}.
            proxy_dict = {"server": proxy}

        self._aihawk = InvisiblePlaywright(
            headless=not headed,
            proxy=proxy_dict,
            seed=self.options.seed,
            **self.options.extra,
        )
        self._browser = self._aihawk.__enter__()
        self._page = self._get_page_from(self._browser)

    def _launch_playwright(self) -> None:
        from playwright.sync_api import sync_playwright

        headed = self.options.headed if self.options.headed is not None else self.settings.headed
        record_dir = self.options.record_dir or self.settings.recordings
        record_dir = Path(record_dir)
        record_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=not headed)
        self._context = self._browser.new_context(
            record_video_dir=str(record_dir),
            record_video_size={"width": 1280, "height": 720},
            user_agent=self.options.user_agent,
        )
        self._page = self._context.new_page()

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
            if self._aihawk is not None:
                self._aihawk.__exit__(None, None, None)
        finally:
            try:
                if self._context is not None and hasattr(self._context, "close"):
                    self._context.close()
            finally:
                if self._playwright is not None and hasattr(self._playwright, "stop"):
                    self._playwright.stop()

    # -- primitives ---------------------------------------------------------

    def switch_to_newest_page(self) -> None:
        """Move the active page pointer to the most recently opened page.

        Apply buttons often open a new tab (`target=_blank`) or an external ATS.
        After clicking, call this so subsequent fill/read operations target the
        form instead of the stale listing tab.
        """
        for candidate in (self._context, self._browser):
            if candidate is None or not hasattr(candidate, "pages"):
                continue
            try:
                pages = candidate.pages()
            except Exception:  # noqa: BLE001,S112 - try the next object that has pages()
                continue
            if pages:
                self._page = pages[-1]
                return

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
