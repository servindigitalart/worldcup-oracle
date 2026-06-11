"""
Tests for oracle.bracket — schema, slots, fifa2026, builder — Week 21.
"""
from __future__ import annotations

import pytest

from oracle.bracket.fifa2026 import FIFA2026_R32_TEMPLATE, BRACKET_NOTE
from oracle.bracket.slots import (
    ALL_SLOTS, WINNER_SLOTS, RUNNER_UP_SLOTS, THIRD_SLOTS,
    is_winner_slot, is_runner_up_slot, is_third_slot,
    slot_group, slot_finish,
)
from oracle.bracket.schema import BracketTeam, BracketMatch, BracketRound, TournamentBracket
from oracle.bracket.builder import build_bracket
from oracle.bracket.third_place import select_best_thirds


# ── Helpers ───────────────────────────────────────────────────────────────────

_GROUPS = list("ABCDEFGHIJKL")


def _fake_standings() -> dict[str, list[dict]]:
    """Build 12-group standings with realistic team IDs."""
    teams_by_group = {
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
    standings = {}
    for g, teams in teams_by_group.items():
        base_pts = [9, 6, 3, 0]
        standings[g] = [
            {"team": t, "points": base_pts[i], "gd": 3 - i, "gf": 5 - i}
            for i, t in enumerate(teams)
        ]
    return standings


def _fake_best_thirds(n: int = 8) -> list[dict]:
    groups = list("ABCDEFGHIJKL")[:n]
    return [
        {"team": f"{g}_3rd", "group": g, "points": 4, "gd": 0, "gf": 2}
        for g in groups
    ]


# ── Slot constants ────────────────────────────────────────────────────────────

class TestSlots:
    def test_all_slots_count_32(self):
        assert len(ALL_SLOTS) == 32

    def test_no_duplicate_slots(self):
        assert len(set(ALL_SLOTS)) == 32

    def test_winner_slots_count(self):
        assert len(WINNER_SLOTS) == 12

    def test_runner_up_slots_count(self):
        assert len(RUNNER_UP_SLOTS) == 12

    def test_third_slots_count(self):
        assert len(THIRD_SLOTS) == 8

    def test_is_winner_slot(self):
        for g in _GROUPS:
            assert is_winner_slot(f"{g}1")
            assert not is_winner_slot(f"{g}2")

    def test_is_runner_up_slot(self):
        for g in _GROUPS:
            assert is_runner_up_slot(f"{g}2")
            assert not is_runner_up_slot(f"{g}1")

    def test_is_third_slot(self):
        for i in range(1, 9):
            assert is_third_slot(f"T{i}")
        assert not is_third_slot("A1")
        assert not is_third_slot("T0")

    def test_slot_group_winner(self):
        assert slot_group("A1") == "A"
        assert slot_group("L1") == "L"

    def test_slot_group_runner_up(self):
        assert slot_group("B2") == "B"

    def test_slot_group_third_returns_none(self):
        assert slot_group("T1") is None
        assert slot_group("T8") is None

    def test_slot_finish_winner(self):
        assert slot_finish("A1") == "1st"

    def test_slot_finish_runner_up(self):
        assert slot_finish("G2") == "2nd"

    def test_slot_finish_third(self):
        assert slot_finish("T5") == "3rd"


# ── FIFA2026_R32_TEMPLATE ─────────────────────────────────────────────────────

class TestFIFA2026Template:
    def test_exactly_16_matches(self):
        assert len(FIFA2026_R32_TEMPLATE) == 16

    def test_all_32_slots_present(self):
        slots_in_template = {s for pair in FIFA2026_R32_TEMPLATE for s in pair}
        assert slots_in_template == set(ALL_SLOTS)

    def test_no_duplicate_slots(self):
        all_used = [s for pair in FIFA2026_R32_TEMPLATE for s in pair]
        assert len(all_used) == len(set(all_used))

    def test_upper_half_contains_a_to_f_winners(self):
        upper = FIFA2026_R32_TEMPLATE[:8]
        winner_slots_used = {s for pair in upper for s in pair if s in WINNER_SLOTS}
        for g in "ABCDEF":
            assert f"{g}1" in winner_slots_used

    def test_lower_half_contains_g_to_l_winners(self):
        lower = FIFA2026_R32_TEMPLATE[8:]
        winner_slots_used = {s for pair in lower for s in pair if s in WINNER_SLOTS}
        for g in "GHIJKL":
            assert f"{g}1" in winner_slots_used

    def test_same_group_winner_and_runner_up_in_different_halves(self):
        upper_slots = {s for pair in FIFA2026_R32_TEMPLATE[:8] for s in pair}
        lower_slots = {s for pair in FIFA2026_R32_TEMPLATE[8:] for s in pair}
        for g in _GROUPS:
            w = f"{g}1"
            r = f"{g}2"
            assert (w in upper_slots) != (w in lower_slots), f"Winner {w} in both halves"
            assert (r in upper_slots) != (r in lower_slots), f"Runner-up {r} in both halves"
            assert (w in upper_slots) != (r in upper_slots), f"Both {g}1 and {g}2 in same half"

    def test_eight_third_slots_in_template(self):
        thirds_used = [s for pair in FIFA2026_R32_TEMPLATE for s in pair if s in THIRD_SLOTS]
        assert len(thirds_used) == 8
        assert set(thirds_used) == set(THIRD_SLOTS)

    def test_bracket_note_non_empty(self):
        assert len(BRACKET_NOTE) > 50


# ── BracketSchema ─────────────────────────────────────────────────────────────

class TestBracketSchema:
    def test_bracket_team_to_dict(self):
        bt = BracketTeam(team="mexico", slot="A1", group="A", finish="1st")
        d = bt.to_dict()
        assert d["team"] == "mexico"
        assert d["slot"] == "A1"
        assert d["group"] == "A"
        assert d["finish"] == "1st"

    def test_bracket_match_to_dict_minimal(self):
        bm = BracketMatch(match_id="R32_01", round_name="R32", match_index=0,
                          slot_a="A1", slot_b="G2")
        d = bm.to_dict()
        assert d["match_id"] == "R32_01"
        assert d["round_name"] == "R32"
        assert d["team_a"] is None
        assert d["team_b"] is None

    def test_bracket_match_to_dict_with_teams(self):
        ta = BracketTeam("mexico", "A1", "A", "1st")
        tb = BracketTeam("belgium", "G2", "G", "2nd")
        bm = BracketMatch("R32_01", "R32", 0, "A1", "G2", ta, tb, p_a_wins=0.62)
        d = bm.to_dict()
        assert d["team_a"]["team"] == "mexico"
        assert d["team_b"]["team"] == "belgium"
        assert d["p_a_wins"] == 0.62

    def test_bracket_round_to_dict(self):
        bm = BracketMatch("R32_01", "R32", 0, "A1", "G2")
        br = BracketRound("R32", [bm])
        d = br.to_dict()
        assert d["round_name"] == "R32"
        assert d["n_matches"] == 1
        assert len(d["matches"]) == 1

    def test_tournament_bracket_all_rounds(self):
        r32 = BracketRound("R32", [])
        r16 = BracketRound("R16", [])
        qf  = BracketRound("QF",  [])
        sf  = BracketRound("SF",  [])
        fin = BracketRound("Final", [])
        tb = TournamentBracket(r32, r16, qf, sf, fin, bracket_note="test")
        rounds = tb.all_rounds()
        assert len(rounds) == 5
        assert rounds[0].round_name == "R32"
        assert rounds[4].round_name == "Final"

    def test_tournament_bracket_to_dict(self):
        r32 = BracketRound("R32", [])
        r16 = BracketRound("R16", [])
        qf  = BracketRound("QF",  [])
        sf  = BracketRound("SF",  [])
        fin = BracketRound("Final", [])
        tb = TournamentBracket(r32, r16, qf, sf, fin)
        d = tb.to_dict()
        assert "rounds" in d
        assert len(d["rounds"]) == 5


# ── build_bracket ─────────────────────────────────────────────────────────────

class TestBuildBracket:
    def test_r32_has_16_matches(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        assert len(bracket.round_of_32.matches) == 16

    def test_all_5_rounds_present(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        round_names = {r.round_name for r in bracket.all_rounds()}
        assert round_names == {"R32", "R16", "QF", "SF", "Final"}

    def test_r16_has_8_matches(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        assert len(bracket.round_of_16.matches) == 8

    def test_qf_has_4_matches(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        assert len(bracket.quarterfinals.matches) == 4

    def test_sf_has_2_matches(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        assert len(bracket.semifinals.matches) == 2

    def test_final_has_1_match(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        assert len(bracket.final.matches) == 1

    def test_r32_teams_populated(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        for m in bracket.round_of_32.matches:
            assert m.team_a is not None, f"{m.match_id} team_a is None"
            assert m.team_b is not None, f"{m.match_id} team_b is None"

    def test_group_a_winner_in_first_match(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        m = bracket.round_of_32.matches[0]
        assert m.team_a is not None
        assert m.team_a.team == standings["A"][0]["team"]

    def test_group_a_runner_up_in_lower_half(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        lower_half = bracket.round_of_32.matches[8:]
        a2_teams = [
            m.team_b.team for m in lower_half
            if m.team_b and m.slot_b == "A2"
        ]
        assert len(a2_teams) == 1
        assert a2_teams[0] == standings["A"][1]["team"]

    def test_all_32_teams_in_r32(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        teams_in_r32 = set()
        for m in bracket.round_of_32.matches:
            if m.team_a:
                teams_in_r32.add(m.team_a.team)
            if m.team_b:
                teams_in_r32.add(m.team_b.team)
        assert len(teams_in_r32) == 32

    def test_bracket_note_set(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        assert len(bracket.bracket_note) > 10

    def test_generated_at_set(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        assert bracket.generated_at != ""

    def test_custom_generated_at(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds, generated_at="2026-06-15T00:00:00Z")
        assert bracket.generated_at == "2026-06-15T00:00:00Z"

    def test_to_dict_serializable(self):
        import json
        standings = _fake_standings()
        thirds = _fake_best_thirds()
        bracket = build_bracket(standings, thirds)
        d = bracket.to_dict()
        json.dumps(d, default=str)

    def test_empty_standings_produces_empty_teams(self):
        bracket = build_bracket({}, [])
        for m in bracket.round_of_32.matches:
            assert m.team_a is None
            assert m.team_b is None

    def test_t1_slot_gets_best_third(self):
        standings = _fake_standings()
        thirds = _fake_best_thirds(8)
        bracket = build_bracket(standings, thirds)
        t1_matches = [m for m in bracket.round_of_32.matches if m.slot_a == "T1"]
        assert len(t1_matches) == 1
        assert t1_matches[0].team_a is not None
        assert t1_matches[0].team_a.team == thirds[0]["team"]
