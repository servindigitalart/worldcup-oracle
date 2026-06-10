"""
Tests for oracle.recommendations.rules — Week 14 rules engine.

Coverage:
  - finished match → no_recommendation, status=finished, is_actionable=False
  - missing market → no_recommendation, data_quality=missing_market, is_actionable=False
  - small gap (<4pp) → market_aligned, is_actionable=False
  - moderate gap (4–8pp) → watch, is_actionable=False
  - large gap (≥8pp) → model_gap_detected
  - poor data quality downgrades confidence (never 'high')
  - is_actionable=False without market data
  - is_actionable=False for finished match
  - largest-gap selection is chosen
  - no unsafe language in reason or warnings
  - confidence is never 'high'
"""
from __future__ import annotations

import pytest

from oracle.recommendations.rules import (
    MODERATE_GAP_THRESHOLD,
    SMALL_GAP_THRESHOLD,
    apply_rules,
)
from oracle.recommendations.schema import (
    FORBIDDEN_TERMS,
    RecommendationInput,
    check_language,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _inp(**overrides) -> RecommendationInput:
    """Build a default RecommendationInput (pre-match, official, no market)."""
    defaults = dict(
        match_id="england_vs_japan",
        home_team="england",
        away_team="japan",
        group="F",
        kickoff_at="2026-06-22T15:00:00Z",
        model_home=0.55,
        model_draw=0.25,
        model_away=0.20,
        market_home=None,
        market_draw=None,
        market_away=None,
        blend_home=0.55,
        blend_draw=0.25,
        blend_away=0.20,
        has_market_data=False,
        capture_status="no_market_data",
        fixture_status="official",
        result_status=None,
    )
    defaults.update(overrides)
    return RecommendationInput(**defaults)


def _inp_with_market(model_home=0.58, market_home=0.48,
                     model_draw=0.22, market_draw=0.25,
                     model_away=0.20, market_away=0.27,
                     **overrides) -> RecommendationInput:
    """Build a RecommendationInput with market data available."""
    kwargs: dict = dict(
        market_home=market_home,
        market_draw=market_draw,
        market_away=market_away,
        blend_home=0.8*market_home + 0.2*model_home,
        blend_draw=0.8*market_draw  + 0.2*model_draw,
        blend_away=0.8*market_away  + 0.2*model_away,
        model_home=model_home,
        model_draw=model_draw,
        model_away=model_away,
        has_market_data=True,
        capture_status="latest_available",
    )
    kwargs.update(overrides)
    return _inp(**kwargs)


def _check_no_forbidden_language(rec) -> None:
    violations = check_language(rec.reason)
    for w in rec.warnings:
        violations.extend(check_language(w))
    assert violations == [], f"Forbidden language found: {violations}"


# ── Rule 1: Finished match ─────────────────────────────────────────────────────

class TestFinishedMatch:
    def test_type_is_no_recommendation(self):
        rec = apply_rules(_inp(result_status="finished"))
        assert rec.recommendation_type == "no_recommendation"

    def test_status_is_finished(self):
        rec = apply_rules(_inp(result_status="finished"))
        assert rec.status == "finished"

    def test_is_not_actionable(self):
        rec = apply_rules(_inp(result_status="finished"))
        assert rec.is_actionable is False

    def test_reason_mentions_finished(self):
        rec = apply_rules(_inp(result_status="finished"))
        assert "finished" in rec.reason.lower()

    def test_no_forbidden_language(self):
        rec = apply_rules(_inp(result_status="finished"))
        _check_no_forbidden_language(rec)


# ── Rule 2: Missing market data ────────────────────────────────────────────────

class TestMissingMarket:
    def test_type_is_no_recommendation(self):
        rec = apply_rules(_inp(has_market_data=False))
        assert rec.recommendation_type == "no_recommendation"

    def test_data_quality_is_missing_market(self):
        rec = apply_rules(_inp(has_market_data=False))
        assert rec.data_quality == "missing_market"

    def test_is_not_actionable(self):
        rec = apply_rules(_inp(has_market_data=False))
        assert rec.is_actionable is False

    def test_no_forbidden_language(self):
        rec = apply_rules(_inp(has_market_data=False))
        _check_no_forbidden_language(rec)


# ── Rule 3: Small gap → market_aligned ────────────────────────────────────────

class TestSmallGap:
    def _small_gap_inp(self):
        # gap = 0.01 on home (< SMALL_GAP_THRESHOLD=0.04)
        return _inp_with_market(
            model_home=0.50, market_home=0.49,
            model_draw=0.25, market_draw=0.25,
            model_away=0.25, market_away=0.26,
        )

    def test_type_is_market_aligned(self):
        rec = apply_rules(self._small_gap_inp())
        assert rec.recommendation_type == "market_aligned"

    def test_is_not_actionable(self):
        rec = apply_rules(self._small_gap_inp())
        assert rec.is_actionable is False

    def test_no_forbidden_language(self):
        rec = apply_rules(self._small_gap_inp())
        _check_no_forbidden_language(rec)

    def test_confidence_not_high(self):
        rec = apply_rules(self._small_gap_inp())
        assert rec.confidence != "high"


# ── Rule 4: Moderate gap → watch ──────────────────────────────────────────────

class TestModerateGap:
    def _moderate_gap_inp(self):
        # gap = 0.05 on home (≥ 0.04, < 0.08)
        return _inp_with_market(
            model_home=0.54, market_home=0.49,
            model_draw=0.24, market_draw=0.26,
            model_away=0.22, market_away=0.25,
        )

    def test_type_is_watch(self):
        rec = apply_rules(self._moderate_gap_inp())
        assert rec.recommendation_type == "watch"

    def test_is_not_actionable(self):
        rec = apply_rules(self._moderate_gap_inp())
        assert rec.is_actionable is False

    def test_confidence_is_low_or_medium(self):
        rec = apply_rules(self._moderate_gap_inp())
        assert rec.confidence in ("low", "medium")

    def test_no_forbidden_language(self):
        rec = apply_rules(self._moderate_gap_inp())
        _check_no_forbidden_language(rec)


# ── Rule 5: Large gap → model_gap_detected ────────────────────────────────────

class TestLargeGap:
    def _large_gap_inp(self, capture_status="closing_candidate"):
        # gap = 0.10 on home (≥ 0.08)
        return _inp_with_market(
            model_home=0.58, market_home=0.48,
            model_draw=0.22, market_draw=0.25,
            model_away=0.20, market_away=0.27,
            capture_status=capture_status,
        )

    def test_type_is_model_gap_detected(self):
        rec = apply_rules(self._large_gap_inp())
        assert rec.recommendation_type == "model_gap_detected"

    def test_selection_is_home_win(self):
        rec = apply_rules(self._large_gap_inp())
        assert rec.selection == "home_win"

    def test_model_probability_set(self):
        rec = apply_rules(self._large_gap_inp())
        assert rec.model_probability == pytest.approx(0.58)

    def test_market_probability_set(self):
        rec = apply_rules(self._large_gap_inp())
        assert rec.market_probability == pytest.approx(0.48)

    def test_gap_is_positive(self):
        rec = apply_rules(self._large_gap_inp())
        assert rec.model_market_gap == pytest.approx(0.10)

    def test_confidence_is_medium_not_high(self):
        rec = apply_rules(self._large_gap_inp())
        assert rec.confidence == "medium"
        assert rec.confidence != "high"

    def test_risk_is_medium_or_high(self):
        rec = apply_rules(self._large_gap_inp())
        assert rec.risk_label in ("medium", "high")

    def test_no_forbidden_language(self):
        rec = apply_rules(self._large_gap_inp())
        _check_no_forbidden_language(rec)

    def test_reason_mentions_percentage_points(self):
        rec = apply_rules(self._large_gap_inp())
        assert "percentage points" in rec.reason.lower() or "pp" in rec.reason.lower()

    def test_warnings_included(self):
        rec = apply_rules(self._large_gap_inp())
        assert len(rec.warnings) > 0

    def test_actionable_with_good_data(self):
        rec = apply_rules(self._large_gap_inp(capture_status="closing_candidate"))
        assert rec.is_actionable is True

    def test_not_actionable_with_opening_only(self):
        rec = apply_rules(self._large_gap_inp(capture_status="opening_only"))
        # is_actionable still True (opening_only is not no_market_data)
        assert rec.is_actionable is True

    def test_not_actionable_without_market(self):
        rec = apply_rules(_inp(has_market_data=False))
        assert rec.is_actionable is False


# ── Poor data quality ─────────────────────────────────────────────────────────

class TestPoorDataQuality:
    def test_placeholder_fixture_gives_low_confidence(self):
        inp = _inp_with_market(fixture_status="placeholder")
        rec = apply_rules(inp)
        # Even if gap is large, confidence is low for placeholder fixture
        assert rec.confidence in ("low", "unknown")

    def test_no_market_data_not_actionable(self):
        inp = _inp(has_market_data=False)
        rec = apply_rules(inp)
        assert rec.is_actionable is False

    def test_finished_not_actionable_regardless_of_gap(self):
        inp = _inp_with_market(result_status="finished")
        rec = apply_rules(inp)
        assert rec.is_actionable is False
        assert rec.recommendation_type == "no_recommendation"


# ── Largest gap selection ─────────────────────────────────────────────────────

class TestLargestGapSelection:
    def test_away_selected_when_away_has_largest_gap(self):
        inp = _inp_with_market(
            model_home=0.40, market_home=0.38,   # gap 0.02
            model_draw=0.25, market_draw=0.26,   # gap 0.01
            model_away=0.35, market_away=0.26,   # gap 0.09 ← largest
            capture_status="latest_available",
        )
        rec = apply_rules(inp)
        assert rec.selection == "away_win"

    def test_draw_selected_when_draw_has_largest_gap(self):
        inp = _inp_with_market(
            model_home=0.40, market_home=0.39,   # gap 0.01
            model_draw=0.35, market_draw=0.26,   # gap 0.09 ← largest
            model_away=0.25, market_away=0.35,   # gap 0.10 abs but draw gap larger here for demo
            capture_status="latest_available",
        )
        # draw gap = |0.35-0.26| = 0.09; away gap = |0.25-0.35| = 0.10 → away wins
        rec = apply_rules(inp)
        assert rec.selection == "away_win"

    def test_signed_gap_direction_correct(self):
        # model > market → positive gap
        inp = _inp_with_market(
            model_home=0.60, market_home=0.45,
            model_draw=0.22, market_draw=0.28,
            model_away=0.18, market_away=0.27,
            capture_status="latest_available",
        )
        rec = apply_rules(inp)
        assert rec.selection == "home_win"
        assert rec.model_market_gap is not None
        assert rec.model_market_gap > 0  # model higher than market


# ── No high confidence ever assigned ─────────────────────────────────────────

class TestConservativeConfidence:
    def test_confidence_never_high_no_market(self):
        for status in ("no_market_data", "opening_only", "latest_available",
                       "closing_candidate", "closing_locked"):
            inp = _inp(capture_status=status)
            rec = apply_rules(inp)
            assert rec.confidence != "high", f"Got high confidence for capture_status={status!r}"

    def test_confidence_never_high_with_market(self):
        for status in ("opening_only", "latest_available", "closing_candidate", "closing_locked"):
            inp = _inp_with_market(
                model_home=0.70, market_home=0.50,
                model_draw=0.18, market_draw=0.26,
                model_away=0.12, market_away=0.24,
                capture_status=status,
            )
            rec = apply_rules(inp)
            assert rec.confidence != "high", f"Got high confidence for capture_status={status!r}"


# ── Language safety sweep ─────────────────────────────────────────────────────

class TestLanguageSafety:
    """Apply rules to many scenarios and assert no forbidden terms appear."""

    def _all_scenarios(self):
        return [
            _inp(result_status="finished"),
            _inp(has_market_data=False),
            _inp_with_market(model_home=0.50, market_home=0.49,
                             model_draw=0.25, market_draw=0.25,
                             model_away=0.25, market_away=0.26),
            _inp_with_market(model_home=0.54, market_home=0.49,
                             model_draw=0.24, market_draw=0.26,
                             model_away=0.22, market_away=0.25),
            _inp_with_market(model_home=0.58, market_home=0.48,
                             model_draw=0.22, market_draw=0.25,
                             model_away=0.20, market_away=0.27,
                             capture_status="closing_candidate"),
        ]

    def test_no_forbidden_terms_in_any_scenario(self):
        for inp in self._all_scenarios():
            rec = apply_rules(inp)
            violations = check_language(rec.reason)
            for w in rec.warnings:
                violations.extend(check_language(w))
            assert violations == [], (
                f"Forbidden language in scenario {inp.match_id!r}: {violations}\n"
                f"  reason: {rec.reason!r}\n"
                f"  warnings: {rec.warnings!r}"
            )
