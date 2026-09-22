"""Application form filler.

Uses the LLM to map resume data onto the fields it finds on a page, then fills
the browser form. The final submit click is left to the caller so the agent can
apply its success-detection policy (confirmation/thank-you page).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.llm import get_llm
from agent.models import MatchResult, Resume

# Fields that are part of a job board's own chrome (search, nav), not a job
# application. If these are the only inputs on the page we are still on a
# *listing*, not a form.
_SEARCH_FIELD_HINTS = (
    "job title",
    "keywords",
    "company",
    "city",
    "state",
    "zip",
    "location",
    "where",
    "remote",
    "what",
    "search",
)

_UPLOAD_FIELD_TYPES = {"file", "upload"}

_FORM_FILL_PROMPT = """You fill a job application form.
You are given the resume JSON and the form fields found on the page.
For each field, return the value to enter. Use ONLY data from the resume or
values that are unambiguous (e.g. matching the exact resume text). If you do
not know a value, return null for that field.

Return ONLY a JSON object mapping field name -> value or null:
{ "<field name>": "<value or null>", ... }"""


@dataclass
class ApplyResult:
    ok: bool
    filled_fields: dict[str, str]
    missing_fields: list[str]
    message: str


def _is_search_field(field: dict) -> bool:
    """True when a field is a job-board search/navigation input, not part of a
    job application form."""
    key = str(field.get("key", "")).lower()
    label = str(field.get("label", "")).lower()
    kind = str(field.get("type", "")).lower()
    if kind in _UPLOAD_FIELD_TYPES:
        return False
    text = f"{key} {label}"
    return any(hint in text for hint in _SEARCH_FIELD_HINTS)


def detect_application_fields(browser) -> tuple[list[dict], bool]:
    """Return (real application fields, has_file_upload) for the current page.

    Job-board search/navigation inputs are excluded, so a bare listing page is
    reported as having no application fields instead of being mistaken for a
    form (which previously produced a fake "form filled" success).
    """
    filler = FormFiller(browser)
    fields = filler.detect_fields()
    has_upload = any(f.get("type") in _UPLOAD_FIELD_TYPES for f in fields)
    real = [f for f in fields if not _is_search_field(f)]
    return real, has_upload


class FormFiller:
    def __init__(self, browser) -> None:
        self.browser = browser
        self._frames: list[Any] = []

    # ------------------------------------------------------------ frames

    def _frame_list(self) -> list[Any]:
        """All frames on the current page; the main frame first.

        Job boards often render the real form inside an iframe (e.g. Indeed's
        inline apply), so field detection must reach into every frame.
        """
        page = self.browser.page
        try:
            frames = list(page.frames)
        except Exception:  # noqa: BLE001 - fall back to main page
            frames = []
        return frames if frames else [page]

    # ---------------------------------------------------------- detection

    def detect_fields(self) -> list[dict]:
        """Return visible input/select/textarea fields across ALL frames.

        Each field carries a private ``_frame`` index so filling can target the
        same frame the field was found in (important for iframed forms).
        """
        self._frames = self._frame_list()
        fields: list[dict] = []
        for idx, frame in enumerate(self._frames):
            try:
                elements = frame.locator("input, select, textarea").all()
            except Exception:  # noqa: BLE001,S112 - a detached frame must not break us
                continue
            for el in elements:
                field = self._describe(el, idx)
                if field:
                    fields.append(field)
        return fields

    @staticmethod
    def _describe(el, frame_idx: int) -> dict | None:
        try:
            if not el.is_visible():
                return None
        except Exception:  # noqa: BLE001 - hidden/detached element
            return None
        try:
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            name = el.get_attribute("name") or el.get_attribute("id") or ""
            label = el.evaluate(
                "e => (e.labels && e.labels[0] ? e.labels[0].innerText : '')"
            )
            placeholder = el.get_attribute("placeholder") or ""
            kind = el.get_attribute("type") or "text"
        except Exception:  # noqa: BLE001 - unreadable element
            return None
        return {
            "key": name or placeholder or label or kind,
            "tag": tag,
            "type": kind,
            "label": (label or placeholder).strip(),
            "_frame": frame_idx,
            "_el": el,
        }

    # ------------------------------------------------------------ planning

    def plan_values(self, resume: Resume, match: MatchResult | None, fields: list[dict]) -> dict:
        """Ask the LLM how to fill each field, returning name -> value."""
        llm = get_llm()
        # The `_frame` marker is internal; do not confuse the model with it.
        public = [{k: v for k, v in f.items() if not k.startswith("_")} for f in fields]
        payload = {
            "resume": resume.model_dump(),
            "fields": public,
            "suggested_answers": match.suggested_answers if match else {},
        }
        result = llm.chat_json(
            [
                {"role": "system", "content": _FORM_FILL_PROMPT},
                {"role": "user", "content": str(payload)},
            ],
            temperature=0.0,
        )
        return {k: v for k, v in (result or {}).items() if v}

    # -------------------------------------------------------------- filling

    def fill_form(self, resume: Resume, match: MatchResult | None) -> ApplyResult:
        """Detect fields, plan values, fill them. Does NOT submit.

        Only genuine application fields are filled; job-board search/nav inputs
        are ignored. When no real fields exist (e.g. we are still on a listing
        page), `ok` is False and `missing_fields` carries an honest message.
        """
        fields = self.detect_fields()
        has_upload = any(f.get("type") in _UPLOAD_FIELD_TYPES for f in fields)
        real = [f for f in fields if not _is_search_field(f)]
        if not real and not has_upload:
            return ApplyResult(
                ok=False,
                filled_fields={},
                missing_fields=["no application form detected on this page"],
                message=(
                    "No application form found — only search/navigation fields "
                    "are present. Did not fill anything."
                ),
            )

        values = self.plan_values(resume, match, real)
        filled: dict[str, str] = {}
        missing: list[str] = []

        for field in real:
            key = field["key"]
            value = values.get(key) or values.get(field["label"]) or values.get(field["type"])
            if value is None:
                missing.append(key)
                continue
            # Prefer the exact element we located (most reliable, works for
            # fields without a `name` attribute); fall back to a selector.
            el = field.get("_el")
            try:
                if field["tag"] == "select":
                    el.select_option(str(value)) if el else self._frames[0].select_option(
                        self._selector_for(field), str(value)
                    )
                else:
                    el.fill(str(value)) if el else self._frames[0].fill(
                        self._selector_for(field), str(value)
                    )
                filled[key] = str(value)
            except Exception:  # noqa: BLE001 - a failed fill is recorded as missing
                missing.append(key)

        return ApplyResult(
            ok=len(filled) > 0,
            filled_fields=filled,
            missing_fields=missing,
            message=(
                f"Filled {len(filled)} fields; missing {len(missing)}."
                if missing
                else f"Filled {len(filled)} fields."
            ),
        )

    def _selector_for(self, field: dict) -> str:
        key = field["key"]
        if field["tag"] == "textarea":
            return f"textarea[name='{key}']" if key else "textarea"
        if field["tag"] == "select":
            return f"select[name='{key}']" if key else "select"
        kind = field["type"]
        return f"input[type='{kind}'][name='{key}']" if key else f"input[type='{kind}']"
