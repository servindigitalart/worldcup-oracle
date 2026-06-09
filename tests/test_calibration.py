"""Tests: calibration diagnostics."""
from __future__ import annotations

import math

import pytest

from oracle.scoring.calibration import (
    CalibrationBin,
    CalibrationResult,
    calibration_bins,
    calibration_to_dict,
)


class TestCalibrationBins:
    def test_returns_calibration_result(self) -> None:
        probs    = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.2, 0.35, 0.65, 0.75]
        observed = [0,   0,   1,   1,   1,   1,   0,  0,    1,   1]
        result = calibration_bins(probs, observed, n_bins=5)
        assert isinstance(result, CalibrationResult)

    def test_correct_n_matches(self) -> None:
        n = 20
        probs    = [0.5] * n
        observed = [1] * n
        result = calibration_bins(probs, observed, n_bins=4)
        assert result.n_matches == n

    def test_bins_cover_all_matches(self) -> None:
        probs    = list(range(1, 21))  # 1..20
        probs    = [p / 20 for p in probs]
        observed = [1 if p > 0.5 else 0 for p in probs]
        result = calibration_bins(probs, observed, n_bins=4)
        total = sum(b.n_matches for b in result.bins)
        assert total == len(probs)

    def test_perfect_calibration_gap_is_zero(self) -> None:
        # Predicted=0.5 throughout, observe exactly 50% outcomes
        probs    = [0.5] * 100
        observed = [1] * 50 + [0] * 50
        result = calibration_bins(probs, observed, n_bins=1)
        assert len(result.bins) == 1
        b = result.bins[0]
        assert b.mean_predicted == pytest.approx(0.5)
        assert b.observed_rate  == pytest.approx(0.5)
        assert b.calibration_gap == pytest.approx(0.0)

    def test_overconfident_model_has_positive_gap(self) -> None:
        # Model always says 0.9 but outcomes are only 50%
        probs    = [0.9] * 20
        observed = [1] * 10 + [0] * 10
        result = calibration_bins(probs, observed, n_bins=1)
        b = result.bins[0]
        assert b.calibration_gap > 0

    def test_underconfident_model_has_negative_gap(self) -> None:
        # Model always says 0.1 but outcomes are 50%
        probs    = [0.1] * 20
        observed = [1] * 10 + [0] * 10
        result = calibration_bins(probs, observed, n_bins=1)
        b = result.bins[0]
        assert b.calibration_gap < 0

    def test_mean_calibration_gap_is_non_negative(self) -> None:
        probs    = [0.3, 0.5, 0.7, 0.9, 0.1, 0.6, 0.4, 0.8, 0.2, 0.55]
        observed = [0,   1,   1,   0,   0,   1,   0,   1,   0,   1]
        result = calibration_bins(probs, observed, n_bins=5)
        assert result.mean_calibration_gap >= 0

    def test_uniform_baseline_prob_is_one_third(self) -> None:
        result = calibration_bins([0.5] * 10, [1] * 5 + [0] * 5, n_bins=2)
        assert result.uniform_baseline_prob == pytest.approx(1 / 3)

    def test_small_sample_warning_flag(self) -> None:
        # n_matches < 100 → small_sample_warning=True in dict output
        result = calibration_bins([0.5] * 10, [1] * 5 + [0] * 5, n_bins=2)
        d = calibration_to_dict(result)
        assert d["small_sample_warning"] is True

    def test_large_sample_no_warning(self) -> None:
        result = calibration_bins([0.5] * 200, [1] * 100 + [0] * 100, n_bins=5)
        d = calibration_to_dict(result)
        assert d["small_sample_warning"] is False

    def test_single_bin(self) -> None:
        probs    = [0.3, 0.4, 0.6, 0.7]
        observed = [0,   0,   1,   1]
        result = calibration_bins(probs, observed, n_bins=1)
        assert len(result.bins) == 1
        assert result.bins[0].n_matches == 4

    def test_raises_on_length_mismatch(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            calibration_bins([0.5, 0.6], [1], n_bins=1)

    def test_raises_on_empty(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            calibration_bins([], [], n_bins=1)

    def test_raises_on_n_bins_too_large(self) -> None:
        with pytest.raises(ValueError, match="n_bins"):
            calibration_bins([0.5, 0.6], [1, 0], n_bins=5)

    def test_last_bin_absorbs_remainder(self) -> None:
        # 11 matches, 3 bins: bin sizes 3, 3, 5
        probs    = [0.1 * i for i in range(1, 12)]
        observed = [1 if p > 0.5 else 0 for p in probs]
        result = calibration_bins(probs, observed, n_bins=3)
        total = sum(b.n_matches for b in result.bins)
        assert total == 11


class TestCalibrationToDict:
    def test_returns_dict(self) -> None:
        result = calibration_bins([0.4, 0.5, 0.6, 0.7, 0.8], [0, 1, 1, 0, 1], n_bins=2)
        d = calibration_to_dict(result)
        assert isinstance(d, dict)

    def test_keys_present(self) -> None:
        result = calibration_bins([0.4, 0.5, 0.6, 0.7, 0.8], [0, 1, 1, 0, 1], n_bins=2)
        d = calibration_to_dict(result)
        assert {"outcome_label", "n_matches", "n_bins", "bins",
                "mean_abs_calibration_gap", "small_sample_warning"} <= set(d.keys())

    def test_bins_list_present(self) -> None:
        result = calibration_bins([0.4, 0.5, 0.6, 0.7, 0.8], [0, 1, 1, 0, 1], n_bins=2)
        d = calibration_to_dict(result)
        assert isinstance(d["bins"], list)
        assert len(d["bins"]) == 2

    def test_bin_keys(self) -> None:
        result = calibration_bins([0.4, 0.5, 0.6, 0.7, 0.8], [0, 1, 1, 0, 1], n_bins=2)
        d = calibration_to_dict(result)
        for b in d["bins"]:
            assert {"bin_index", "n_matches", "mean_predicted",
                    "observed_rate", "calibration_gap"} <= set(b.keys())


class TestCalibrationBinDataclass:
    def test_calibration_gap_computed(self) -> None:
        b = CalibrationBin(bin_index=0, n_matches=10,
                           mean_predicted=0.6, observed_rate=0.4)
        assert b.calibration_gap == pytest.approx(0.2)

    def test_negative_gap(self) -> None:
        b = CalibrationBin(bin_index=0, n_matches=10,
                           mean_predicted=0.3, observed_rate=0.5)
        assert b.calibration_gap == pytest.approx(-0.2)
