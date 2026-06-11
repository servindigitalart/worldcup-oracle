"""
Tests for oracle.pipeline.closing_lines and oracle.market.movement_analysis — Week 20.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pytest

from oracle.market.movement_analysis import analyze_match_movement, build_market_movement
from oracle.market.lifecycle import CheckpointSnapshot, LifecycleEntry, build_lifecycle_entry
from oracle.market.schema import build_1x2_snapshots
from oracle.pipeline.closing_lines import run as cl_run, _entry_to_row


# ── Helpers ───────────────────────────────────────────────────────────────────

_KICKOFF = datetime(2026, 6, 20, 15, 0, 0, tzinfo=timezone.utc)


def _snaps(match_id: str, hours_before: float, bookmaker: str = "testbook") -> list:
    captured = (_KICKOFF - timedelta(hours=hours_before)).isoformat()
    return build_1x2_snapshots(
        match_id=match_id,
        home_team="teamA",
        away_team="teamB",
        bookmaker=bookmaker,
        odds_1x2={"home": 2.0, "draw": 3.5, "away": 3.2},
        captured_at=captured,
        source="test",
    )


def _write_snapshots(tmp_path: Path, hours_list: list[float], match_id: str = "m001"):
    artifacts = tmp_path / "data" / "artifacts"
    artifacts.mkdir(parents=True)
    all_snaps = []
    for h in hours_list:
        all_snaps.extend(_snaps(match_id, h))
    rows = [s.to_dict() for s in all_snaps]
    if rows:
        df = pl.DataFrame(rows)
        df.write_parquet(artifacts / "market_snapshots.parquet")
    return artifacts


# ── _entry_to_row ─────────────────────────────────────────────────────────────

class TestEntryToRow:
    def test_row_has_all_fields(self):
        snaps = []
        for h in [48.0, 24.0, 1.0]:
            snaps.extend(_snaps("m001", h))
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF, generated_at="ts",
        )
        row = _entry_to_row(entry)
        required = [
            "match_id", "home_team", "away_team", "kickoff_at",
            "n_pre_kickoff_snapshots", "closing_status",
            "opening_captured_at", "opening_home_prob",
            "closing_captured_at", "closing_home_prob",
        ]
        for f in required:
            assert f in row, f"missing field: {f}"

    def test_no_snapshots_null_fields(self):
        entry = build_lifecycle_entry(
            snapshots=[], match_id="m001",
            home_team="A", away_team="B",
            kickoff_at=_KICKOFF, generated_at="ts",
        )
        row = _entry_to_row(entry)
        assert row["opening_home_prob"] is None
        assert row["closing_home_prob"] is None


# ── closing_lines pipeline run() ─────────────────────────────────────────────

class TestClosingLinesPipeline:
    def test_no_snapshots_writes_empty_parquet(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        summary = cl_run(artifacts_dir=artifacts)
        assert (artifacts / "closing_lines.parquet").exists()
        assert (artifacts / "closing_line_summary.json").exists()
        assert summary["n_matches"] == 0

    def test_with_snapshots_writes_rows(self, tmp_path):
        artifacts = _write_snapshots(tmp_path, [48.0, 24.0, 1.0])
        summary = cl_run(artifacts_dir=artifacts)
        assert summary["n_matches"] >= 1
        df = pl.read_parquet(artifacts / "closing_lines.parquet")
        assert len(df) >= 1

    def test_summary_json_valid(self, tmp_path):
        artifacts = _write_snapshots(tmp_path, [24.0])
        cl_run(artifacts_dir=artifacts)
        text = (artifacts / "closing_line_summary.json").read_text()
        data = json.loads(text)
        assert "n_matches" in data
        assert "by_closing_status" in data
        assert "validation" in data

    def test_market_movement_json_written(self, tmp_path):
        artifacts = _write_snapshots(tmp_path, [48.0, 1.0])
        cl_run(artifacts_dir=artifacts)
        assert (artifacts / "market_movement.json").exists()
        data = json.loads((artifacts / "market_movement.json").read_text())
        assert "n_matches_with_movement" in data
        assert "disclaimer" in data

    def test_closing_lines_parquet_schema(self, tmp_path):
        artifacts = _write_snapshots(tmp_path, [24.0])
        cl_run(artifacts_dir=artifacts)
        df = pl.read_parquet(artifacts / "closing_lines.parquet")
        for col in ("match_id", "home_team", "away_team", "closing_status",
                    "opening_home_prob", "closing_home_prob"):
            assert col in df.columns


# ── analyze_match_movement ────────────────────────────────────────────────────

class TestAnalyzeMatchMovement:
    def _entry(self, open_prob=0.40, close_prob=0.50) -> LifecycleEntry:
        return LifecycleEntry(
            match_id="m001", home_team="A", away_team="B",
            kickoff_at=None, n_pre_kickoff_snapshots=6,
            opening=CheckpointSnapshot(
                captured_at="2026-06-18T00:00:00+00:00",
                home_prob=open_prob, draw_prob=0.30, away_prob=1.0 - open_prob - 0.30,
            ),
            h24=None, h12=None, h6=None, h1=None,
            closing=CheckpointSnapshot(
                captured_at="2026-06-19T14:00:00+00:00",
                home_prob=close_prob, draw_prob=0.28, away_prob=1.0 - close_prob - 0.28,
            ),
            closing_status="latest_available",
            generated_at="ts",
        )

    def test_computes_movement(self):
        result = analyze_match_movement(self._entry())
        assert result is not None
        assert "home_move" in result
        assert "max_abs_move" in result

    def test_positive_home_move(self):
        result = analyze_match_movement(self._entry(open_prob=0.40, close_prob=0.50))
        assert result["home_move"] > 0

    def test_no_opening_returns_none(self):
        entry = LifecycleEntry(
            match_id="m001", home_team="A", away_team="B",
            kickoff_at=None, n_pre_kickoff_snapshots=0,
            opening=None, h24=None, h12=None, h6=None, h1=None, closing=None,
            closing_status="no_market_data", generated_at="ts",
        )
        assert analyze_match_movement(entry) is None

    def test_same_timestamp_returns_none(self):
        ts = "2026-06-18T00:00:00+00:00"
        cp = CheckpointSnapshot(captured_at=ts, home_prob=0.4, draw_prob=0.3, away_prob=0.3)
        entry = LifecycleEntry(
            match_id="m001", home_team="A", away_team="B",
            kickoff_at=None, n_pre_kickoff_snapshots=3,
            opening=cp, h24=None, h12=None, h6=None, h1=None, closing=cp,
            closing_status="opening_only", generated_at="ts",
        )
        assert analyze_match_movement(entry) is None

    def test_biggest_mover_detected(self):
        result = analyze_match_movement(self._entry(open_prob=0.40, close_prob=0.60))
        assert result["biggest_mover"] in ("home", "draw", "away")
        assert result["biggest_mover_direction"] in ("up", "down")


# ── build_market_movement ─────────────────────────────────────────────────────

class TestBuildMarketMovement:
    def test_empty_returns_zero(self):
        result = build_market_movement([])
        assert result["n_matches_with_movement"] == 0
        assert result["avg_max_abs_movement"] is None

    def test_counts_entries_with_data(self):
        entry = LifecycleEntry(
            match_id="m001", home_team="A", away_team="B",
            kickoff_at=None, n_pre_kickoff_snapshots=6,
            opening=CheckpointSnapshot(
                captured_at="2026-06-18T00:00:00+00:00",
                home_prob=0.40, draw_prob=0.30, away_prob=0.30,
            ),
            h24=None, h12=None, h6=None, h1=None,
            closing=CheckpointSnapshot(
                captured_at="2026-06-19T14:00:00+00:00",
                home_prob=0.50, draw_prob=0.28, away_prob=0.22,
            ),
            closing_status="latest_available",
            generated_at="ts",
        )
        result = build_market_movement([entry])
        assert result["n_matches_with_movement"] == 1
        assert result["avg_max_abs_movement"] is not None

    def test_disclaimer_present(self):
        result = build_market_movement([])
        assert "disclaimer" in result
        assert len(result["disclaimer"]) > 0
