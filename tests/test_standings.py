"""
Tests for oracle.state.standings — Week 13 group standings engine.

Coverage:
  - Empty results → all zeros, all status_label='unknown'
  - Single result applied correctly (points, GD, GF)
  - After 6 results (group complete): rank 1-2 = qualified_top2, rank 4 = eliminated
  - Partial results (3 of 6): status = alive
  - Deterministic sort: points → GD → GF → alphabetical team ID
  - Output schema and row count
"""
from __future__ import annotations

import polars as pl
import pytest

from oracle.state.standings import compute_standings


# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_GROUPS = {
    "X": ["alpha", "beta", "gamma", "delta"],
}

_SCHEMA = {
    "match_id":   pl.Utf8,
    "home_team":  pl.Utf8,
    "away_team":  pl.Utf8,
    "group":      pl.Utf8,
    "home_goals": pl.Int32,
    "away_goals": pl.Int32,
    "status":     pl.Utf8,
}


def _results(*rows: dict) -> pl.DataFrame:
    return pl.DataFrame(list(rows), schema=_SCHEMA)


def _empty_results() -> pl.DataFrame:
    return pl.DataFrame(schema=_SCHEMA)


# ── Schema / empty ─────────────────────────────────────────────────────────────

class TestStandingsSchema:
    def test_returns_dataframe(self) -> None:
        df = compute_standings(SIMPLE_GROUPS, _empty_results())
        assert isinstance(df, pl.DataFrame)

    def test_has_expected_columns(self) -> None:
        df = compute_standings(SIMPLE_GROUPS, _empty_results())
        expected = {
            "group", "team", "played", "won", "drawn", "lost",
            "gf", "ga", "gd", "points", "rank", "status_label",
        }
        assert expected <= set(df.columns)

    def test_row_count_matches_teams(self) -> None:
        groups = {
            "A": ["t1", "t2", "t3", "t4"],
            "B": ["t5", "t6", "t7", "t8"],
        }
        df = compute_standings(groups, _empty_results())
        assert len(df) == 8

    def test_all_12_groups_produce_48_rows(self) -> None:
        from oracle.sim.groups import WC2026_GROUPS
        df = compute_standings(WC2026_GROUPS, _empty_results())
        assert len(df) == 48


# ── Empty results ──────────────────────────────────────────────────────────────

class TestStandingsEmpty:
    def test_all_zeros_when_no_results(self) -> None:
        df = compute_standings(SIMPLE_GROUPS, _empty_results())
        assert df["played"].sum() == 0
        assert df["points"].sum() == 0

    def test_all_status_unknown(self) -> None:
        df = compute_standings(SIMPLE_GROUPS, _empty_results())
        assert (df["status_label"] == "unknown").all()


# ── Single result ──────────────────────────────────────────────────────────────

class TestStandingsSingleResult:
    def test_home_win_gives_3_points(self) -> None:
        results = _results({
            "match_id": "m1", "home_team": "alpha", "away_team": "beta",
            "group": "X", "home_goals": 2, "away_goals": 0, "status": "finished",
        })
        df = compute_standings(SIMPLE_GROUPS, results)
        alpha = df.filter(pl.col("team") == "alpha")
        assert alpha["points"][0] == 3

    def test_away_win_gives_3_points_to_away(self) -> None:
        results = _results({
            "match_id": "m1", "home_team": "alpha", "away_team": "beta",
            "group": "X", "home_goals": 0, "away_goals": 1, "status": "finished",
        })
        df = compute_standings(SIMPLE_GROUPS, results)
        beta = df.filter(pl.col("team") == "beta")
        assert beta["points"][0] == 3

    def test_draw_gives_1_point_each(self) -> None:
        results = _results({
            "match_id": "m1", "home_team": "alpha", "away_team": "beta",
            "group": "X", "home_goals": 1, "away_goals": 1, "status": "finished",
        })
        df = compute_standings(SIMPLE_GROUPS, results)
        alpha = df.filter(pl.col("team") == "alpha")
        beta  = df.filter(pl.col("team") == "beta")
        assert alpha["points"][0] == 1
        assert beta["points"][0] == 1

    def test_gd_computed_correctly(self) -> None:
        results = _results({
            "match_id": "m1", "home_team": "alpha", "away_team": "beta",
            "group": "X", "home_goals": 3, "away_goals": 1, "status": "finished",
        })
        df = compute_standings(SIMPLE_GROUPS, results)
        alpha = df.filter(pl.col("team") == "alpha")
        beta  = df.filter(pl.col("team") == "beta")
        assert alpha["gd"][0] == 2
        assert beta["gd"][0] == -2

    def test_non_finished_ignored(self) -> None:
        results = _results({
            "match_id": "m1", "home_team": "alpha", "away_team": "beta",
            "group": "X", "home_goals": None, "away_goals": None, "status": "scheduled",
        })
        df = compute_standings(SIMPLE_GROUPS, results)
        assert df["played"].sum() == 0


# ── Status labels ─────────────────────────────────────────────────────────────

class TestStandingsStatusLabels:
    def _complete_group_results(self) -> pl.DataFrame:
        """All 6 matches in group X with alpha dominating."""
        pairs = [
            ("alpha", "beta",  3, 0),
            ("alpha", "gamma", 2, 0),
            ("alpha", "delta", 1, 0),
            ("beta",  "gamma", 1, 0),
            ("beta",  "delta", 1, 0),
            ("gamma", "delta", 1, 0),
        ]
        rows = [
            {
                "match_id":   f"m{i+1}",
                "home_team":  h,
                "away_team":  a,
                "group":      "X",
                "home_goals": hg,
                "away_goals": ag,
                "status":     "finished",
            }
            for i, (h, a, hg, ag) in enumerate(pairs)
        ]
        return pl.DataFrame(rows, schema=_SCHEMA)

    def test_top_2_are_qualified_top2(self) -> None:
        df = compute_standings(SIMPLE_GROUPS, self._complete_group_results())
        top2 = df.filter(pl.col("rank") <= 2)
        assert (top2["status_label"] == "qualified_top2").all()

    def test_rank_4_is_eliminated(self) -> None:
        df = compute_standings(SIMPLE_GROUPS, self._complete_group_results())
        last = df.filter(pl.col("rank") == 4)
        assert (last["status_label"] == "eliminated").all()

    def test_partial_results_give_alive(self) -> None:
        # Only 3 of 6 matches played
        partial = _results(
            {"match_id": "m1", "home_team": "alpha", "away_team": "beta",
             "group": "X", "home_goals": 1, "away_goals": 0, "status": "finished"},
            {"match_id": "m2", "home_team": "gamma", "away_team": "delta",
             "group": "X", "home_goals": 0, "away_goals": 1, "status": "finished"},
            {"match_id": "m3", "home_team": "alpha", "away_team": "gamma",
             "group": "X", "home_goals": 2, "away_goals": 1, "status": "finished"},
        )
        df = compute_standings(SIMPLE_GROUPS, partial)
        played_teams = df.filter(pl.col("played") > 0)
        assert (played_teams["status_label"] == "alive").all()


# ── Deterministic sort ────────────────────────────────────────────────────────

class TestStandingsSort:
    def test_higher_points_ranks_first(self) -> None:
        results = _results({
            "match_id": "m1", "home_team": "alpha", "away_team": "beta",
            "group": "X", "home_goals": 1, "away_goals": 0, "status": "finished",
        })
        df = compute_standings(SIMPLE_GROUPS, results)
        alpha_rank = df.filter(pl.col("team") == "alpha")["rank"][0]
        beta_rank  = df.filter(pl.col("team") == "beta")["rank"][0]
        assert alpha_rank < beta_rank

    def test_alphabetical_tiebreak(self) -> None:
        """All four teams with 0 points — should sort alpha, beta, delta, gamma."""
        df = compute_standings(SIMPLE_GROUPS, _empty_results())
        ranks = {row["team"]: row["rank"] for row in df.iter_rows(named=True)}
        assert ranks["alpha"] < ranks["beta"] < ranks["delta"] < ranks["gamma"]

    def test_sort_is_deterministic(self) -> None:
        df1 = compute_standings(SIMPLE_GROUPS, _empty_results())
        df2 = compute_standings(SIMPLE_GROUPS, _empty_results())
        assert df1["team"].to_list() == df2["team"].to_list()

    def test_gd_tiebreak_within_same_points(self) -> None:
        # alpha and beta both win one match (3 pts each), but alpha has better GD
        results = _results(
            {"match_id": "m1", "home_team": "alpha", "away_team": "gamma",
             "group": "X", "home_goals": 3, "away_goals": 0, "status": "finished"},
            {"match_id": "m2", "home_team": "beta", "away_team": "delta",
             "group": "X", "home_goals": 1, "away_goals": 0, "status": "finished"},
        )
        df = compute_standings(SIMPLE_GROUPS, results)
        alpha_rank = df.filter(pl.col("team") == "alpha")["rank"][0]
        beta_rank  = df.filter(pl.col("team") == "beta")["rank"][0]
        assert alpha_rank < beta_rank
