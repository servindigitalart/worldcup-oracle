"""
Tests for oracle.pipeline.prediction_ledger and oracle.pipeline.grading — Week 18.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from oracle.grading.ledger import load_ledger
from oracle.pipeline.grading import run as grading_run
from oracle.pipeline.prediction_ledger import run as ledger_run


# ── Minimal fixture data ───────────────────────────────────────────────────────

def _make_blend_df():
    return pl.DataFrame({
        "match_id":   ["wc2026_m001", "wc2026_m002"],
        "home_team":  ["mexico", "south_korea"],
        "away_team":  ["south_africa", "czech_republic"],
        "group":      ["A", "A"],
        "blend_home": [0.45, 0.40],
        "blend_draw": [0.30, 0.30],
        "blend_away": [0.25, 0.30],
        "market_weight": [0.4, 0.4],
        "model_weight":  [0.6, 0.6],
        "has_market_data": [False, False],
        "label": ["model_only", "model_only"],
    })


def _make_comparison_df():
    return pl.DataFrame({
        "match_id":   ["wc2026_m001", "wc2026_m002"],
        "home_team":  ["mexico", "south_korea"],
        "away_team":  ["south_africa", "czech_republic"],
        "group":      ["A", "A"],
        "model_home": [0.45, 0.40],
        "model_draw": [0.30, 0.30],
        "model_away": [0.25, 0.30],
        "market_home": [None, None],
        "market_draw": [None, None],
        "market_away": [None, None],
        "gap_home":  [None, None],
        "gap_draw":  [None, None],
        "gap_away":  [None, None],
        "max_gap_selection": [None, None],
        "max_gap_value":     [None, None],
        "has_market_data": [False, False],
        "label": ["model_only", "model_only"],
    })


def _make_recommendations_df():
    return pl.DataFrame({
        "match_id":             ["wc2026_m001", "wc2026_m002"],
        "home_team":            ["mexico",      "south_korea"],
        "away_team":            ["south_africa","czech_republic"],
        "group":                ["A", "A"],
        "kickoff_at":           [None, None],
        "recommendation_type":  ["no_recommendation", "no_recommendation"],
        "market":               ["1x2", "1x2"],
        "selection":            [None, None],
        "model_probability":    [None, None],
        "market_probability":   [None, None],
        "blended_probability":  [None, None],
        "model_market_gap":     [None, None],
        "confidence":           ["unknown", "unknown"],
        "risk_label":           ["unknown", "unknown"],
        "data_quality":         ["missing_market", "missing_market"],
        "status":               ["pre_match", "pre_match"],
        "reason":               ["no market data", "no market data"],
        "warnings":             ['[]', '[]'],
        "is_actionable":        [False, False],
        "edge_confidence":      ["none", "none"],
        "generated_at":         ["2026-06-11T12:00:00+00:00", "2026-06-11T12:00:00+00:00"],
    })


def _make_live_results_df(finished: bool = False):
    status = "finished" if finished else "scheduled"
    return pl.DataFrame({
        "match_id":    ["wc2026_m001"],
        "home_team":   ["mexico"],
        "away_team":   ["south_africa"],
        "group":       ["A"],
        "home_goals":  [2] if finished else [None],
        "away_goals":  [0] if finished else [None],
        "status":      [status],
        "source":      ["manual"],
        "source_event_id": [None],
        "kickoff_at":  [None],
        "finished_at": [None],
        "captured_at": ["2026-06-11T22:00:00+00:00"],
    })


def _write_artifacts(
    tmp_path: Path,
    finished: bool = False,
) -> dict:
    artifacts_dir = tmp_path / "data" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    blend = _make_blend_df()
    compare = _make_comparison_df()
    recs = _make_recommendations_df()
    results = _make_live_results_df(finished=finished)

    blend.write_parquet(artifacts_dir / "blended_predictions.parquet")
    compare.write_parquet(artifacts_dir / "model_market_comparison.parquet")
    recs.write_parquet(artifacts_dir / "recommendations.parquet")
    results.write_parquet(artifacts_dir / "live_results.parquet")

    return {
        "artifacts_dir":  artifacts_dir,
        "blend_path":     artifacts_dir / "blended_predictions.parquet",
        "comparison_path": artifacts_dir / "model_market_comparison.parquet",
        "recommendations_path": artifacts_dir / "recommendations.parquet",
        "live_results_path": artifacts_dir / "live_results.parquet",
        "ledger_path":    artifacts_dir / "prediction_ledger.parquet",
    }


# ── Prediction ledger capture ─────────────────────────────────────────────────

class TestPredictionLedgerCapture:
    def test_artifacts_written(self, tmp_path):
        paths = _write_artifacts(tmp_path)
        ledger_run(**paths)
        assert paths["ledger_path"].exists()
        assert (paths["artifacts_dir"] / "prediction_ledger_summary.json").exists()

    def test_captures_future_matches(self, tmp_path):
        paths = _write_artifacts(tmp_path)
        summary = ledger_run(**paths)
        assert summary["n_appended"] == 2  # both matches are unfinished

    def test_skips_finished_matches(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=True)
        summary = ledger_run(**paths)
        # wc2026_m001 is finished → skipped; wc2026_m002 is not in live_results → captured
        assert summary["n_appended"] == 1  # only m002 captured

    def test_idempotent_same_day(self, tmp_path):
        paths = _write_artifacts(tmp_path)
        ledger_run(**paths)
        summary2 = ledger_run(**paths)
        # Second run same day: all duplicates
        assert summary2["n_appended"] == 0
        assert summary2["n_skipped"] == 2

    def test_result_known_false_in_ledger(self, tmp_path):
        paths = _write_artifacts(tmp_path)
        ledger_run(**paths)
        ledger = load_ledger(paths["ledger_path"])
        assert all(not row for row in ledger["result_known"].to_list())

    def test_summary_counts(self, tmp_path):
        paths = _write_artifacts(tmp_path)
        summary = ledger_run(**paths)
        assert summary["total_predictions"] == 2
        assert summary["graded_predictions"] == 0
        assert summary["pending_predictions"] == 2

    def test_no_blend_no_comparison_returns_empty(self, tmp_path):
        artifacts_dir = tmp_path / "data" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        summary = ledger_run(
            artifacts_dir=artifacts_dir,
            blend_path=artifacts_dir / "missing.parquet",
            comparison_path=artifacts_dir / "missing2.parquet",
            recommendations_path=artifacts_dir / "missing3.parquet",
            live_results_path=artifacts_dir / "missing4.parquet",
            ledger_path=artifacts_dir / "ledger.parquet",
        )
        assert summary["n_appended"] == 0


# ── Grading pipeline ──────────────────────────────────────────────────────────

class TestGradingPipeline:
    def _setup(self, tmp_path, finished=True):
        paths = _write_artifacts(tmp_path, finished=finished)
        # First capture predictions (while matches are unfinished)
        unfinished = _write_artifacts(tmp_path)
        ledger_run(**unfinished)
        # Now write finished results
        results = _make_live_results_df(finished=finished)
        results.write_parquet(paths["live_results_path"])
        return paths

    def test_artifacts_written(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=False)
        ledger_run(**paths)
        grading_run(
            artifacts_dir=paths["artifacts_dir"],
            ledger_path=paths["ledger_path"],
            live_results_path=paths["live_results_path"],
        )
        assert (paths["artifacts_dir"] / "prediction_grades.parquet").exists()
        assert (paths["artifacts_dir"] / "grading_summary.json").exists()
        assert (paths["artifacts_dir"] / "clv_summary.json").exists()
        assert (paths["artifacts_dir"] / "recommendation_performance.json").exists()
        assert (paths["artifacts_dir"] / "model_vs_market.json").exists()
        assert (paths["artifacts_dir"] / "performance_trends.json").exists()

    def test_grades_finished_result(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=False)
        ledger_run(**paths)

        # Switch to finished results
        results = _make_live_results_df(finished=True)
        results.write_parquet(paths["live_results_path"])

        grading_run(
            artifacts_dir=paths["artifacts_dir"],
            ledger_path=paths["ledger_path"],
            live_results_path=paths["live_results_path"],
        )

        ledger = load_ledger(paths["ledger_path"])
        graded = ledger.filter(pl.col("result_known") == True)
        assert len(graded) == 1  # wc2026_m001 has result

    def test_pending_match_not_graded(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=False)
        ledger_run(**paths)

        # wc2026_m001 finished; wc2026_m002 still scheduled
        results = _make_live_results_df(finished=True)
        results.write_parquet(paths["live_results_path"])

        grading_run(
            artifacts_dir=paths["artifacts_dir"],
            ledger_path=paths["ledger_path"],
            live_results_path=paths["live_results_path"],
        )

        ledger = load_ledger(paths["ledger_path"])
        pending = ledger.filter(pl.col("result_known") == False)
        assert len(pending) == 1  # wc2026_m002 still pending

    def test_empty_ledger_runs_cleanly(self, tmp_path):
        artifacts_dir = tmp_path / "data" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        results = _make_live_results_df(finished=True)
        results.write_parquet(artifacts_dir / "live_results.parquet")

        summary = grading_run(
            artifacts_dir=artifacts_dir,
            ledger_path=artifacts_dir / "prediction_ledger.parquet",
            live_results_path=artifacts_dir / "live_results.parquet",
        )
        assert summary["graded_predictions"] == 0

    def test_grading_summary_json_valid(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=False)
        ledger_run(**paths)
        grading_run(
            artifacts_dir=paths["artifacts_dir"],
            ledger_path=paths["ledger_path"],
            live_results_path=paths["live_results_path"],
        )
        text = (paths["artifacts_dir"] / "grading_summary.json").read_text()
        data = json.loads(text)
        assert "graded_predictions" in data
        assert "disclaimer" in data

    def test_idempotent_regrading(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=False)
        ledger_run(**paths)
        results = _make_live_results_df(finished=True)
        results.write_parquet(paths["live_results_path"])

        kwargs = dict(
            artifacts_dir=paths["artifacts_dir"],
            ledger_path=paths["ledger_path"],
            live_results_path=paths["live_results_path"],
        )
        summary1 = grading_run(**kwargs)
        summary2 = grading_run(**kwargs)

        assert summary1["graded_predictions"] == summary2["graded_predictions"]
        assert summary2["newly_graded"] == 0  # already graded

    def test_brier_computed_for_graded_entry(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=False)
        ledger_run(**paths)
        results = _make_live_results_df(finished=True)
        results.write_parquet(paths["live_results_path"])
        grading_run(
            artifacts_dir=paths["artifacts_dir"],
            ledger_path=paths["ledger_path"],
            live_results_path=paths["live_results_path"],
        )
        ledger = load_ledger(paths["ledger_path"])
        graded = ledger.filter(pl.col("result_known") == True)
        assert len(graded) > 0
        assert graded["brier"][0] is not None

    def test_performance_trends_has_windows(self, tmp_path):
        paths = _write_artifacts(tmp_path, finished=False)
        ledger_run(**paths)
        grading_run(
            artifacts_dir=paths["artifacts_dir"],
            ledger_path=paths["ledger_path"],
            live_results_path=paths["live_results_path"],
        )
        text = (paths["artifacts_dir"] / "performance_trends.json").read_text()
        data = json.loads(text)
        assert "windows" in data
        assert len(data["windows"]) == 4  # last 10, 25, 50, all-time
