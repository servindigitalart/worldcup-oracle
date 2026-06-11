"""
Tests for oracle.grading.true_clv and oracle.grading.recommendation_clv — Week 20.
"""
from __future__ import annotations

import pytest

from oracle.grading.recommendation_clv import compute_recommendation_clv
from oracle.grading.true_clv import (
    aggregate_true_clv,
    compute_entry_true_clv,
    compute_true_clv,
)


# ── compute_true_clv ──────────────────────────────────────────────────────────

class TestComputeTrueClv:
    def test_closing_locked_returns_value(self):
        result = compute_true_clv(0.55, 0.45, "closing_locked")
        assert result is not None
        assert abs(result - 0.10) < 1e-6

    def test_not_locked_returns_none(self):
        for status in ("opening_only", "latest_available", "closing_candidate",
                       "no_market_data"):
            assert compute_true_clv(0.55, 0.45, status) is None

    def test_none_closing_prob_returns_none(self):
        assert compute_true_clv(0.55, None, "closing_locked") is None

    def test_negative_clv(self):
        result = compute_true_clv(0.30, 0.50, "closing_locked")
        assert result is not None
        assert result < 0

    def test_rounding_to_6_places(self):
        result = compute_true_clv(0.5555555, 0.4444444, "closing_locked")
        assert result is not None
        assert len(str(result).split(".")[-1]) <= 6


# ── compute_entry_true_clv ────────────────────────────────────────────────────

class TestComputeEntryTrueClv:
    def test_closing_locked_all_three(self):
        result = compute_entry_true_clv(
            home_win_prob=0.50,
            draw_prob=0.25,
            away_win_prob=0.25,
            closing_home_prob=0.45,
            closing_draw_prob=0.28,
            closing_away_prob=0.27,
            closing_status="closing_locked",
        )
        assert result["true_clv_home"] is not None
        assert result["true_clv_draw"] is not None
        assert result["true_clv_away"] is not None

    def test_not_locked_all_none(self):
        result = compute_entry_true_clv(
            home_win_prob=0.50,
            draw_prob=0.25,
            away_win_prob=0.25,
            closing_home_prob=0.45,
            closing_draw_prob=0.28,
            closing_away_prob=0.27,
            closing_status="latest_available",
        )
        assert result["true_clv_home"] is None
        assert result["true_clv_draw"] is None
        assert result["true_clv_away"] is None

    def test_returns_dict_with_correct_keys(self):
        result = compute_entry_true_clv(
            home_win_prob=0.4, draw_prob=0.3, away_win_prob=0.3,
            closing_home_prob=None, closing_draw_prob=None, closing_away_prob=None,
            closing_status="closing_locked",
        )
        assert set(result.keys()) == {"true_clv_home", "true_clv_draw", "true_clv_away"}

    def test_none_closing_probs_with_locked_status(self):
        result = compute_entry_true_clv(
            home_win_prob=0.4, draw_prob=0.3, away_win_prob=0.3,
            closing_home_prob=None, closing_draw_prob=None, closing_away_prob=None,
            closing_status="closing_locked",
        )
        assert result["true_clv_home"] is None
        assert result["true_clv_draw"] is None
        assert result["true_clv_away"] is None


# ── aggregate_true_clv ────────────────────────────────────────────────────────

class TestAggregateTrueClv:
    def test_empty_returns_zeros(self):
        result = aggregate_true_clv([])
        assert result["n"] == 0
        assert result["average_true_clv"] is None
        assert result["median_true_clv"] is None
        assert result["positive_true_clv_rate"] is None

    def test_all_none_values(self):
        rows = [{"true_clv_home": None, "true_clv_draw": None, "true_clv_away": None}]
        result = aggregate_true_clv(rows)
        assert result["n"] == 0

    def test_positive_values(self):
        rows = [
            {"true_clv_home": 0.05, "true_clv_draw": 0.02, "true_clv_away": 0.01},
        ]
        result = aggregate_true_clv(rows)
        assert result["n"] == 3
        assert result["average_true_clv"] is not None
        assert result["positive_true_clv_rate"] == 1.0

    def test_mixed_positive_negative(self):
        rows = [
            {"true_clv_home": 0.10, "true_clv_draw": None, "true_clv_away": -0.05},
        ]
        result = aggregate_true_clv(rows)
        assert result["n"] == 2
        assert result["positive_true_clv_rate"] == 0.5

    def test_note_present(self):
        result = aggregate_true_clv([])
        assert "note" in result
        assert len(result["note"]) > 0


# ── compute_recommendation_clv ────────────────────────────────────────────────

class TestComputeRecommendationClv:
    def _row(self, match_id="m001", rec_type="model_gap_detected",
             selection="home", home_prob=0.55, draw_prob=0.25, away_prob=0.20):
        return {
            "match_id": match_id,
            "home_team": "teamA",
            "away_team": "teamB",
            "recommendation_type": rec_type,
            "recommendation_selection": selection,
            "recommendation_confidence": "medium",
            "rec_result": "won",
            "home_win_prob": home_prob,
            "draw_prob": draw_prob,
            "away_win_prob": away_prob,
        }

    def _closing(self, match_id="m001", status="closing_locked",
                 home=0.45, draw=0.28, away=0.27):
        return {
            match_id: {
                "closing_status": status,
                "closing_home_prob": home,
                "closing_draw_prob": draw,
                "closing_away_prob": away,
            }
        }

    def test_returns_dict_with_required_keys(self):
        result = compute_recommendation_clv(
            graded_rows=[self._row()],
            closing_lines=self._closing(),
        )
        for key in ("n_recommendations", "n_with_closing_line",
                    "average_true_clv", "recommendations", "note", "disclaimer"):
            assert key in result

    def test_closing_locked_computes_clv(self):
        result = compute_recommendation_clv(
            graded_rows=[self._row()],
            closing_lines=self._closing(status="closing_locked"),
        )
        assert result["n_recommendations"] == 1
        assert result["n_with_closing_line"] == 1
        recs = result["recommendations"]
        assert recs[0]["true_clv"] is not None

    def test_not_locked_no_clv(self):
        result = compute_recommendation_clv(
            graded_rows=[self._row()],
            closing_lines=self._closing(status="latest_available"),
        )
        assert result["n_with_closing_line"] == 0
        assert result["average_true_clv"] is None

    def test_non_model_gap_excluded(self):
        row = self._row(rec_type="no_recommendation")
        result = compute_recommendation_clv(
            graded_rows=[row],
            closing_lines=self._closing(),
        )
        assert result["n_recommendations"] == 0

    def test_empty_rows(self):
        result = compute_recommendation_clv(graded_rows=[], closing_lines={})
        assert result["n_recommendations"] == 0
        assert result["average_true_clv"] is None

    def test_missing_closing_lines_for_match(self):
        result = compute_recommendation_clv(
            graded_rows=[self._row(match_id="m999")],
            closing_lines={},  # no closing line for m999
        )
        assert result["n_with_closing_line"] == 0

    def test_draw_selection(self):
        row = self._row(selection="draw")
        result = compute_recommendation_clv(
            graded_rows=[row],
            closing_lines=self._closing(status="closing_locked"),
        )
        assert result["n_recommendations"] == 1
        recs = result["recommendations"]
        # draw: model 0.25, closing 0.28 → true_clv = -0.03
        assert recs[0]["true_clv"] is not None
        assert recs[0]["true_clv"] < 0

    def test_invalid_selection_excluded(self):
        row = self._row(selection="invalid_side")
        result = compute_recommendation_clv(
            graded_rows=[row],
            closing_lines=self._closing(),
        )
        assert result["n_recommendations"] == 0
