"""Tests: artifacts (DuckDB, Parquet) are written and read back correctly."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest

from oracle.db import get_conn, init_db
from oracle.harness.backtest import (
    MatchResult,
    MarketSnapshot,
    Prediction,
    run_backtest,
    write_scores_to_db,
    score_prediction,
)
from oracle.teams import teams_dataframe


class TestDuckDBInit:
    def test_init_creates_all_tables(self, tmp_db: str) -> None:
        init_db(tmp_db)
        with get_conn(tmp_db) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }
        assert {"results", "fixtures", "market_snapshots",
                "predictions", "scores", "teams"} <= tables

    def test_init_is_idempotent(self, tmp_db: str) -> None:
        init_db(tmp_db)
        init_db(tmp_db)  # second call must not raise

    def test_in_memory_db(self) -> None:
        with get_conn(":memory:") as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchone()[0]
        assert count >= 6


class TestTeamsTable:
    def test_load_48_teams(self, tmp_db: str) -> None:
        df = teams_dataframe()
        with get_conn(tmp_db) as conn:
            conn.execute("INSERT INTO teams SELECT * FROM df")
            count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        assert count == 48

    def test_team_ids_are_unique_in_db(self, tmp_db: str) -> None:
        df = teams_dataframe()
        with get_conn(tmp_db) as conn:
            conn.execute("INSERT INTO teams SELECT * FROM df")
            dup_count = conn.execute(
                "SELECT COUNT(*) FROM (SELECT team_id, COUNT(*) AS c "
                "FROM teams GROUP BY team_id HAVING c > 1)"
            ).fetchone()[0]
        assert dup_count == 0

    def test_parquet_roundtrip(self, tmp_path: Path) -> None:
        df = teams_dataframe()
        path = tmp_path / "teams.parquet"
        df.write_parquet(path)
        loaded = pl.read_parquet(path)
        assert loaded.shape == df.shape
        assert set(loaded.columns) == set(df.columns)


class TestMarketSnapshotsTable:
    def test_odds_snapshot_written(self, tmp_db: str) -> None:
        snapshot_data = {
            "snapshot_id": "snap_001",
            "fixture_id":  "wc2026_m001",
            "captured_at": "2026-06-10T18:00:00",
            "bookmaker":   "pinnacle",
            "market":      "1x2",
            "outcome":     "home",
            "decimal_odds": 2.25,
        }
        df = pl.DataFrame([snapshot_data])
        with get_conn(tmp_db) as conn:
            conn.execute("INSERT INTO market_snapshots SELECT * FROM df")
            row = conn.execute(
                "SELECT decimal_odds FROM market_snapshots WHERE outcome = 'home'"
            ).fetchone()
        assert row[0] == pytest.approx(2.25)


class TestScoresTable:
    def test_scoring_results_persisted(
        self,
        tmp_db: str,
        sample_prediction: Prediction,
        sample_market_snapshot: MarketSnapshot,
        sample_result_home_win: MatchResult,
    ) -> None:
        scored = score_prediction(
            sample_prediction, sample_result_home_win, sample_market_snapshot
        )
        write_scores_to_db([scored], db_path=tmp_db)

        with get_conn(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
            metrics = {
                row[0]
                for row in conn.execute("SELECT metric FROM scores").fetchall()
            }

        assert count >= 3  # rps, log_loss_home, brier_home at minimum
        assert "rps" in metrics
        assert "log_loss_home" in metrics

    def test_all_metric_values_finite(
        self,
        tmp_db: str,
        sample_prediction: Prediction,
        sample_market_snapshot: MarketSnapshot,
        sample_result_home_win: MatchResult,
    ) -> None:
        import math
        scored = score_prediction(
            sample_prediction, sample_result_home_win, sample_market_snapshot
        )
        write_scores_to_db([scored], db_path=tmp_db)

        with get_conn(tmp_db) as conn:
            values = [
                row[0]
                for row in conn.execute("SELECT value FROM scores").fetchall()
            ]
        for v in values:
            assert math.isfinite(v), f"Non-finite score value: {v}"


class TestParquetArtifact:
    def test_backtest_details_to_parquet(
        self,
        tmp_path: Path,
        sample_prediction: Prediction,
        sample_market_snapshot: MarketSnapshot,
        sample_result_home_win: MatchResult,
    ) -> None:
        summary = run_backtest(
            predictions=[sample_prediction],
            results=[sample_result_home_win],
            markets=[sample_market_snapshot],
        )
        artifact_path = tmp_path / "backtest_details.parquet"
        summary["details"].write_parquet(artifact_path)

        assert artifact_path.exists()
        loaded = pl.read_parquet(artifact_path)
        assert len(loaded) == 1
        assert "rps" in loaded.columns
        assert "market_rps" in loaded.columns
        assert "clv_home" in loaded.columns
