"""Tests for the doctor setup checks."""

from agent.doctor import Check, DoctorReport, Status, check_python, format_report


def test_python_version_ok():
    c = check_python()
    assert c.status is Status.OK
    assert "3." in c.detail


def test_report_tracks_failures():
    report = DoctorReport()
    report.add(Check("good", Status.OK))
    report.add(Check("bad", Status.FAIL, "broken", "fix it"))
    assert report.ok is False
    assert len(report.failed) == 1
    assert report.failed[0].name == "bad"


def test_report_warnings_do_not_block():
    report = DoctorReport()
    report.add(Check("good", Status.OK))
    report.add(Check("meh", Status.WARN, "optional"))
    assert report.ok is True
    assert len(report.warned) == 1


def test_format_report_includes_fix_and_summary():
    report = DoctorReport()
    report.add(Check("thing", Status.FAIL, "missing", "do the thing"))
    out = format_report(report)
    assert "[FAIL] thing" in out
    assert "fix: do the thing" in out
    assert "1 problem(s) to fix" in out


def test_format_report_all_good():
    report = DoctorReport()
    report.add(Check("thing", Status.OK, "present"))
    out = format_report(report)
    assert "All checks passed" in out


def test_run_all_returns_report():
    from agent.doctor import run_all

    report = run_all()
    names = [c.name for c in report.checks]
    # Core checks must always be present.
    assert "Python version" in names
    assert "DeepSeek API key" in names
    assert "Resume PDF" in names
