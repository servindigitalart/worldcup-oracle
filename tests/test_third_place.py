"""
Tests for oracle.bracket.third_place — Week 21.
"""
from __future__ import annotations

import random

import pytest

from oracle.bracket.third_place import rank_third_place_teams, select_best_thirds


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(team: str, group: str, points: int, gd: int, gf: int,
         fair_play: int = 0) -> dict:
    return {
        "team": team, "group": group,
        "points": points, "gd": gd, "gf": gf,
        "fair_play_score": fair_play,
    }


def _make_standings(*thirds: dict) -> dict[str, list[dict]]:
    """Build a fake group_standings dict where each group has 4 rows.

    The third row (index 2) in each group is set to the provided dict.
    """
    standings: dict[str, list[dict]] = {}
    for row in thirds:
        g = row["group"]
        standings[g] = [
            {"team": f"{g}_1st", "points": 9, "gd": 5, "gf": 8},
            {"team": f"{g}_2nd", "points": 6, "gd": 2, "gf": 5},
            row,
            {"team": f"{g}_4th", "points": 0, "gd": -5, "gf": 1},
        ]
    return standings


# ── rank_third_place_teams ────────────────────────────────────────────────────

class TestRankThirdPlaceTeams:
    def test_returns_all_thirds(self):
        thirds = [_row("a3", "A", 4, 1, 3), _row("b3", "B", 3, 0, 2)]
        standings = _make_standings(*thirds)
        ranked = rank_third_place_teams(standings)
        assert len(ranked) == 2
        teams = [r["team"] for r in ranked]
        assert "a3" in teams
        assert "b3" in teams

    def test_higher_points_first(self):
        thirds = [
            _row("low", "A", 2, 0, 2),
            _row("high", "B", 5, 2, 5),
        ]
        ranked = rank_third_place_teams(_make_standings(*thirds))
        assert ranked[0]["team"] == "high"

    def test_equal_points_gd_tiebreak(self):
        thirds = [
            _row("team_a", "A", 4, -1, 3),
            _row("team_b", "B", 4,  2, 4),
        ]
        ranked = rank_third_place_teams(_make_standings(*thirds))
        assert ranked[0]["team"] == "team_b"

    def test_equal_points_gd_gf_tiebreak(self):
        thirds = [
            _row("low_gf",  "A", 4, 1, 2),
            _row("high_gf", "B", 4, 1, 5),
        ]
        ranked = rank_third_place_teams(_make_standings(*thirds))
        assert ranked[0]["team"] == "high_gf"

    def test_alphabetical_final_tiebreak(self):
        thirds = [
            _row("zebra",  "A", 4, 1, 4),
            _row("ant",    "B", 4, 1, 4),
        ]
        ranked = rank_third_place_teams(_make_standings(*thirds))
        assert ranked[0]["team"] == "ant"

    def test_fair_play_tiebreak(self):
        thirds = [
            _row("clean",   "A", 4, 1, 4, fair_play=0),
            _row("booked",  "B", 4, 1, 4, fair_play=3),
        ]
        ranked = rank_third_place_teams(_make_standings(*thirds))
        assert ranked[0]["team"] == "clean"

    def test_group_key_injected(self):
        row = _row("teamx", "X", 3, 0, 2)
        del row["group"]
        # Rebuild standings manually to include the group-less row at index 2
        standings = {"X": [
            {"team": "X_1st", "points": 9, "gd": 5, "gf": 8},
            {"team": "X_2nd", "points": 6, "gd": 2, "gf": 5},
            {"team": "teamx", "points": 3, "gd": 0, "gf": 2},
            {"team": "X_4th", "points": 0, "gd": -5, "gf": 1},
        ]}
        ranked = rank_third_place_teams(standings)
        assert ranked[0]["group"] == "X"

    def test_empty_standings_returns_empty(self):
        assert rank_third_place_teams({}) == []

    def test_group_with_fewer_than_3_rows_skipped(self):
        standings = {"A": [
            {"team": "a1", "points": 9, "gd": 5, "gf": 8},
            {"team": "a2", "points": 6, "gd": 2, "gf": 5},
            # no third row
        ]}
        result = rank_third_place_teams(standings)
        assert result == []

    def test_12_groups_returns_12(self):
        groups = list("ABCDEFGHIJKL")
        thirds = [_row(f"{g}3", g, 3, 0, 2) for g in groups]
        ranked = rank_third_place_teams(_make_standings(*thirds))
        assert len(ranked) == 12

    def test_all_have_group_key(self):
        thirds = [_row(f"{g}3", g, 3, 0, 2) for g in "ABC"]
        ranked = rank_third_place_teams(_make_standings(*thirds))
        for r in ranked:
            assert "group" in r

    def test_rng_does_not_break_tie_determinism_when_none(self):
        thirds = [
            _row("beta",  "A", 4, 1, 4),
            _row("alpha", "B", 4, 1, 4),
        ]
        r1 = rank_third_place_teams(_make_standings(*thirds))
        r2 = rank_third_place_teams(_make_standings(*thirds))
        assert [r["team"] for r in r1] == [r["team"] for r in r2]

    def test_rng_produces_variation_with_provided_rng(self):
        thirds = [_row(f"t{i}", chr(65 + i), 4, 1, 4) for i in range(6)]
        # Same points/gd/gf — with rng, order should be random
        results = set()
        for seed in range(20):
            rng = random.Random(seed)
            ranked = rank_third_place_teams(_make_standings(*thirds), rng=rng)
            results.add(ranked[0]["team"])
        assert len(results) > 1


# ── select_best_thirds ────────────────────────────────────────────────────────

class TestSelectBestThirds:
    def test_returns_exactly_n(self):
        thirds = [_row(f"{g}3", g, 4, 1, 3) for g in "ABCDEFGHIJKL"]
        result = select_best_thirds(_make_standings(*thirds), n=8)
        assert len(result) == 8

    def test_default_n_is_8(self):
        thirds = [_row(f"{g}3", g, 4, 1, 3) for g in "ABCDEFGHIJKL"]
        result = select_best_thirds(_make_standings(*thirds))
        assert len(result) == 8

    def test_fewer_groups_than_n_returns_all(self):
        thirds = [_row("a3", "A", 4, 1, 3), _row("b3", "B", 3, 0, 2)]
        result = select_best_thirds(_make_standings(*thirds), n=8)
        assert len(result) == 2

    def test_best_team_is_first(self):
        thirds = [
            _row("best",  "A", 7, 5, 7),
            _row("worst", "B", 1, -3, 1),
        ]
        result = select_best_thirds(_make_standings(*thirds), n=8)
        assert result[0]["team"] == "best"

    def test_n_zero_returns_empty(self):
        thirds = [_row("a3", "A", 4, 1, 3)]
        result = select_best_thirds(_make_standings(*thirds), n=0)
        assert result == []

    def test_custom_n(self):
        thirds = [_row(f"{g}3", g, 4, 1, 3) for g in "ABCDEF"]
        result = select_best_thirds(_make_standings(*thirds), n=3)
        assert len(result) == 3

    def test_consistent_selection_no_rng(self):
        thirds = [_row(f"{g}3", g, 3, 0, 2) for g in "ABCDEFGHIJKL"]
        result1 = select_best_thirds(_make_standings(*thirds))
        result2 = select_best_thirds(_make_standings(*thirds))
        assert [r["team"] for r in result1] == [r["team"] for r in result2]
