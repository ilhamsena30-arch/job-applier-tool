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

    def looks_like_agent_thread(self, sender: str = "") -> bool:
        """True when this message is plausibly a reply to one of our emails.

        Guards against treating any unseen inbox message as a job answer.
        """
        if sender and sender.lower() not in self.sender.lower():
            return False
        markers = (
            "⏳",  # pending
            "❓",  # need info
            "🎯",  # easy-apply match
            "📌",  # easy-apply low match
            "✅",  # applied
            "re-apply",
            "pending:",
            "need info to apply",
            "easy apply",
        )
        text = f"{self.subject} {self.body}".lower()
        return any(m.lower() in text for m in markers)


class EmailReceiver:
    """Polls INBOX for new messages and exposes a simple callback hook."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._seen_uids: set[int] = set()

    def fetch_new(self, mark_seen: bool = False, limit: int = 20) -> list[Reply]:
        """Return recent UNSEEN inbox messages (most recent first).

        Only unseen messages are considered, and at most `limit` of them, so the
        first run does not try to download an entire mailbox. (A plain
        ``search("ALL")`` did exactly that: for a 7k-message inbox it appeared to
        hang for minutes before anything else happened.)
        """
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
            # UNSEEN keeps this fast and focused on messages we have not handled.
            uids = client.search(["UNSEEN"])
            uids = uids[-limit:]  # newest are last; keep the most recent few
            new_uids = [u for u in uids if u not in self._seen_uids]
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
        """Fetch new replies and invoke `handler` on each.

        Only messages that plausibly belong to an agent thread are handled, so
        unrelated unseen mail is not mistaken for a job-application answer.
        """
        me = self.settings.gmail_user
        for reply in self.fetch_new(mark_seen=mark_seen):
            if not reply.looks_like_agent_thread(sender=me):
                continue
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
