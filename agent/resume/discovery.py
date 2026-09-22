"""Resume file discovery.

The resume filename is NOT hardcoded. The agent finds any PDF whose name
contains "resume" (case-insensitive):

    data/Resume-Ilham_Perdana_Jalasena-SDET.pdf   -> matched
    data/Ilham_Perdana_Resume.pdf                 -> matched
    data/cv-2027.pdf                              -> not matched (no "resume")

When several files match, the newest by modified time wins and the others are
removed, so exactly one resume PDF remains on disk.

An explicit override is honoured first: set ``RESUME_PDF_PATH`` in ``.env`` to
pin a specific file and skip discovery/cleanup entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.config import ROOT, get_settings

#: Directory scanned for resume PDFs (relative to the project root).
RESUME_DIR = "data"

#: A candidate must contain this token (case-insensitive) in its filename.
NAME_TOKEN = "resume"


@dataclass
class ResumeFile:
    """The resolved resume PDF, plus what discovery had to do to find it."""

    path: Path
    removed: list[Path]
    matched: list[Path]


def candidate_pdfs(directory: Path | None = None) -> list[Path]:
    """Return PDFs in `directory` whose name contains 'resume' (case-insensitive)."""
    directory = directory or (ROOT / RESUME_DIR)
    if not directory.is_dir():
        return []
    return [
        p
        for p in directory.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".pdf"
        and NAME_TOKEN in p.name.lower()
    ]


def _newest_first(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def find_resume(
    directory: Path | None = None,
    *,
    prune: bool = True,
    explicit: Path | None = None,
) -> ResumeFile:
    """Resolve the resume PDF.

    Order of precedence:
      1. `explicit` argument, if given.
      2. `RESUME_PDF_PATH` from `.env`, if it points at an existing file.
      3. Discovery: newest `*resume*.pdf` in `data/`.

    When discovery is used and `prune` is True, every other matching PDF is
    deleted so only the chosen one remains.

    Raises FileNotFoundError when nothing is found.
    """
    settings = get_settings()

    # 1/2. Explicit path (argument beats config).
    pinned = explicit
    if pinned is None:
        # `settings.resume_pdf` is None when the value is blank, so an unset
        # RESUME_PDF_PATH correctly falls through to discovery.
        configured = settings.resume_pdf
        if configured is not None and configured.is_file():
            pinned = configured

    if pinned is not None:
        return ResumeFile(path=pinned, removed=[], matched=[pinned])

    # 3. Discovery.
    matches = candidate_pdfs(directory)
    if not matches:
        searched = directory or (ROOT / RESUME_DIR)
        raise FileNotFoundError(
            f"No resume PDF found in {searched}. "
            f'Add a PDF whose name contains "{NAME_TOKEN}" '
            f"(e.g. Resume-Your_Name.pdf)."
        )

    ordered = _newest_first(matches)
    chosen, stale = ordered[0], ordered[1:]

    removed: list[Path] = []
    if prune:
        for old in stale:
            try:
                old.unlink()
                removed.append(old)
            except OSError:
                # Leaving a stale file is preferable to failing the run; the
                # caller is told about the one we could not remove.
                pass

    return ResumeFile(path=chosen, removed=removed, matched=matches)


def describe(result: ResumeFile) -> str:
    """One-line human summary of a discovery result."""
    msg = f"Resume: {result.path.name}"
    if result.removed:
        names = ", ".join(p.name for p in result.removed)
        msg += f"  (removed {len(result.removed)} stale: {names})"
    elif len(result.matched) > 1:
        msg += f"  ({len(result.matched)} matched; kept newest)"
    return msg
