"""Tests: baseline forecast module and holdout pipeline (synthetic data)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import polars as pl
import pytest

from oracle.forecast.baseline import MODEL_VERSION, forecast_fixtures, make_prediction
from oracle.harness.backtest import MatchResult
from oracle.pipeline.holdout import _outcome_str, run as run_holdout
from oracle.ratings.elo import EloRatings
from tests.test_elo import SMALL_HISTORY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fitted_elo() -> EloRatings:
    elo = EloRatings()
    elo.fit(SMALL_HISTORY)
    return elo


# ---------------------------------------------------------------------------
# Forecast unit tests
# ---------------------------------------------------------------------------

class TestMakePrediction:
    def test_returns_prediction(self) -> None:
        pred = make_prediction(_fitted_elo(), "fx_001", "argentina", "france")
        assert pred.fixture_id == "fx_001"

    def test_probs_sum_to_one(self) -> None:
        pred = make_prediction(_fitted_elo(), "fx_001", "argentina", "france")
        assert abs(pred.p_home + pred.p_draw + pred.p_away - 1.0) < 1e-9

    def test_model_version_set(self) -> None:
        pred = make_prediction(_fitted_elo(), "fx_001", "argentina", "france")
        assert pred.model_version == MODEL_VERSION
        assert "elo" in MODEL_VERSION.lower()

    def test_neutral_true_by_default(self) -> None:
        elo = _fitted_elo()
        pred_neutral  = make_prediction(elo, "fx", "argentina", "france", neutral=True)
        pred_home     = make_prediction(elo, "fx", "argentina", "france", neutral=False)
        # Neutral should give lower home-win probability than home advantage
        assert pred_home.p_home > pred_neutral.p_home

    def test_custom_predicted_at(self) -> None:
        ts = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        pred = make_prediction(_fitted_elo(), "fx_001", "argentina", "france", predicted_at=ts)
        assert pred.predicted_at == ts


class TestForecastFixtures:
    FIXTURES = [
        {"fixture_id": "m1", "home_team_id": "argentina", "away_team_id": "france"},
        {"fixture_id": "m2", "home_team_id": "brazil",    "away_team_id": "germany"},
        {"fixture_id": "m3", "home_team_id": "spain",     "away_team_id": "england"},
    ]

    def test_returns_correct_count(self) -> None:
        preds = forecast_fixtures(_fitted_elo(), self.FIXTURES)
        assert len(preds) == 3

    def test_all_probs_sum_to_one(self) -> None:
        preds = forecast_fixtures(_fitted_elo(), self.FIXTURES)
        for pred in preds:
            assert abs(pred.p_home + pred.p_draw + pred.p_away - 1.0) < 1e-9

    def test_fixture_ids_match(self) -> None:
        preds = forecast_fixtures(_fitted_elo(), self.FIXTURES)
        pred_ids = {p.fixture_id for p in preds}
        assert pred_ids == {"m1", "m2", "m3"}

    def test_per_fixture_neutral_override(self) -> None:
        fixtures = [
            {"fixture_id": "n", "home_team_id": "argentina", "away_team_id": "france", "neutral": True},
            {"fixture_id": "h", "home_team_id": "argentina", "away_team_id": "france", "neutral": False},
        ]
        preds = {p.fixture_id: p for p in forecast_fixtures(_fitted_elo(), fixtures)}
        assert preds["h"].p_home > preds["n"].p_home

    def test_empty_fixtures_returns_empty(self) -> None:
        preds = forecast_fixtures(_fitted_elo(), [])
        assert preds == []


# ---------------------------------------------------------------------------
# Holdout pipeline (synthetic data, no network)
# ---------------------------------------------------------------------------

def _make_synthetic_results() -> pl.DataFrame:
    """72 matches: 24 pre-holdout + 8 fake 'FIFA World Cup' group stage."""
    rows = []
    teams = ["argentina", "brazil", "france", "germany",
             "spain", "england", "portugal", "italy"]

    # Pre-holdout training: 2018–2022
    idx = 0
    for year in range(2018, 2022):
        for i, ht in enumerate(teams):
            at = teams[(i + 1) % len(teams)]
            rows.append({
                "date": date(year, 6, idx % 28 + 1),
                "home_team": ht, "away_team": at,
                "home_score": (idx % 3), "away_score": (idx % 2),
                "tournament": "Friendly" if idx % 3 == 0 else "UEFA Nations League",
                "neutral": False,
                "home_team_id": ht, "away_team_id": at,
            })
            idx += 1

    # Holdout: 8 FIFA World Cup group stage matches in Nov 2022
    wc_pairs = [
        ("argentina", "brazil",   1, 0),
        ("france",    "germany",  2, 1),
        ("spain",     "england",  1, 1),
        ("portugal",  "italy",    3, 2),
        ("brazil",    "france",   0, 1),
        ("germany",   "argentina",0, 2),
        ("england",   "spain",    1, 0),
        ("italy",     "portugal", 1, 1),
    ]
    for i, (ht, at, hs, as_) in enumerate(wc_pairs):
        rows.append({
            "date": date(2022, 11, 20 + i),
            "home_team": ht, "away_team": at,
            "home_score": hs, "away_score": as_,
            "tournament": "FIFA World Cup",
            "neutral": True,
            "home_team_id": ht, "away_team_id": at,
        })

    return pl.DataFrame(rows)


class TestHoldoutPipeline:
    def test_runs_without_error(self, tmp_path: Path) -> None:
        df = _make_synthetic_results()
        result = run_holdout(
            results_df=df,
            artifacts_dir=tmp_path / "artifacts",
        )
        assert result["n_holdout_scored"] > 0

    def test_mean_rps_in_valid_range(self, tmp_path: Path) -> None:
        df = _make_synthetic_results()
        result = run_holdout(results_df=df, artifacts_dir=tmp_path / "artifacts")
        assert 0.0 <= result["mean_rps"] <= 1.0

    def test_artifacts_written(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        assert (artifact_dir / "ratings_elo.parquet").exists()
        assert (artifact_dir / "holdout_2022_wc.parquet").exists()
        assert (artifact_dir / "holdout_summary.json").exists()

    def test_ratings_parquet_has_62_rows(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        df = pl.read_parquet(artifact_dir / "ratings_elo.parquet")
        assert len(df) == 62

    def test_holdout_parquet_has_scored_columns(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        df = pl.read_parquet(artifact_dir / "holdout_2022_wc.parquet")
        # Week 3: per-model RPS columns
        assert "rps_elo_full" in df.columns
        assert "log_loss_home" in df.columns

    def test_week3_artifacts_written(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        assert (artifact_dir / "ratings_elo_recent.parquet").exists()
        assert (artifact_dir / "ratings_dc_params.parquet").exists()
        assert (artifact_dir / "model_comparison_2022.json").exists()
        assert (artifact_dir / "calibration_2022.json").exists()

    def test_model_comparison_has_expected_keys(self, tmp_path: Path) -> None:
        import json
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        comp = json.loads((artifact_dir / "model_comparison_2022.json").read_text())
        assert "models" in comp
        assert len(comp["models"]) >= 2
        for m in comp["models"]:
            assert "model" in m
            assert "mean_rps" in m

    def test_calibration_json_has_models(self, tmp_path: Path) -> None:
        import json
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        cal = json.loads((artifact_dir / "calibration_2022.json").read_text())
        assert "models" in cal
        assert len(cal["models"]) >= 1

    def test_empty_holdout_returns_gracefully(self, tmp_path: Path) -> None:
        # Only pre-holdout data, no WC matches
        df = _make_synthetic_results().filter(
            ~pl.col("tournament").str.contains("World Cup")
        )
        result = run_holdout(results_df=df, artifacts_dir=tmp_path / "artifacts")
        assert result["n_holdout"] == 0

    def test_summary_json_has_required_keys(self, tmp_path: Path) -> None:
        import json
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        summary = json.loads((artifact_dir / "holdout_summary.json").read_text())
        for key in ("mean_rps", "uniform_rps", "beats_uniform", "n_holdout_scored",
                    "model_version", "generated_at"):
            assert key in summary

    def test_uniform_rps_is_0_25(self, tmp_path: Path) -> None:
        import json
        artifact_dir = tmp_path / "artifacts"
        run_holdout(results_df=_make_synthetic_results(), artifacts_dir=artifact_dir)
        summary = json.loads((artifact_dir / "holdout_summary.json").read_text())
        assert summary["uniform_rps"] == pytest.approx(0.25)


class TestOutcomeStr:
    def test_home_win(self) -> None:
        assert _outcome_str(2, 0) == "home"

    def test_draw(self) -> None:
        assert _outcome_str(1, 1) == "draw"

    def test_away_win(self) -> None:
        assert _outcome_str(0, 3) == "away"
