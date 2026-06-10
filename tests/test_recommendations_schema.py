"""
Tests for oracle.recommendations.schema — Week 14.

Coverage:
  - Recommendation serializes to dict with all required fields
  - Allowed enum values are enforced (__post_init__ assertions)
  - Forbidden language check raises on violations
  - check_language() detects forbidden terms
  - FORBIDDEN_TERMS and RECOMMENDATION_TYPES are correctly defined
"""
from __future__ import annotations

import pytest

from oracle.recommendations.schema import (
    CONFIDENCE_LEVELS,
    DATA_QUALITY_LEVELS,
    FORBIDDEN_TERMS,
    RECOMMENDATION_TYPES,
    RISK_LABELS,
    SAFE_TERMS,
    STATUSES,
    Recommendation,
    RecommendationInput,
    check_language,
)


# ── check_language() ──────────────────────────────────────────────────────────

class TestCheckLanguage:
    def test_clean_text_returns_empty(self):
        assert check_language("Model gap detected — educational signal only.") == []

    def test_detects_guaranteed(self):
        result = check_language("This is guaranteed to win.")
        assert "guaranteed" in result

    def test_detects_profit(self):
        result = check_language("You will make a profit here.")
        assert "profit" in result

    def test_detects_sure_bet(self):
        result = check_language("This is a sure bet pick.")
        assert "sure bet" in result

    def test_case_insensitive(self):
        result = check_language("GUARANTEED returns every time.")
        assert "guaranteed" in result

    def test_multiple_violations(self):
        result = check_language("Guaranteed profit on this sure bet.")
        assert len(result) >= 2

    def test_all_forbidden_terms_detected(self):
        for term in FORBIDDEN_TERMS:
            result = check_language(f"This match is a {term} situation.")
            assert term in result, f"Expected {term!r} to be detected"


# ── RECOMMENDATION_TYPES ──────────────────────────────────────────────────────

class TestRecommendationTypes:
    def test_required_types_present(self):
        required = {"no_recommendation", "model_gap_detected", "market_aligned", "avoid", "watch"}
        assert required <= RECOMMENDATION_TYPES

    def test_risk_labels_present(self):
        assert {"low", "medium", "high", "unknown"} <= RISK_LABELS

    def test_confidence_levels_present(self):
        assert {"low", "medium", "high", "unknown"} <= CONFIDENCE_LEVELS

    def test_data_quality_levels_present(self):
        required = {"complete", "partial", "missing_market", "placeholder", "stale", "unknown"}
        assert required <= DATA_QUALITY_LEVELS

    def test_statuses_present(self):
        assert {"pre_match", "live", "finished", "unavailable"} <= STATUSES


# ── Recommendation dataclass ──────────────────────────────────────────────────

def _make_rec(**overrides) -> Recommendation:
    defaults = dict(
        match_id="mexico_vs_south_africa",
        home_team="mexico",
        away_team="south_africa",
        group="A",
        kickoff_at="2026-06-11T19:00:00Z",
        recommendation_type="no_recommendation",
        market="1x2",
        selection=None,
        model_probability=None,
        market_probability=None,
        blended_probability=None,
        model_market_gap=None,
        confidence="unknown",
        risk_label="unknown",
        data_quality="missing_market",
        status="pre_match",
        reason="Market benchmark unavailable.",
        warnings=["Educational signal only — not betting advice."],
        is_actionable=False,
        generated_at="2026-06-09T00:00:00Z",
    )
    defaults.update(overrides)
    return Recommendation(**defaults)


class TestRecommendationDataclass:
    def test_creates_successfully(self):
        rec = _make_rec()
        assert rec.match_id == "mexico_vs_south_africa"

    def test_to_dict_has_all_fields(self):
        rec = _make_rec()
        d = rec.to_dict()
        required_fields = {
            "match_id", "home_team", "away_team", "group", "kickoff_at",
            "recommendation_type", "market", "selection", "model_probability",
            "market_probability", "blended_probability", "model_market_gap",
            "confidence", "risk_label", "data_quality", "status",
            "reason", "warnings", "is_actionable", "generated_at",
        }
        assert required_fields <= set(d.keys())

    def test_to_dict_values_match(self):
        rec = _make_rec(recommendation_type="watch", is_actionable=False)
        d = rec.to_dict()
        assert d["recommendation_type"] == "watch"
        assert d["is_actionable"] is False

    def test_to_dict_warnings_is_list(self):
        rec = _make_rec(warnings=["Warning A", "Warning B"])
        d = rec.to_dict()
        assert isinstance(d["warnings"], list)
        assert len(d["warnings"]) == 2

    def test_invalid_recommendation_type_raises(self):
        with pytest.raises(AssertionError):
            _make_rec(recommendation_type="sure_thing")

    def test_invalid_risk_label_raises(self):
        with pytest.raises(AssertionError):
            _make_rec(risk_label="extreme")

    def test_invalid_confidence_raises(self):
        with pytest.raises(AssertionError):
            _make_rec(confidence="very_high")

    def test_invalid_data_quality_raises(self):
        with pytest.raises(AssertionError):
            _make_rec(data_quality="garbage")

    def test_invalid_status_raises(self):
        with pytest.raises(AssertionError):
            _make_rec(status="pending")

    def test_forbidden_reason_raises(self):
        with pytest.raises(AssertionError, match="Forbidden"):
            _make_rec(reason="This is a guaranteed winner.")

    def test_forbidden_warning_raises(self):
        with pytest.raises(AssertionError, match="Forbidden"):
            _make_rec(warnings=["This will make you profit."])

    def test_safe_reason_passes(self):
        rec = _make_rec(reason="Probability signal — educational only.")
        assert rec.reason.startswith("Probability signal")

    def test_model_gap_detected_with_data(self):
        rec = _make_rec(
            recommendation_type="model_gap_detected",
            selection="home_win",
            model_probability=0.58,
            market_probability=0.48,
            model_market_gap=0.10,
            confidence="medium",
            risk_label="medium",
            data_quality="complete",
            reason="Model probability is 10 percentage points higher than the market benchmark on home_win.",
        )
        d = rec.to_dict()
        assert d["model_market_gap"] == pytest.approx(0.10)
        assert d["selection"] == "home_win"
