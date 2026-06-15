"""
Tests for oracle.betting.markets — Week 22.
"""
from __future__ import annotations

import math
import pytest
import numpy as np

from oracle.betting.markets import (
    compute_1x2_markets,
    compute_double_chance,
    compute_draw_no_bet,
    compute_goal_markets,
    compute_btts,
    compute_correct_scores,
    compute_all_markets,
    _classify_signal,
    _fair_odds,
)
from oracle.betting.schema import BetMarketProbability


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_grid(home_goals: int = 1, away_goals: int = 0) -> np.ndarray:
    """Grid heavily skewed toward one scoreline."""
    g = np.zeros((11, 11), dtype=float)
    g[home_goals, away_goals] = 0.90
    # Spread remainder into cells that don't clash with the target
    for (h, a) in [(0, 0), (3, 2)]:
        if h != home_goals or a != away_goals:
            g[h, a] = 0.05
    s = g.sum()
    return g / s


def _uniform_grid() -> np.ndarray:
    g = np.ones((11, 11), dtype=float)
    return g / g.sum()


# ── _classify_signal ──────────────────────────────────────────────────────────

class TestClassifySignal:
    def test_no_market_data(self):
        assert _classify_signal(0.15, False) == "model_probability_only"

    def test_gap_none_no_market(self):
        assert _classify_signal(None, False) == "model_probability_only"

    def test_gap_none_with_market(self):
        assert _classify_signal(None, True) == "model_probability_only"

    def test_below_threshold_no_signal(self):
        assert _classify_signal(0.02, True) == "no_signal"

    def test_at_threshold_watch(self):
        assert _classify_signal(0.03, True) == "watch"

    def test_moderate(self):
        assert _classify_signal(0.07, True) == "moderate_signal"

    def test_strong(self):
        assert _classify_signal(0.12, True) == "strong_signal"

    def test_negative_gap_watch(self):
        assert _classify_signal(-0.04, True) == "watch"

    def test_negative_gap_strong(self):
        assert _classify_signal(-0.15, True) == "strong_signal"


# ── _fair_odds ────────────────────────────────────────────────────────────────

class TestFairOdds:
    def test_normal(self):
        result = _fair_odds(0.5)
        assert result == pytest.approx(2.0, rel=1e-5)

    def test_zero_returns_none(self):
        assert _fair_odds(0.0) is None

    def test_negative_returns_none(self):
        assert _fair_odds(-0.1) is None

    def test_one_returns_1(self):
        assert _fair_odds(1.0) == pytest.approx(1.0, rel=1e-5)


# ── compute_1x2_markets ───────────────────────────────────────────────────────

class TestCompute1x2Markets:
    def test_returns_3_markets(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27)
        assert len(result) == 3

    def test_selections(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27)
        sels = {r.selection for r in result}
        assert sels == {"home_win", "draw", "away_win"}

    def test_market_type_is_1x2(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27)
        for r in result:
            assert r.market_type == "1x2"

    def test_probabilities_match(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27)
        by_sel = {r.selection: r for r in result}
        assert by_sel["home_win"].probability == pytest.approx(0.45, abs=1e-4)
        assert by_sel["draw"].probability == pytest.approx(0.28, abs=1e-4)
        assert by_sel["away_win"].probability == pytest.approx(0.27, abs=1e-4)

    def test_no_market_data_model_probability_only(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27, has_market_data=False)
        for r in result:
            assert r.signal_level == "model_probability_only"
            assert r.market_probability is None
            assert r.market_gap is None

    def test_with_market_data_gap_computed(self):
        result = compute_1x2_markets(
            "m1", 0.52, 0.28, 0.20,
            market_home=0.40, market_draw=0.30, market_away=0.30,
            has_market_data=True,
        )
        by_sel = {r.selection: r for r in result}
        # home gap: 0.52 - 0.40 = 0.12 → strong_signal (clearly > 0.10)
        assert by_sel["home_win"].signal_level == "strong_signal"
        assert by_sel["home_win"].market_gap == pytest.approx(0.12, abs=1e-3)

    def test_strong_signal_threshold(self):
        result = compute_1x2_markets(
            "m1", 0.60, 0.25, 0.15,
            market_home=0.45, market_draw=0.30, market_away=0.25,
            has_market_data=True,
        )
        by_sel = {r.selection: r for r in result}
        assert by_sel["home_win"].signal_level == "strong_signal"

    def test_no_forbidden_language_in_reason(self):
        from oracle.betting.schema import check_language
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27)
        for r in result:
            assert check_language(r.reason) == []

    def test_data_quality_complete_with_market(self):
        result = compute_1x2_markets(
            "m1", 0.5, 0.28, 0.22,
            market_home=0.42, market_draw=0.30, market_away=0.28,
            has_market_data=True,
        )
        for r in result:
            assert r.data_quality == "complete"

    def test_data_quality_model_only_without_market(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27, has_market_data=False)
        for r in result:
            assert r.data_quality == "model_only"

    def test_model_source(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27)
        for r in result:
            assert r.model_source == "elo_blend"

    def test_generated_at_propagated(self):
        result = compute_1x2_markets("m1", 0.45, 0.28, 0.27, generated_at="2026-06-01")
        for r in result:
            assert r.generated_at == "2026-06-01"

    def test_fair_odds_set(self):
        result = compute_1x2_markets("m1", 0.5, 0.25, 0.25)
        by_sel = {r.selection: r for r in result}
        assert by_sel["home_win"].fair_decimal_odds == pytest.approx(2.0, rel=1e-3)


# ── compute_double_chance ─────────────────────────────────────────────────────

class TestComputeDoubleChance:
    def test_returns_3_markets(self):
        result = compute_double_chance("m1", 0.45, 0.28, 0.27)
        assert len(result) == 3

    def test_selections(self):
        result = compute_double_chance("m1", 0.45, 0.28, 0.27)
        sels = {r.selection for r in result}
        assert sels == {"home_or_draw", "home_or_away", "draw_or_away"}

    def test_probabilities_sum_correctly(self):
        result = compute_double_chance("m1", 0.45, 0.28, 0.27)
        by_sel = {r.selection: r for r in result}
        assert by_sel["home_or_draw"].probability == pytest.approx(0.73, abs=1e-4)
        assert by_sel["home_or_away"].probability == pytest.approx(0.72, abs=1e-4)
        assert by_sel["draw_or_away"].probability == pytest.approx(0.55, abs=1e-4)

    def test_all_model_probability_only(self):
        result = compute_double_chance("m1", 0.45, 0.28, 0.27)
        for r in result:
            assert r.signal_level == "model_probability_only"

    def test_market_type(self):
        result = compute_double_chance("m1", 0.45, 0.28, 0.27)
        for r in result:
            assert r.market_type == "double_chance"

    def test_prob_capped_at_1(self):
        result = compute_double_chance("m1", 0.60, 0.40, 0.00)
        by_sel = {r.selection: r for r in result}
        assert by_sel["home_or_draw"].probability <= 1.0

    def test_no_forbidden_language(self):
        from oracle.betting.schema import check_language
        result = compute_double_chance("m1", 0.45, 0.28, 0.27)
        for r in result:
            assert check_language(r.reason) == []


# ── compute_draw_no_bet ───────────────────────────────────────────────────────

class TestComputeDrawNoBet:
    def test_returns_2_markets(self):
        result = compute_draw_no_bet("m1", 0.45, 0.27)
        assert len(result) == 2

    def test_probabilities_sum_to_1(self):
        result = compute_draw_no_bet("m1", 0.45, 0.27)
        total = sum(r.probability for r in result)
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_selections(self):
        result = compute_draw_no_bet("m1", 0.45, 0.27)
        sels = {r.selection for r in result}
        assert sels == {"home_win", "away_win"}

    def test_market_type(self):
        result = compute_draw_no_bet("m1", 0.45, 0.27)
        for r in result:
            assert r.market_type == "draw_no_bet"

    def test_zero_total_gives_half_half(self):
        result = compute_draw_no_bet("m1", 0.0, 0.0)
        for r in result:
            assert r.probability == pytest.approx(0.5, abs=1e-4)


# ── compute_goal_markets ──────────────────────────────────────────────────────

class TestComputeGoalMarkets:
    def test_returns_6_markets(self):
        grid = _uniform_grid()
        result = compute_goal_markets("m1", grid)
        assert len(result) == 6

    def test_market_types(self):
        grid = _uniform_grid()
        result = compute_goal_markets("m1", grid)
        types = {r.market_type for r in result}
        assert types == {"over_under_1_5", "over_under_2_5", "over_under_3_5"}

    def test_over_under_sum_to_1(self):
        grid = _uniform_grid()
        result = compute_goal_markets("m1", grid)
        for market_type in ["over_under_1_5", "over_under_2_5", "over_under_3_5"]:
            rows = [r for r in result if r.market_type == market_type]
            total = sum(r.probability for r in rows)
            assert total == pytest.approx(1.0, abs=1e-4)

    def test_probabilities_in_range(self):
        grid = _uniform_grid()
        result = compute_goal_markets("m1", grid)
        for r in result:
            assert 0.0 <= r.probability <= 1.0

    def test_skewed_grid_high_scoring(self):
        grid = _fake_grid(home_goals=3, away_goals=2)
        result = compute_goal_markets("m1", grid)
        by_type_sel = {(r.market_type, r.selection): r for r in result}
        # 3+2 = 5 goals → over 2.5 should be high
        assert by_type_sel[("over_under_2_5", "over")].probability > 0.5

    def test_model_source_dixon_coles(self):
        grid = _uniform_grid()
        result = compute_goal_markets("m1", grid)
        for r in result:
            assert r.model_source == "dixon_coles"

    def test_all_model_probability_only(self):
        grid = _uniform_grid()
        result = compute_goal_markets("m1", grid)
        for r in result:
            assert r.signal_level == "model_probability_only"


# ── compute_btts ──────────────────────────────────────────────────────────────

class TestComputeBtts:
    def test_returns_2_markets(self):
        grid = _uniform_grid()
        result = compute_btts("m1", grid)
        assert len(result) == 2

    def test_selections(self):
        grid = _uniform_grid()
        result = compute_btts("m1", grid)
        sels = {r.selection for r in result}
        assert sels == {"yes", "no"}

    def test_probs_sum_to_1(self):
        grid = _uniform_grid()
        result = compute_btts("m1", grid)
        total = sum(r.probability for r in result)
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_market_type(self):
        grid = _uniform_grid()
        result = compute_btts("m1", grid)
        for r in result:
            assert r.market_type == "btts"

    def test_skewed_grid_no_score_game(self):
        grid = np.zeros((11, 11), dtype=float)
        grid[0, 0] = 1.0  # 0-0 clean sheet
        result = compute_btts("m1", grid)
        by_sel = {r.selection: r for r in result}
        assert by_sel["no"].probability == pytest.approx(1.0, abs=1e-4)
        assert by_sel["yes"].probability == pytest.approx(0.0, abs=1e-4)


# ── compute_correct_scores ────────────────────────────────────────────────────

class TestComputeCorrectScores:
    def test_returns_top_5(self):
        grid = _uniform_grid()
        result = compute_correct_scores("m1", grid)
        assert len(result) == 5

    def test_custom_top_n(self):
        grid = _uniform_grid()
        result = compute_correct_scores("m1", grid, top_n=3)
        assert len(result) == 3

    def test_market_type(self):
        grid = _uniform_grid()
        result = compute_correct_scores("m1", grid)
        for r in result:
            assert r.market_type == "correct_score"

    def test_risk_label_high(self):
        grid = _uniform_grid()
        result = compute_correct_scores("m1", grid)
        for r in result:
            assert r.risk_label == "high"

    def test_sorted_by_probability_desc(self):
        grid = _fake_grid(home_goals=1, away_goals=0)
        result = compute_correct_scores("m1", grid)
        probs = [r.probability for r in result]
        assert probs == sorted(probs, reverse=True)

    def test_top_scoreline_matches_skewed_grid(self):
        grid = _fake_grid(home_goals=2, away_goals=1)
        result = compute_correct_scores("m1", grid, top_n=1)
        assert result[0].selection == "2-1"

    def test_selection_format(self):
        grid = _uniform_grid()
        result = compute_correct_scores("m1", grid)
        for r in result:
            parts = r.selection.split("-")
            assert len(parts) == 2
            assert all(p.isdigit() for p in parts)


# ── compute_all_markets ───────────────────────────────────────────────────────

class TestComputeAllMarkets:
    def test_without_grid(self):
        result = compute_all_markets("m1", 0.45, 0.28, 0.27, None)
        # 3 (1x2) + 3 (dc) + 2 (dnb) = 8
        assert len(result) == 8

    def test_with_grid(self):
        grid = _uniform_grid()
        result = compute_all_markets("m1", 0.45, 0.28, 0.27, grid)
        # 8 + 6 (ou) + 2 (btts) + 5 (cs) = 21
        assert len(result) == 21

    def test_all_are_bet_market_probability(self):
        grid = _uniform_grid()
        result = compute_all_markets("m1", 0.45, 0.28, 0.27, grid)
        for r in result:
            assert isinstance(r, BetMarketProbability)

    def test_no_forbidden_language_any_market(self):
        from oracle.betting.schema import check_language
        grid = _uniform_grid()
        result = compute_all_markets("m1", 0.45, 0.28, 0.27, grid)
        for r in result:
            assert check_language(r.reason) == []
            for w in r.warnings:
                assert check_language(w) == []
