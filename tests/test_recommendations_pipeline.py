"""
Tests for oracle.pipeline.recommendations — Week 14.

Coverage:
  - Artifacts written on a fresh run with no market data
  - Summary counts match artifact rows
  - No forbidden terms appear in output JSON
  - Missing artifacts handled gracefully
  - Conservative output: all no_recommendation without market data
  - With injected market data: model_gap_detected / watch / market_aligned appear
  - n_actionable is 0 without real market data
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from oracle.pipeline.recommendations import run
from oracle.recommendations.schema import FORBIDDEN_TERMS


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fake_comp_df(has_market: bool = False) -> pl.DataFrame:
    """Minimal model_market_comparison-like DataFrame."""
    rows = [
        {
            "match_id":          "england_vs_japan",
            "home_team":         "england",
            "away_team":         "japan",
            "group":             "F",
            "model_home":        0.58,
            "model_draw":        0.22,
            "model_away":        0.20,
            "market_home":       0.48 if has_market else None,
            "market_draw":       0.25 if has_market else None,
            "market_away":       0.27 if has_market else None,
            "gap_home":          0.10 if has_market else None,
            "gap_draw":         -0.03 if has_market else None,
            "gap_away":         -0.07 if has_market else None,
            "max_gap_selection": "home"   if has_market else None,
            "max_gap_value":     0.10     if has_market else None,
            "has_market_data":   has_market,
            "label":             "model_market_gap" if has_market else "model_only",
        },
        {
            "match_id":          "brazil_vs_morocco",
            "home_team":         "brazil",
            "away_team":         "morocco",
            "group":             "C",
            "model_home":        0.55,
            "model_draw":        0.25,
            "model_away":        0.20,
            "market_home":       0.52 if has_market else None,
            "market_draw":       0.27 if has_market else None,
            "market_away":       0.21 if has_market else None,
            "gap_home":          0.03 if has_market else None,
            "gap_draw":         -0.02 if has_market else None,
            "gap_away":         -0.01 if has_market else None,
            "max_gap_selection": "home"  if has_market else None,
            "max_gap_value":     0.03    if has_market else None,
            "has_market_data":   has_market,
            "label":             "model_market_gap" if has_market else "model_only",
        },
    ]
    schema = {
        "match_id": pl.Utf8, "home_team": pl.Utf8, "away_team": pl.Utf8,
        "group": pl.Utf8,
        "model_home": pl.Float64, "model_draw": pl.Float64, "model_away": pl.Float64,
        "market_home": pl.Float64, "market_draw": pl.Float64, "market_away": pl.Float64,
        "gap_home": pl.Float64, "gap_draw": pl.Float64, "gap_away": pl.Float64,
        "max_gap_selection": pl.Utf8, "max_gap_value": pl.Float64,
        "has_market_data": pl.Boolean, "label": pl.Utf8,
    }
    return pl.DataFrame(rows, schema=schema)


def _fake_blend_df() -> pl.DataFrame:
    rows = [
        {
            "match_id": "england_vs_japan",
            "home_team": "england", "away_team": "japan", "group": "F",
            "blend_home": 0.58, "blend_draw": 0.22, "blend_away": 0.20,
            "market_weight": 0.0, "model_weight": 1.0,
            "has_market_data": False, "label": "model_only",
        },
        {
            "match_id": "brazil_vs_morocco",
            "home_team": "brazil", "away_team": "morocco", "group": "C",
            "blend_home": 0.55, "blend_draw": 0.25, "blend_away": 0.20,
            "market_weight": 0.0, "model_weight": 1.0,
            "has_market_data": False, "label": "model_only",
        },
    ]
    return pl.DataFrame(rows)


def _setup_artifacts(tmp_path: Path, has_market: bool = False) -> Path:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    _fake_comp_df(has_market).write_parquet(artifacts / "model_market_comparison.parquet")
    _fake_blend_df().write_parquet(artifacts / "blended_predictions.parquet")
    (artifacts / "market_capture_status.json").write_text(json.dumps({
        "has_real_api_key": has_market,
        "n_new_rows": 0,
        "n_total_snapshots": 0,
        "n_matches": 0,
        "by_status": {},
        "n_closing_locked": 0,
    }))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "wc2026_fixtures.json").write_text(json.dumps({
        "metadata": {"is_official": True, "is_placeholder": False},
        "fixtures": [
            {"match_id": "wc2026_m001", "home_team": "england", "away_team": "japan",
             "group": "F", "kickoff_at": "2026-06-22T15:00:00Z",
             "stage": "group", "venue": "SoFi Stadium", "city": "Los Angeles",
             "host_country": "USA", "source": "official_fifa_2026", "is_placeholder": False},
        ],
    }))
    return artifacts


# ── Artifact existence ────────────────────────────────────────────────────────

class TestArtifactsWritten:
    def test_parquet_written(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        assert (artifacts / "recommendations.parquet").exists()

    def test_json_written(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        assert (artifacts / "recommendations.json").exists()

    def test_summary_written(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        assert (artifacts / "recommendations_summary.json").exists()

    def test_json_is_valid_list(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        assert isinstance(data, list)

    def test_summary_has_required_keys(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        summary = json.loads((artifacts / "recommendations_summary.json").read_text())
        for key in ("generated_at", "total_matches", "n_no_recommendation",
                    "n_watch", "n_market_aligned", "n_model_gap_detected",
                    "n_actionable", "n_missing_market", "disclaimer"):
            assert key in summary, f"Key {key!r} missing from summary"


# ── Conservative output without market data ───────────────────────────────────

class TestNoMarketData:
    def test_all_no_recommendation(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path, has_market=False)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        for rec in data:
            assert rec["recommendation_type"] == "no_recommendation", (
                f"Expected no_recommendation, got {rec['recommendation_type']!r} "
                f"for {rec['match_id']!r}"
            )

    def test_n_actionable_is_zero(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path, has_market=False)
        summary = run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        assert summary["n_actionable"] == 0

    def test_all_missing_market_quality(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path, has_market=False)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        for rec in data:
            assert rec["data_quality"] == "missing_market"


# ── With injected market data ─────────────────────────────────────────────────

class TestWithMarketData:
    def test_model_gap_detected_appears(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path, has_market=True)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        types = {r["recommendation_type"] for r in data}
        # england vs japan has gap=0.10 → model_gap_detected
        assert "model_gap_detected" in types

    def test_market_aligned_appears(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path, has_market=True)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        types = {r["recommendation_type"] for r in data}
        # brazil vs morocco has gap=0.03 → market_aligned
        assert "market_aligned" in types


# ── Count consistency ─────────────────────────────────────────────────────────

class TestCountConsistency:
    def test_total_matches_equals_json_length(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        summary = run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        assert summary["total_matches"] == len(data)

    def test_type_counts_sum_to_total(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        summary = run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        total = (
            summary["n_no_recommendation"] + summary["n_watch"]
            + summary["n_market_aligned"] + summary["n_model_gap_detected"]
            + summary["n_avoid"]
        )
        assert total == summary["total_matches"]


# ── No forbidden language in output ──────────────────────────────────────────

class TestNoForbiddenLanguage:
    def _scan_text(self, text: str) -> list[str]:
        lower = text.lower()
        return [term for term in FORBIDDEN_TERMS if term in lower]

    def test_no_forbidden_terms_in_reasons(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path, has_market=True)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        for rec in data:
            violations = self._scan_text(rec.get("reason", ""))
            assert violations == [], (
                f"Forbidden language in reason for {rec['match_id']!r}: {violations}"
            )

    def test_no_forbidden_terms_in_warnings(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path, has_market=True)
        run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        data = json.loads((artifacts / "recommendations.json").read_text())
        for rec in data:
            warnings = rec.get("warnings", [])
            if isinstance(warnings, str):
                warnings = json.loads(warnings)
            for w in warnings:
                violations = self._scan_text(w)
                assert violations == [], (
                    f"Forbidden language in warning for {rec['match_id']!r}: {violations}"
                )

    def test_no_forbidden_terms_in_disclaimer(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        summary = run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        violations = self._scan_text(summary.get("disclaimer", ""))
        assert violations == []


# ── Missing input artifacts handled gracefully ────────────────────────────────

class TestMissingInputsGraceful:
    def test_runs_without_comparison_parquet(self, tmp_path: Path) -> None:
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        seed = tmp_path / "seed"
        seed.mkdir()
        (seed / "wc2026_fixtures.json").write_text(json.dumps(
            {"metadata": {}, "fixtures": []}
        ))
        # No comparison parquet — should not crash
        summary = run(artifacts_dir=artifacts, seed_dir=seed)
        assert summary["total_matches"] == 0

    def test_runs_without_match_results(self, tmp_path: Path) -> None:
        artifacts = _setup_artifacts(tmp_path)
        # Explicitly ensure match_results.parquet does NOT exist
        results_path = artifacts / "match_results.parquet"
        results_path.unlink(missing_ok=True)
        summary = run(artifacts_dir=artifacts, seed_dir=tmp_path / "seed")
        # Should still produce recommendations (no result_status = pre-match)
        assert summary["total_matches"] == 2
