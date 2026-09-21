"""Matching engine: score a job description against the resume."""

from agent.matching.score import match_job, should_auto_apply

__all__ = ["match_job", "should_auto_apply"]
