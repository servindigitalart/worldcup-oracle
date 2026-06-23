"""Tests for oracle.knowledge_calibration.weights — adaptive weight engine."""
from __future__ import annotations

import pytest
from oracle.knowledge_calibration.weights import (
    score_to_weight,
    build_adaptive_weights,
    lookup_chain_weight,
    lookup_script_weight,
    lookup_manager_weight,
    lookup_archetype_weight,
)


class TestScoreToWeight:
    def test_neutral_score_returns_near_neutral_weight(self):
        # A score of ~42 should be in the neutral zone
        w = score_to_weight(42, activations=20)
        assert 0.95 <= w <= 1.05

    def test_high_score_returns_elevated_weight(self):
        w = score_to_weight(85, activations=40)
        assert w > 1.10

    def test_low_score_returns_reduced_weight(self):
        w = score_to_weight(15, activations=20)
        assert w < 0.90

    def test_zero_score_returns_min_weight(self):
        w = score_to_weight(0, activations=20)
        assert w >= 0.50

    def test_max_score_returns_max_weight(self):
        w = score_to_weight(100, activations=50)
        assert w <= 1.50

    def test_weight_is_never_zero(self):
        for score in range(0, 101, 10):
            w = score_to_weight(float(score), activations=25)
            assert w > 0.0, f"score={score} gave weight={w}"

    def test_weight_is_never_negative(self):
        for score in range(0, 101, 5):
            w = score_to_weight(float(score), activations=25)
            assert w >= 0.0

    def test_weight_increases_monotonically_with_score(self):
        activations = 30
        scores = [0, 20, 35, 50, 70, 85, 100]
        weights = [score_to_weight(float(s), activations) for s in scores]
        for i in range(1, len(weights)):
            assert weights[i] >= weights[i - 1] - 0.001, f"Non-monotonic at {scores[i]}"

    def test_very_small_sample_pinned_to_neutral(self):
        # activations < 5 should pin to neutral regardless of score
        w_high = score_to_weight(90, activations=3)
        w_low  = score_to_weight(10, activations=3)
        assert w_high == 1.0
        assert w_low  == 1.0

    def test_weight_bounded_within_limits(self):
        for score in range(0, 101, 10):
            for activations in [0, 3, 10, 50]:
                w = score_to_weight(float(score), activations)
                assert 0.50 <= w <= 1.50, f"score={score}, act={activations}: w={w}"


class TestBuildAdaptiveWeights:
    def _make_chain(self, chain_id: str, weight: float) -> dict:
        return {"chain_id": chain_id, "weight": weight}

    def _make_script(self, script_id: str, weight: float) -> dict:
        return {"script_id": script_id, "weight": weight}

    def _make_manager(self, manager_id: str, pattern_id: str, weight: float) -> dict:
        return {"manager_id": manager_id, "pattern_id": pattern_id, "weight": weight}

    def _make_archetype(self, archetype_id: str, weight: float) -> dict:
        return {"archetype_id": archetype_id, "weight": weight}

    def test_returns_dict_with_all_keys(self):
        weights = build_adaptive_weights([], [], [], [])
        assert "chains" in weights
        assert "scripts" in weights
        assert "managers" in weights
        assert "archetypes" in weights
        assert "meta" in weights

    def test_chain_weights_populated(self):
        chains = [self._make_chain("C-03", 1.15), self._make_chain("G-07", 1.20)]
        weights = build_adaptive_weights(chains, [], [], [])
        assert weights["chains"]["C-03"] == 1.15
        assert weights["chains"]["G-07"] == 1.20

    def test_script_weights_populated(self):
        scripts = [self._make_script("tactical_neutralization", 1.08)]
        weights = build_adaptive_weights([], scripts, [], [])
        assert weights["scripts"]["tactical_neutralization"] == 1.08

    def test_manager_weights_keyed_correctly(self):
        managers = [self._make_manager("scaloni", "disciplined_defense_first", 1.12)]
        weights = build_adaptive_weights([], [], managers, [])
        assert weights["managers"]["scaloni:disciplined_defense_first"] == 1.12

    def test_archetype_weights_populated(self):
        archetypes = [self._make_archetype("possession_control", 1.07)]
        weights = build_adaptive_weights([], [], [], archetypes)
        assert weights["archetypes"]["possession_control"] == 1.07

    def test_meta_contains_bounds(self):
        weights = build_adaptive_weights([], [], [], [])
        assert "neutral_weight" in weights["meta"]
        assert "min_weight" in weights["meta"]
        assert "max_weight" in weights["meta"]


class TestLookupFunctions:
    def _base_weights(self) -> dict:
        return build_adaptive_weights(
            [{"chain_id": "C-03", "weight": 1.15}],
            [{"script_id": "tactical_neutralization", "weight": 1.08}],
            [{"manager_id": "scaloni", "pattern_id": "disciplined_defense_first", "weight": 1.12}],
            [{"archetype_id": "possession_control", "weight": 1.07}],
        )

    def test_lookup_chain_weight(self):
        w = self._base_weights()
        assert lookup_chain_weight(w, "C-03") == 1.15

    def test_lookup_chain_weight_unknown_returns_neutral(self):
        w = self._base_weights()
        assert lookup_chain_weight(w, "FAKE-99") == 1.0

    def test_lookup_script_weight(self):
        w = self._base_weights()
        assert lookup_script_weight(w, "tactical_neutralization") == 1.08

    def test_lookup_script_weight_unknown_returns_neutral(self):
        w = self._base_weights()
        assert lookup_script_weight(w, "nonexistent") == 1.0

    def test_lookup_manager_weight(self):
        w = self._base_weights()
        assert lookup_manager_weight(w, "scaloni", "disciplined_defense_first") == 1.12

    def test_lookup_manager_weight_unknown_returns_neutral(self):
        w = self._base_weights()
        assert lookup_manager_weight(w, "unknown_manager", "pattern") == 1.0

    def test_lookup_archetype_weight(self):
        w = self._base_weights()
        assert lookup_archetype_weight(w, "possession_control") == 1.07

    def test_lookup_archetype_weight_unknown_returns_neutral(self):
        w = self._base_weights()
        assert lookup_archetype_weight(w, "nonexistent") == 1.0
