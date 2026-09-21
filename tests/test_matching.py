"""Tests for the matching engine (no LLM calls — just the routing helpers)."""

from agent.matching.score import should_auto_apply
from agent.models import MatchResult


def test_should_auto_apply_high_score(monkeypatch):
    # Force the threshold via settings monkeypatch is heavier; here we test the
    # pure function shape by checking score comparison with a custom value.
    from agent.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "confidence_threshold", 75.0)
    assert should_auto_apply(MatchResult(score=80.0)) is True
    assert should_auto_apply(MatchResult(score=70.0)) is False
