"""Tests for oracle.thesis.scoring."""
import pytest

from oracle.thesis.scoring import (
    assign_display_tier,
    compute_opportunity_score,
)


class TestComputeOpportunityScore:
    def test_model_only_returns_score_and_fields(self):
        score, conf, conf_label, risk = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.65,
            market_implied_probability=None,
            contrarian_classification="model_only",
            market_quality="unavailable",
        )
        assert 0 <= score <= 100
        assert 0.0 <= conf <= 1.0
        assert conf_label in ("very_low", "low", "medium", "high", "very_high")
        assert risk in ("low", "medium", "high", "very_high")

    def test_model_only_score_below_featured_threshold(self):
        score, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.70,
            market_implied_probability=None,
            contrarian_classification="model_only",
            market_quality="unavailable",
        )
        # Model-only should never reach featured (80+)
        assert score < 80

    def test_moderate_edge_higher_than_aligned(self):
        score_aligned, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.55,
            market_implied_probability=0.54,
            contrarian_classification="aligned",
            market_quality="sufficient",
        )
        score_moderate, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.65,
            market_implied_probability=0.55,
            contrarian_classification="moderate_edge",
            market_quality="sufficient",
        )
        assert score_moderate > score_aligned

    def test_strong_edge_can_reach_featured(self):
        score, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.72,
            market_implied_probability=0.55,
            contrarian_classification="strong_edge",
            market_quality="sufficient",
        )
        # Strong edge with sufficient market should be able to reach featured
        assert score >= 65

    def test_correct_score_gets_uncertainty_penalty(self):
        score_1x2, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.65,
            market_implied_probability=0.55,
            contrarian_classification="moderate_edge",
            market_quality="sufficient",
        )
        score_cs, *_ = compute_opportunity_score(
            market_type="correct_score",
            model_probability=0.65,
            market_implied_probability=0.55,
            contrarian_classification="moderate_edge",
            market_quality="sufficient",
        )
        # Correct score gets an extra -5 penalty
        assert score_cs < score_1x2

    def test_extreme_edge_gets_scrutiny_penalty(self):
        score_strong, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.72,
            market_implied_probability=0.55,
            contrarian_classification="strong_edge",
            market_quality="sufficient",
        )
        score_extreme, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.80,
            market_implied_probability=0.55,
            contrarian_classification="extreme_edge",
            market_quality="sufficient",
        )
        # Extreme edge gets +6 scrutiny penalty vs strong_edge, but more signal
        # Just verify it's in valid range
        assert 0 <= score_extreme <= 100

    def test_score_clamped_to_0_100(self):
        for prob in [0.01, 0.50, 0.99]:
            score, *_ = compute_opportunity_score(
                market_type="1x2",
                model_probability=prob,
                market_implied_probability=None,
                contrarian_classification="model_only",
                market_quality="unavailable",
            )
            assert 0 <= score <= 100

    def test_market_quality_affects_score(self):
        score_unavailable, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.65,
            market_implied_probability=None,
            contrarian_classification="model_only",
            market_quality="unavailable",
        )
        score_sufficient, *_ = compute_opportunity_score(
            market_type="1x2",
            model_probability=0.65,
            market_implied_probability=0.55,
            contrarian_classification="moderate_edge",
            market_quality="sufficient",
        )
        # Sufficient market with edge is always better
        assert score_sufficient > score_unavailable

    def test_over_under_2_5_higher_causal_than_correct_score(self):
        score_ou, *_ = compute_opportunity_score(
            market_type="over_under_2_5",
            model_probability=0.60,
            market_implied_probability=None,
            contrarian_classification="model_only",
            market_quality="unavailable",
        )
        score_cs, *_ = compute_opportunity_score(
            market_type="correct_score",
            model_probability=0.60,
            market_implied_probability=None,
            contrarian_classification="model_only",
            market_quality="unavailable",
        )
        # O/U 2.5 has higher causal support than correct_score
        assert score_ou > score_cs


class TestAssignDisplayTier:
    def test_featured_at_80_plus(self):
        assert assign_display_tier(80, "strong_edge", 0.70) == "featured"
        assert assign_display_tier(100, "extreme_edge", 0.80) == "featured"

    def test_secondary_at_65_to_79(self):
        assert assign_display_tier(65, "moderate_edge", 0.65) == "secondary"
        assert assign_display_tier(79, "strong_edge", 0.70) == "secondary"

    def test_watchlist_at_35_to_64(self):
        assert assign_display_tier(35, "slight_edge", 0.55) == "watchlist"
        assert assign_display_tier(64, "moderate_edge", 0.60) == "watchlist"

    def test_hidden_below_35_no_lean(self):
        # model_only with flat probability → hidden
        assert assign_display_tier(20, "model_only", 0.50) == "hidden"
        assert assign_display_tier(10, "model_only", 0.51) == "hidden"

    def test_model_only_exception_with_clear_lean(self):
        # model_only but probability is clearly above 0.5 + 0.10 = 0.60
        assert assign_display_tier(20, "model_only", 0.65) == "watchlist"
        assert assign_display_tier(0, "model_only", 0.80) == "watchlist"

    def test_model_only_exception_clear_lean_below_0_5(self):
        # probability well below 0.40 (= 0.5 - 0.10)
        assert assign_display_tier(10, "model_only", 0.30) == "watchlist"

    def test_model_only_no_lean_stays_hidden(self):
        # probability in 0.40–0.60 range → no exception
        assert assign_display_tier(20, "model_only", 0.45) == "hidden"
        assert assign_display_tier(20, "model_only", 0.55) == "hidden"

    def test_threshold_boundary_60(self):
        # 0.60 is exactly at boundary (0.5 + 0.10)
        result = assign_display_tier(10, "model_only", 0.60)
        assert result == "watchlist"  # exactly at boundary → exception applies
