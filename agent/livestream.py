"""Live browser stream: registry of the active browser + MJPEG frame source.

The orchestrator (and the dashboard demo) register the browser they are driving.
The dashboard's `/stream` endpoint reads the active browser and emits an MJPEG
stream (`multipart/x-mixed-replace`), which any browser can display in a plain
`<img>` tag — no WebSocket or client library needed.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from typing import Any

# The browser currently being streamed. Protected by _lock.
_active_browser: Any = None
_lock = threading.Lock()


def set_active_browser(browser: Any) -> None:
    global _active_browser
    with _lock:
        _active_browser = browser


def get_active_browser() -> Any:
    with _lock:
        return _active_browser


def clear_active_browser(browser: Any | None = None) -> None:
    """Clear the active browser, optionally only if it matches `browser`."""
    global _active_browser
    with _lock:
        if browser is None or _active_browser is browser:
            _active_browser = None


def placeholder_frame(text: str = "No active browser — start a demo or apply to a job") -> bytes:
    """Render a placeholder frame with a message (using pymupdf, no new deps)."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=1280, height=720)
    page.draw_rect(pymupdf.Rect(0, 0, 1280, 720), color=(0.08, 0.08, 0.1), fill=(0.08, 0.08, 0.1))
    page.insert_text((50, 360), text, fontsize=24, color=(0.85, 0.85, 0.9))
    pix = page.get_pixmap(dpi=72)
    doc.close()
    return pix.tobytes("jpeg")


def capture_or_placeholder(browser: Any) -> bytes:
    if browser is None:
        return placeholder_frame()
    try:
        return browser.capture_frame()
    except Exception:
        return placeholder_frame("Browser busy or closed — retrying…")


def mjpeg_stream(fps: float = 3.0) -> Generator[bytes, None, None]:
    """Yield MJPEG multipart chunks forever (~fps frames per second)."""
    interval = 1.0 / max(fps, 0.2)
    while True:
        frame = capture_or_placeholder(get_active_browser())
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
            + frame
            + b"\r\n"
        )
        time.sleep(interval)
