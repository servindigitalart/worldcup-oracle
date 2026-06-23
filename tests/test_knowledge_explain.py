"""Tests for oracle.knowledge.explain — explanation generation."""
from __future__ import annotations

import pytest
from oracle.knowledge.resolver import resolve_knowledge_for_match
from oracle.knowledge.explain import build_knowledge_explanation


FORBIDDEN = {
    "bet this", "lock", "guaranteed", "sure thing", "profit", "free money",
    "must bet", "bet this now", "risk-free",
}


def _explain(home: str, away: str):
    activation = resolve_knowledge_for_match("test", home, away, "2026-06-20T00:00:00Z")
    return build_knowledge_explanation(activation)


class TestBuildKnowledgeExplanation:
    def test_returns_three_strings(self):
        result = _explain("argentina", "france")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_all_parts_are_strings(self):
        headline, body, key_risk = _explain("spain", "brazil")
        assert isinstance(headline, str)
        assert isinstance(body, str)
        assert isinstance(key_risk, str)

    def test_headline_not_empty(self):
        headline, _, _ = _explain("germany", "england")
        assert headline.strip() != ""

    def test_body_not_empty(self):
        _, body, _ = _explain("france", "germany")
        assert body.strip() != ""

    def test_key_risk_not_empty(self):
        _, _, key_risk = _explain("argentina", "uruguay")
        assert key_risk.strip() != ""


class TestUnknownTeams:
    def test_unknown_home_produces_output(self):
        headline, body, key_risk = _explain("atlantis", "brazil")
        assert headline != ""
        assert body != ""

    def test_both_unknown_produces_output(self):
        headline, body, key_risk = _explain("atlantis", "narnia")
        assert headline != ""

    def test_unknown_teams_mention_limitation(self):
        headline, body, key_risk = _explain("atlantis", "narnia")
        # Body should indicate limited data
        combined = (headline + body + key_risk).lower()
        assert any(word in combined for word in ["limited", "unavailable", "insufficient", "unknown", "data"])


class TestSafeLanguage:
    def _check_no_forbidden(self, text: str):
        lower = text.lower()
        for term in FORBIDDEN:
            assert term not in lower, f"Forbidden term '{term}' found in: {text}"

    def test_headline_safe_language(self):
        for home, away in [("argentina", "france"), ("spain", "brazil"), ("germany", "england")]:
            headline, _, _ = _explain(home, away)
            self._check_no_forbidden(headline)

    def test_body_safe_language(self):
        for home, away in [("argentina", "france"), ("spain", "brazil"), ("atlantis", "narnia")]:
            _, body, _ = _explain(home, away)
            self._check_no_forbidden(body)

    def test_key_risk_safe_language(self):
        for home, away in [("argentina", "france"), ("germany", "england")]:
            _, _, key_risk = _explain(home, away)
            self._check_no_forbidden(key_risk)
