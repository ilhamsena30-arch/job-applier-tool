"""Daily application rate limiting.

`DAILY_RATE_LIMIT` was previously decorative — it appeared in config and on the
dashboard but nothing enforced it. This module makes it real: applications
submitted today are counted from the app store, and the runner stops once the
limit is reached.

The count resets at local midnight.
"""

from __future__ import annotations

from datetime import date, datetime

from agent.config import get_settings
from agent.models import ApplicationStatus
from agent.store import AppStore

#: Statuses that count against the daily limit (i.e. we actually applied).
COUNTED_STATUSES = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.NOTIFY_ONLY,
}


def _local_day(dt: datetime) -> date:
    """The local calendar date of an aware/naive UTC timestamp."""
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.date()


def applied_today(store: AppStore | None = None) -> int:
    """How many applications were submitted today (local time)."""
    store = store or AppStore()
    today = date.today()  # noqa: DTZ011 - the daily quota is a LOCAL-day concept
    count = 0
    for app in store.list():
        if app.status in COUNTED_STATUSES and _local_day(app.updated_at) == today:
            count += 1
    return count


def remaining_today(store: AppStore | None = None) -> int:
    """How many more applications are allowed today."""
    limit = get_settings().daily_rate_limit
    return max(0, limit - applied_today(store))


def has_capacity(store: AppStore | None = None) -> bool:
    """True when at least one more application is allowed today."""
    return remaining_today(store) > 0
