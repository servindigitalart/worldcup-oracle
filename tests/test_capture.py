"""
Week 9 tests: closing-line candidate logic, capture pipeline, workflow file.

All tests are offline — no network calls, no writes to real data paths.
Injectable `now` parameter used throughout to keep time-dependent assertions
deterministic.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pytest

from oracle.market.closing import (
    CLOSING_WINDOW_HOURS,
    closing_line_clv_record,
    closing_line_summary,
    match_snapshot_status,
)
from oracle.harness.clv import aggregate_clv
from oracle.market.schema import OddsSnapshot

# ─────────────────────────── fixtures / helpers ──────────────────────────────

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)

_FUTURE_KICKOFF = _NOW + timedelta(hours=10)     # well in the future
_PAST_KICKOFF   = _NOW - timedelta(hours=1)      # already kicked off
_CLOSE_KICKOFF  = _NOW + timedelta(hours=1)      # within closing window


def _snap(
    match_id: str,
    captured_at: str,
    *,
    bookmaker: str = "bwin",
    market: str = "1x2",
    selection: str = "home",
    decimal_odds: float = 2.0,
    devigged: float = 0.48,
) -> OddsSnapshot:
    return OddsSnapshot(
        snapshot_id=f"{match_id}_{bookmaker}_{selection}_{captured_at}",
        bookmaker=bookmaker,
        market=market,
        match_id=match_id,
        home_team="team_a",
        away_team="team_b",
        selection=selection,
        decimal_odds=decimal_odds,
        implied_probability_raw=1 / decimal_odds,
        implied_probability_devigged=devigged,
        devig_method="shin",
        captured_at=captured_at,
        source="test",
    )


def _snaps_at(match_id: str, *timestamps: str) -> list[OddsSnapshot]:
    """One home-selection snapshot per timestamp."""
    return [_snap(match_id, t) for t in timestamps]


# ──────────────────────── TestMatchSnapshotStatus ────────────────────────────

class TestMatchSnapshotStatus:
    def test_no_market_data(self):
        result = match_snapshot_status([], "m1", now=_NOW)
        assert result["status"] == "no_market_data"
        assert result["n_snapshots"] == 0
        assert result["has_closing_line"] is False
        assert result["opening_captured_at"] is None
        assert result["latest_captured_at"] is None

    def test_opening_only_single_snapshot(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z")
        result = match_snapshot_status(snaps, "m1", now=_NOW)
        assert result["status"] == "opening_only"
        assert result["n_snapshots"] == 1
        assert result["has_closing_line"] is False

    def test_opening_only_multiple_bookmakers_same_timestamp(self):
        snaps = [
            _snap("m1", "2026-06-10T08:00:00Z", bookmaker="bwin"),
            _snap("m1", "2026-06-10T08:00:00Z", bookmaker="bet365"),
        ]
        result = match_snapshot_status(snaps, "m1", now=_NOW)
        assert result["status"] == "opening_only"

    def test_latest_available_no_kickoff(self):
        snaps = _snaps_at("m1", "2026-06-09T08:00:00Z", "2026-06-10T08:00:00Z")
        result = match_snapshot_status(snaps, "m1", now=_NOW)
        assert result["status"] == "latest_available"
        assert result["n_snapshots"] == 2

    def test_latest_available_kickoff_far_future(self):
        snaps = _snaps_at("m1", "2026-06-09T08:00:00Z", "2026-06-10T08:00:00Z")
        result = match_snapshot_status(
            snaps, "m1", kickoff_at=_FUTURE_KICKOFF, now=_NOW
        )
        assert result["status"] == "latest_available"

    def test_closing_candidate_within_window(self):
        # latest snapshot 1 hour before kickoff; window = 2 h
        latest_at = "2026-06-10T11:00:00Z"   # 1 h before _CLOSE_KICKOFF (13:00)
        snaps = _snaps_at("m1", "2026-06-09T08:00:00Z", latest_at)
        result = match_snapshot_status(
            snaps, "m1",
            kickoff_at=_NOW + timedelta(hours=1),
            now=_NOW,
        )
        assert result["status"] == "closing_candidate"
        assert result["has_closing_line"] is False

    def test_closing_candidate_exactly_at_window_boundary(self):
        # latest snapshot exactly CLOSING_WINDOW_HOURS before kickoff
        kickoff = _NOW + timedelta(hours=CLOSING_WINDOW_HOURS)
        latest_at = _NOW.strftime("%Y-%m-%dT%H:%M:%SZ")  # captured right now
        snaps = _snaps_at("m1", "2026-06-09T08:00:00Z", latest_at)
        result = match_snapshot_status(
            snaps, "m1", kickoff_at=kickoff, now=_NOW
        )
        assert result["status"] == "closing_candidate"

    def test_not_closing_candidate_outside_window(self):
        # latest snapshot 5 hours before kickoff; window = 2 h → too early
        snaps = _snaps_at("m1", "2026-06-09T08:00:00Z", "2026-06-10T07:00:00Z")
        kickoff = _NOW + timedelta(hours=5)  # 17:00 UTC; latest at 07:00 = 10h gap
        result = match_snapshot_status(
            snaps, "m1", kickoff_at=kickoff, now=_NOW
        )
        assert result["status"] == "latest_available"

    def test_closing_locked_past_kickoff(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z", "2026-06-10T10:00:00Z")
        result = match_snapshot_status(
            snaps, "m1", kickoff_at=_PAST_KICKOFF, now=_NOW
        )
        assert result["status"] == "closing_locked"
        assert result["has_closing_line"] is True

    def test_closing_locked_kickoff_exactly_now(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z", "2026-06-10T10:00:00Z")
        result = match_snapshot_status(
            snaps, "m1", kickoff_at=_NOW, now=_NOW
        )
        assert result["status"] == "closing_locked"
        assert result["has_closing_line"] is True

    def test_hours_of_coverage_computed(self):
        snaps = _snaps_at("m1", "2026-06-09T08:00:00Z", "2026-06-10T08:00:00Z")
        result = match_snapshot_status(snaps, "m1", now=_NOW)
        assert abs(result["hours_of_coverage"] - 24.0) < 0.01

    def test_custom_closing_window(self):
        # latest 30 min before kickoff; window = 1 h → candidate
        kickoff = _NOW + timedelta(minutes=30)
        latest_at = _NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
        snaps = _snaps_at("m1", "2026-06-09T08:00:00Z", latest_at)
        result = match_snapshot_status(
            snaps, "m1",
            kickoff_at=kickoff,
            closing_window_hours=1.0,
            now=_NOW,
        )
        assert result["status"] == "closing_candidate"

    def test_ignores_other_markets(self):
        snaps = [_snap("m1", "2026-06-10T08:00:00Z", market="asian_handicap")]
        result = match_snapshot_status(snaps, "m1", market="1x2", now=_NOW)
        assert result["status"] == "no_market_data"

    def test_ignores_other_match_ids(self):
        snaps = _snaps_at("m2", "2026-06-10T08:00:00Z")
        result = match_snapshot_status(snaps, "m1", now=_NOW)
        assert result["status"] == "no_market_data"


# ──────────────────────── TestClosingLineSummary ──────────────────────────────

class TestClosingLineSummary:
    def test_infers_match_ids_from_snapshots(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z") + _snaps_at("m2", "2026-06-10T09:00:00Z")
        rows = closing_line_summary(snaps, now=_NOW)
        assert len(rows) == 2
        assert {r["match_id"] for r in rows} == {"m1", "m2"}

    def test_explicit_match_ids_includes_no_data_entry(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z")
        rows = closing_line_summary(snaps, match_ids=["m1", "m99"], now=_NOW)
        assert len(rows) == 2
        statuses = {r["match_id"]: r["status"] for r in rows}
        assert statuses["m1"] == "opening_only"
        assert statuses["m99"] == "no_market_data"

    def test_empty_snapshots_returns_empty(self):
        rows = closing_line_summary([], now=_NOW)
        assert rows == []

    def test_kickoff_times_propagated(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z", "2026-06-10T10:00:00Z")
        rows = closing_line_summary(
            snaps,
            kickoff_times={"m1": _PAST_KICKOFF},
            now=_NOW,
        )
        assert rows[0]["status"] == "closing_locked"

    def test_each_row_has_required_fields(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z")
        row = closing_line_summary(snaps, now=_NOW)[0]
        required = {
            "match_id", "status", "n_snapshots",
            "opening_captured_at", "latest_captured_at",
            "hours_of_coverage", "has_closing_line",
        }
        assert required.issubset(set(row.keys()))

    def test_sorted_by_match_id(self):
        snaps = (
            _snaps_at("m3", "2026-06-10T08:00:00Z")
            + _snaps_at("m1", "2026-06-10T08:00:00Z")
            + _snaps_at("m2", "2026-06-10T08:00:00Z")
        )
        rows = closing_line_summary(snaps, now=_NOW)
        ids = [r["match_id"] for r in rows]
        assert ids == sorted(ids)


# ─────────────────────── TestClosingLineClvRecord ────────────────────────────

class TestClosingLineClvRecord:
    def _make_snap(self, devigged: float = 0.45) -> OddsSnapshot:
        return _snap("m1", "2026-06-10T11:00:00Z", devigged=devigged)

    def test_market_close_prob_none_when_latest_available(self):
        rec = closing_line_clv_record(
            "m1", "home", 0.50,
            self._make_snap(0.42), self._make_snap(0.45),
            "latest_available",
        )
        assert rec.market_close_prob is None

    def test_market_close_prob_none_when_closing_candidate(self):
        rec = closing_line_clv_record(
            "m1", "home", 0.50,
            self._make_snap(0.42), self._make_snap(0.45),
            "closing_candidate",
        )
        assert rec.market_close_prob is None

    def test_market_close_prob_none_when_opening_only(self):
        rec = closing_line_clv_record(
            "m1", "home", 0.50,
            self._make_snap(0.42), self._make_snap(0.45),
            "opening_only",
        )
        assert rec.market_close_prob is None

    def test_market_close_prob_none_when_no_market_data(self):
        rec = closing_line_clv_record(
            "m1", "home", 0.50, None, None, "no_market_data"
        )
        assert rec.market_close_prob is None
        assert rec.market_open_prob is None

    def test_market_close_prob_set_when_closing_locked(self):
        close_snap = self._make_snap(devigged=0.47)
        rec = closing_line_clv_record(
            "m1", "home", 0.50,
            self._make_snap(0.42), close_snap,
            "closing_locked",
        )
        assert rec.market_close_prob == pytest.approx(0.47)

    def test_open_prob_always_set_if_snap_provided(self):
        open_snap = self._make_snap(devigged=0.42)
        rec = closing_line_clv_record(
            "m1", "home", 0.50,
            open_snap, self._make_snap(0.45),
            "latest_available",
        )
        assert rec.market_open_prob == pytest.approx(0.42)

    def test_aggregate_clv_skips_non_locked_records(self):
        close_snap = self._make_snap(devigged=0.47)
        records = [
            closing_line_clv_record(
                "m1", "home", 0.55,
                self._make_snap(0.42), close_snap,
                "closing_locked",
            ),
            closing_line_clv_record(
                "m2", "home", 0.55,
                self._make_snap(0.42), self._make_snap(0.45),
                "latest_available",
            ),
        ]
        result = aggregate_clv(records)
        assert result["n_records"] == 1   # only closing_locked counted

    def test_aggregate_clv_empty_when_none_locked(self):
        records = [
            closing_line_clv_record(
                "m1", "home", 0.55,
                self._make_snap(0.42), self._make_snap(0.45),
                "latest_available",
            )
        ]
        result = aggregate_clv(records)
        assert result["n_records"] == 0

    def test_no_true_clv_before_kickoff(self):
        """Statuses other than closing_locked must not produce market_close_prob."""
        for status in ("no_market_data", "opening_only", "latest_available", "closing_candidate"):
            rec = closing_line_clv_record(
                "m1", "home", 0.50,
                self._make_snap(0.42), self._make_snap(0.45),
                status,
            )
            assert rec.market_close_prob is None, (
                f"market_close_prob should be None for status={status!r}"
            )


# ──────────────────────── TestWorkflowFile ───────────────────────────────────

_WORKFLOW_PATH = (
    Path(__file__).parent.parent / ".github" / "workflows" / "capture-odds.yml"
)


class TestWorkflowFile:
    def _content(self) -> str:
        assert _WORKFLOW_PATH.exists(), (
            f"Workflow file missing: {_WORKFLOW_PATH}"
        )
        return _WORKFLOW_PATH.read_text()

    def test_workflow_file_exists(self):
        assert _WORKFLOW_PATH.exists()

    def test_has_cron_schedule(self):
        assert "cron:" in self._content()

    def test_has_workflow_dispatch(self):
        assert "workflow_dispatch" in self._content()

    def test_uses_secrets_not_hardcoded_key(self):
        content = self._content()
        assert "secrets.ODDS_API_KEY" in content
        # Must not contain a literal API key (alphanumeric string of 32+ chars)
        import re
        assert not re.search(r"ODDS_API_KEY:\s+[a-f0-9]{32,}", content)

    def test_no_hardcoded_api_key_value(self):
        content = self._content()
        # The key value should only ever come from secrets
        assert "ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}" in content

    def test_uses_capture_pipeline(self):
        assert "oracle.pipeline.capture" in self._content()

    def test_has_skip_ci_in_commit(self):
        assert "[skip ci]" in self._content()

    def test_commit_only_on_diff(self):
        assert "git diff --cached --quiet" in self._content()

    def test_checkout_step_present(self):
        assert "actions/checkout" in self._content()

    def test_python_setup_present(self):
        assert "actions/setup-python" in self._content()

    def test_permissions_contents_write(self):
        assert "contents: write" in self._content()


# ──────────────────────── TestCapturePipeline ────────────────────────────────

class TestCapturePipeline:
    """Pipeline-level tests using tmp_path to avoid touching real data files."""

    def test_run_produces_status_json(self, tmp_path):
        from oracle.pipeline.capture import run
        run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        status_file = tmp_path / "out" / "market_capture_status.json"
        assert status_file.exists()

    def test_run_produces_candidates_parquet(self, tmp_path):
        from oracle.pipeline.capture import run
        run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        cand_file = tmp_path / "out" / "closing_line_candidates.parquet"
        assert cand_file.exists()

    def test_status_json_schema(self, tmp_path):
        from oracle.pipeline.capture import run
        result = run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        required_keys = {
            "generated_at", "has_real_api_key", "n_new_rows",
            "n_total_snapshots", "n_matches", "by_status",
            "n_closing_locked", "note",
        }
        assert required_keys.issubset(set(result.keys()))

    def test_by_status_has_all_five_keys(self, tmp_path):
        from oracle.pipeline.capture import run
        result = run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        by_status = result["by_status"]
        assert set(by_status.keys()) == {
            "no_market_data", "opening_only", "latest_available",
            "closing_candidate", "closing_locked",
        }

    def test_has_real_api_key_false_without_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ODDS_API_KEY", raising=False)
        from oracle.pipeline.capture import run
        result = run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        assert result["has_real_api_key"] is False

    def test_status_json_written_to_disk_matches_return(self, tmp_path):
        from oracle.pipeline.capture import run
        result = run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        on_disk = json.loads((tmp_path / "out" / "market_capture_status.json").read_text())
        # Spot-check key fields (generated_at may differ by milliseconds)
        assert on_disk["has_real_api_key"] == result["has_real_api_key"]
        assert on_disk["by_status"] == result["by_status"]
        assert on_disk["n_closing_locked"] == result["n_closing_locked"]

    def test_candidates_parquet_schema(self, tmp_path):
        import polars as pl
        from oracle.pipeline.capture import run
        run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        df = pl.read_parquet(tmp_path / "out" / "closing_line_candidates.parquet")
        required_cols = {
            "match_id", "status", "n_snapshots",
            "opening_captured_at", "latest_captured_at",
            "hours_of_coverage", "has_closing_line",
        }
        assert required_cols.issubset(set(df.columns))

    def test_run_without_api_key_does_not_raise(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ODDS_API_KEY", raising=False)
        from oracle.pipeline.capture import run
        # Should complete without raising; dummy provider used
        run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )

    def test_n_closing_locked_zero_without_kickoff_data(self, tmp_path):
        from oracle.pipeline.capture import run
        result = run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        # No kickoff times supplied → no closing_locked matches
        assert result["n_closing_locked"] == 0

    def test_no_network_calls(self, tmp_path, monkeypatch):
        """Capture pipeline must not open real sockets."""
        import socket
        original_socket = socket.socket

        def mock_socket(*args, **kwargs):
            raise RuntimeError("Network call detected in test — forbidden")

        monkeypatch.setattr(socket, "socket", mock_socket)
        monkeypatch.delenv("ODDS_API_KEY", raising=False)

        from oracle.pipeline.capture import run
        run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )


# ──────────────────────── TestTerminologyCapture ─────────────────────────────

class TestTerminologyCapture:
    """No forbidden terms in capture artifact output."""

    _FORBIDDEN = {"edge", "profit", "guaranteed", "sure bet", "beat the market"}

    def _check(self, text: str):
        low = text.lower()
        for term in self._FORBIDDEN:
            assert term not in low, f"Forbidden term {term!r} found in output"

    def test_status_note_no_forbidden_terms(self, tmp_path):
        from oracle.pipeline.capture import run
        result = run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        self._check(result.get("note", ""))

    def test_status_json_on_disk_no_forbidden_terms(self, tmp_path):
        from oracle.pipeline.capture import run
        run(
            curated_path=tmp_path / "snaps.parquet",
            raw_dir=tmp_path / "raw",
            output_dir=tmp_path / "out",
            archive_raw=False,
        )
        content = (tmp_path / "out" / "market_capture_status.json").read_text()
        self._check(content)

    def test_status_values_do_not_use_clv_label(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z")
        for row in closing_line_summary(snaps, now=_NOW):
            assert row["status"] != "clv", (
                "status field must never equal 'clv' — use 'closing_locked'"
            )

    def test_has_closing_line_false_before_kickoff(self):
        snaps = _snaps_at("m1", "2026-06-10T08:00:00Z", "2026-06-10T10:00:00Z")
        row = match_snapshot_status(
            snaps, "m1", kickoff_at=_FUTURE_KICKOFF, now=_NOW
        )
        assert row["has_closing_line"] is False

    def test_workflow_file_mentions_clv_disclaimer(self):
        content = _WORKFLOW_PATH.read_text()
        # Workflow comment should note that dummy data is used without key
        assert "dummy" in content.lower() or "DummyOddsProvider" in content
