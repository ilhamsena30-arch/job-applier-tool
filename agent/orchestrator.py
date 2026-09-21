"""Orchestrator: the main control loop tying everything together."""

from __future__ import annotations

import contextlib
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from agent.apply.filler import FormFiller
from agent.browser.engine import Browser, BrowserOptions
from agent.config import get_settings
from agent.email.receiver import Reply
from agent.email.sender import EmailSender
from agent.llm import get_llm
from agent.matching.score import match_job, should_auto_apply
from agent.models import (
    Application,
    ApplicationStatus,
    Job,
    Resume,
    utcnow,
)
from agent.pdf.gen import generate_tailored_resume
from agent.resume.extract import load_resume
from agent.tracker.sheets import Tracker


@dataclass
class Orchestrator:
    """Coordinates search -> match -> route -> apply -> track -> email -> reply."""

    settings: object = field(default_factory=get_settings)
    browser: Browser | None = None
    tracker: Tracker | None = None
    sender: EmailSender | None = None

    def __post_init__(self) -> None:
        self.tracker = self.tracker or Tracker()
        self.sender = self.sender or EmailSender()

    def _browser(self) -> Browser:
        if self.browser is None:
            self.browser = Browser(
                BrowserOptions(record_dir=Path(self.settings.recordings_dir))
            ).launch()
            # Expose the live browser to the dashboard's video stream.
            from agent import livestream

            livestream.set_active_browser(self.browser)
        return self.browser

    # ------------------------------------------------------------------ flow

    def process_job(self, job: Job, resume: Resume) -> Application:
        """Run one job through match -> route -> apply/notify."""
        app = Application(id=uuid.uuid4().hex[:12], job=job)
        match = match_job(resume, job)
        app.match = match
        app.status = ApplicationStatus.MATCHED
        self.tracker.upsert(app)

        # Route decision.
        if job.easy_apply:
            # LinkedIn Easy Apply / one-click: NEVER auto-submit.
            app.status = ApplicationStatus.NOTIFY_ONLY
            app.notes = "Easy Apply — notify only per policy."
            self._send_easy_apply_email(resume, app)
            self.tracker.upsert(app)
            return app

        if not should_auto_apply(match):
            app.status = ApplicationStatus.PENDING
            self._send_pending_email(resume, app)
            app.status = ApplicationStatus.AWAITING_REPLY
            self.tracker.upsert(app)
            return app

        # Above threshold -> apply.
        return self._apply(job, resume, app)

    def _apply(self, job: Job, resume: Resume, app: Application) -> Application:
        browser = self._browser()
        app.status = ApplicationStatus.APPLYING
        self.tracker.upsert(app)

        url = job.apply_url or job.url
        browser.goto(url)

        filler = FormFiller(browser)
        result = filler.fill_form(resume, app.match)
        app.notes = result.message

        if result.missing_fields:
            # We don't have the data -> stop and email the user (4b).
            app.status = ApplicationStatus.PENDING
            app.extra["missing_fields"] = result.missing_fields
            self._send_missing_email(resume, app, result.missing_fields)
            app.status = ApplicationStatus.AWAITING_REPLY
            self.tracker.upsert(app)
            return app

        # Final submit + success detection.
        submitted = self._submit_and_confirm(browser)
        if submitted:
            app.status = ApplicationStatus.APPLIED
            self._send_success_email(resume, app)
        else:
            app.status = ApplicationStatus.FAILED
            app.notes = "Could not confirm submission (no thank-you page)."
        self.tracker.upsert(app)
        return app

    def _submit_and_confirm(self, browser: Browser) -> bool:
        """Click the submit button and check for a confirmation/thank-you page."""
        for selector in (
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
        ):
            try:
                browser.click(selector)
                break
            except Exception:
                continue

        with contextlib.suppress(Exception):
            browser.page.wait_for_load_state("domcontentloaded")
        text = browser.content().lower()
        return any(
            marker in text
            for marker in (
                "thank you",
                "application submitted",
                "we've received",
                "submitted successfully",
                "thanks for applying",
                "your application has been",
            )
        )

    # ---------------------------------------------------------------- emails

    def _send_success_email(self, resume: Resume, app: Application) -> None:
        job = app.job
        self.sender.send(
            subject=f"✅ Applied: {job.title} @ {job.company}",
            body=(
                f"Successfully applied.\n\n"
                f"Job: {job.title}\nCompany: {job.company}\n"
                f"Score: {app.match.score if app.match else '?'}\n"
                f"Link: {job.url}\n"
            ),
        )

    def _send_easy_apply_email(self, resume: Resume, app: Application) -> None:
        job = app.job
        match = app.match
        score = match.score if match else 0.0
        if score >= self.settings.confidence_threshold:
            pdf = generate_tailored_resume(
                resume,
                job,
                match,
                Path(self.settings.recordings_dir) / f"tailored_{app.id}.pdf",
            )
            self.sender.send(
                subject=f"🎯 Easy Apply match: {job.title} @ {job.company}",
                body=(
                    f"Easy Apply job matched ({score:.0f}/100). "
                    f"Attached is your tailored resume.\n\n"
                    f"Company: {job.company}\nTitle: {job.title}\n"
                    f"Apply here: {job.url}\n"
                ),
                attachments=[pdf],
            )
        else:
            missing = ", ".join(match.missing_skills) if match else ""
            self.sender.send(
                subject=f"📌 Easy Apply (low match): {job.title} @ {job.company}",
                body=(
                    f"Easy Apply job scored {score:.0f}/100 (below threshold).\n"
                    f"What you may lack: {missing}\n\n"
                    f"Apply here: {job.url}\n"
                ),
            )

    def _send_pending_email(self, resume: Resume, app: Application) -> None:
        job = app.job
        match = app.match
        missing = ", ".join(match.missing_skills) if match else ""
        score = match.score if match else "?"
        self.sender.send(
            subject=f"⏳ Pending: {job.title} @ {job.company} (score {score}/100)",
            body=(
                f"Confidence too low to auto-apply.\n\n"
                f"Job: {job.title}\nCompany: {job.company}\n"
                f"Score: {score}/100\n"
                f"Missing / to improve: {missing}\n"
                f"Link: {job.url}\n\n"
                f"Reply to this email with the missing details (e.g. 'I have 5 years of "
                f"AWS experience') and I'll update your resume and re-apply."
            ),
        )

    def _send_missing_email(self, resume: Resume, app: Application, missing: list[str]) -> None:
        job = app.job
        self.sender.send(
            subject=f"❓ Need info to apply: {job.title} @ {job.company}",
            body=(
                "I started the application but don't have some required data:\n"
                + "\n".join(f"- {m}" for m in missing)
                + f"\n\nJob: {job.title}\nCompany: {job.company}\nLink: {job.url}\n\n"
                f"Reply with the answers and I'll finish the application."
            ),
        )

    # ----------------------------------------------------------------- reply

    def handle_reply(self, reply: Reply, resume_path: Path | None = None) -> None:
        """Step 4c: parse a user reply, update the resume, re-apply."""
        # Match reply to application via In-Reply-To subject heuristics.
        app_id = self._extract_app_id(reply)
        if app_id:
            self._reapply(app_id, reply.body)
        else:
            # Generic update: feed into resume JSON via the LLM.
            self._update_resume_from_reply(reply.body, resume_path)

    def _extract_app_id(self, reply: Reply) -> str | None:
        # Our emails include the app id in brackets; look for a 12-hex token.
        m = re.search(r"\b([0-9a-f]{12})\b", reply.subject + " " + reply.in_reply_to)
        return m.group(1) if m else None

    def _update_resume_from_reply(self, body: str, resume_path: Path | None) -> None:
        resume = load_resume(resume_path) if resume_path else load_resume()
        llm = get_llm()
        updated = llm.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You update a resume JSON with new information the user provides. "
                        "Merge carefully; do not delete existing fields. Return the FULL "
                        "updated resume JSON in the same schema."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Current resume: {resume.model_dump_json()}\n\nUser update: {body}",
                },
            ]
        )
        new_resume = Resume(**updated)
        from agent.resume.extract import save_resume

        save_resume(new_resume, resume_path)

    def _reapply(self, app_id: str, body: str) -> None:
        """Re-load the original application and re-apply with an updated resume."""
        from agent.store import AppStore

        store = AppStore()
        try:
            old_app = store.load(app_id)
        except FileNotFoundError:
            self.sender.send(
                subject=f"Re-apply failed for {app_id}",
                body=f"Could not find application {app_id}.",
            )
            return

        # Update the resume JSON with the user's reply, then re-run the flow.
        self._update_resume_from_reply(body, None)
        resume = load_resume()
        new_app = self.process_job(old_app.job, resume)
        new_app.extra["reapplied_from"] = app_id
        new_app.reply_received_at = utcnow()
        store.save(new_app)
        self.tracker.upsert(new_app)
