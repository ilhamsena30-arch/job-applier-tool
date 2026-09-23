"""Tests for merging the extra-info defaults into the resume."""

from agent.models import Resume
from agent.resume.extract import apply_extra_defaults


def test_defaults_fill_empty_fields():
    resume = apply_extra_defaults(
        Resume(name="Test"),
        {"work_authorization": "Open to visa transfer", "notice_period": "2 months"},
    )
    assert resume.work_authorization == "Open to visa transfer"
    assert resume.notice_period == "2 months"


def test_existing_values_win_over_defaults():
    resume = apply_extra_defaults(
        Resume(name="Test", work_authorization="Green card"),
        {"work_authorization": "Open to visa transfer"},
    )
    assert resume.work_authorization == "Green card"


def test_unknown_keys_are_ignored():
    resume = apply_extra_defaults(Resume(name="Test"), {"nonsense": "x"})
    assert not hasattr(resume, "nonsense")
