"""Tailored resume PDF generation from structured resume JSON."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from agent.models import Job, MatchResult, Resume


def generate_tailored_resume(
    resume: Resume,
    job: Job,
    match: MatchResult | None,
    out_path: Path,
) -> Path:
    """Render a clean single-page resume PDF tailored to the job."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter
    y = height - 0.9 * inch

    def line(text: str, size: int = 11, gap: float = 16, bold: bool = False) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(0.9 * inch, y, text)
        y -= gap

    # Header
    line(resume.name, size=20, bold=True)
    contact = " | ".join(
        p for p in [resume.email, resume.phone, resume.location, resume.linkedin] if p
    )
    if contact:
        line(contact, size=9, gap=20)

    # Summary
    if resume.summary:
        line("Summary", size=13, bold=True)
        _wrap(c, resume.summary, 0.9 * inch, y, width - 1.8 * inch, 11, 14)
        y -= 22

    # Tailored note
    if job.title:
        line(
            f"Target: {job.title} at {job.company}",
            size=10,
            gap=18,
        )

    # Skills (put matched skills first when available)
    line("Skills", size=13, bold=True)
    skills = resume.skills
    if match:
        matched = match.matched_skills
        skills = [s for s in matched if s] + [s for s in skills if s not in matched]
    _wrap(c, ", ".join(skills), 0.9 * inch, y, width - 1.8 * inch, 10, 14)
    y -= 24

    # Experience
    line("Experience", size=13, bold=True)
    for exp in resume.experience:
        line(f"{exp.title} — {exp.company}", size=11, bold=True)
        if exp.start or exp.end:
            line(f"{exp.start} – {exp.end}", size=9, gap=12)
        for b in exp.bullets:
            _wrap(c, f"• {b}", 0.9 * inch, y, width - 1.8 * inch, 10, 13)
        y -= 8

    # Education
    line("Education", size=13, bold=True)
    for edu in resume.education:
        line(
            f"{edu.degree}{' in ' + edu.field if edu.field else ''} — {edu.school}",
            size=11,
        )
        if edu.start or edu.end:
            line(f"{edu.start} – {edu.end}", size=9, gap=14)

    c.save()
    return out_path


def _wrap(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_w: float,
    size: int,
    gap: float,
) -> None:
    """Draw text with naive word wrapping; returns nothing (mutates via canvas)."""
    c.setFont("Helvetica", size)
    words = text.split()
    if not words:
        return
    line_buf = ""
    yy = y
    for w in words:
        trial = f"{line_buf} {w}".strip()
        if c.stringWidth(trial, "Helvetica", size) <= max_w:
            line_buf = trial
        else:
            c.drawString(x, yy, line_buf)
            yy -= gap
            line_buf = w
    c.drawString(x, yy, line_buf)
