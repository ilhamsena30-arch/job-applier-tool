"""Receive and parse user replies (step 4c) via Gmail IMAP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser

from imapclient import IMAPClient

from agent.config import get_settings


@dataclass
class Reply:
    uid: int
    sender: str
    subject: str
    body: str
    in_reply_to: str = ""


class EmailReceiver:
    """Polls INBOX for new messages and exposes a simple callback hook."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._seen_uids: set[int] = set()

    def fetch_new(self, mark_seen: bool = False) -> list[Reply]:
        """Return new INBOX messages since the last call."""
        if not self.settings.gmail_user or not self.settings.gmail_app_password:
            raise RuntimeError("Gmail credentials not configured in .env")

        replies: list[Reply] = []
        with IMAPClient(
            self.settings.imap_host, port=self.settings.imap_port, ssl=True
        ) as client:
            client.login(
                self.settings.gmail_user, self.settings.gmail_app_password
            )
            client.select_folder("INBOX", readonly=not mark_seen)
            messages = client.search("ALL")
            new_uids = [u for u in messages if u not in self._seen_uids]
            if not new_uids:
                return []

            for uid, msg_data in client.fetch(new_uids, ["RFC822"]).items():
                raw = msg_data[b"RFC822"]
                msg = BytesParser(policy=policy.default).parsebytes(raw)
                body = _extract_body(msg)
                replies.append(
                    Reply(
                        uid=uid,
                        sender=msg.get("From", ""),
                        subject=msg.get("Subject", ""),
                        body=body,
                        in_reply_to=msg.get("In-Reply-To", ""),
                    )
                )
            self._seen_uids.update(new_uids)
        return replies

    def poll(self, handler: Callable[[Reply], None], mark_seen: bool = True) -> None:
        """Fetch new replies and invoke `handler` on each."""
        for reply in self.fetch_new(mark_seen=mark_seen):
            handler(reply)


def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == "text/plain":
                return part.get_content()
        # Fallback to HTML
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                return part.get_content()
        return ""
    return msg.get_content()
