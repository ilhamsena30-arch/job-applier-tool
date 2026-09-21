"""Send notification emails via Gmail SMTP."""

from __future__ import annotations

import smtplib
import ssl
from collections.abc import Iterable
from email.message import EmailMessage
from pathlib import Path

from agent.config import get_settings


class EmailSender:
    def __init__(self) -> None:
        self.settings = get_settings()

    def send(
        self,
        subject: str,
        body: str,
        *,
        to: str | None = None,
        attachments: Iterable[Path] | None = None,
        body_html: str | None = None,
    ) -> None:
        to = to or self.settings.gmail_user
        if not self.settings.gmail_user or not self.settings.gmail_app_password:
            raise RuntimeError("Gmail credentials not configured in .env")

        msg = EmailMessage()
        msg["From"] = self.settings.gmail_user
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        for path in attachments or []:
            p = Path(path)
            if not p.exists():
                continue
            msg.add_attachment(
                p.read_bytes(),
                maintype="application",
                subtype="pdf" if p.suffix.lower() == ".pdf" else "octet-stream",
                filename=p.name,
            )

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            self.settings.smtp_host, self.settings.smtp_port, context=ctx
        ) as server:
            server.login(self.settings.gmail_user, self.settings.gmail_app_password)
            server.send_message(msg)
