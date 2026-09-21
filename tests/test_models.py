"""Tests for the job-applier agent."""

from agent.models import Experience, Job, JobSource, Resume


def make_resume() -> Resume:
    return Resume(
        name="Test User",
        email="test@example.com",
        skills=["python", "aws", "docker", "fastapi"],
        experience=[
            Experience(
                title="Backend Engineer",
                company="Acme",
                start="2020-01",
                end="2024-01",
                bullets=["Built APIs", "Led AWS migration"],
            )
        ],
    )


def test_years_experience():
    r = make_resume()
    assert r.years_experience >= 4


def test_job_model():
    job = Job(
        id="abc123",
        title="SWE",
        company="Acme",
        url="https://example.com/job",
        source=JobSource.MANUAL,
        description="Looking for a Python developer.",
    )
    assert job.title == "SWE"
    assert job.source == JobSource.MANUAL


def test_match_result_defaults():
    from agent.models import MatchResult

    m = MatchResult()
    assert m.score == 0.0
    assert m.missing_skills == []
