"""Search adapters: discover jobs from various boards."""

from agent.search.base import JobSearchAdapter
from agent.search.aggregator import AggregatorSearch

__all__ = ["JobSearchAdapter", "AggregatorSearch"]
