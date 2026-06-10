"""
Tests for oracle.scoring.calibration_history — Week 15.

Coverage:
  - calibration_history_from_bins: bucket labelling, sort order, content
  - generate_calibration_history: extraction from full JSON structure
  - edge cases: empty bins, missing model key
"""
from __future__ import annotations

import pytest

from oracle.scoring.calibration_history import (
    _bucket_label,
    calibration_history_from_bins,
    generate_calibration_history,
)


# ── _bucket_label ─────────────────────────────────────────────────────────────

class TestBucketLabel:
    def test_low_probability(self):
        label = _bucket_label(0.22)
        assert label == "0.20-0.25"

    def test_exactly_on_boundary(self):
        # 0.25 // 0.05 = 4.0 due to FP → lo = 0.20
        label = _bucket_label(0.25)
        assert label == "0.20-0.25"

    def test_high_probability(self):
        # 0.65 // 0.05 = 12.0 due to FP (0.65/0.05 ≈ 12.999) → lo = 0.60
        label = _bucket_label(0.65)
        assert label == "0.60-0.65"

    def test_mid_range(self):
        label = _bucket_label(0.47)
        assert label == "0.45-0.50"

    def test_returns_string(self):
        assert isinstance(_bucket_label(0.3), str)

    def test_contains_hyphen(self):
        assert "-" in _bucket_label(0.3)


# ── calibration_history_from_bins ─────────────────────────────────────────────

class TestCalibrationHistoryFromBins:
    def _bins(self):
        return [
            {"bin_index": 0, "n_matches": 14, "mean_predicted": 0.207,
             "observed_rate": 0.214, "calibration_gap": -0.007},
            {"bin_index": 1, "n_matches": 14, "mean_predicted": 0.270,
             "observed_rate": 0.071, "calibration_gap": 0.199},
            {"bin_index": 2, "n_matches": 14, "mean_predicted": 0.308,
             "observed_rate": 0.214, "calibration_gap": 0.094},
        ]

    def test_returns_list(self):
        result = calibration_history_from_bins(self._bins())
        assert isinstance(result, list)

    def test_length_matches_input(self):
        result = calibration_history_from_bins(self._bins())
        assert len(result) == 3

    def test_required_fields_present(self):
        result = calibration_history_from_bins(self._bins())
        for item in result:
            for field in ("bucket", "predicted", "actual", "samples", "gap"):
                assert field in item, f"Missing field: {field!r}"

    def test_sorted_by_predicted_ascending(self):
        bins = [
            {"n_matches": 10, "mean_predicted": 0.55, "observed_rate": 0.5, "calibration_gap": 0.05},
            {"n_matches": 10, "mean_predicted": 0.20, "observed_rate": 0.25, "calibration_gap": -0.05},
            {"n_matches": 10, "mean_predicted": 0.38, "observed_rate": 0.40, "calibration_gap": -0.02},
        ]
        result = calibration_history_from_bins(bins)
        preds = [r["predicted"] for r in result]
        assert preds == sorted(preds)

    def test_samples_matches_n_matches(self):
        result = calibration_history_from_bins(self._bins())
        for item, original in zip(sorted(result, key=lambda x: x["predicted"]),
                                  sorted(self._bins(), key=lambda x: x["mean_predicted"])):
            assert item["samples"] == original["n_matches"]

    def test_gap_computed_when_missing(self):
        bins = [{"n_matches": 10, "mean_predicted": 0.6, "observed_rate": 0.5}]
        result = calibration_history_from_bins(bins)
        assert result[0]["gap"] == pytest.approx(0.1)

    def test_empty_bins_returns_empty(self):
        assert calibration_history_from_bins([]) == []

    def test_bucket_label_is_string(self):
        result = calibration_history_from_bins(self._bins())
        for item in result:
            assert isinstance(item["bucket"], str)
            assert "-" in item["bucket"]


# ── generate_calibration_history ──────────────────────────────────────────────

class TestGenerateCalibrationHistory:
    def _cal_json(self):
        return {
            "models": {
                "elo-baseline-v0.2": {
                    "outcome_label": "home_win",
                    "n_matches": 144,
                    "bins": [
                        {"bin_index": 0, "n_matches": 14, "mean_predicted": 0.2078,
                         "observed_rate": 0.2143, "calibration_gap": -0.0065},
                        {"bin_index": 1, "n_matches": 14, "mean_predicted": 0.2708,
                         "observed_rate": 0.0714, "calibration_gap": 0.1993},
                    ],
                },
                "dixon-coles-v0.3": {
                    "outcome_label": "home_win",
                    "n_matches": 144,
                    "bins": [
                        {"bin_index": 0, "n_matches": 14, "mean_predicted": 0.0906,
                         "observed_rate": 0.2143, "calibration_gap": -0.1237},
                    ],
                },
            }
        }

    def test_extracts_primary_model(self):
        result = generate_calibration_history(self._cal_json(), "elo-baseline-v0.2")
        assert len(result) == 2

    def test_extracts_secondary_model(self):
        result = generate_calibration_history(self._cal_json(), "dixon-coles-v0.3")
        assert len(result) == 1

    def test_missing_model_returns_empty(self):
        result = generate_calibration_history(self._cal_json(), "nonexistent-model")
        assert result == []

    def test_empty_json_returns_empty(self):
        result = generate_calibration_history({}, "elo-baseline-v0.2")
        assert result == []

    def test_result_has_correct_structure(self):
        result = generate_calibration_history(self._cal_json(), "elo-baseline-v0.2")
        assert all("bucket" in r for r in result)
        assert all("predicted" in r for r in result)
        assert all("actual" in r for r in result)
        assert all("samples" in r for r in result)

    def test_sorted_ascending(self):
        result = generate_calibration_history(self._cal_json(), "elo-baseline-v0.2")
        preds = [r["predicted"] for r in result]
        assert preds == sorted(preds)
