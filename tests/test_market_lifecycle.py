"""
Tests for oracle.market.lifecycle and oracle.market.validation — Week 20.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from oracle.market.lifecycle import (
    CheckpointSnapshot,
    LifecycleEntry,
    _avg_probs_at,
    _nearest_timestamp,
    build_all_lifecycles,
    build_lifecycle_entry,
)
from oracle.market.schema import build_1x2_snapshots
from oracle.market.validation import validate_all, validate_lifecycle_entry


# ── Helpers ───────────────────────────────────────────────────────────────────

_KICKOFF = datetime(2026, 6, 20, 15, 0, 0, tzinfo=timezone.utc)


def _snaps(match_id: str, hours_before: float, home=2.0, draw=3.5, away=3.2,
           bookmaker: str = "testbook") -> list:
    captured = (_KICKOFF - timedelta(hours=hours_before)).isoformat()
    return build_1x2_snapshots(
        match_id=match_id,
        home_team="teamA",
        away_team="teamB",
        bookmaker=bookmaker,
        odds_1x2={"home": home, "draw": draw, "away": away},
        captured_at=captured,
        source="test",
    )


def _multi_snaps(match_id: str, hours_list: list[float]) -> list:
    snaps = []
    for h in hours_list:
        snaps.extend(_snaps(match_id, h))
    return snaps


# ── CheckpointSnapshot ────────────────────────────────────────────────────────

class TestCheckpointSnapshot:
    def test_to_dict_keys(self):
        cp = CheckpointSnapshot(captured_at="2026-06-20T12:00:00+00:00",
                                home_prob=0.5, draw_prob=0.3, away_prob=0.2)
        d = cp.to_dict()
        assert set(d.keys()) == {"captured_at", "home_prob", "draw_prob", "away_prob"}

    def test_to_dict_rounded(self):
        cp = CheckpointSnapshot(captured_at="t", home_prob=0.333333333,
                                draw_prob=0.333333333, away_prob=0.333333334)
        d = cp.to_dict()
        assert d["home_prob"] == round(0.333333333, 6)


# ── _avg_probs_at ─────────────────────────────────────────────────────────────

class TestAvgProbs:
    def test_returns_checkpoint(self):
        snaps = _snaps("m001", 24.0)
        ts = snaps[0].captured_at
        cp = _avg_probs_at(snaps, "m001", ts)
        assert cp is not None
        assert isinstance(cp.home_prob, float)

    def test_prob_sum_near_one(self):
        snaps = _snaps("m001", 24.0)
        ts = snaps[0].captured_at
        cp = _avg_probs_at(snaps, "m001", ts)
        assert abs(cp.home_prob + cp.draw_prob + cp.away_prob - 1.0) < 0.05

    def test_missing_timestamp_returns_none(self):
        snaps = _snaps("m001", 24.0)
        cp = _avg_probs_at(snaps, "m001", "2000-01-01T00:00:00+00:00")
        assert cp is None

    def test_wrong_match_returns_none(self):
        snaps = _snaps("m001", 24.0)
        ts = snaps[0].captured_at
        cp = _avg_probs_at(snaps, "m999", ts)
        assert cp is None

    def test_averages_multiple_bookmakers(self):
        # Use power de-vig (stable for any odds) to test averaging logic
        from oracle.market.schema import build_1x2_snapshots as _b
        ts = (_KICKOFF - timedelta(hours=24.0)).isoformat()
        snaps1 = _b(match_id="m001", home_team="A", away_team="B",
                    bookmaker="book1",
                    odds_1x2={"home": 2.0, "draw": 3.5, "away": 3.2},
                    captured_at=ts, source="test", devig_method="power")
        snaps2 = _b(match_id="m001", home_team="A", away_team="B",
                    bookmaker="book2",
                    odds_1x2={"home": 2.0, "draw": 3.5, "away": 3.2},
                    captured_at=ts, source="test", devig_method="power")
        cp = _avg_probs_at(snaps1 + snaps2, "m001", ts)
        assert cp is not None
        # Same odds → averaged probs equal individual probs
        expected = snaps1[0].implied_probability_devigged
        assert abs(cp.home_prob - expected) < 1e-6


# ── _nearest_timestamp ────────────────────────────────────────────────────────

class TestNearestTimestamp:
    def test_finds_in_window(self):
        times = [(_KICKOFF - timedelta(hours=h)).isoformat() for h in [30, 24, 12, 6, 1]]
        result = _nearest_timestamp(times, _KICKOFF, target_hours=24.0, tolerance_hours=6.0)
        expected = (_KICKOFF - timedelta(hours=24)).isoformat()
        assert result == expected

    def test_returns_none_outside_window(self):
        times = [(_KICKOFF - timedelta(hours=h)).isoformat() for h in [48, 36]]
        result = _nearest_timestamp(times, _KICKOFF, target_hours=24.0, tolerance_hours=6.0)
        assert result is None

    def test_picks_closest_when_multiple_in_window(self):
        # 20h and 26h both in [18, 30] window for 24h target
        times = [
            (_KICKOFF - timedelta(hours=20)).isoformat(),
            (_KICKOFF - timedelta(hours=26)).isoformat(),
        ]
        result = _nearest_timestamp(times, _KICKOFF, target_hours=24.0, tolerance_hours=6.0)
        # 20h is 4h from target, 26h is 2h from target → 26h is closer
        assert result == (_KICKOFF - timedelta(hours=26)).isoformat()


# ── build_lifecycle_entry ─────────────────────────────────────────────────────

class TestBuildLifecycleEntry:
    def test_empty_snapshots_returns_nulls(self):
        entry = build_lifecycle_entry(
            snapshots=[], match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="2026-06-20T00:00:00+00:00",
        )
        assert entry.opening is None
        assert entry.closing is None
        assert entry.n_pre_kickoff_snapshots == 0

    def test_single_snapshot_sets_opening_and_closing(self):
        snaps = _snaps("m001", 48.0)
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="2026-06-20T00:00:00+00:00",
        )
        assert entry.opening is not None
        assert entry.closing is not None
        # Single snapshot → opening == closing
        assert entry.opening.captured_at == entry.closing.captured_at

    def test_closing_is_latest_pre_kickoff(self):
        snaps = _multi_snaps("m001", [48.0, 36.0, 12.0, 2.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        expected_ts = (_KICKOFF - timedelta(hours=2.0)).isoformat()
        assert entry.closing is not None
        assert entry.closing.captured_at == expected_ts

    def test_opening_is_earliest_pre_kickoff(self):
        snaps = _multi_snaps("m001", [48.0, 36.0, 12.0, 2.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        expected_ts = (_KICKOFF - timedelta(hours=48.0)).isoformat()
        assert entry.opening is not None
        assert entry.opening.captured_at == expected_ts

    def test_post_kickoff_snapshots_excluded(self):
        pre = _snaps("m001", 2.0)   # 2h before kickoff
        post = _snaps("m001", -1.0) # 1h after kickoff (negative = post)
        all_snaps = pre + post
        entry = build_lifecycle_entry(
            snapshots=all_snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        assert entry.n_pre_kickoff_snapshots == 3  # 3 selections pre-kickoff

    def test_h24_checkpoint_populated(self):
        snaps = _multi_snaps("m001", [48.0, 24.0, 12.0, 1.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        assert entry.h24 is not None
        expected_ts = (_KICKOFF - timedelta(hours=24.0)).isoformat()
        assert entry.h24.captured_at == expected_ts

    def test_h12_checkpoint_populated(self):
        snaps = _multi_snaps("m001", [48.0, 24.0, 12.0, 1.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        assert entry.h12 is not None

    def test_h1_checkpoint_populated(self):
        snaps = _multi_snaps("m001", [48.0, 24.0, 1.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        assert entry.h1 is not None

    def test_no_kickoff_yields_no_timed_checkpoints(self):
        snaps = _multi_snaps("m001", [48.0, 24.0, 12.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=None,
            generated_at="ts",
        )
        assert entry.h24 is None
        assert entry.h12 is None
        assert entry.h6 is None
        assert entry.h1 is None
        # But opening/closing should still be set
        assert entry.opening is not None
        assert entry.closing is not None

    def test_closing_status_set(self):
        snaps = _multi_snaps("m001", [24.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        assert entry.closing_status in (
            "no_market_data", "opening_only", "latest_available",
            "closing_candidate", "closing_locked",
        )

    def test_to_dict_serializable(self):
        import json
        snaps = _multi_snaps("m001", [24.0, 1.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="teamA", away_team="teamB",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )
        d = entry.to_dict()
        json.dumps(d, default=str)  # must not raise


# ── build_all_lifecycles ──────────────────────────────────────────────────────

class TestBuildAllLifecycles:
    def test_returns_one_per_match(self):
        snaps = _multi_snaps("m001", [24.0]) + _multi_snaps("m002", [12.0])
        entries = build_all_lifecycles(
            snapshots=snaps,
            match_ids=["m001", "m002"],
            match_meta={
                "m001": {"home_team": "A", "away_team": "B", "kickoff_at": _KICKOFF},
                "m002": {"home_team": "C", "away_team": "D", "kickoff_at": _KICKOFF},
            },
            generated_at="ts",
        )
        assert len(entries) == 2

    def test_missing_match_meta_uses_empty_strings(self):
        snaps = _multi_snaps("m001", [24.0])
        entries = build_all_lifecycles(
            snapshots=snaps,
            match_ids=["m001"],
            match_meta={},
            generated_at="ts",
        )
        assert entries[0].home_team == ""
        assert entries[0].away_team == ""

    def test_empty_inputs(self):
        entries = build_all_lifecycles(
            snapshots=[],
            match_ids=[],
            match_meta={},
            generated_at="ts",
        )
        assert entries == []


# ── validate_lifecycle_entry ──────────────────────────────────────────────────

class TestValidateLifecycleEntry:
    def _valid_entry(self) -> LifecycleEntry:
        snaps = _multi_snaps("m001", [48.0, 24.0, 1.0])
        return build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="A", away_team="B",
            kickoff_at=_KICKOFF,
            generated_at="ts",
        )

    def test_valid_entry_no_warnings(self):
        entry = self._valid_entry()
        warnings = validate_lifecycle_entry(entry)
        assert warnings == []

    def test_bad_prob_sum_warns(self):
        cp = CheckpointSnapshot(
            captured_at="2026-06-19T00:00:00+00:00",
            home_prob=0.6, draw_prob=0.6, away_prob=0.6,  # sum = 1.8
        )
        entry = LifecycleEntry(
            match_id="m001", home_team="A", away_team="B",
            kickoff_at=None, n_pre_kickoff_snapshots=3,
            opening=cp, h24=None, h12=None, h6=None, h1=None, closing=None,
            closing_status="opening_only", generated_at="ts",
        )
        warnings = validate_lifecycle_entry(entry)
        assert any("sum" in w for w in warnings)

    def test_negative_prob_warns(self):
        cp = CheckpointSnapshot(
            captured_at="2026-06-19T00:00:00+00:00",
            home_prob=-0.1, draw_prob=0.6, away_prob=0.5,
        )
        entry = LifecycleEntry(
            match_id="m001", home_team="A", away_team="B",
            kickoff_at=None, n_pre_kickoff_snapshots=3,
            opening=cp, h24=None, h12=None, h6=None, h1=None, closing=None,
            closing_status="opening_only", generated_at="ts",
        )
        warnings = validate_lifecycle_entry(entry)
        assert any("negative" in w for w in warnings)


# ── validate_all ──────────────────────────────────────────────────────────────

class TestValidateAll:
    def test_all_valid_returns_zero_warnings(self):
        snaps = _multi_snaps("m001", [24.0, 1.0])
        entry = build_lifecycle_entry(
            snapshots=snaps, match_id="m001",
            home_team="A", away_team="B",
            kickoff_at=_KICKOFF, generated_at="ts",
        )
        result = validate_all([entry])
        assert result["n_entries"] == 1
        assert result["n_valid"] == 1
        assert result["n_with_warnings"] == 0
        assert result["warnings"] == []

    def test_summary_counts(self):
        result = validate_all([])
        assert result["n_entries"] == 0
        assert result["n_valid"] == 0
