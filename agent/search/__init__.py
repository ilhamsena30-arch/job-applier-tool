"""Search adapters: discover jobs from various boards."""

from agent.search.base import JobSearchAdapter
from agent.search.indeed import IndeedSearch
from agent.search.linkedin import LinkedInSearch

__all__ = ["IndeedSearch", "JobSearchAdapter", "LinkedInSearch"]
