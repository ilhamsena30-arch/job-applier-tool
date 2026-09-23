"""Tests for the JSON app store and its duplicate cleanup."""

from datetime import timedelta

from agent.models import Application, Job, JobSource, utcnow
from agent.store import AppStore


def _app(app_id: str, url: str, company: str = "Acme") -> Application:
    return Application(
        id=app_id,
        job=Job(
            id=app_id,
            title="SDET",
            company=company,
            url=url,
            source=JobSource.INDEED,
        ),
    )


def test_save_prunes_older_record_with_same_canonical_key(tmp_path):
    """The same Indeed posting under different tracking URLs stores once."""
    store = AppStore(directory=tmp_path)
    url_old = "https://www.indeed.com/jobs?q=SDET&jk=abc123&bb=1"
    url_new = "https://www.indeed.com/viewjob?jk=abc123&fccid=x"
    other_url = "https://www.indeed.com/jobs?q=SDET&jk=zzz999"

    old = _app("old1", url_old)
    old.created_at = old.updated_at = utcnow() - timedelta(days=2)
    newer = _app("new1", url_new)
    other = _app("other", other_url)

    store.save(old)
    store.save(other)
    store.save(newer)  # save() prunes `old1`, which shares the `jk` key

    assert {a.id for a in store.list()} == {"new1", "other"}


def test_dedupe_returns_removed_count_and_keeps_newest(tmp_path):
    store = AppStore(directory=tmp_path)
    url_a = "https://www.indeed.com/jobs?q=SDET&jk=abc123"
    url_b = "https://www.indeed.com/jobs?q=SDET&jk=zzz999"

    old = _app("a_old", url_a)
    old.created_at = old.updated_at = utcnow() - timedelta(days=1)
    new = _app("a_new", url_a)
    other = _app("b", url_b)

    for app in (old, other, new):
        store.save(app)

    removed = store.dedupe()
    assert removed == 0  # save() already pruned as records were written
    assert {a.id for a in store.list()} == {"a_new", "b"}
