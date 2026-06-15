"""
Tests for oracle.betting.explain — Week 22.
"""
from __future__ import annotations

import pytest

from oracle.betting.explain import explain_signal, supporting_factors
from oracle.betting.schema import BetMarketProbability


# ── Helpers ───────────────────────────────────────────────────────────────────

def _market(
    signal_level: str = "watch",
    probability: float = 0.55,
    market_gap: float | None = None,
    fair_decimal_odds: float | None = None,
    data_quality: str = "model_only",
) -> BetMarketProbability:
    odds = fair_decimal_odds or (round(1 / probability, 4) if probability > 0 else None)
    return BetMarketProbability(
        match_id="m1",
        market_type="1x2",
        selection="home_win",
        probability=probability,
        fair_decimal_odds=odds,
        model_source="elo_blend",
        confidence="medium",
        risk_label="medium",
        data_quality=data_quality,
        signal_level=signal_level,
        market_gap=market_gap,
        reason="Test market",
    )


# ── explain_signal ────────────────────────────────────────────────────────────

class TestExplainSignal:
    def test_returns_dict(self):
        m = _market()
        result = explain_signal(m)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        m = _market()
        result = explain_signal(m)
        for key in ("signal_level", "label", "description", "factors", "disclaimer"):
            assert key in result

    def test_signal_level_matches(self):
        m = _market(signal_level="moderate_signal")
        result = explain_signal(m)
        assert result["signal_level"] == "moderate_signal"

    def test_label_for_strong_signal(self):
        m = _market(signal_level="strong_signal", market_gap=0.12)
        result = explain_signal(m)
        assert result["label"] == "Model edge detected"

    def test_label_for_watch(self):
        m = _market(signal_level="watch", market_gap=0.04)
        result = explain_signal(m)
        assert result["label"] == "Watch"

    def test_label_for_no_signal(self):
        m = _market(signal_level="no_signal")
        result = explain_signal(m)
        assert result["label"] == "Aligned"

    def test_label_for_model_only(self):
        m = _market(signal_level="model_probability_only")
        result = explain_signal(m)
        assert result["label"] == "Model only"

    def test_disclaimer_present_and_non_empty(self):
        m = _market()
        result = explain_signal(m)
        assert len(result["disclaimer"]) > 0

    def test_disclaimer_no_forbidden_terms(self):
        from oracle.betting.schema import check_language
        m = _market(signal_level="strong_signal", market_gap=0.15)
        result = explain_signal(m)
        assert check_language(result["disclaimer"]) == []

    def test_description_non_empty(self):
        for level in ["strong_signal", "moderate_signal", "watch", "no_signal", "model_probability_only"]:
            m = _market(signal_level=level)
            result = explain_signal(m)
            assert len(result["description"]) > 0

    def test_factors_is_list(self):
        m = _market()
        result = explain_signal(m)
        assert isinstance(result["factors"], list)


# ── supporting_factors ────────────────────────────────────────────────────────

class TestSupportingFactors:
    def test_model_only_no_market_message(self):
        m = _market(signal_level="model_probability_only")
        factors = supporting_factors(m)
        assert any("model probability" in f.lower() for f in factors)
        assert len(factors) == 1

    def test_gap_factor_above(self):
        m = _market(signal_level="watch", market_gap=0.06, data_quality="complete")
        factors = supporting_factors(m)
        assert any("above" in f.lower() for f in factors)

    def test_gap_factor_below(self):
        m = _market(signal_level="watch", market_gap=-0.06, data_quality="complete")
        factors = supporting_factors(m)
        assert any("below" in f.lower() for f in factors)

    def test_high_probability_factor(self):
        m = _market(signal_level="watch", probability=0.75, market_gap=0.04, data_quality="complete")
        factors = supporting_factors(m)
        assert any("high probability" in f.lower() for f in factors)

    def test_low_probability_factor(self):
        m = _market(signal_level="watch", probability=0.10, market_gap=0.04, data_quality="complete")
        factors = supporting_factors(m)
        assert any("variance" in f.lower() or "low-probability" in f.lower() for f in factors)

    def test_short_odds_factor(self):
        m = _market(signal_level="watch", fair_decimal_odds=1.2, market_gap=0.04, data_quality="complete")
        factors = supporting_factors(m)
        assert any("short-odds" in f.lower() for f in factors)

    def test_long_odds_factor(self):
        m = _market(signal_level="watch", probability=0.15, fair_decimal_odds=6.5, market_gap=0.04, data_quality="complete")
        factors = supporting_factors(m)
        assert any("long-odds" in f.lower() for f in factors)

    def test_complete_data_factor(self):
        m = _market(signal_level="watch", market_gap=0.04, data_quality="complete")
        factors = supporting_factors(m)
        assert any("market data" in f.lower() for f in factors)

    def test_no_forbidden_terms_in_factors(self):
        from oracle.betting.schema import check_language
        for level in ["strong_signal", "watch", "no_signal", "model_probability_only"]:
            m = _market(signal_level=level, market_gap=0.08, data_quality="complete")
            factors = supporting_factors(m)
            for f in factors:
                assert check_language(f) == [], f"Forbidden term in: {f}"
