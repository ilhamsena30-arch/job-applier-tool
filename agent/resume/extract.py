"""Resume extraction: PDF -> text -> structured JSON via DeepSeek (vision + JSON)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pymupdf

from agent.config import get_settings
from agent.llm import get_llm
from agent.models import Resume

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
    """Extract a Resume from the configured PDF.

    Strategy: try embedded text first (cheap). If the PDF appears to be a
    scanned/image resume with little text, fall back to vision on page images.
    """
    settings = get_settings()
    pdf_path = Path(pdf_path) if pdf_path else settings.resume_pdf
    if not pdf_path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")

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
    return Resume(**data)


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
    return Resume(**json.loads(path.read_text(encoding="utf-8")))
