"""Base interface for job-search adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent.models import Job


class JobSearchAdapter(ABC):
    """A source of jobs. Implementations normalize results into `Job` models."""

    @abstractmethod
    def search(self, query: str, location: str = "", limit: int = 20) -> list[Job]:
        ...
