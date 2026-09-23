"""Stable identity for job postings.

Job boards decorate every link with per-click tracking parameters that change
on each visit (Indeed's ``bb``, ``xkcb``, ``fccid``, ``vjs``). De-duplicating on
the raw URL therefore fails and the same opening gets applied twice. This module
derives a canonical key that ignores tracking noise.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def canonical_job_key(url: str, company: str = "", title: str = "") -> str:
    """Return a stable identity for a job posting.

    - Indeed: the ``jk`` (or ``vjk``) param — the posting id.
    - LinkedIn: the ``currentJobId`` param, else the URL path.
    - Other hosts: the full URL (the only identity we have).
    - No URL: a lower-cased ``company|title`` pair as a fallback.
    """
    url = (url or "").strip()
    if not url:
        return f"pair:{company.strip().lower()}|{title.strip().lower()}"

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    qs = parse_qs(parsed.query)

    if "indeed.com" in host or host.endswith("indeed.com"):
        jk = qs.get("jk") or qs.get("vjk")
        if jk:
            return f"indeed:{jk[0]}"
    elif "linkedin.com" in host or host.endswith("linkedin.com"):
        cjid = qs.get("currentJobId")
        if cjid:
            return f"linkedin:{cjid[0]}"
        return f"linkedin:{parsed.path}"

    return f"url:{url}"
