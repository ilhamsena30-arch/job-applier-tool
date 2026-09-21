"""Application form filler.

Uses the LLM to map resume data onto the fields it finds on a page, then fills
the browser form. The final submit click is left to the caller so the agent can
apply its success-detection policy (confirmation/thank-you page).
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.llm import get_llm
from agent.models import MatchResult, Resume

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


class FormFiller:
    def __init__(self, browser) -> None:
        self.browser = browser

    def detect_fields(self) -> list[dict]:
        """Return a list of visible input fields on the current page."""
        # Playwright-style locator scan of inputs, selects and textareas.
        try:
            elements = self.browser.page.locator(
                "input, select, textarea"
            ).all()
        except Exception:
            return []

        fields: list[dict] = []
        for el in elements:
            try:
                if not el.is_visible():
                    continue
            except Exception:
                continue
            try:
                tag = el.evaluate("e => e.tagName.toLowerCase()")
                name = el.get_attribute("name") or el.get_attribute("id") or ""
                label = el.evaluate(
                    "e => (e.labels && e.labels[0] ? e.labels[0].innerText : '')"
                )
                placeholder = el.get_attribute("placeholder") or ""
                kind = el.get_attribute("type") or "text"
            except Exception:
                continue
            fields.append(
                {
                    "key": name or placeholder or label or kind,
                    "tag": tag,
                    "type": kind,
                    "label": (label or placeholder).strip(),
                }
            )
        return fields

    def plan_values(self, resume: Resume, match: MatchResult | None, fields: list[dict]) -> dict:
        """Ask the LLM how to fill each field, returning name -> value."""
        llm = get_llm()
        payload = {
            "resume": resume.model_dump(),
            "fields": fields,
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

    def fill_form(self, resume: Resume, match: MatchResult | None) -> ApplyResult:
        """Detect fields, plan values, fill them. Does NOT submit."""
        fields = self.detect_fields()
        values = self.plan_values(resume, match, fields)
        filled: dict[str, str] = {}
        missing: list[str] = []

        for field in fields:
            key = field["key"]
            value = values.get(key) or values.get(field["label"]) or values.get(field["type"])
            if value is None:
                missing.append(key)
                continue
            selector = self._selector_for(field)
            try:
                if field["tag"] == "select":
                    self.browser.page.select_option(selector, value)
                else:
                    self.browser.fill(selector, value)
                filled[key] = value
            except Exception:
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
