"""
Tests for edge_confidence classification — Week 15.

Coverage:
  - _edge_confidence_for_gap helper: threshold correctness
  - apply_rules integration: edge_confidence in all 5 rule paths
  - schema: EDGE_CONFIDENCE_LEVELS enum validation
  - to_dict: edge_confidence serialised correctly
"""
from __future__ import annotations

import pytest

from oracle.recommendations.rules import (
    _EDGE_HIGH_MAX,
    _EDGE_LOW_MAX,
    _EDGE_MEDIUM_MAX,
    _edge_confidence_for_gap,
    apply_rules,
)
from oracle.recommendations.schema import (
    EDGE_CONFIDENCE_LEVELS,
    Recommendation,
    RecommendationInput,
)


# ── _edge_confidence_for_gap ──────────────────────────────────────────────────

class TestEdgeConfidenceForGap:
    def test_none_returns_none(self):
        assert _edge_confidence_for_gap(None) == "none"

    def test_zero_is_low(self):
        assert _edge_confidence_for_gap(0.0) == "low"

    def test_just_below_low_max_is_low(self):
        assert _edge_confidence_for_gap(_EDGE_LOW_MAX - 0.001) == "low"

    def test_at_low_max_is_medium(self):
        assert _edge_confidence_for_gap(_EDGE_LOW_MAX) == "medium"

    def test_mid_medium_range_is_medium(self):
        assert _edge_confidence_for_gap(0.045) == "medium"

    def test_at_medium_max_is_high(self):
        assert _edge_confidence_for_gap(_EDGE_MEDIUM_MAX) == "high"

    def test_mid_high_range_is_high(self):
        assert _edge_confidence_for_gap(0.08) == "high"

    def test_at_high_max_is_very_high(self):
        assert _edge_confidence_for_gap(_EDGE_HIGH_MAX) == "very_high"

    def test_large_gap_is_very_high(self):
        assert _edge_confidence_for_gap(0.20) == "very_high"

    def test_thresholds_exactly_3_6_10(self):
        assert _edge_confidence_for_gap(0.029) == "low"
        assert _edge_confidence_for_gap(0.030) == "medium"
        assert _edge_confidence_for_gap(0.059) == "medium"
        assert _edge_confidence_for_gap(0.060) == "high"
        assert _edge_confidence_for_gap(0.099) == "high"
        assert _edge_confidence_for_gap(0.100) == "very_high"

    def test_returns_string(self):
        for gap in [None, 0.0, 0.05, 0.10, 0.20]:
            assert isinstance(_edge_confidence_for_gap(gap), str)

    def test_all_values_in_enum(self):
        for gap in [None, 0.0, 0.03, 0.06, 0.10, 0.20]:
            result = _edge_confidence_for_gap(gap)
            assert result in EDGE_CONFIDENCE_LEVELS


# ── EDGE_CONFIDENCE_LEVELS enum ───────────────────────────────────────────────

class TestEdgeConfidenceLevelsEnum:
    def test_contains_all_expected_values(self):
        assert {"low", "medium", "high", "very_high", "none"} <= EDGE_CONFIDENCE_LEVELS

    def test_is_frozenset(self):
        assert isinstance(EDGE_CONFIDENCE_LEVELS, frozenset)


# ── apply_rules integration ───────────────────────────────────────────────────

def _inp(**overrides) -> RecommendationInput:
    defaults = dict(
        match_id="x_vs_y", home_team="x", away_team="y", group="A",
        kickoff_at=None,
        model_home=0.55, model_draw=0.25, model_away=0.20,
        market_home=None, market_draw=None, market_away=None,
        blend_home=0.55, blend_draw=0.25, blend_away=0.20,
        has_market_data=False, capture_status="no_market_data",
        fixture_status="official", result_status=None,
    )
    defaults.update(overrides)
    return RecommendationInput(**defaults)


def _inp_with_market(model_home=0.58, market_home=0.48,
                     model_draw=0.22, market_draw=0.25,
                     model_away=0.20, market_away=0.27,
                     **overrides) -> RecommendationInput:
    kwargs: dict = dict(
        market_home=market_home, market_draw=market_draw, market_away=market_away,
        blend_home=0.8*market_home + 0.2*model_home,
        blend_draw=0.8*market_draw  + 0.2*model_draw,
        blend_away=0.8*market_away  + 0.2*model_away,
        model_home=model_home, model_draw=model_draw, model_away=model_away,
        has_market_data=True, capture_status="latest_available",
    )
    kwargs.update(overrides)
    return _inp(**kwargs)


class TestApplyRulesEdgeConfidence:
    def test_finished_match_edge_confidence_is_none(self):
        rec = apply_rules(_inp(result_status="finished"))
        assert rec.edge_confidence == "none"

    def test_no_market_data_edge_confidence_is_none(self):
        rec = apply_rules(_inp(has_market_data=False))
        assert rec.edge_confidence == "none"

    def test_small_gap_is_low(self):
        # gap = 0.01 < 0.03
        rec = apply_rules(_inp_with_market(model_home=0.50, market_home=0.49,
                                           model_draw=0.25, market_draw=0.25,
                                           model_away=0.25, market_away=0.26))
        assert rec.edge_confidence == "low"

    def test_medium_gap(self):
        # gap = 0.04 (exactly at _EDGE_LOW_MAX)
        rec = apply_rules(_inp_with_market(model_home=0.54, market_home=0.50,
                                           model_draw=0.24, market_draw=0.26,
                                           model_away=0.22, market_away=0.24))
        assert rec.edge_confidence == "medium"

    def test_high_gap(self):
        # gap = 0.07 (between 0.06 and 0.10)
        rec = apply_rules(_inp_with_market(model_home=0.57, market_home=0.50,
                                           model_draw=0.22, market_draw=0.25,
                                           model_away=0.21, market_away=0.25))
        assert rec.edge_confidence == "high"

    def test_very_high_gap(self):
        # gap = 0.15 (>= 0.10)
        rec = apply_rules(_inp_with_market(model_home=0.65, market_home=0.50,
                                           model_draw=0.20, market_draw=0.27,
                                           model_away=0.15, market_away=0.23,
                                           capture_status="closing_candidate"))
        assert rec.edge_confidence == "very_high"

    def test_edge_confidence_in_allowed_set(self):
        for inp in [
            _inp(result_status="finished"),
            _inp(has_market_data=False),
            _inp_with_market(model_home=0.50, market_home=0.49,
                             model_draw=0.25, market_draw=0.25,
                             model_away=0.25, market_away=0.26),
            _inp_with_market(model_home=0.65, market_home=0.50,
                             model_draw=0.20, market_draw=0.27,
                             model_away=0.15, market_away=0.23,
                             capture_status="closing_candidate"),
        ]:
            rec = apply_rules(inp)
            assert rec.edge_confidence in EDGE_CONFIDENCE_LEVELS

    def test_edge_confidence_in_to_dict(self):
        rec = apply_rules(_inp_with_market(model_home=0.65, market_home=0.50,
                                           model_draw=0.20, market_draw=0.27,
                                           model_away=0.15, market_away=0.23,
                                           capture_status="closing_candidate"))
        d = rec.to_dict()
        assert "edge_confidence" in d
        assert d["edge_confidence"] == rec.edge_confidence


# ── Schema validation ─────────────────────────────────────────────────────────

class TestSchemaEdgeConfidenceValidation:
    def _make_rec(self, edge_confidence="none"):
        return Recommendation(
            match_id="a_vs_b", home_team="a", away_team="b",
            group="A", kickoff_at=None,
            recommendation_type="no_recommendation",
            market="1x2", selection=None,
            model_probability=None, market_probability=None,
            blended_probability=None, model_market_gap=None,
            confidence="unknown", risk_label="unknown",
            data_quality="missing_market", status="pre_match",
            reason="Market benchmark unavailable.",
            warnings=[], is_actionable=False,
            edge_confidence=edge_confidence,
            generated_at="2026-06-10T00:00:00Z",
        )

    def test_valid_values_accepted(self):
        for v in ("none", "low", "medium", "high", "very_high"):
            rec = self._make_rec(edge_confidence=v)
            assert rec.edge_confidence == v

    def test_invalid_value_raises(self):
        with pytest.raises(AssertionError):
            self._make_rec(edge_confidence="extreme")

    def test_default_is_none(self):
        rec = self._make_rec()
        assert rec.edge_confidence == "none"
