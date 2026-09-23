"""Navigate from a job *listing* page to the actual application form.

Indeed/LinkedIn land you on a listing page first; the real form is behind an
"Apply" / "Apply now" / "Apply on company site" click, possibly on a new tab
or an external ATS. This module performs that hop and then decides whether a
genuine application form is now visible (as opposed to the board's own
search/navigation inputs).
"""

from __future__ import annotations

from typing import Any

from agent.apply.filler import detect_application_fields

# Common apply affordances, most direct first.
_APPLY_SELECTORS = [
    # Indeed's inline apply button
    "button#indeedApplyButton",
    "button[data-testid='applyButton']",
    "a[data-testid='applyButton']",
    "button:has-text('Apply now')",
    "a:has-text('Apply now')",
    "button:has-text('Apply on company site')",
    "a:has-text('Apply on company site')",
    "button:has-text('Apply')",
    "a:has-text('Apply')",
    "button:has-text('Easy Apply')",
    "a:has-text('Easy Apply')",
]


def _looks_like_form(real_fields: list[dict], has_upload: bool) -> bool:
    """A resume-upload input is the strongest signal; otherwise require several
    non-search fields before trusting that we are on a real form."""
    if has_upload:
        return True
    return len(real_fields) >= 3


def reach_application_form(browser: Any) -> bool:
    """Click through to a real application form; return True when one is found.

    Safe to call on a page that already IS the form: it returns True
    immediately without clicking anything.
    """
    real, has_upload = detect_application_fields(browser)
    if _looks_like_form(real, has_upload):
        return True

    page = browser.page
    clicked = False
    for selector in _APPLY_SELECTORS:
        try:
            loc = page.locator(selector)
            if loc.count() == 0:
                continue
            loc.first.click()
            clicked = True
            break
        except Exception:  # noqa: BLE001,S112 - try the next candidate selector
            continue

    if not clicked:
        return False

    # The click may navigate in-place or open a new tab. Wait, then move to the
    # newest page so a target=_blank / external ATS tab becomes the active page.
    try:
        page.wait_for_timeout(1500)
    except Exception:  # noqa: BLE001,S110 - timing is best-effort
        pass
    try:
        page.wait_for_load_state("domcontentloaded")
    except Exception:  # noqa: BLE001,S110 - the page may already be loaded
        pass
    browser.switch_to_newest_page()

    real, has_upload = detect_application_fields(browser)
    return _looks_like_form(real, has_upload)
