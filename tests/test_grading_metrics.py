"""
Tests for oracle.grading.grade, oracle.grading.clv, oracle.grading.recommendations,
oracle.grading.trends, oracle.grading.comparison — Week 18.
"""
from __future__ import annotations

import math
import pytest

from oracle.grading.clv import aggregate_clv, compute_clv, compute_entry_clv
from oracle.grading.comparison import compute_model_vs_market
from oracle.grading.grade import (
    compute_brier,
    compute_log_loss,
    compute_rps,
    compute_surprise,
    grade_prediction,
    outcome_from_goals,
)
from oracle.grading.recommendations import (
    aggregate_recommendation_performance,
    grade_recommendation,
)
from oracle.grading.trends import build_performance_trends, compute_window_metrics


# ── outcome_from_goals ────────────────────────────────────────────────────────

class TestOutcomeFromGoals:
    def test_home_win(self):
        assert outcome_from_goals(2, 0) == "home_win"

    def test_draw(self):
        assert outcome_from_goals(1, 1) == "draw"

    def test_away_win(self):
        assert outcome_from_goals(0, 1) == "away_win"

    def test_nil_nil(self):
        assert outcome_from_goals(0, 0) == "draw"


# ── compute_brier ─────────────────────────────────────────────────────────────

class TestBrier:
    def test_perfect_home_win(self):
        score = compute_brier(1.0, 0.0, 0.0, "home_win")
        assert abs(score) < 1e-9

    def test_perfect_draw(self):
        score = compute_brier(0.0, 1.0, 0.0, "draw")
        assert abs(score) < 1e-9

    def test_perfect_away_win(self):
        score = compute_brier(0.0, 0.0, 1.0, "away_win")
        assert abs(score) < 1e-9

    def test_worst_home_win(self):
        # predicted away_win with certainty, home_win happened
        score = compute_brier(0.0, 0.0, 1.0, "home_win")
        assert abs(score - 2.0) < 1e-9

    def test_uniform_prediction(self):
        # 1/3 each; home_win occurred → (1/3-1)^2 + (1/3-0)^2 + (1/3-0)^2 = 4/9+1/9+1/9 = 6/9
        score = compute_brier(1 / 3, 1 / 3, 1 / 3, "home_win")
        assert abs(score - 6 / 9) < 1e-9

    def test_range_nonnegative(self):
        score = compute_brier(0.5, 0.3, 0.2, "draw")
        assert score >= 0


# ── compute_rps ───────────────────────────────────────────────────────────────

class TestRps:
    def test_perfect_home_win(self):
        rps = compute_rps(1.0, 0.0, 0.0, "home_win")
        assert abs(rps) < 1e-9

    def test_perfect_away_win(self):
        rps = compute_rps(0.0, 0.0, 1.0, "away_win")
        assert abs(rps) < 1e-9

    def test_range(self):
        rps = compute_rps(0.4, 0.3, 0.3, "home_win")
        assert 0.0 <= rps <= 1.0

    def test_uniform_rps(self):
        # uniform probs, home_win occurred
        rps = compute_rps(1 / 3, 1 / 3, 1 / 3, "home_win")
        # cum_p1 = 1/3, cum_y1 = 1; cum_p2 = 2/3, cum_y2 = 1
        # RPS = ((1/3-1)^2 + (2/3-1)^2) / 2 = (4/9 + 1/9) / 2 = 5/18
        assert abs(rps - 5 / 18) < 1e-9

    def test_lower_for_better_prediction(self):
        good = compute_rps(0.8, 0.1, 0.1, "home_win")
        bad  = compute_rps(0.1, 0.1, 0.8, "home_win")
        assert good < bad


# ── compute_log_loss ──────────────────────────────────────────────────────────

class TestLogLoss:
    def test_perfect_home_win(self):
        ll = compute_log_loss(1.0, 0.0, 0.0, "home_win")
        assert abs(ll) < 1e-6  # -log(1) = 0

    def test_symmetric_home_away(self):
        ll_h = compute_log_loss(0.5, 0.3, 0.2, "home_win")
        ll_a = compute_log_loss(0.2, 0.3, 0.5, "away_win")
        assert abs(ll_h - ll_a) < 1e-9

    def test_nonnegative(self):
        assert compute_log_loss(0.4, 0.3, 0.3, "draw") >= 0

    def test_higher_for_worse_prediction(self):
        confident = compute_log_loss(0.9, 0.05, 0.05, "home_win")
        uncertain = compute_log_loss(0.33, 0.33, 0.34, "home_win")
        assert confident < uncertain


# ── compute_surprise ──────────────────────────────────────────────────────────

class TestSurprise:
    def test_high_for_low_prob(self):
        assert compute_surprise(0.05) > 0.9

    def test_zero_for_certain(self):
        assert abs(compute_surprise(1.0)) < 1e-9

    def test_range(self):
        s = compute_surprise(0.5)
        assert 0.0 <= s <= 1.0


# ── grade_prediction ──────────────────────────────────────────────────────────

class TestGradePrediction:
    def _grade(self, home_goals=2, away_goals=0, p_h=0.6, p_d=0.25, p_a=0.15):
        return grade_prediction(
            home_win_prob=p_h,
            draw_prob=p_d,
            away_win_prob=p_a,
            market_home_prob=None,
            market_draw_prob=None,
            market_away_prob=None,
            blended_home_prob=p_h,
            blended_draw_prob=p_d,
            blended_away_prob=p_a,
            home_goals=home_goals,
            away_goals=away_goals,
            graded_at="2026-06-11T22:00:00+00:00",
        )

    def test_outcome_set(self):
        g = self._grade(2, 0)
        assert g["outcome"] == "home_win"

    def test_result_known_true(self):
        g = self._grade()
        assert g["result_known"] is True

    def test_brier_present(self):
        g = self._grade()
        assert g["brier"] is not None
        assert g["brier"] >= 0

    def test_rps_present(self):
        g = self._grade()
        assert g["rps"] is not None

    def test_log_loss_present(self):
        g = self._grade()
        assert g["log_loss"] is not None

    def test_correct_side_true_when_home_win_predicted(self):
        g = self._grade(home_goals=2, away_goals=0, p_h=0.7, p_d=0.2, p_a=0.1)
        assert g["correct_side"] is True

    def test_correct_side_false_when_wrong(self):
        g = self._grade(home_goals=0, away_goals=1, p_h=0.7, p_d=0.2, p_a=0.1)
        assert g["correct_side"] is False

    def test_market_metrics_absent_when_no_market(self):
        g = self._grade()
        assert "brier_market" not in g or g.get("brier_market") is None

    def test_market_metrics_computed_when_market_present(self):
        result = grade_prediction(
            home_win_prob=0.6, draw_prob=0.25, away_win_prob=0.15,
            market_home_prob=0.55, market_draw_prob=0.28, market_away_prob=0.17,
            blended_home_prob=0.58, blended_draw_prob=0.26, blended_away_prob=0.16,
            home_goals=2, away_goals=0,
            graded_at="2026-06-11T22:00:00+00:00",
        )
        assert result.get("brier_market") is not None
        assert result.get("brier_blend") is not None

    def test_graded_at_preserved(self):
        g = self._grade()
        assert g["graded_at"] == "2026-06-11T22:00:00+00:00"

    def test_draw_outcome(self):
        g = self._grade(home_goals=1, away_goals=1)
        assert g["outcome"] == "draw"

    def test_away_win_outcome(self):
        g = self._grade(home_goals=0, away_goals=2)
        assert g["outcome"] == "away_win"


# ── CLV ───────────────────────────────────────────────────────────────────────

class TestClv:
    def test_positive_clv(self):
        clv = compute_clv(0.6, 0.5)
        assert abs(clv - 0.1) < 1e-9

    def test_negative_clv(self):
        clv = compute_clv(0.4, 0.5)
        assert abs(clv - (-0.1)) < 1e-9

    def test_zero_clv(self):
        clv = compute_clv(0.5, 0.5)
        assert abs(clv) < 1e-9

    def test_none_when_model_missing(self):
        assert compute_clv(None, 0.5) is None

    def test_none_when_market_missing(self):
        assert compute_clv(0.5, None) is None

    def test_none_when_both_missing(self):
        assert compute_clv(None, None) is None


class TestComputeEntryCLV:
    def test_all_three_computed(self):
        result = compute_entry_clv(
            home_win_prob=0.6, draw_prob=0.25, away_win_prob=0.15,
            market_home_prob=0.55, market_draw_prob=0.28, market_away_prob=0.17,
        )
        assert result["clv_home"] is not None
        assert result["clv_draw"] is not None
        assert result["clv_away"] is not None

    def test_all_none_when_no_market(self):
        result = compute_entry_clv(
            home_win_prob=0.6, draw_prob=0.25, away_win_prob=0.15,
            market_home_prob=None, market_draw_prob=None, market_away_prob=None,
        )
        assert result["clv_home"] is None
        assert result["clv_draw"] is None
        assert result["clv_away"] is None


class TestAggregateCLV:
    def test_empty_returns_nones(self):
        r = aggregate_clv([])
        assert r["n"] == 0
        assert r["average_clv"] is None
        assert r["positive_clv_rate"] is None

    def test_all_positive(self):
        r = aggregate_clv([0.1, 0.05, 0.2])
        assert r["positive_clv_rate"] == 1.0

    def test_all_negative(self):
        r = aggregate_clv([-0.1, -0.05])
        assert r["positive_clv_rate"] == 0.0

    def test_mixed(self):
        r = aggregate_clv([0.1, -0.1, 0.05, -0.05])
        assert abs(r["positive_clv_rate"] - 0.5) < 1e-9

    def test_average_correct(self):
        r = aggregate_clv([0.1, 0.2, 0.3])
        assert abs(r["average_clv"] - 0.2) < 1e-6


# ── Recommendations grading ───────────────────────────────────────────────────

class TestGradeRecommendation:
    def test_won(self):
        g = grade_recommendation(
            recommendation_type="model_gap_detected",
            recommendation_selection="home_win",
            recommendation_confidence="medium",
            edge=0.08,
            outcome="home_win",
        )
        assert g["rec_result"] == "won"

    def test_lost(self):
        g = grade_recommendation(
            recommendation_type="model_gap_detected",
            recommendation_selection="home_win",
            recommendation_confidence="medium",
            edge=0.08,
            outcome="away_win",
        )
        assert g["rec_result"] == "lost"

    def test_push_for_no_recommendation(self):
        g = grade_recommendation(
            recommendation_type="no_recommendation",
            recommendation_selection=None,
            recommendation_confidence="unknown",
            edge=None,
            outcome="home_win",
        )
        assert g["rec_result"] == "push"

    def test_push_for_watch(self):
        g = grade_recommendation(
            recommendation_type="watch",
            recommendation_selection=None,
            recommendation_confidence="low",
            edge=0.03,
            outcome="draw",
        )
        assert g["rec_result"] == "push"

    def test_ungraded_when_no_outcome(self):
        g = grade_recommendation(
            recommendation_type="model_gap_detected",
            recommendation_selection="home_win",
            recommendation_confidence="high",
            edge=0.12,
            outcome=None,
        )
        assert g["rec_result"] == "ungraded"

    def test_edge_bucket_small(self):
        g = grade_recommendation("no_recommendation", None, None, edge=0.02, outcome="home_win")
        assert g["edge_bucket"] == "small"

    def test_edge_bucket_medium(self):
        g = grade_recommendation("no_recommendation", None, None, edge=0.08, outcome="home_win")
        assert g["edge_bucket"] == "medium"

    def test_edge_bucket_large(self):
        g = grade_recommendation("no_recommendation", None, None, edge=0.12, outcome="home_win")
        assert g["edge_bucket"] == "large"

    def test_edge_bucket_none_when_no_edge(self):
        g = grade_recommendation("no_recommendation", None, None, edge=None, outcome="home_win")
        assert g["edge_bucket"] is None


class TestAggregateRecommendationPerformance:
    def _make_graded(self, rec_result, rec_type="model_gap_detected",
                     edge_bucket="medium", conf_bucket="medium"):
        return {
            "rec_result": rec_result,
            "recommendation_type": rec_type,
            "edge_bucket": edge_bucket,
            "conf_bucket": conf_bucket,
        }

    def test_empty(self):
        r = aggregate_recommendation_performance([])
        assert r["n_total"] == 0
        assert r["hit_rate"] is None

    def test_all_won(self):
        rows = [self._make_graded("won")] * 3
        r = aggregate_recommendation_performance(rows)
        assert r["n_won"] == 3
        assert r["hit_rate"] == 1.0

    def test_all_lost(self):
        rows = [self._make_graded("lost")] * 2
        r = aggregate_recommendation_performance(rows)
        assert r["n_lost"] == 2
        assert r["hit_rate"] == 0.0

    def test_push_not_in_actionable(self):
        rows = [self._make_graded("push"), self._make_graded("won")]
        r = aggregate_recommendation_performance(rows)
        assert r["n_push"] == 1
        assert r["n_actionable"] == 1

    def test_hit_rate_fifty_percent(self):
        rows = [self._make_graded("won"), self._make_graded("lost")]
        r = aggregate_recommendation_performance(rows)
        assert abs(r["hit_rate"] - 0.5) < 1e-9

    def test_note_field_present(self):
        r = aggregate_recommendation_performance([])
        assert "note" in r


# ── Trends ────────────────────────────────────────────────────────────────────

def _fake_graded(n: int = 5) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "brier": 0.3 + i * 0.01,
            "rps": 0.2 + i * 0.01,
            "log_loss": 0.8 + i * 0.01,
            "brier_market": None,
            "rps_market": None,
            "brier_blend": None,
            "rps_blend": None,
            "clv_home": 0.05,
            "clv_draw": None,
            "clv_away": -0.02,
            "correct_side": i % 2 == 0,
            "recommendation_type": "model_gap_detected" if i % 2 == 0 else "no_recommendation",
        })
    return rows


class TestComputeWindowMetrics:
    def test_empty_all_nones(self):
        r = compute_window_metrics([], window=10)
        assert r["n_matches"] == 0
        assert r["mean_brier"] is None

    def test_window_limits_rows(self):
        rows = _fake_graded(20)
        r = compute_window_metrics(rows, window=5)
        assert r["n_matches"] == 5

    def test_none_window_uses_all(self):
        rows = _fake_graded(8)
        r = compute_window_metrics(rows, window=None)
        assert r["n_matches"] == 8

    def test_mean_brier_computed(self):
        rows = _fake_graded(4)
        r = compute_window_metrics(rows, window=None)
        assert r["mean_brier"] is not None

    def test_positive_clv_rate(self):
        rows = _fake_graded(4)
        r = compute_window_metrics(rows, window=None)
        # clv_home=0.05 > 0, clv_away=-0.02 < 0; max per row = 0.05 > 0 → all positive
        assert r["positive_clv_rate"] == 1.0


class TestBuildPerformanceTrends:
    def test_structure(self):
        rows = _fake_graded(30)
        result = build_performance_trends(rows)
        assert "n_graded_total" in result
        assert "windows" in result
        assert len(result["windows"]) == 4  # last 10, 25, 50, all-time

    def test_empty(self):
        result = build_performance_trends([])
        assert result["n_graded_total"] == 0

    def test_all_time_window_null(self):
        rows = _fake_graded(5)
        result = build_performance_trends(rows)
        all_time = [w for w in result["windows"] if w["window"] is None]
        assert len(all_time) == 1


# ── Model vs Market comparison ────────────────────────────────────────────────

def _fake_graded_with_market(n: int = 5) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "brier": 0.3 + i * 0.01,
            "rps": 0.2,
            "log_loss": 0.8,
            "brier_market": 0.35 + i * 0.01,
            "rps_market": 0.25,
            "log_loss_market": 0.9,
            "brier_blend": 0.28 + i * 0.01,
            "rps_blend": 0.18,
            "log_loss_blend": 0.75,
        })
    return rows


class TestComputeModelVsMarket:
    def test_empty(self):
        r = compute_model_vs_market([])
        assert r["n_graded"] == 0
        assert r["winner"] is None

    def test_winner_is_one_of_three(self):
        rows = _fake_graded_with_market(5)
        r = compute_model_vs_market(rows)
        assert r["winner"] in ("model", "market", "blend")

    def test_blend_wins_in_fixture(self):
        rows = _fake_graded_with_market(5)
        r = compute_model_vs_market(rows)
        # blend brier is smallest → blend should win
        assert r["winner"] == "blend"

    def test_disclaimer_present(self):
        r = compute_model_vs_market([])
        assert "disclaimer" in r

    def test_metrics_all_present(self):
        rows = _fake_graded_with_market(3)
        r = compute_model_vs_market(rows)
        assert "brier" in r and "rps" in r and "log_loss" in r
