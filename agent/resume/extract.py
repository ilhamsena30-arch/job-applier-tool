"""Resume extraction: PDF -> text -> structured JSON via DeepSeek (vision + JSON)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pymupdf

from agent.config import get_settings
from agent.llm import get_llm
from agent.models import Resume

#: Committed answers the PDF cannot carry (visa, notice period, salary, links).
_DEFAULTS_PATH = Path(__file__).resolve().parent / "resume_defaults.json"

_SYSTEM_PROMPT = """You extract structured data from a resume into JSON.
Return ONLY a valid JSON object with exactly these keys (use empty string / [] when unknown):
{
  "name": str,
  "email": str,
  "phone": str,
  "location": str,
  "linkedin": str,
  "website": str,
  "summary": str,
  "skills": [str],
  "experience": [{"title": str, "company": str, "start": str, "end": str, "bullets": [str]}],
  "education": [{"school": str, "degree": str, "field": str, "start": str, "end": str}]
}
Dates as "YYYY-MM" when possible, else "YYYY", else the text as-is.
Do not invent information. Only include what is actually present."""


def _pdf_text(pdf_path: Path) -> str:
    doc = pymupdf.open(pdf_path)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _pdf_page_images(pdf_path: Path, max_pages: int = 3) -> list[str]:
    """Render the first pages to PNG and return base64 strings (for vision)."""
    doc = pymupdf.open(pdf_path)
    images: list[str] = []
    try:
        for page in doc[:max_pages]:
            pix = page.get_pixmap(dpi=150)
            images.append(base64.b64encode(pix.tobytes("png")).decode())
    finally:
        doc.close()
    return images


def extract_resume(pdf_path: Path | None = None) -> Resume:
    """Extract a Resume from the discovered/configured PDF.

    The filename is not hardcoded: any `*resume*.pdf` in the resume directory is
    accepted, newest wins, and stale duplicates are pruned.

    Strategy: try embedded text first (cheap). If the PDF appears to be a
    scanned/image resume with little text, fall back to vision on page images.
    """
    from agent.resume.discovery import find_resume

    if pdf_path is not None:
        resolved = Path(pdf_path)
    else:
        resolved = find_resume(explicit=None).path

    if not resolved.exists():
        raise FileNotFoundError(f"Resume PDF not found: {resolved}")

    pdf_path = resolved
    llm = get_llm()
    text = _pdf_text(pdf_path)

    # Scanned PDFs yield little text; use vision then.
    if len(text.strip()) < 50:
        images = _pdf_page_images(pdf_path)
        if not images:
            raise ValueError("Could not render resume pages for vision extraction.")
        # Vision first on page 1; if more pages, send sequentially and merge text.
        extracted_text = ""
        for img in images:
            extracted_text += llm.vision(
                "Transcribe all text from this resume page exactly. "
                "Preserve structure (headings, bullets, dates).",
                img,
            ) + "\n"
        text = extracted_text

    user_prompt = (
        "Extract the structured resume data from the following resume text.\n\n"
        f"<resume>\n{text}\n</resume>\n\n"
        "Return the JSON object with the exact schema described."
    )
    data = llm.chat_json(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=llm.model,  # flash (vision-capable) by default
    )
    return apply_extra_defaults(Resume(**data))


def apply_extra_defaults(resume: Resume, defaults: dict | None = None) -> Resume:
    """Fill empty extra-info fields from the defaults file; never overwrite.

    Answers like visa status or notice period are not on the PDF, so they are
    committed separately and merged in whenever a resume is loaded. Values
    already present in `data/resume.json` always win.
    """
    if defaults is None:
        defaults = {}
        if _DEFAULTS_PATH.exists():
            try:
                defaults = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                defaults = {}
    for key, value in (defaults or {}).items():
        if key not in Resume.model_fields:
            continue
        if not getattr(resume, key, ""):
            setattr(resume, key, value)
    return resume


def save_resume(resume: Resume, path: Path | None = None) -> Path:
    settings = get_settings()
    path = Path(path) if path else settings.resume_json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(resume.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_resume(path: Path | None = None) -> Resume:
    settings = get_settings()
    path = Path(path) if path else settings.resume_json
    if not path.exists():
        raise FileNotFoundError(
            f"Resume JSON not found: {path}. Run extraction first."
        )
    return apply_extra_defaults(Resume(**json.loads(path.read_text(encoding="utf-8"))))
