"""
Tests for oracle.scoring.reliability — Week 15.

Coverage:
  - ece_from_bins: correct formula, edge cases
  - sharpness: correct mean max-probability
  - log_loss_1x2: proper multi-class log-loss
  - brier_multi: proper multi-class Brier
  - calibration_badge: threshold correctness
  - reliability_dict: structure and content
"""
from __future__ import annotations

import math
import pytest

from oracle.scoring.reliability import (
    brier_multi,
    calibration_badge,
    ece_from_bins,
    log_loss_1x2,
    reliability_dict,
    sharpness,
)


# ── ece_from_bins ─────────────────────────────────────────────────────────────

class TestEce:
    def _bins(self, predicted, actual, n=10):
        """Helper to build a single-bin list."""
        return [{"n_matches": n, "mean_predicted": predicted, "observed_rate": actual}]

    def test_perfect_calibration_gives_zero(self):
        bins = [
            {"n_matches": 10, "mean_predicted": 0.3, "observed_rate": 0.3},
            {"n_matches": 10, "mean_predicted": 0.6, "observed_rate": 0.6},
        ]
        assert ece_from_bins(bins) == pytest.approx(0.0)

    def test_single_bin_formula(self):
        # ECE = |0.6 - 0.5| = 0.1 (one bin, all weight = 1.0)
        bins = self._bins(0.6, 0.5, n=20)
        assert ece_from_bins(bins) == pytest.approx(0.1)

    def test_weighted_by_sample_count(self):
        # Two bins of unequal size; ECE should weight accordingly
        bins = [
            {"n_matches": 10, "mean_predicted": 0.5, "observed_rate": 0.4},   # gap=0.1
            {"n_matches": 90, "mean_predicted": 0.7, "observed_rate": 0.72},  # gap=0.02
        ]
        total = 100
        expected = (10/100)*0.1 + (90/100)*0.02
        assert ece_from_bins(bins) == pytest.approx(expected)

    def test_empty_returns_nan(self):
        result = ece_from_bins([])
        assert math.isnan(result)

    def test_zero_total_returns_nan(self):
        bins = [{"n_matches": 0, "mean_predicted": 0.5, "observed_rate": 0.5}]
        result = ece_from_bins(bins)
        assert math.isnan(result)

    def test_non_negative(self):
        # ECE is always >= 0
        bins = [
            {"n_matches": 14, "mean_predicted": 0.207, "observed_rate": 0.214},
            {"n_matches": 14, "mean_predicted": 0.270, "observed_rate": 0.071},
        ]
        assert ece_from_bins(bins) >= 0

    def test_multiple_bins_from_real_data(self):
        # From calibration_worldcups.json (elo-baseline-v0.2, first two bins)
        bins = [
            {"n_matches": 14, "mean_predicted": 0.2078, "observed_rate": 0.2143},
            {"n_matches": 14, "mean_predicted": 0.2708, "observed_rate": 0.0714},
        ]
        result = ece_from_bins(bins)
        assert 0.0 < result < 0.15

    def test_returns_float(self):
        bins = [{"n_matches": 10, "mean_predicted": 0.4, "observed_rate": 0.45}]
        assert isinstance(ece_from_bins(bins), float)


# ── sharpness ─────────────────────────────────────────────────────────────────

class TestSharpness:
    def test_uniform_approx_one_third(self):
        probs = [(1/3, 1/3, 1/3)] * 30
        result = sharpness(probs)
        assert result == pytest.approx(1/3, abs=1e-9)

    def test_all_certain_gives_one(self):
        probs = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        result = sharpness(probs)
        assert result == pytest.approx(1.0)

    def test_empty_returns_nan(self):
        assert math.isnan(sharpness([]))

    def test_single_prediction(self):
        result = sharpness([(0.7, 0.2, 0.1)])
        assert result == pytest.approx(0.7)

    def test_higher_concentration_gives_higher_sharpness(self):
        low  = sharpness([(0.4, 0.3, 0.3)])
        high = sharpness([(0.8, 0.15, 0.05)])
        assert high > low

    def test_realistic_values_above_one_third(self):
        probs = [
            (0.55, 0.25, 0.20),
            (0.45, 0.30, 0.25),
            (0.60, 0.22, 0.18),
        ]
        result = sharpness(probs)
        assert result > 1/3


# ── log_loss_1x2 ─────────────────────────────────────────────────────────────

class TestLogLoss1x2:
    def test_perfect_prediction_gives_zero(self):
        probs = [(1.0, 0.0, 0.0)]
        outcomes = ["home"]
        result = log_loss_1x2(probs, outcomes)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_wrong_prediction_gives_high_loss(self):
        probs = [(0.99, 0.005, 0.005)]
        outcomes = ["away"]
        result = log_loss_1x2(probs, outcomes)
        assert result > 4.0

    def test_uniform_gives_log_3(self):
        probs = [(1/3, 1/3, 1/3)]
        for outcome in ["home", "draw", "away"]:
            result = log_loss_1x2(probs, [outcome])
            assert result == pytest.approx(math.log(3), abs=1e-9)

    def test_mean_over_multiple_predictions(self):
        probs = [(0.7, 0.2, 0.1), (0.3, 0.4, 0.3)]
        outcomes = ["home", "draw"]
        result = log_loss_1x2(probs, outcomes)
        expected = (-math.log(0.7) - math.log(0.4)) / 2
        assert result == pytest.approx(expected)

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            log_loss_1x2([(0.5, 0.3, 0.2)], ["home", "draw"])

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            log_loss_1x2([], [])

    def test_all_outcomes(self):
        probs = [(0.5, 0.3, 0.2)]
        for outcome, idx in [("home", 0), ("draw", 1), ("away", 2)]:
            result = log_loss_1x2(probs, [outcome])
            assert result == pytest.approx(-math.log(probs[0][idx]))


# ── brier_multi ───────────────────────────────────────────────────────────────

class TestBrierMulti:
    def test_perfect_prediction_gives_zero(self):
        probs = [(1.0, 0.0, 0.0)]
        result = brier_multi(probs, ["home"])
        assert result == pytest.approx(0.0)

    def test_worst_prediction(self):
        # Predict 1.0 for home, but outcome is away: (1-0)^2 + (0-0)^2 + (0-1)^2 = 2, /3 = 2/3
        probs = [(1.0, 0.0, 0.0)]
        result = brier_multi(probs, ["away"])
        assert result == pytest.approx(2/3)

    def test_uniform_gives_expected(self):
        # (1/3-1)^2 + (1/3-0)^2 + (1/3-0)^2 = (2/3)^2 + 2*(1/3)^2 = 4/9 + 2/9 = 6/9 = 2/3; /3 = 2/9
        probs = [(1/3, 1/3, 1/3)]
        result = brier_multi(probs, ["home"])
        assert result == pytest.approx(2/9)

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            brier_multi([(0.5, 0.3, 0.2)], ["home", "draw"])

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            brier_multi([], [])

    def test_lower_for_better_prediction(self):
        good = brier_multi([(0.8, 0.1, 0.1)], ["home"])
        bad  = brier_multi([(0.2, 0.4, 0.4)], ["home"])
        assert good < bad


# ── calibration_badge ─────────────────────────────────────────────────────────

class TestCalibrationBadge:
    def test_excellent_threshold(self):
        assert calibration_badge(0.01) == "excellent"
        assert calibration_badge(0.019) == "excellent"

    def test_good_threshold(self):
        assert calibration_badge(0.02) == "good"
        assert calibration_badge(0.049) == "good"

    def test_fair_threshold(self):
        assert calibration_badge(0.05) == "fair"
        assert calibration_badge(0.099) == "fair"

    def test_poor_threshold(self):
        assert calibration_badge(0.10) == "poor"
        assert calibration_badge(0.25) == "poor"

    def test_nan_returns_unknown(self):
        assert calibration_badge(float("nan")) == "unknown"

    def test_zero_is_excellent(self):
        assert calibration_badge(0.0) == "excellent"


# ── reliability_dict ──────────────────────────────────────────────────────────

class TestReliabilityDict:
    def _make_dict(self, **overrides):
        defaults = dict(
            rps=0.217, log_loss=0.98, brier=0.19,
            ece=0.058, sharp=0.45, n_matches=144,
            model_version="elo-baseline-v0.2",
        )
        defaults.update(overrides)
        return reliability_dict(**defaults)

    def test_required_keys_present(self):
        d = self._make_dict()
        for key in ("rps", "log_loss", "brier", "ece", "sharpness",
                    "calibration_badge", "beats_uniform", "formulas"):
            assert key in d, f"Missing key: {key!r}"

    def test_beats_uniform_true_below_0_25(self):
        d = self._make_dict(rps=0.217)
        assert d["beats_uniform"] is True

    def test_beats_uniform_false_above_0_25(self):
        d = self._make_dict(rps=0.26)
        assert d["beats_uniform"] is False

    def test_badge_included(self):
        d = self._make_dict(ece=0.058)
        assert d["calibration_badge"] == "fair"

    def test_formulas_dict_has_all_metrics(self):
        d = self._make_dict()
        for metric in ("rps", "log_loss", "brier", "ece", "sharpness"):
            assert metric in d["formulas"]

    def test_values_rounded(self):
        d = self._make_dict(rps=0.21712345)
        assert d["rps"] == pytest.approx(0.2171, abs=1e-4)
