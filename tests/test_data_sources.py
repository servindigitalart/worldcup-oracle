"""
Tests for oracle.pipeline.data_sources — Week 15.

Coverage:
  - run() against real CSV (if present): correct counts, required fields
  - run() with missing CSV: graceful fallback with 0 counts
  - run() with synthetic CSV: deterministic count verification
  - output JSON structure
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from oracle.pipeline.data_sources import (
    _is_friendly,
    _is_qualifier,
    _is_world_cup,
    run,
)


# ── Helper classifiers ────────────────────────────────────────────────────────

class TestClassifiers:
    def test_world_cup_exact_match(self):
        assert _is_world_cup("FIFA World Cup") is True

    def test_world_cup_partial_no_match(self):
        assert _is_world_cup("FIFA World Cup qualification") is False

    def test_friendly_case_insensitive(self):
        assert _is_friendly("Friendly") is True
        assert _is_friendly("International Friendly") is True

    def test_not_friendly(self):
        assert _is_friendly("FIFA World Cup") is False

    def test_qualifier_patterns(self):
        assert _is_qualifier("FIFA World Cup qualification") is True
        assert _is_qualifier("UEFA Euro qualifying") is True
        assert _is_qualifier("AFC qualifier") is True

    def test_non_qualifier(self):
        assert _is_qualifier("FIFA World Cup") is False
        assert _is_qualifier("Friendly") is False


# ── run() with missing CSV ─────────────────────────────────────────────────────

class TestMissingCsv:
    def test_graceful_with_missing_csv(self, tmp_path):
        result = run(artifacts_dir=tmp_path, raw_csv=tmp_path / "nonexistent.csv")
        assert result["historical_matches"] == 0

    def test_writes_json_even_without_csv(self, tmp_path):
        run(artifacts_dir=tmp_path, raw_csv=tmp_path / "nonexistent.csv")
        assert (tmp_path / "data_sources.json").exists()

    def test_missing_csv_has_note(self, tmp_path):
        result = run(artifacts_dir=tmp_path, raw_csv=tmp_path / "nonexistent.csv")
        assert "note" in result


# ── run() with synthetic CSV ──────────────────────────────────────────────────

class TestSyntheticCsv:
    def _write_csv(self, tmp_path, rows):
        path = tmp_path / "results.csv"
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "home_team", "away_team",
                                               "home_score", "away_score", "tournament",
                                               "city", "country", "neutral"])
            w.writeheader()
            for row in rows:
                w.writerow(row)
        return path

    def _row(self, tournament, date="2022-01-01"):
        return {"date": date, "home_team": "A", "away_team": "B",
                "home_score": "1", "away_score": "0",
                "tournament": tournament, "city": "X", "country": "Y",
                "neutral": "FALSE"}

    def test_total_count_correct(self, tmp_path):
        rows = [self._row("FIFA World Cup")] * 3 + [self._row("Friendly")] * 2
        csv_path = self._write_csv(tmp_path, rows)
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert result["historical_matches"] == 5

    def test_world_cup_count_correct(self, tmp_path):
        rows = [self._row("FIFA World Cup")] * 4 + [self._row("Friendly")]
        csv_path = self._write_csv(tmp_path, rows)
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert result["world_cup_matches"] == 4

    def test_friendly_count_correct(self, tmp_path):
        rows = [self._row("Friendly")] * 6 + [self._row("FIFA World Cup")]
        csv_path = self._write_csv(tmp_path, rows)
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert result["friendly_matches"] == 6

    def test_qualifier_count_correct(self, tmp_path):
        rows = [self._row("FIFA World Cup qualification")] * 3
        csv_path = self._write_csv(tmp_path, rows)
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert result["qualifier_matches"] == 3

    def test_json_written(self, tmp_path):
        csv_path = self._write_csv(tmp_path, [self._row("FIFA World Cup")])
        run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert (tmp_path / "data_sources.json").exists()

    def test_required_keys_present(self, tmp_path):
        rows = [self._row("FIFA World Cup")]
        csv_path = self._write_csv(tmp_path, rows)
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        for key in ("historical_matches", "world_cups", "qualifiers",
                    "friendlies", "source", "generated_at"):
            assert key in result

    def test_source_is_martj42(self, tmp_path):
        csv_path = self._write_csv(tmp_path, [self._row("Friendly")])
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert "martj42" in result["source"]

    def test_wc_years_list(self, tmp_path):
        rows = (
            [self._row("FIFA World Cup", "2014-06-01")] +
            [self._row("FIFA World Cup", "2018-06-01")] +
            [self._row("Friendly", "2019-01-01")]
        )
        csv_path = self._write_csv(tmp_path, rows)
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert 2014 in result["world_cup_years"]
        assert 2018 in result["world_cup_years"]
        assert len(result["world_cup_years"]) == 2

    def test_returns_dict(self, tmp_path):
        csv_path = self._write_csv(tmp_path, [self._row("Friendly")])
        result = run(artifacts_dir=tmp_path, raw_csv=csv_path)
        assert isinstance(result, dict)


# ── run() against real CSV (when present) ─────────────────────────────────────

class TestRealCsv:
    REAL_CSV = Path("data/raw/results/results.csv")

    def test_real_csv_total_matches(self):
        if not self.REAL_CSV.exists():
            pytest.skip("Real CSV not present.")
        result = run()
        assert result["historical_matches"] == 49437

    def test_real_csv_has_world_cup_matches(self):
        if not self.REAL_CSV.exists():
            pytest.skip("Real CSV not present.")
        result = run()
        assert result["world_cup_matches"] > 0
        assert result["world_cups"] >= 20

    def test_real_csv_has_friendlies(self):
        if not self.REAL_CSV.exists():
            pytest.skip("Real CSV not present.")
        result = run()
        assert result["friendlies"] is True
        assert result["friendly_matches"] > 10000

    def test_real_csv_has_qualifiers(self):
        if not self.REAL_CSV.exists():
            pytest.skip("Real CSV not present.")
        result = run()
        assert result["qualifiers"] is True
        assert result["qualifier_matches"] > 1000
