"""Tests for search adapters (no live network — selector/parse unit tests)."""

from agent.models import Job, JobSource
from agent.search.indeed import IndeedSearch
from agent.search.linkedin import LinkedInSearch


class _FakeLocator:
    def __init__(self, text="", href="", count=1):
        self._text = text
        self._href = href
        self._count = count
        self.first = self

    def inner_text(self):
        return self._text

    def get_attribute(self, name):
        return self._href

    def count(self):
        return self._count


class _FakeCard:
    def __init__(self, text="", href="/rc/clk?jk=abc", easy=False):
        self._text = text
        self._href = href
        self._easy = easy

    def locator(self, selector):
        if "company" in selector:
            return _FakeLocator("Acme Corp")
        if "location" in selector:
            return _FakeLocator("Remote")
        # Title/link selectors (Indeed /rc/clk, LinkedIn job-card-list__title)
        if (
            "/rc/clk" in selector
            or "/viewjob" in selector
            or "job-card-list__title" in selector
        ):
            return _FakeLocator("Python Dev", self._href)
        return _FakeLocator(self._text)

    def inner_text(self):
        return self._text


def test_indeed_parse_card():
    adapter = IndeedSearch.__new__(IndeedSearch)  # bypass __init__
    card = _FakeCard(text="Python Dev\nAcme Corp\nRemote")
    job = adapter._parse_card(card)
    assert job is not None
    assert job.title == "Python Dev"
    assert job.company == "Acme Corp"
    assert job.source == JobSource.INDEED
    assert job.url.startswith("https://www.indeed.com")


def test_linkedin_parse_card():
    adapter = LinkedInSearch.__new__(LinkedInSearch)
    card = _FakeCard(text="Easy Apply", href="/jobs/view/123")
    job = adapter._parse_card(card)
    assert job is not None
    assert job.source == JobSource.LINKEDIN
    assert job.url.startswith("https://www.linkedin.com")


def test_linkedin_easy_apply_detection():
    adapter = LinkedInSearch.__new__(LinkedInSearch)
    card = _FakeCard(text="Senior SWE\nEasy Apply\nAcme", href="/jobs/view/456")
    job = adapter._parse_card(card)
    assert job is not None
    assert job.easy_apply is True
