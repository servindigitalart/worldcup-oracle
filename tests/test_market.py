"""
Tests for oracle.market — Week 7 odds ingestion and CLV-ready pipeline.

Coverage:
  TestOddsSnapshot          — schema fields, to_dict round-trip
  TestBuild1x2Snapshots     — 3 rows, de-vig sum, raw implied prob, validation
  TestDummyOddsProvider     — returns valid snapshots, no network calls
  TestTheOddsAPIProviderKey — missing key raises, explicit key accepted
  TestTheOddsAPIProviderParsing — fake HTTP response, outcome mapping, incomplete market
  TestSnapshotPersistence   — append-only, dedup, raw JSON archival
  TestLoadSnapshots         — empty when file missing, round-trips
  TestOpeningLatestSnapshot — selection from multiple captures
  TestSnapshotMovement      — fields, labeled "snapshot_movement" not "clv", n_hours
  TestCLVReadyRecord        — creates CLVRecord, model_prob, None when no snapshot
"""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

from oracle.harness.clv import CLVRecord
from oracle.market.movement import (
    clv_ready_record,
    latest_snapshot,
    opening_snapshot,
    snapshot_movement,
)
from oracle.market.provider import (
    DummyOddsProvider,
    OddsAPIKeyMissing,
    TheOddsAPIProvider,
    _map_h2h_outcomes,
)
from oracle.market.schema import (
    OddsSnapshot,
    build_1x2_snapshots,
    df_to_snapshots,
    snapshots_to_df,
)
from oracle.market.snapshot import load_snapshots, save_snapshots

# ── Shared fixtures ───────────────────────────────────────────────────────────

_ODDS_1X2 = {"home": 2.25, "draw": 3.50, "away": 3.20}


def _make_snapshot(
    match_id="m001",
    selection="home",
    odds=2.25,
    captured_at="2026-06-11T10:00:00Z",
    bookmaker="test_book",
    snapshot_id="snap-1",
) -> OddsSnapshot:
    return OddsSnapshot(
        snapshot_id=snapshot_id,
        bookmaker=bookmaker,
        market="1x2",
        match_id=match_id,
        home_team="france",
        away_team="germany",
        selection=selection,
        decimal_odds=odds,
        implied_probability_raw=1.0 / odds,
        implied_probability_devigged=0.42,
        devig_method="shin",
        captured_at=captured_at,
        source="test",
    )


def _build_pair(match_id="m001") -> list[OddsSnapshot]:
    """Two consecutive captures for the same match (for movement tests)."""
    first = build_1x2_snapshots(
        match_id=match_id,
        home_team="france",
        away_team="germany",
        bookmaker="book_a",
        odds_1x2={"home": 2.20, "draw": 3.40, "away": 3.30},
        captured_at="2026-06-11T08:00:00Z",
        source="test",
    )
    second = build_1x2_snapshots(
        match_id=match_id,
        home_team="france",
        away_team="germany",
        bookmaker="book_a",
        odds_1x2={"home": 2.10, "draw": 3.50, "away": 3.40},
        captured_at="2026-06-11T16:00:00Z",
        source="test",
    )
    return first + second


# ── TestOddsSnapshot ──────────────────────────────────────────────────────────

class TestOddsSnapshot:
    def test_fields_accessible(self):
        s = _make_snapshot()
        assert s.snapshot_id == "snap-1"
        assert s.selection == "home"
        assert s.market == "1x2"

    def test_to_dict_has_all_fields(self):
        s = _make_snapshot()
        d = s.to_dict()
        expected = {
            "snapshot_id", "bookmaker", "market", "match_id",
            "home_team", "away_team", "selection", "decimal_odds",
            "implied_probability_raw", "implied_probability_devigged",
            "devig_method", "captured_at", "source", "source_event_id",
        }
        assert set(d.keys()) == expected

    def test_source_event_id_defaults_to_none(self):
        s = _make_snapshot()
        assert s.source_event_id is None

    def test_source_event_id_can_be_set(self):
        s = OddsSnapshot(
            snapshot_id="s2", bookmaker="b", market="1x2", match_id="m",
            home_team="a", away_team="b2", selection="home",
            decimal_odds=2.0, implied_probability_raw=0.5,
            implied_probability_devigged=0.48, devig_method="shin",
            captured_at="2026-06-01T00:00:00Z", source="test",
            source_event_id="evt_xyz",
        )
        assert s.source_event_id == "evt_xyz"


# ── TestBuild1x2Snapshots ─────────────────────────────────────────────────────

class TestBuild1x2Snapshots:
    def _rows(self) -> list[OddsSnapshot]:
        return build_1x2_snapshots(
            match_id="wc2026_m001",
            home_team="france",
            away_team="germany",
            bookmaker="pinnacle",
            odds_1x2=_ODDS_1X2,
            captured_at="2026-06-11T15:00:00Z",
            source="test",
        )

    def test_returns_three_rows(self):
        assert len(self._rows()) == 3

    def test_selections_are_home_draw_away(self):
        sels = {r.selection for r in self._rows()}
        assert sels == {"home", "draw", "away"}

    def test_devigged_probs_sum_to_one(self):
        total = sum(r.implied_probability_devigged for r in self._rows())
        assert abs(total - 1.0) < 0.01

    def test_raw_prob_is_inverse_of_odds(self):
        for row in self._rows():
            assert abs(row.implied_probability_raw - 1.0 / row.decimal_odds) < 1e-9

    def test_market_is_1x2(self):
        for row in self._rows():
            assert row.market == "1x2"

    def test_source_event_id_propagated(self):
        rows = build_1x2_snapshots(
            match_id="m", home_team="a", away_team="b",
            bookmaker="bk", odds_1x2=_ODDS_1X2,
            captured_at="2026-01-01T00:00:00Z",
            source="test", source_event_id="evt_99",
        )
        for row in rows:
            assert row.source_event_id == "evt_99"

    def test_shared_snapshot_id_within_build(self):
        rows = self._rows()
        ids = {r.snapshot_id for r in rows}
        assert len(ids) == 1, "All 3 rows of one build() share a snapshot_id"

    def test_raises_on_wrong_keys(self):
        with pytest.raises(ValueError, match="keys"):
            build_1x2_snapshots(
                match_id="m", home_team="a", away_team="b",
                bookmaker="bk",
                odds_1x2={"home": 2.0, "draw": 3.0},  # missing 'away'
                captured_at="2026-01-01T00:00:00Z",
                source="test",
            )


# ── TestDummyOddsProvider ─────────────────────────────────────────────────────

class TestDummyOddsProvider:
    def _provider(self) -> DummyOddsProvider:
        return DummyOddsProvider()

    def test_returns_list(self):
        assert isinstance(self._provider().fetch_upcoming_1x2(), list)

    def test_returns_snapshots(self):
        snaps = self._provider().fetch_upcoming_1x2()
        assert len(snaps) > 0
        assert all(isinstance(s, OddsSnapshot) for s in snaps)

    def test_devigged_probs_sum_to_one_per_match_capture(self):
        snaps = self._provider().fetch_upcoming_1x2()
        # Group by (snapshot_id) — each 3-row group must sum to ~1
        from collections import defaultdict
        groups: dict[str, float] = defaultdict(float)
        for s in snaps:
            groups[s.snapshot_id] += s.implied_probability_devigged
        for sid, total in groups.items():
            assert abs(total - 1.0) < 0.01, f"snapshot_id={sid} sum={total:.4f}"

    def test_required_fields_non_empty(self):
        for s in self._provider().fetch_upcoming_1x2():
            assert s.bookmaker
            assert s.match_id
            assert s.selection in {"home", "draw", "away"}
            assert s.decimal_odds > 1.0
            assert s.captured_at

    def test_source_is_dummy(self):
        for s in self._provider().fetch_upcoming_1x2():
            assert s.source == "dummy"

    def test_no_network_calls(self, monkeypatch):
        """DummyOddsProvider must not touch the network."""
        def _no_network(*_a, **_kw):
            raise OSError("network blocked in test")

        monkeypatch.setattr(socket, "getaddrinfo", _no_network)
        snaps = DummyOddsProvider().fetch_upcoming_1x2()
        assert len(snaps) > 0


# ── TestTheOddsAPIProviderKey ─────────────────────────────────────────────────

class TestTheOddsAPIProviderKey:
    def test_raises_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("ODDS_API_KEY", raising=False)
        with pytest.raises(OddsAPIKeyMissing):
            TheOddsAPIProvider()

    def test_accepts_explicit_key(self, monkeypatch):
        monkeypatch.delenv("ODDS_API_KEY", raising=False)
        p = TheOddsAPIProvider(api_key="test_key_123")
        assert p._api_key == "test_key_123"

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("ODDS_API_KEY", "env_key_abc")
        p = TheOddsAPIProvider()
        assert p._api_key == "env_key_abc"

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ODDS_API_KEY", "env_key")
        p = TheOddsAPIProvider(api_key="explicit_key")
        assert p._api_key == "explicit_key"


# ── TestTheOddsAPIProviderParsing ─────────────────────────────────────────────

_SAMPLE_EVENTS = [
    {
        "id": "evt_abc123",
        "sport_key": "soccer_fifa_world_cup",
        "home_team": "France",
        "away_team": "Germany",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "France", "price": 2.10},
                            {"name": "Draw",   "price": 3.40},
                            {"name": "Germany","price": 3.25},
                        ],
                    }
                ],
            }
        ],
    }
]


class _FakeResponse:
    def __init__(self, data):
        self.status_code = 200
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class TestTheOddsAPIProviderParsing:
    def _provider(self) -> TheOddsAPIProvider:
        fake_get = lambda url, *, params, timeout: _FakeResponse(_SAMPLE_EVENTS)
        return TheOddsAPIProvider(api_key="test_key", _http_get=fake_get)

    def test_returns_three_outcome_rows(self):
        snaps = self._provider().fetch_upcoming_1x2()
        assert len(snaps) == 3

    def test_selections_are_home_draw_away(self):
        sels = {s.selection for s in self._provider().fetch_upcoming_1x2()}
        assert sels == {"home", "draw", "away"}

    def test_home_odds_correct(self):
        snaps = self._provider().fetch_upcoming_1x2()
        home = next(s for s in snaps if s.selection == "home")
        assert abs(home.decimal_odds - 2.10) < 0.01

    def test_source_is_the_odds_api(self):
        for s in self._provider().fetch_upcoming_1x2():
            assert s.source == "the-odds-api"

    def test_source_event_id_set(self):
        for s in self._provider().fetch_upcoming_1x2():
            assert s.source_event_id == "evt_abc123"

    def test_devigged_probs_sum_to_one(self):
        total = sum(
            s.implied_probability_devigged
            for s in self._provider().fetch_upcoming_1x2()
        )
        assert abs(total - 1.0) < 0.01

    def test_skips_incomplete_market(self, monkeypatch):
        incomplete = [
            {
                "id": "evt_x",
                "home_team": "Brazil",
                "away_team": "Argentina",
                "bookmakers": [
                    {
                        "key": "bk",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Brazil", "price": 1.80},
                                    # missing Draw and Argentina
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        fake_get = lambda url, *, params, timeout: _FakeResponse(incomplete)
        p = TheOddsAPIProvider(api_key="key", _http_get=fake_get)
        assert p.fetch_upcoming_1x2() == []


# ── TestMapH2hOutcomes ────────────────────────────────────────────────────────

class TestMapH2hOutcomes:
    def test_maps_all_three(self):
        outcomes = [
            {"name": "France", "price": 2.10},
            {"name": "Draw",   "price": 3.40},
            {"name": "Germany","price": 3.25},
        ]
        result = _map_h2h_outcomes(outcomes, "France", "Germany")
        assert set(result.keys()) == {"home", "draw", "away"}
        assert abs(result["home"] - 2.10) < 0.01
        assert abs(result["draw"] - 3.40) < 0.01
        assert abs(result["away"] - 3.25) < 0.01

    def test_case_insensitive_team_names(self):
        outcomes = [
            {"name": "FRANCE", "price": 2.10},
            {"name": "Draw",   "price": 3.40},
            {"name": "germany","price": 3.25},
        ]
        result = _map_h2h_outcomes(outcomes, "France", "Germany")
        assert "home" in result
        assert "away" in result


# ── TestSnapshotPersistence ───────────────────────────────────────────────────

class TestSnapshotPersistence:
    def _snaps(self) -> list[OddsSnapshot]:
        return build_1x2_snapshots(
            match_id="m1", home_team="a", away_team="b",
            bookmaker="bk", odds_1x2=_ODDS_1X2,
            captured_at="2026-06-01T00:00:00Z", source="test",
        )

    def test_writes_parquet(self, tmp_path):
        path = tmp_path / "snaps.parquet"
        save_snapshots(self._snaps(), curated_path=path)
        assert path.exists()

    def test_returns_new_row_count(self, tmp_path):
        path = tmp_path / "snaps.parquet"
        n = save_snapshots(self._snaps(), curated_path=path)
        assert n == 3

    def test_append_only_grows_file(self, tmp_path):
        path = tmp_path / "snaps.parquet"
        save_snapshots(self._snaps(), curated_path=path)

        second_batch = build_1x2_snapshots(
            match_id="m2", home_team="c", away_team="d",
            bookmaker="bk", odds_1x2=_ODDS_1X2,
            captured_at="2026-06-02T00:00:00Z", source="test",
        )
        save_snapshots(second_batch, curated_path=path)

        snaps = load_snapshots(path)
        assert len(snaps) == 6  # 3 + 3

    def test_deduplication_on_double_write(self, tmp_path):
        path = tmp_path / "snaps.parquet"
        snaps = self._snaps()
        save_snapshots(snaps, curated_path=path)
        n2 = save_snapshots(snaps, curated_path=path)  # same rows
        assert n2 == 0
        assert len(load_snapshots(path)) == 3

    def test_returns_zero_for_empty_input(self, tmp_path):
        path = tmp_path / "snaps.parquet"
        n = save_snapshots([], curated_path=path)
        assert n == 0
        assert not path.exists()

    def test_archives_raw_json(self, tmp_path):
        raw_dir = tmp_path / "raw"
        path = tmp_path / "snaps.parquet"
        save_snapshots(
            self._snaps(),
            curated_path=path,
            archive_raw=True,
            raw_dir=raw_dir,
            raw_label="test",
        )
        json_files = list(raw_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "snaps.parquet"
        save_snapshots(self._snaps(), curated_path=path)
        assert path.exists()


# ── TestLoadSnapshots ─────────────────────────────────────────────────────────

class TestLoadSnapshots:
    def test_empty_when_file_missing(self, tmp_path):
        assert load_snapshots(tmp_path / "nonexistent.parquet") == []

    def test_round_trips(self, tmp_path):
        path = tmp_path / "snaps.parquet"
        snaps = build_1x2_snapshots(
            match_id="m99", home_team="x", away_team="y",
            bookmaker="bk", odds_1x2=_ODDS_1X2,
            captured_at="2026-07-01T00:00:00Z", source="rt_test",
        )
        save_snapshots(snaps, curated_path=path)
        loaded = load_snapshots(path)
        assert len(loaded) == 3
        assert {s.match_id for s in loaded} == {"m99"}
        assert {s.source for s in loaded} == {"rt_test"}


# ── TestOpeningLatestSnapshot ─────────────────────────────────────────────────

class TestOpeningLatestSnapshot:
    def _snaps(self) -> list[OddsSnapshot]:
        return _build_pair("m001")

    def test_opening_is_earliest(self):
        snaps = self._snaps()
        s = opening_snapshot(snaps, "m001", "book_a", "1x2", "home")
        assert s is not None
        assert s.captured_at == "2026-06-11T08:00:00Z"

    def test_latest_is_most_recent(self):
        snaps = self._snaps()
        s = latest_snapshot(snaps, "m001", "book_a", "1x2", "home")
        assert s is not None
        assert s.captured_at == "2026-06-11T16:00:00Z"

    def test_returns_none_when_match_not_found(self):
        snaps = self._snaps()
        assert opening_snapshot(snaps, "m999", "book_a", "1x2", "home") is None
        assert latest_snapshot(snaps, "m999", "book_a", "1x2", "home") is None

    def test_filters_by_selection(self):
        snaps = self._snaps()
        home = opening_snapshot(snaps, "m001", "book_a", "1x2", "home")
        draw = opening_snapshot(snaps, "m001", "book_a", "1x2", "draw")
        assert home is not None
        assert draw is not None
        assert home.selection == "home"
        assert draw.selection == "draw"

    def test_filters_by_bookmaker(self):
        snaps = self._snaps()
        assert opening_snapshot(snaps, "m001", "other_book", "1x2", "home") is None


# ── TestSnapshotMovement ──────────────────────────────────────────────────────

class TestSnapshotMovement:
    def _movement(self) -> dict:
        snaps = _build_pair("m001")
        open_s = opening_snapshot(snaps, "m001", "book_a", "1x2", "home")
        late_s = latest_snapshot(snaps, "m001", "book_a", "1x2", "home")
        return snapshot_movement(open_s, late_s)

    def test_label_is_snapshot_movement_not_clv(self):
        mv = self._movement()
        assert mv["label"] == "snapshot_movement"
        assert "clv" not in mv["label"]

    def test_required_fields_present(self):
        mv = self._movement()
        for field in (
            "match_id", "bookmaker", "market", "selection",
            "open_decimal_odds", "latest_decimal_odds", "odds_movement",
            "open_devigged_prob", "latest_devigged_prob", "prob_movement",
            "n_hours", "label",
        ):
            assert field in mv, f"Missing field: {field}"

    def test_prob_movement_is_difference(self):
        mv = self._movement()
        expected = mv["latest_devigged_prob"] - mv["open_devigged_prob"]
        assert abs(mv["prob_movement"] - expected) < 1e-9

    def test_odds_movement_is_difference(self):
        mv = self._movement()
        expected = mv["latest_decimal_odds"] - mv["open_decimal_odds"]
        assert abs(mv["odds_movement"] - expected) < 1e-9

    def test_n_hours_is_eight(self):
        mv = self._movement()
        # 08:00 → 16:00 = 8 hours
        assert abs(mv["n_hours"] - 8.0) < 0.01


# ── TestCLVReadyRecord ────────────────────────────────────────────────────────

class TestCLVReadyRecord:
    def _snaps(self) -> list[OddsSnapshot]:
        return _build_pair("m001")

    def test_returns_clv_record(self):
        snaps = self._snaps()
        open_s = opening_snapshot(snaps, "m001", "book_a", "1x2", "home")
        late_s = latest_snapshot(snaps, "m001", "book_a", "1x2", "home")
        rec = clv_ready_record("m001", "home", 0.45, open_s, late_s)
        assert isinstance(rec, CLVRecord)

    def test_model_prob_preserved(self):
        snaps = self._snaps()
        open_s = opening_snapshot(snaps, "m001", "book_a", "1x2", "home")
        late_s = latest_snapshot(snaps, "m001", "book_a", "1x2", "home")
        rec = clv_ready_record("m001", "home", 0.45, open_s, late_s)
        assert abs(rec.model_prob - 0.45) < 1e-9

    def test_market_open_prob_from_open_snap(self):
        snaps = self._snaps()
        open_s = opening_snapshot(snaps, "m001", "book_a", "1x2", "home")
        late_s = latest_snapshot(snaps, "m001", "book_a", "1x2", "home")
        rec = clv_ready_record("m001", "home", 0.45, open_s, late_s)
        assert rec.market_open_prob is not None
        assert abs(
            rec.market_open_prob - open_s.implied_probability_devigged
        ) < 1e-9

    def test_market_close_prob_from_latest_snap(self):
        snaps = self._snaps()
        open_s = opening_snapshot(snaps, "m001", "book_a", "1x2", "home")
        late_s = latest_snapshot(snaps, "m001", "book_a", "1x2", "home")
        rec = clv_ready_record("m001", "home", 0.45, open_s, late_s)
        assert rec.market_close_prob is not None
        assert abs(
            rec.market_close_prob - late_s.implied_probability_devigged
        ) < 1e-9

    def test_none_probs_when_no_snapshots(self):
        rec = clv_ready_record("m001", "home", 0.45, None, None)
        assert rec.market_open_prob is None
        assert rec.market_close_prob is None

    def test_outcome_defaults_to_none(self):
        rec = clv_ready_record("m001", "home", 0.45, None, None)
        assert rec.outcome is None

    def test_outcome_can_be_set(self):
        rec = clv_ready_record("m001", "home", 0.45, None, None, outcome=1)
        assert rec.outcome == 1
