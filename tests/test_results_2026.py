"""
Tests for oracle.ingest.results_2026 — Week 13 match results ingestion.

Coverage:
  - Empty seed returns empty DataFrame with correct schema
  - Valid finished result loads correctly
  - Validation errors: missing match_id, duplicate match_id, unknown match_id,
    mismatched teams, negative goals, missing goals for finished, invalid status
  - ingest_results_2026 writes parquet + summary JSON
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from oracle.ingest.results_2026 import (
    ResultValidationError,
    load_results_2026,
    ingest_results_2026,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write_results(tmp_path: Path, results: list[dict]) -> Path:
    p = tmp_path / "results.json"
    p.write_text(json.dumps({"metadata": {}, "results": results}))
    return p


FIXTURE_PATH = Path(__file__).parent.parent / "data" / "seed" / "wc2026_fixtures.json"

# A known fixture from the official seed
_MATCH_ID   = "wc2026_m001"
_HOME_TEAM  = "mexico"
_AWAY_TEAM  = "south_africa"


# ── Schema / empty ────────────────────────────────────────────────────────────

class TestLoadResultsEmpty:
    def test_empty_seed_returns_dataframe(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [])
        df = load_results_2026(path, FIXTURE_PATH)
        assert isinstance(df, pl.DataFrame)

    def test_empty_seed_zero_rows(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [])
        df = load_results_2026(path, FIXTURE_PATH)
        assert len(df) == 0

    def test_empty_seed_has_correct_columns(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [])
        df = load_results_2026(path, FIXTURE_PATH)
        assert set(df.columns) == {
            "match_id", "home_team", "away_team", "group",
            "home_goals", "away_goals", "status",
        }


# ── Valid result ───────────────────────────────────────────────────────────────

class TestLoadResultsValid:
    def _valid_result(self) -> dict:
        return {
            "match_id":   _MATCH_ID,
            "home_team":  _HOME_TEAM,
            "away_team":  _AWAY_TEAM,
            "home_goals": 2,
            "away_goals": 1,
            "status":     "finished",
        }

    def test_loads_one_result(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [self._valid_result()])
        df = load_results_2026(path, FIXTURE_PATH)
        assert len(df) == 1

    def test_correct_match_id(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [self._valid_result()])
        df = load_results_2026(path, FIXTURE_PATH)
        assert df["match_id"][0] == _MATCH_ID

    def test_correct_goals(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [self._valid_result()])
        df = load_results_2026(path, FIXTURE_PATH)
        assert df["home_goals"][0] == 2
        assert df["away_goals"][0] == 1

    def test_group_populated_from_fixture(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [self._valid_result()])
        df = load_results_2026(path, FIXTURE_PATH)
        assert df["group"][0] == "A"

    def test_draw_goals_allowed(self, tmp_path: Path) -> None:
        r = self._valid_result()
        r["home_goals"] = 0
        r["away_goals"] = 0
        path = _write_results(tmp_path, [r])
        df = load_results_2026(path, FIXTURE_PATH)
        assert df["home_goals"][0] == 0

    def test_status_scheduled_no_goals_required(self, tmp_path: Path) -> None:
        r = {"match_id": _MATCH_ID, "home_team": _HOME_TEAM, "away_team": _AWAY_TEAM,
             "status": "scheduled"}
        path = _write_results(tmp_path, [r])
        df = load_results_2026(path, FIXTURE_PATH)
        assert df["status"][0] == "scheduled"


# ── Validation errors ─────────────────────────────────────────────────────────

class TestLoadResultsValidation:
    def test_missing_match_id_raises(self, tmp_path: Path) -> None:
        path = _write_results(tmp_path, [{"home_team": "mexico", "away_team": "south_africa",
                                          "home_goals": 1, "away_goals": 0, "status": "finished"}])
        with pytest.raises(ResultValidationError, match="match_id"):
            load_results_2026(path, FIXTURE_PATH)

    def test_duplicate_match_id_raises(self, tmp_path: Path) -> None:
        r = {"match_id": _MATCH_ID, "home_team": _HOME_TEAM, "away_team": _AWAY_TEAM,
             "home_goals": 1, "away_goals": 0, "status": "finished"}
        path = _write_results(tmp_path, [r, r.copy()])
        with pytest.raises(ResultValidationError, match="Duplicate"):
            load_results_2026(path, FIXTURE_PATH)

    def test_unknown_match_id_raises(self, tmp_path: Path) -> None:
        r = {"match_id": "wc2026_m999", "home_team": "mexico", "away_team": "south_africa",
             "home_goals": 1, "away_goals": 0, "status": "finished"}
        path = _write_results(tmp_path, [r])
        with pytest.raises(ResultValidationError, match="not found"):
            load_results_2026(path, FIXTURE_PATH)

    def test_mismatched_teams_raises(self, tmp_path: Path) -> None:
        r = {"match_id": _MATCH_ID, "home_team": "brazil", "away_team": "south_africa",
             "home_goals": 1, "away_goals": 0, "status": "finished"}
        path = _write_results(tmp_path, [r])
        with pytest.raises(ResultValidationError, match="teams"):
            load_results_2026(path, FIXTURE_PATH)

    def test_negative_home_goals_raises(self, tmp_path: Path) -> None:
        r = {"match_id": _MATCH_ID, "home_team": _HOME_TEAM, "away_team": _AWAY_TEAM,
             "home_goals": -1, "away_goals": 0, "status": "finished"}
        path = _write_results(tmp_path, [r])
        with pytest.raises(ResultValidationError, match="non-negative"):
            load_results_2026(path, FIXTURE_PATH)

    def test_missing_goals_for_finished_raises(self, tmp_path: Path) -> None:
        r = {"match_id": _MATCH_ID, "home_team": _HOME_TEAM, "away_team": _AWAY_TEAM,
             "status": "finished"}
        path = _write_results(tmp_path, [r])
        with pytest.raises(ResultValidationError, match="requires"):
            load_results_2026(path, FIXTURE_PATH)

    def test_invalid_status_raises(self, tmp_path: Path) -> None:
        r = {"match_id": _MATCH_ID, "home_team": _HOME_TEAM, "away_team": _AWAY_TEAM,
             "home_goals": 1, "away_goals": 0, "status": "abandoned"}
        path = _write_results(tmp_path, [r])
        with pytest.raises(ResultValidationError, match="status"):
            load_results_2026(path, FIXTURE_PATH)


# ── ingest_results_2026 ───────────────────────────────────────────────────────

class TestIngestResults2026:
    def test_writes_parquet(self, tmp_path: Path) -> None:
        results_path = _write_results(tmp_path, [])
        ingest_results_2026(results_path, FIXTURE_PATH, artifacts_dir=tmp_path / "artifacts")
        assert (tmp_path / "artifacts" / "match_results.parquet").exists()

    def test_writes_summary_json(self, tmp_path: Path) -> None:
        results_path = _write_results(tmp_path, [])
        ingest_results_2026(results_path, FIXTURE_PATH, artifacts_dir=tmp_path / "artifacts")
        assert (tmp_path / "artifacts" / "match_results_summary.json").exists()

    def test_summary_has_expected_keys(self, tmp_path: Path) -> None:
        results_path = _write_results(tmp_path, [])
        summary = ingest_results_2026(results_path, FIXTURE_PATH, artifacts_dir=tmp_path / "artifacts")
        for key in ("generated_at", "n_results", "n_finished", "by_group"):
            assert key in summary

    def test_empty_results_zero_finished(self, tmp_path: Path) -> None:
        results_path = _write_results(tmp_path, [])
        summary = ingest_results_2026(results_path, FIXTURE_PATH, artifacts_dir=tmp_path / "artifacts")
        assert summary["n_finished"] == 0

    def test_finished_result_counted(self, tmp_path: Path) -> None:
        r = {"match_id": _MATCH_ID, "home_team": _HOME_TEAM, "away_team": _AWAY_TEAM,
             "home_goals": 2, "away_goals": 0, "status": "finished"}
        results_path = _write_results(tmp_path, [r])
        summary = ingest_results_2026(results_path, FIXTURE_PATH, artifacts_dir=tmp_path / "artifacts")
        assert summary["n_finished"] == 1
        assert summary["by_group"].get("A", 0) == 1

    def test_parquet_schema_correct(self, tmp_path: Path) -> None:
        results_path = _write_results(tmp_path, [])
        ingest_results_2026(results_path, FIXTURE_PATH, artifacts_dir=tmp_path / "artifacts")
        df = pl.read_parquet(tmp_path / "artifacts" / "match_results.parquet")
        assert set(df.columns) == {
            "match_id", "home_team", "away_team", "group",
            "home_goals", "away_goals", "status",
        }
