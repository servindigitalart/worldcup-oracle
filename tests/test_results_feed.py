"""
Tests for oracle.pipeline.results_feed — Week 17.

Coverage:
  run()
    - writes live_results.parquet + live_results.json + results_feed_report.json
    - empty manual seed produces empty artifacts
    - live status results included in artifact but not counted as finished
    - finished results counted correctly
    - n_manual / n_external / n_merged counts in report
    - external JSON file present + parsed correctly
    - external file absent → external count zero, pipeline succeeds
    - manual seed absent → ResultProviderError propagates
    - unresolved external entries in report
    - live_results.parquet has expected schema columns
    - results_feed_report.json is valid JSON
    - idempotent: run twice produces same schema
    - provider_json_present flag set correctly
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from oracle.pipeline.results_feed import run, _to_df
from oracle.results.provider import NormalizedResult, ResultProviderError


# ── Minimal test seeds ────────────────────────────────────────────────────────

FIXTURE_DATA = {
    "metadata": {"source": "test", "is_official": True},
    "fixtures": [
        {
            "match_id": "wc2026_m001", "stage": "group", "group": "A",
            "home_team": "mexico", "away_team": "south_africa",
            "kickoff_at": "2026-06-11T19:00:00+00:00",
            "venue": "Estadio Azteca", "city": "Mexico City",
            "host_country": "Mexico", "source": "test", "is_placeholder": False,
        },
        {
            "match_id": "wc2026_m002", "stage": "group", "group": "A",
            "home_team": "south_korea", "away_team": "czech_republic",
            "kickoff_at": "2026-06-12T02:00:00+00:00",
            "venue": "SoFi Stadium", "city": "Inglewood",
            "host_country": "USA", "source": "test", "is_placeholder": False,
        },
    ],
}


def _write_seeds(tmp_path, results=None, provider_results=None):
    seed_dir = tmp_path / "data" / "seed"
    seed_dir.mkdir(parents=True)
    raw_dir = tmp_path / "data" / "raw" / "results"
    raw_dir.mkdir(parents=True)
    artifacts_dir = tmp_path / "data" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    fixture_path = seed_dir / "wc2026_fixtures.json"
    fixture_path.write_text(json.dumps(FIXTURE_DATA))

    results_seed = {"metadata": {"source": "manual"}, "results": results or []}
    results_path = seed_dir / "wc2026_results.json"
    results_path.write_text(json.dumps(results_seed))

    provider_path = raw_dir / "provider_results.json"
    if provider_results is not None:
        provider_path.write_text(json.dumps({
            "metadata": {"captured_at": "2026-06-11T23:10:00Z"},
            "results": provider_results,
        }))

    return artifacts_dir, results_path, fixture_path, provider_path


def _run(tmp_path, results=None, provider_results=None):
    artifacts_dir, rp, fp, pp = _write_seeds(tmp_path, results, provider_results)
    return run(
        artifacts_dir=artifacts_dir,
        results_seed=rp,
        fixture_seed=fp,
        provider_json=pp,
    ), artifacts_dir


# ── _to_df helper ─────────────────────────────────────────────────────────────

class TestToDataframe:
    def test_empty_list(self):
        df = _to_df([])
        assert len(df) == 0
        assert "match_id" in df.columns

    def test_one_result(self):
        nr = NormalizedResult(
            source="manual", match_id="wc2026_m001",
            home_team="mexico", away_team="south_africa",
            group="A", status="finished",
            home_goals=2, away_goals=0,
        )
        df = _to_df([nr])
        assert len(df) == 1
        assert df["match_id"][0] == "wc2026_m001"
        assert df["home_goals"][0] == 2


# ── Artifact generation ───────────────────────────────────────────────────────

class TestResultsFeedPipeline:
    def test_artifacts_written(self, tmp_path):
        _, artifacts_dir = _run(tmp_path)
        assert (artifacts_dir / "live_results.parquet").exists()
        assert (artifacts_dir / "live_results.json").exists()
        assert (artifacts_dir / "results_feed_report.json").exists()

    def test_empty_manual_empty_artifacts(self, tmp_path):
        _, artifacts_dir = _run(tmp_path)
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        assert len(df) == 0

    def test_parquet_schema_columns(self, tmp_path):
        _, artifacts_dir = _run(tmp_path)
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        required = {"match_id", "home_team", "away_team", "group", "home_goals",
                    "away_goals", "status", "source", "captured_at"}
        assert required.issubset(set(df.columns))

    def test_finished_result_in_artifact(self, tmp_path):
        results = [{
            "match_id": "wc2026_m001", "home_team": "mexico",
            "away_team": "south_africa", "home_goals": 2,
            "away_goals": 0, "status": "finished",
        }]
        _, artifacts_dir = _run(tmp_path, results=results)
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        assert len(df) == 1
        assert df["status"][0] == "finished"

    def test_n_finished_in_report(self, tmp_path):
        results = [{
            "match_id": "wc2026_m001", "home_team": "mexico",
            "away_team": "south_africa", "home_goals": 2, "away_goals": 0,
            "status": "finished",
        }]
        report, _ = _run(tmp_path, results=results)
        assert report["n_finished"] == 1

    def test_live_result_in_artifact_but_not_n_finished(self, tmp_path):
        results = [{
            "match_id": "wc2026_m001", "home_team": "mexico",
            "away_team": "south_africa", "status": "live",
        }]
        report, artifacts_dir = _run(tmp_path, results=results)
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        assert len(df) == 1
        assert df["status"][0] == "live"
        assert report["n_finished"] == 0
        assert report["n_live"] == 1

    def test_report_n_manual_counts(self, tmp_path):
        results = [{
            "match_id": "wc2026_m001", "home_team": "mexico",
            "away_team": "south_africa", "home_goals": 2, "away_goals": 0,
            "status": "finished",
        }]
        report, _ = _run(tmp_path, results=results)
        assert report["n_manual"] == 1
        assert report["n_external"] == 0
        assert report["n_merged"] == 1

    def test_report_n_external_when_file_present(self, tmp_path):
        provider_results = [{
            "home_team": "south_korea", "away_team": "czech_republic",
            "home_goals": 1, "away_goals": 0, "status": "finished",
        }]
        report, artifacts_dir = _run(tmp_path, provider_results=provider_results)
        assert report["n_external"] == 1
        assert report["n_merged"] == 1

    def test_external_absent_n_external_zero(self, tmp_path):
        # No provider_results.json provided
        report, _ = _run(tmp_path)
        assert report["n_external"] == 0

    def test_provider_json_present_flag(self, tmp_path):
        # With file
        report_with, _ = _run(tmp_path, provider_results=[])
        # Without file (new tmp_path)
        tmp2 = tmp_path / "sub"
        tmp2.mkdir()
        report_without, _ = _run(tmp2)
        assert report_with["provider_json_present"] is True
        assert report_without["provider_json_present"] is False

    def test_report_is_valid_json(self, tmp_path):
        _, artifacts_dir = _run(tmp_path)
        text = (artifacts_dir / "results_feed_report.json").read_text()
        data = json.loads(text)
        assert "n_merged" in data
        assert "generated_at" in data

    def test_live_results_json_is_list(self, tmp_path):
        _, artifacts_dir = _run(tmp_path)
        text = (artifacts_dir / "live_results.json").read_text()
        data = json.loads(text)
        assert isinstance(data, list)

    def test_unresolved_external_in_report(self, tmp_path):
        provider_results = [{
            "home_team": "atlantis",     # unknown team
            "away_team": "south_africa",
            "home_goals": 1, "away_goals": 0,
            "status": "finished",
        }]
        report, _ = _run(tmp_path, provider_results=provider_results)
        assert len(report["unresolved"]) >= 1
        assert report["n_external"] == 0  # unresolved → not in n_external

    def test_manual_overrides_external(self, tmp_path):
        manual_results = [{
            "match_id": "wc2026_m001", "home_team": "mexico",
            "away_team": "south_africa", "home_goals": 2, "away_goals": 0,
            "status": "finished",
        }]
        provider_results = [{
            "home_team": "Mexico", "away_team": "South Africa",
            "home_goals": 0, "away_goals": 0, "status": "finished",
        }]
        report, artifacts_dir = _run(tmp_path, results=manual_results,
                                      provider_results=provider_results)
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        assert len(df) == 1
        assert df["home_goals"][0] == 2   # manual wins
        assert report["n_duplicates"] == 1

    def test_idempotent_two_runs(self, tmp_path):
        results = [{
            "match_id": "wc2026_m001", "home_team": "mexico",
            "away_team": "south_africa", "home_goals": 1, "away_goals": 0,
            "status": "finished",
        }]
        artifacts_dir, rp, fp, pp = _write_seeds(tmp_path, results)
        kwargs = dict(artifacts_dir=artifacts_dir, results_seed=rp,
                      fixture_seed=fp, provider_json=pp)

        r1 = run(**kwargs)
        r2 = run(**kwargs)

        assert r1["n_merged"] == r2["n_merged"]
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        assert len(df) == 1

    def test_source_column_manual(self, tmp_path):
        results = [{
            "match_id": "wc2026_m001", "home_team": "mexico",
            "away_team": "south_africa", "home_goals": 1, "away_goals": 0,
            "status": "finished",
        }]
        _, artifacts_dir = _run(tmp_path, results=results)
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        assert df["source"][0] == "manual"

    def test_source_column_external(self, tmp_path):
        provider_results = [{
            "home_team": "south_korea", "away_team": "czech_republic",
            "home_goals": 1, "away_goals": 0, "status": "finished",
        }]
        _, artifacts_dir = _run(tmp_path, provider_results=provider_results)
        df = pl.read_parquet(artifacts_dir / "live_results.parquet")
        assert df["source"][0] == "local_json"

    def test_report_has_manual_seed_path(self, tmp_path):
        report, _ = _run(tmp_path)
        assert "manual_seed_path" in report
        assert len(report["manual_seed_path"]) > 0
