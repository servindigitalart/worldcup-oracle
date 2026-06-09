"""Tests: multi-year World Cup backtest pipeline."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from oracle.pipeline.multi_holdout import (
    WC_WINDOWS,
    WCWindow,
    _aggregate_rps,
    _pool_predictions,
    run as run_multi,
    score_year,
)


# ---------------------------------------------------------------------------
# Synthetic dataset helpers
# ---------------------------------------------------------------------------

_CANONICAL_TEAMS = [
    "argentina", "brazil", "france", "germany",
    "spain", "england", "portugal", "italy",
    "netherlands", "belgium", "croatia", "senegal",
    "japan", "morocco", "australia", "ecuador",
]

# Non-canonical teams to simulate historical WC participants
_HISTORICAL_TEAMS = ["Ghana", "Russia", "Iceland", "Peru", "Wales", "Tunisia"]


def _make_multi_year_df(seed: int = 42) -> pl.DataFrame:
    """Synthetic match history covering 2012–2022 with WC holdout windows."""
    import random
    rng = random.Random(seed)
    all_teams = _CANONICAL_TEAMS + _HISTORICAL_TEAMS
    rows: list[dict] = []

    # ── Training matches (2012–2013, pre-2014 WC) ────────────────────────
    base = date(2012, 1, 1)
    for i in range(120):
        h, a = rng.sample(all_teams, 2)
        rows.append({
            "date": base + timedelta(days=i * 5),
            "home_team":  h, "away_team":  a,
            "home_score": rng.randint(0, 3), "away_score": rng.randint(0, 3),
            "tournament": rng.choice(["Friendly", "Qualifier"]),
            "neutral": False,
            "home_team_id": h if h in _CANONICAL_TEAMS else None,
            "away_team_id": a if a in _CANONICAL_TEAMS else None,
        })

    # ── 2014 WC group stage (Jun 12–26) ─────────────────────────────────
    wc2014 = [
        ("brazil",    "Croatia",     3, 1),
        ("germany",   "Ghana",       2, 2),
        ("france",    "ecuador",     0, 0),
        ("spain",     "netherlands", 1, 5),
        ("argentina", "Iran",        1, 0),
        ("england",   "Italy",       1, 2),
        ("brazil",    "mexico",      0, 0),
    ]
    for i, (h, a, hs, as_) in enumerate(wc2014):
        rows.append({
            "date": date(2014, 6, 12 + i),
            "home_team":  h, "away_team":  a,
            "home_score": hs, "away_score": as_,
            "tournament": "FIFA World Cup",
            "neutral": True,
            "home_team_id": h if h in _CANONICAL_TEAMS else None,
            "away_team_id": a if a in _CANONICAL_TEAMS else None,
        })

    # ── Training matches (2015–2017, post-2014 / pre-2018) ──────────────
    base2 = date(2015, 1, 1)
    for i in range(120):
        h, a = rng.sample(all_teams, 2)
        rows.append({
            "date": base2 + timedelta(days=i * 5),
            "home_team":  h, "away_team":  a,
            "home_score": rng.randint(0, 3), "away_score": rng.randint(0, 3),
            "tournament": rng.choice(["Friendly", "Qualifier"]),
            "neutral": rng.choice([True, False]),
            "home_team_id": h if h in _CANONICAL_TEAMS else None,
            "away_team_id": a if a in _CANONICAL_TEAMS else None,
        })

    # ── 2018 WC group stage (Jun 14–28) ─────────────────────────────────
    wc2018 = [
        ("france",    "Australia",  2, 1),
        ("argentina", "Iceland",    1, 1),
        ("germany",   "mexico",     0, 1),
        ("brazil",    "Switzerland",1, 1),
        ("belgium",   "Peru",       3, 0),
        ("england",   "Tunisia",    2, 1),
        ("spain",     "Iran",       1, 0),
    ]
    for i, (h, a, hs, as_) in enumerate(wc2018):
        rows.append({
            "date": date(2018, 6, 14 + i),
            "home_team":  h, "away_team":  a,
            "home_score": hs, "away_score": as_,
            "tournament": "FIFA World Cup",
            "neutral": True,
            "home_team_id": h if h in _CANONICAL_TEAMS else None,
            "away_team_id": a if a in _CANONICAL_TEAMS else None,
        })

    # ── Training matches (2019–2021, post-2018 / pre-2022) ──────────────
    base3 = date(2019, 1, 1)
    for i in range(120):
        h, a = rng.sample(all_teams, 2)
        rows.append({
            "date": base3 + timedelta(days=i * 5),
            "home_team":  h, "away_team":  a,
            "home_score": rng.randint(0, 3), "away_score": rng.randint(0, 3),
            "tournament": rng.choice(["Friendly", "Qualifier"]),
            "neutral": rng.choice([True, False]),
            "home_team_id": h if h in _CANONICAL_TEAMS else None,
            "away_team_id": a if a in _CANONICAL_TEAMS else None,
        })

    # ── 2022 WC group stage (Nov 20 – Dec 2) ────────────────────────────
    wc2022 = [
        ("argentina", "saudi_arabia", 1, 2),
        ("france",    "australia",    4, 1),
        ("germany",   "japan",        1, 2),
        ("brazil",    "serbia",       2, 0),
        ("england",   "iran",         6, 2),
        ("netherlands", "senegal",    2, 0),
        ("spain",     "costa_rica",   7, 0),
    ]
    for i, (h, a, hs, as_) in enumerate(wc2022):
        rows.append({
            "date": date(2022, 11, 20 + i),
            "home_team":  h, "away_team":  a,
            "home_score": hs, "away_score": as_,
            "tournament": "FIFA World Cup",
            "neutral": True,
            "home_team_id": h if h in _CANONICAL_TEAMS else None,
            "away_team_id": a if a in _CANONICAL_TEAMS else None,
        })

    return pl.DataFrame(rows)


MULTI_DF = _make_multi_year_df()
WINDOWS_TEST = WC_WINDOWS  # use real WC dates (our synthetic data matches them)


# ---------------------------------------------------------------------------
# WCWindow tests
# ---------------------------------------------------------------------------

class TestWCWindow:
    def test_windows_count(self) -> None:
        assert len(WC_WINDOWS) == 3

    def test_years_are_2014_2018_2022(self) -> None:
        assert [w.year for w in WC_WINDOWS] == [2014, 2018, 2022]

    def test_train_cutoff_is_day_before_start(self) -> None:
        for w in WC_WINDOWS:
            assert w.train_cutoff == w.start - timedelta(days=1)

    def test_start_before_end(self) -> None:
        for w in WC_WINDOWS:
            assert w.start < w.end


# ---------------------------------------------------------------------------
# Leakage prevention tests
# ---------------------------------------------------------------------------

class TestLeakagePrevention:
    def _train_for_window(self, window: WCWindow) -> pl.DataFrame:
        return MULTI_DF.filter(pl.col("date") <= pl.lit(window.train_cutoff))

    def test_no_holdout_matches_in_train_2014(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2014)
        train = self._train_for_window(w)
        leakage = train.filter(pl.col("date") >= pl.lit(w.start))
        assert len(leakage) == 0, f"Leakage: {len(leakage)} matches from holdout period in train"

    def test_no_holdout_matches_in_train_2018(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2018)
        train = self._train_for_window(w)
        leakage = train.filter(pl.col("date") >= pl.lit(w.start))
        assert len(leakage) == 0

    def test_no_holdout_matches_in_train_2022(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        train = self._train_for_window(w)
        leakage = train.filter(pl.col("date") >= pl.lit(w.start))
        assert len(leakage) == 0

    def test_train_grows_across_years(self) -> None:
        # Each successive year has more training data
        trains = [
            len(self._train_for_window(w))
            for w in sorted(WC_WINDOWS, key=lambda w: w.year)
        ]
        assert trains[0] < trains[1] < trains[2]

    def test_holdout_contains_only_target_year(self) -> None:
        for w in WC_WINDOWS:
            holdout = MULTI_DF.filter(
                (pl.col("date") >= pl.lit(w.start))
                & (pl.col("date") <= pl.lit(w.end))
                & pl.col("tournament").str.contains("FIFA World Cup")
            )
            if len(holdout) > 0:
                years_in_holdout = holdout["date"].dt.year().unique().to_list()
                assert all(y == w.year for y in years_in_holdout), (
                    f"Year {w.year} holdout contains matches from years: {years_in_holdout}"
                )


# ---------------------------------------------------------------------------
# Group-stage selection tests
# ---------------------------------------------------------------------------

class TestGroupStageSelection:
    def test_holdout_filters_to_wc_tournament(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        holdout = MULTI_DF.filter(
            (pl.col("date") >= pl.lit(w.start))
            & (pl.col("date") <= pl.lit(w.end))
            & pl.col("tournament").str.contains("FIFA World Cup")
        )
        assert all("World Cup" in t for t in holdout["tournament"].to_list())

    def test_non_wc_matches_excluded(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        holdout = MULTI_DF.filter(
            (pl.col("date") >= pl.lit(w.start))
            & (pl.col("date") <= pl.lit(w.end))
            & pl.col("tournament").str.contains("FIFA World Cup")
        )
        assert not any("Friendly" in t for t in holdout["tournament"].to_list())


# ---------------------------------------------------------------------------
# score_year unit tests
# ---------------------------------------------------------------------------

class TestScoreYear:
    def test_returns_expected_keys(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        result = score_year(w, MULTI_DF)
        for key in ("year", "n_matches", "rps", "context_rows"):
            assert key in result

    def test_rps_keys_are_model_names(self) -> None:
        from oracle.forecast.baseline import MODEL_VERSION as ELO_VERSION
        from oracle.ratings.dixon_coles import MODEL_VERSION as DC_VERSION
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        result = score_year(w, MULTI_DF)
        assert ELO_VERSION in result["rps"]
        assert f"{ELO_VERSION}-recent" in result["rps"]
        assert DC_VERSION in result["rps"]

    def test_rps_values_in_valid_range(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        result = score_year(w, MULTI_DF)
        for rps_val in result["rps"].values():
            if rps_val is not None:
                assert 0.0 <= rps_val <= 1.0

    def test_context_rows_have_year(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        result = score_year(w, MULTI_DF)
        for row in result["context_rows"]:
            assert row["year"] == 2022

    def test_context_rows_have_rps_columns(self) -> None:
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        result = score_year(w, MULTI_DF)
        if result["context_rows"]:
            row = result["context_rows"][0]
            assert "rps_elo_full"   in row
            assert "rps_elo_recent" in row
            assert "rps_dc"         in row

    def test_leakage_guard_raises(self) -> None:
        # Construct a dataset with deliberate leakage (holdout match in train)
        w = next(w for w in WC_WINDOWS if w.year == 2022)
        # Insert a WC match dated inside the holdout window but with train label
        bad_row = {
            "date": date(2022, 11, 21),  # inside holdout window
            "home_team": "france", "away_team": "germany",
            "home_score": 1, "away_score": 0,
            "tournament": "Friendly",  # not WC, so won't be in holdout filter
            "neutral": True,
            "home_team_id": "france", "away_team_id": "germany",
        }
        # The train filter is date <= train_cutoff, so this date won't be in
        # train anyway — test the guard by patching the train_cutoff logic instead
        # via a custom window where cutoff > start (broken by design)
        broken_window = WCWindow(
            year=2022,
            start=date(2022, 11, 20),
            end=date(2022, 12, 2),
            train_cutoff=date(2022, 11, 25),  # cutoff AFTER start = leakage
        )
        with pytest.raises(RuntimeError, match="LEAKAGE"):
            score_year(broken_window, MULTI_DF)


# ---------------------------------------------------------------------------
# Aggregate and pooling tests
# ---------------------------------------------------------------------------

class TestAggregation:
    def _mock_year_results(self) -> list[dict]:
        """Minimal fake year results for aggregate math tests."""
        return [
            {"year": 2014, "n_matches": 10, "rps": {"model_a": 0.20}},
            {"year": 2018, "n_matches": 20, "rps": {"model_a": 0.30}},
            {"year": 2022, "n_matches": 30, "rps": {"model_a": 0.40}},
        ]

    def test_aggregate_rps_is_weighted_average(self) -> None:
        year_results = self._mock_year_results()
        agg = _aggregate_rps(year_results, "model_a")
        # weighted: (0.20*10 + 0.30*20 + 0.40*30) / 60 = 22/60 ≈ 0.3333
        expected = (0.20 * 10 + 0.30 * 20 + 0.40 * 30) / 60
        assert agg == pytest.approx(expected)

    def test_aggregate_rps_handles_missing(self) -> None:
        year_results = [
            {"year": 2014, "n_matches": 10, "rps": {}},  # no model_b
            {"year": 2018, "n_matches": 20, "rps": {"model_b": 0.25}},
        ]
        agg = _aggregate_rps(year_results, "model_b")
        assert agg == pytest.approx(0.25)  # only year with data

    def test_aggregate_rps_all_missing_returns_none(self) -> None:
        year_results = [
            {"year": 2014, "n_matches": 10, "rps": {}},
        ]
        assert _aggregate_rps(year_results, "model_z") is None


# ---------------------------------------------------------------------------
# Full pipeline (synthetic data) tests
# ---------------------------------------------------------------------------

class TestMultiHoldoutPipeline:
    def test_runs_without_error(self, tmp_path: Path) -> None:
        result = run_multi(results_df=MULTI_DF, artifacts_dir=tmp_path / "artifacts")
        assert "aggregate" in result

    def test_artifacts_written(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        assert (artifact_dir / "backtest_worldcups.parquet").exists()
        assert (artifact_dir / "backtest_worldcups_summary.json").exists()
        assert (artifact_dir / "model_comparison_worldcups.json").exists()
        assert (artifact_dir / "calibration_worldcups.json").exists()

    def test_parquet_has_year_column(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        df = pl.read_parquet(artifact_dir / "backtest_worldcups.parquet")
        assert "year" in df.columns

    def test_parquet_has_rps_columns(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        df = pl.read_parquet(artifact_dir / "backtest_worldcups.parquet")
        assert "rps_elo_full"   in df.columns
        assert "rps_elo_recent" in df.columns
        assert "rps_dc"         in df.columns

    def test_parquet_covers_all_years(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        df = pl.read_parquet(artifact_dir / "backtest_worldcups.parquet")
        years_present = set(df["year"].unique().to_list())
        assert {2014, 2018, 2022} == years_present

    def test_summary_has_per_year_and_aggregate(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        summary = json.loads((artifact_dir / "backtest_worldcups_summary.json").read_text())
        assert "per_year" in summary
        assert "aggregate" in summary
        for year in ["2014", "2018", "2022"]:
            assert year in summary["per_year"]

    def test_summary_aggregate_has_rps(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        summary = json.loads((artifact_dir / "backtest_worldcups_summary.json").read_text())
        agg = summary["aggregate"]
        assert "rps" in agg
        assert "n_matches" in agg

    def test_model_comparison_is_sorted_by_rps(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        comp = json.loads((artifact_dir / "model_comparison_worldcups.json").read_text())
        models_with_rps = [m for m in comp["models"] if m["model"] != "uniform"
                           and m["aggregate_rps"] is not None]
        rpss = [m["aggregate_rps"] for m in models_with_rps]
        assert rpss == sorted(rpss)

    def test_calibration_has_all_models(self, tmp_path: Path) -> None:
        from oracle.forecast.baseline import MODEL_VERSION as ELO_VERSION
        from oracle.ratings.dixon_coles import MODEL_VERSION as DC_VERSION
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        cal = json.loads((artifact_dir / "calibration_worldcups.json").read_text())
        assert ELO_VERSION             in cal["models"]
        assert f"{ELO_VERSION}-recent" in cal["models"]
        assert DC_VERSION              in cal["models"]

    def test_total_matches_is_sum_of_years(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        summary = json.loads((artifact_dir / "backtest_worldcups_summary.json").read_text())
        per_year_total = sum(
            summary["per_year"][str(y)]["n_matches"]
            for y in [2014, 2018, 2022]
        )
        assert summary["total_matches"] == per_year_total

    def test_uniform_rps_constant(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        run_multi(results_df=MULTI_DF, artifacts_dir=artifact_dir)
        summary = json.loads((artifact_dir / "backtest_worldcups_summary.json").read_text())
        assert summary["uniform_rps"] == pytest.approx(0.25)
