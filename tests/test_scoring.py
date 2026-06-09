"""Tests: predictions can be scored with proper scoring rules."""
from __future__ import annotations

import math
import pytest

from oracle.scoring.metrics import (
    brier_score,
    log_loss_binary,
    mean_log_loss,
    mean_rps,
    rps,
    rps_1x2,
)
from oracle.harness.backtest import (
    MarketSnapshot,
    MatchResult,
    Prediction,
    run_backtest,
    score_prediction,
)


class TestRPS:
    def test_perfect_prediction_home(self) -> None:
        assert rps([1.0, 0.0, 0.0], outcome_index=0) == pytest.approx(0.0)

    def test_perfect_prediction_draw(self) -> None:
        assert rps([0.0, 1.0, 0.0], outcome_index=1) == pytest.approx(0.0)

    def test_perfect_prediction_away(self) -> None:
        assert rps([0.0, 0.0, 1.0], outcome_index=2) == pytest.approx(0.0)

    def test_worst_prediction_home(self) -> None:
        # predicted all mass on away, outcome was home — worst case
        assert rps([0.0, 0.0, 1.0], outcome_index=0) == pytest.approx(1.0)

    def test_uniform_rps_endpoint_symmetry(self) -> None:
        # RPS is ordinal: home (0) and away (2) are symmetric for uniform predictions
        uniform = [1/3, 1/3, 1/3]
        assert rps(uniform, 0) == pytest.approx(rps(uniform, 2))

    def test_uniform_rps_draw_lower_than_endpoints(self) -> None:
        # Draw (middle position) incurs lower RPS than endpoints — ordinal property
        uniform = [1/3, 1/3, 1/3]
        assert rps(uniform, 1) < rps(uniform, 0)

    def test_rps_in_unit_interval(self) -> None:
        val = rps([0.5, 0.3, 0.2], outcome_index=2)
        assert 0.0 <= val <= 1.0

    def test_raises_on_single_outcome(self) -> None:
        with pytest.raises(ValueError):
            rps([1.0], 0)

    def test_raises_on_bad_outcome_index(self) -> None:
        with pytest.raises(ValueError):
            rps([0.5, 0.5], 5)

    def test_rps_1x2_home_win(self) -> None:
        val = rps_1x2(0.5, 0.3, 0.2, "home")
        assert val == pytest.approx(rps([0.5, 0.3, 0.2], 0))

    def test_rps_1x2_draw(self) -> None:
        val = rps_1x2(0.5, 0.3, 0.2, "draw")
        assert val == pytest.approx(rps([0.5, 0.3, 0.2], 1))

    def test_rps_1x2_away_win(self) -> None:
        val = rps_1x2(0.5, 0.3, 0.2, "away")
        assert val == pytest.approx(rps([0.5, 0.3, 0.2], 2))


class TestLogLoss:
    def test_perfect_positive(self) -> None:
        assert log_loss_binary(1.0, 1) == pytest.approx(0.0, abs=1e-10)

    def test_perfect_negative(self) -> None:
        assert log_loss_binary(0.0, 0) == pytest.approx(0.0, abs=1e-10)

    def test_fifty_fifty(self) -> None:
        val = log_loss_binary(0.5, 1)
        assert val == pytest.approx(math.log(2))

    def test_always_non_negative(self) -> None:
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            assert log_loss_binary(p, 0) >= 0
            assert log_loss_binary(p, 1) >= 0

    def test_mean_log_loss_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            mean_log_loss([])


class TestBrier:
    def test_perfect(self) -> None:
        assert brier_score(1.0, 1) == pytest.approx(0.0)
        assert brier_score(0.0, 0) == pytest.approx(0.0)

    def test_worst_case(self) -> None:
        assert brier_score(1.0, 0) == pytest.approx(1.0)
        assert brier_score(0.0, 1) == pytest.approx(1.0)

    def test_fifty_fifty(self) -> None:
        assert brier_score(0.5, 0) == pytest.approx(0.25)
        assert brier_score(0.5, 1) == pytest.approx(0.25)


class TestScorePrediction:
    def test_score_home_win(
        self, sample_prediction, sample_market_snapshot, sample_result_home_win
    ) -> None:
        result = score_prediction(
            sample_prediction, sample_result_home_win, sample_market_snapshot
        )
        assert result.fixture_id == "wc2026_m001"
        assert 0.0 <= result.rps <= 1.0
        assert result.log_loss_home >= 0.0
        assert result.brier_home >= 0.0
        assert result.market_rps is not None
        assert result.clv_home is not None

    def test_score_without_market(
        self, sample_prediction, sample_result_draw
    ) -> None:
        result = score_prediction(sample_prediction, sample_result_draw, market=None)
        assert result.market_rps is None
        assert result.clv_home is None

    def test_clv_sign(
        self, sample_prediction, sample_market_snapshot, sample_result_home_win
    ) -> None:
        # model p_home=0.42; market implied ~0.424 after devig
        result = score_prediction(
            sample_prediction, sample_result_home_win, sample_market_snapshot
        )
        # CLV should be a small number (close to 0 on a small divergence)
        assert abs(result.clv_home) < 0.10

    def test_perfect_model_beats_market_rps(self) -> None:
        from datetime import datetime, timezone
        pred = Prediction(
            prediction_id="perfect",
            fixture_id="m_test",
            predicted_at=datetime.now(timezone.utc),
            model_version="v0",
            p_home=1.0,
            p_draw=0.0,
            p_away=0.0,
        )
        market = MarketSnapshot(
            fixture_id="m_test",
            bookmaker="test",
            captured_at=datetime.now(timezone.utc),
            odds_home=2.0,
            odds_draw=3.5,
            odds_away=4.0,
        )
        result_obj = MatchResult(fixture_id="m_test", outcome="home")
        scored = score_prediction(pred, result_obj, market)
        assert scored.rps == pytest.approx(0.0)
        assert scored.market_rps > 0.0  # market isn't perfect


class TestRunBacktest:
    def test_empty_predictions_returns_zero_matches(self) -> None:
        result = run_backtest([], [], [])
        assert result["n_matches"] == 0

    def test_single_prediction_scored(
        self,
        sample_prediction,
        sample_market_snapshot,
        sample_result_home_win,
    ) -> None:
        summary = run_backtest(
            predictions=[sample_prediction],
            results=[sample_result_home_win],
            markets=[sample_market_snapshot],
        )
        assert summary["n_matches"] == 1
        assert 0.0 <= summary["mean_rps"] <= 1.0
        assert summary["mean_market_rps"] is not None

    def test_unmatched_prediction_skipped(
        self, sample_prediction
    ) -> None:
        unrelated_result = MatchResult(fixture_id="other_fixture", outcome="draw")
        summary = run_backtest(
            predictions=[sample_prediction],
            results=[unrelated_result],
        )
        assert summary["n_matches"] == 0

    def test_prediction_probs_must_sum_to_one(self) -> None:
        from datetime import datetime, timezone
        with pytest.raises(ValueError, match="sum to 1"):
            Prediction(
                prediction_id="bad",
                fixture_id="m",
                predicted_at=datetime.now(timezone.utc),
                model_version="v0",
                p_home=0.5,
                p_draw=0.5,
                p_away=0.5,  # sums to 1.5
            )
