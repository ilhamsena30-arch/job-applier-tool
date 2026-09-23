"""Tests for resume file discovery (pattern matching + stale pruning)."""

from pathlib import Path

from agent.resume.discovery import candidate_pdfs, describe, find_resume


def _make_pdf(directory: Path, name: str, mtime: float | None = None) -> Path:
    p = directory / name
    p.write_bytes(b"%PDF-1.4 fake")
    if mtime is not None:
        import os

        os.utime(p, (mtime, mtime))
    return p


def test_candidate_matching_is_case_insensitive(tmp_path):
    _make_pdf(tmp_path, "Resume-Ilham.pdf")
    _make_pdf(tmp_path, "My_RESUME_v2.PDF")
    _make_pdf(tmp_path, "cv-ilham.pdf")  # no "resume" -> excluded
    _make_pdf(tmp_path, "notes.txt")

    names = sorted(p.name for p in candidate_pdfs(tmp_path))
    assert names == ["My_RESUME_v2.PDF", "Resume-Ilham.pdf"]


def test_newest_wins_and_stale_are_pruned(tmp_path):
    old = _make_pdf(tmp_path, "Resume-old.pdf", mtime=1_000_000)
    new = _make_pdf(tmp_path, "Resume-new.pdf", mtime=2_000_000)

    result = find_resume(tmp_path, prune=True)

    assert result.path == new
    assert old in result.removed
    assert not old.exists()
    assert new.exists()


def test_prune_false_keeps_everything(tmp_path):
    old = _make_pdf(tmp_path, "Resume-old.pdf", mtime=1_000_000)
    new = _make_pdf(tmp_path, "Resume-new.pdf", mtime=2_000_000)

    result = find_resume(tmp_path, prune=False)

    assert result.path == new
    assert result.removed == []
    assert old.exists() and new.exists()
    assert len(result.matched) == 2


def test_missing_resume_raises(tmp_path):
    _make_pdf(tmp_path, "cv.pdf")  # does not match
    try:
        find_resume(tmp_path, prune=True)
    except FileNotFoundError as exc:
        assert "resume" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("expected FileNotFoundError")


def test_explicit_path_bypasses_discovery(tmp_path):
    other = tmp_path / "anything.pdf"
    other.write_bytes(b"%PDF-1.4 fake")
    _make_pdf(tmp_path, "Resume-ignored.pdf")

    result = find_resume(tmp_path, explicit=other)

    assert result.path == other
    assert result.removed == []


def test_describe_mentions_removal(tmp_path):
    _make_pdf(tmp_path, "Resume-old.pdf", mtime=1_000_000)
    _make_pdf(tmp_path, "Resume-new.pdf", mtime=2_000_000)

    text = describe(find_resume(tmp_path, prune=True))
    assert "Resume-new.pdf" in text
    assert "removed 1 stale" in text


def test_tailored_filename_variants():
    from agent.models import Job, JobSource, Resume
    from agent.pdf.gen import tailored_filename

    r = Resume(name="Ilham Perdana Jalasena")
    acme = Job(id="1", title="SDET", company="Acme Corp", source=JobSource.MANUAL)
    blank_co = Job(id="2", title="QA", company="", source=JobSource.MANUAL)

    assert tailored_filename(r, acme) == "Ilham_Perdana_Jalasena_Resume_Acme_Corp.pdf"
    assert tailored_filename(r, blank_co) == "Ilham_Perdana_Jalasena_Resume.pdf"
    # No duplicated "Resume_Resume" when the name is missing.
    assert tailored_filename(Resume(), acme) == "Resume_Acme_Corp.pdf"
    assert tailored_filename(Resume(), blank_co) == "Resume.pdf"
