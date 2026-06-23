"""Tests for oracle.knowledge.resolver — KnowledgeActivation output."""
from __future__ import annotations

import pytest
from oracle.knowledge.resolver import resolve_knowledge_for_match
from oracle.knowledge.schema import KnowledgeActivation


def _resolve(home: str, away: str, match_id: str = "test_match") -> KnowledgeActivation:
    return resolve_knowledge_for_match(match_id, home, away, "2026-06-20T00:00:00Z")


class TestResolverOutput:
    def test_returns_knowledge_activation(self):
        result = _resolve("argentina", "uruguay")
        assert isinstance(result, KnowledgeActivation)

    def test_match_id_preserved(self):
        result = _resolve("france", "germany", "fra_vs_ger")
        assert result.match_id == "fra_vs_ger"

    def test_team_ids_preserved(self):
        result = _resolve("spain", "brazil")
        assert result.home_team == "spain"
        assert result.away_team == "brazil"

    def test_to_dict_is_json_serialisable(self):
        import json
        result = _resolve("argentina", "france")
        d = result.to_dict()
        json.dumps(d)  # should not raise

    def test_data_stage_is_stage1(self):
        result = _resolve("germany", "england")
        assert result.data_stage == "stage_1"


class TestConfidenceBounds:
    def test_both_seeded_confidence_above_floor(self):
        result = _resolve("argentina", "france")
        assert result.knowledge_confidence >= 0.30

    def test_both_seeded_confidence_at_most_ceiling(self):
        result = _resolve("argentina", "france")
        assert result.knowledge_confidence <= 0.95

    def test_both_unknown_confidence_penalised(self):
        result = _resolve("atlantis", "narnia")
        # Should be at floor after penalty
        assert result.knowledge_confidence == 0.30

    def test_one_unknown_reduces_confidence(self):
        full = _resolve("argentina", "france")
        partial = _resolve("argentina", "atlantis")
        assert partial.knowledge_confidence < full.knowledge_confidence

    def test_confidence_is_float(self):
        result = _resolve("spain", "germany")
        assert isinstance(result.knowledge_confidence, float)


class TestBothSeededBonus:
    def test_both_seeded_has_two_archetypes(self):
        result = _resolve("spain", "brazil")
        # activated_archetypes records the primary archetypes of both teams
        assert result.home_archetype != "unknown"
        assert result.away_archetype != "unknown"

    def test_both_seeded_home_away_confidence_populated(self):
        result = _resolve("france", "germany")
        assert result.home_confidence > 0.30
        assert result.away_confidence > 0.30


class TestGracefulFallback:
    def test_unknown_home_team_no_raise(self):
        result = _resolve("atlantis", "brazil")
        assert result is not None

    def test_unknown_away_team_no_raise(self):
        result = _resolve("argentina", "narnia")
        assert result is not None

    def test_both_unknown_no_raise(self):
        result = _resolve("atlantis", "narnia")
        assert result is not None

    def test_unknown_team_has_unknown_archetype(self):
        result = _resolve("atlantis", "brazil")
        assert result.home_archetype == "unknown"

    def test_unknown_team_warning_present(self):
        result = _resolve("atlantis", "brazil")
        assert len(result.warnings) > 0

    def test_scripts_always_populated(self):
        result = _resolve("atlantis", "narnia")
        assert len(result.activated_scripts) > 0

    def test_scripts_sum_to_one(self):
        result = _resolve("atlantis", "narnia")
        total = sum(s.probability for s in result.activated_scripts)
        assert abs(total - 1.0) < 1e-6


class TestManagerIntegration:
    def test_argentina_manager_patterns_activated(self):
        result = _resolve("argentina", "brazil")
        assert len(result.activated_manager_patterns) > 0

    def test_unseeded_manager_team_no_patterns(self):
        result = _resolve("canada", "australia")
        # Neither has a manager profile — may have 0 patterns
        assert isinstance(result.activated_manager_patterns, list)
