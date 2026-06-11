"""
Tests for oracle.bracket.paths — path difficulty analysis — Week 21.
"""
from __future__ import annotations

import pytest

from oracle.bracket.builder import build_bracket
from oracle.bracket.paths import (
    PathDifficultyEntry,
    calculate_expected_opponents,
    compute_path_difficulty,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_GROUPS = list("ABCDEFGHIJKL")

_TEAMS_BY_GROUP = {
    "A": ["mexico",       "south_africa",       "south_korea",  "czech_republic"],
    "B": ["canada",       "bosnia_herzegovina", "qatar",        "switzerland"],
    "C": ["brazil",       "morocco",            "haiti",        "scotland"],
    "D": ["united_states","paraguay",           "australia",    "turkey"],
    "E": ["germany",      "curacao",            "cote_divoire", "ecuador"],
    "F": ["netherlands",  "japan",              "sweden",       "tunisia"],
    "G": ["belgium",      "egypt",              "iran",         "new_zealand"],
    "H": ["spain",        "cape_verde",         "saudi_arabia", "uruguay"],
    "I": ["france",       "senegal",            "iraq",         "norway"],
    "J": ["argentina",    "algeria",            "austria",      "jordan"],
    "K": ["portugal",     "dr_congo",           "uzbekistan",   "colombia"],
    "L": ["england",      "croatia",            "ghana",        "panama"],
}


def _fake_standings() -> dict[str, list[dict]]:
    standings = {}
    for g, teams in _TEAMS_BY_GROUP.items():
        base_pts = [9, 6, 3, 0]
        standings[g] = [
            {"team": t, "points": base_pts[i], "gd": 3 - i, "gf": 5 - i}
            for i, t in enumerate(teams)
        ]
    return standings


def _fake_thirds(n: int = 8) -> list[dict]:
    groups = list("ABCDEFGHIJKL")[:n]
    return [
        {"team": f"{g}_3rd", "group": g, "points": 4, "gd": 0, "gf": 2}
        for g in groups
    ]


def _fake_elo(base: float = 1800.0) -> dict[str, float]:
    elo: dict[str, float] = {}
    all_teams = [t for teams in _TEAMS_BY_GROUP.values() for t in teams]
    for i, team in enumerate(all_teams):
        elo[team] = base - i * 10
    # Add third-place teams
    for i, g in enumerate("ABCDEFGHIJKL"):
        elo[f"{g}_3rd"] = 1500 - i * 5
    return elo


def _build_test_bracket():
    return build_bracket(_fake_standings(), _fake_thirds())


# ── compute_path_difficulty ───────────────────────────────────────────────────

class TestComputePathDifficulty:
    def test_returns_32_entries(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        assert len(entries) == 32

    def test_each_team_has_entry(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        team_names = {e.team for e in entries}
        assert len(team_names) == 32

    def test_r32_opponent_set_for_all(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        for e in entries:
            assert e.r32_opponent is not None, f"{e.team} has no R32 opponent"

    def test_r32_opponents_are_symmetric(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        opp_map = {e.team: e.r32_opponent for e in entries}
        for team, opp in opp_map.items():
            assert opp is not None
            assert opp_map.get(opp) == team, f"{team} and {opp} not symmetric"

    def test_no_team_has_itself_as_opponent(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        for e in entries:
            assert e.r32_opponent != e.team
            if e.expected_r16_opponent:
                assert e.expected_r16_opponent != e.team
            if e.expected_qf_opponent:
                assert e.expected_qf_opponent != e.team
            if e.expected_sf_opponent:
                assert e.expected_sf_opponent != e.team

    def test_difficulty_scores_in_range(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        for e in entries:
            if e.difficulty_score is not None:
                assert 0.0 <= e.difficulty_score <= 10.0, (
                    f"{e.team} difficulty {e.difficulty_score} out of range"
                )

    def test_sorted_hardest_first(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        scores = [e.difficulty_score for e in entries if e.difficulty_score is not None]
        assert scores == sorted(scores, reverse=True)

    def test_max_score_is_10(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        scores = [e.difficulty_score for e in entries if e.difficulty_score is not None]
        if scores:
            assert max(scores) == pytest.approx(10.0, abs=0.01)

    def test_min_score_is_0(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        scores = [e.difficulty_score for e in entries if e.difficulty_score is not None]
        if scores:
            assert min(scores) == pytest.approx(0.0, abs=0.01)

    def test_avg_elo_computed(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        for e in entries:
            assert e.avg_opponent_elo is not None

    def test_max_elo_ge_avg_elo(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        for e in entries:
            if e.avg_opponent_elo and e.max_opponent_elo:
                assert e.max_opponent_elo >= e.avg_opponent_elo

    def test_cumulative_elo_ge_max(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        for e in entries:
            if e.cumulative_elo and e.max_opponent_elo:
                assert e.cumulative_elo >= e.max_opponent_elo

    def test_empty_bracket_returns_empty(self):
        from oracle.bracket.schema import BracketRound, TournamentBracket
        empty = TournamentBracket(
            BracketRound("R32",   []),
            BracketRound("R16",   []),
            BracketRound("QF",    []),
            BracketRound("SF",    []),
            BracketRound("Final", []),
        )
        entries = compute_path_difficulty(empty, {})
        assert entries == []

    def test_to_dict_has_expected_keys(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        entries = compute_path_difficulty(bracket, elo)
        d = entries[0].to_dict()
        for key in ("team", "slot", "group", "r32_opponent",
                    "expected_r16_opponent", "expected_qf_opponent",
                    "expected_sf_opponent", "avg_opponent_elo",
                    "max_opponent_elo", "cumulative_elo", "difficulty_score"):
            assert key in d, f"Missing key: {key}"

    def test_uniform_elo_gives_5_score(self):
        bracket = _build_test_bracket()
        uniform_elo = {team: 1500.0 for teams in _TEAMS_BY_GROUP.values() for team in teams}
        for g in "ABCDEFGHIJKL":
            uniform_elo[f"{g}_3rd"] = 1500.0
        entries = compute_path_difficulty(bracket, uniform_elo)
        for e in entries:
            if e.difficulty_score is not None:
                assert e.difficulty_score == pytest.approx(5.0, abs=0.01)


# ── calculate_expected_opponents ──────────────────────────────────────────────

class TestCalculateExpectedOpponents:
    def test_returns_dict_for_all_teams(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        result = calculate_expected_opponents(bracket, elo)
        assert len(result) == 32

    def test_each_entry_has_four_keys(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        result = calculate_expected_opponents(bracket, elo)
        for team, opps in result.items():
            assert set(opps.keys()) == {"r32", "r16_expected", "qf_expected", "sf_expected"}

    def test_r32_opponent_non_none(self):
        bracket = _build_test_bracket()
        elo = _fake_elo()
        result = calculate_expected_opponents(bracket, elo)
        for team, opps in result.items():
            assert opps["r32"] is not None, f"{team} has no R32 opponent"
