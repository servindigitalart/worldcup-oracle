"""
Tests for oracle.grading.ledger — Week 18.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from oracle.grading.ledger import (
    LEDGER_SCHEMA,
    PredictionLedgerEntry,
    append_to_ledger,
    load_ledger,
    make_prediction_id,
    save_ledger,
)


def _entry(
    match_id: str = "wc2026_m001",
    date_bucket: str = "2026-06-11",
    home_team: str = "mexico",
    away_team: str = "south_africa",
    group: str = "A",
    home_win_prob: float = 0.45,
    draw_prob: float = 0.30,
    away_win_prob: float = 0.25,
) -> PredictionLedgerEntry:
    pid = make_prediction_id(match_id, date_bucket)
    return PredictionLedgerEntry(
        prediction_id=pid,
        generated_at=f"{date_bucket}T12:00:00+00:00",
        match_id=match_id,
        kickoff_at=None,
        home_team=home_team,
        away_team=away_team,
        group=group,
        home_win_prob=home_win_prob,
        draw_prob=draw_prob,
        away_win_prob=away_win_prob,
        market_home_prob=None,
        market_draw_prob=None,
        market_away_prob=None,
        blended_home_prob=home_win_prob,
        blended_draw_prob=draw_prob,
        blended_away_prob=away_win_prob,
        edge_home=None,
        edge_draw=None,
        edge_away=None,
        recommendation_type=None,
        recommendation_selection=None,
        recommendation_confidence=None,
        model_version="elo_v1",
    )


# ── make_prediction_id ─────────────────────────────────────────────────────────

class TestMakePredictionId:
    def test_deterministic(self):
        id1 = make_prediction_id("wc2026_m001", "2026-06-11")
        id2 = make_prediction_id("wc2026_m001", "2026-06-11")
        assert id1 == id2

    def test_different_match_different_id(self):
        id1 = make_prediction_id("wc2026_m001", "2026-06-11")
        id2 = make_prediction_id("wc2026_m002", "2026-06-11")
        assert id1 != id2

    def test_different_date_different_id(self):
        id1 = make_prediction_id("wc2026_m001", "2026-06-11")
        id2 = make_prediction_id("wc2026_m001", "2026-06-12")
        assert id1 != id2

    def test_length_16(self):
        pid = make_prediction_id("wc2026_m001", "2026-06-11")
        assert len(pid) == 16

    def test_hex_chars_only(self):
        pid = make_prediction_id("wc2026_m001", "2026-06-11")
        assert all(c in "0123456789abcdef" for c in pid)


# ── load_ledger ────────────────────────────────────────────────────────────────

class TestLoadLedger:
    def test_nonexistent_returns_empty(self, tmp_path):
        df = load_ledger(tmp_path / "missing.parquet")
        assert len(df) == 0
        assert set(LEDGER_SCHEMA.keys()).issubset(set(df.columns))

    def test_reads_existing(self, tmp_path):
        e = _entry()
        path = tmp_path / "ledger.parquet"
        append_to_ledger([e], ledger_path=path)
        df = load_ledger(path)
        assert len(df) == 1


# ── append_to_ledger ───────────────────────────────────────────────────────────

class TestAppendToLedger:
    def test_first_append(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        n, skipped = append_to_ledger([_entry()], ledger_path=path)
        assert n == 1
        assert skipped == 0
        assert path.exists()

    def test_second_different_entry(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        append_to_ledger([_entry("wc2026_m001")], ledger_path=path)
        n, skipped = append_to_ledger([_entry("wc2026_m002")], ledger_path=path)
        assert n == 1
        assert skipped == 0
        df = load_ledger(path)
        assert len(df) == 2

    def test_duplicate_skipped(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        e = _entry()
        append_to_ledger([e], ledger_path=path)
        n, skipped = append_to_ledger([e], ledger_path=path)
        assert n == 0
        assert skipped == 1
        df = load_ledger(path)
        assert len(df) == 1

    def test_empty_list(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        n, skipped = append_to_ledger([], ledger_path=path)
        assert n == 0
        assert skipped == 0

    def test_schema_preserved(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        append_to_ledger([_entry()], ledger_path=path)
        df = load_ledger(path)
        for col in LEDGER_SCHEMA:
            assert col in df.columns

    def test_result_known_false_by_default(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        append_to_ledger([_entry()], ledger_path=path)
        df = load_ledger(path)
        assert df["result_known"][0] is False or df["result_known"][0] == False

    def test_outcome_null_by_default(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        append_to_ledger([_entry()], ledger_path=path)
        df = load_ledger(path)
        assert df["outcome"][0] is None

    def test_prediction_data_preserved(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        e = _entry(home_win_prob=0.55)
        append_to_ledger([e], ledger_path=path)
        df = load_ledger(path)
        assert abs(df["home_win_prob"][0] - 0.55) < 1e-9

    def test_multiple_entries_same_call(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        entries = [_entry("wc2026_m001"), _entry("wc2026_m002")]
        n, skipped = append_to_ledger(entries, ledger_path=path)
        assert n == 2
        assert skipped == 0


# ── save_ledger ────────────────────────────────────────────────────────────────

class TestSaveLedger:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "ledger.parquet"
        e = _entry()
        append_to_ledger([e], ledger_path=path)

        df = load_ledger(path)
        # Simulate grading: update result_known
        df = df.with_columns([
            pl.lit(True).alias("result_known"),
            pl.lit("home_win").alias("outcome"),
        ])
        save_ledger(df, path)

        reloaded = load_ledger(path)
        assert reloaded["result_known"][0] is True or reloaded["result_known"][0] == True
        assert reloaded["outcome"][0] == "home_win"


# ── to_dict ────────────────────────────────────────────────────────────────────

class TestToDict:
    def test_all_keys_present(self):
        e = _entry()
        d = e.to_dict()
        for col in LEDGER_SCHEMA:
            assert col in d, f"missing key: {col}"

    def test_json_serializable(self):
        e = _entry()
        d = e.to_dict()
        json.dumps(d, default=str)  # must not raise
