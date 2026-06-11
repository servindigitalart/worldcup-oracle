"""
Tests for bracket integration with tournament simulator and export pipeline — Week 21.
"""
from __future__ import annotations

import random

import pytest


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

ALL_TEAMS = [t for teams in _TEAMS_BY_GROUP.values() for t in teams]


def _fake_standings() -> dict[str, list[dict]]:
    standings = {}
    for g, teams in _TEAMS_BY_GROUP.items():
        base_pts = [9, 6, 3, 0]
        standings[g] = [
            {"team": t, "points": base_pts[i], "gd": 3 - i, "gf": 5 - i}
            for i, t in enumerate(teams)
        ]
    return standings


# ── simulate_knockout_from_template ──────────────────────────────────────────

class TestSimulateKnockoutFromTemplate:
    def _build_slot_assignment(self) -> dict[str, str]:
        from oracle.bracket.third_place import select_best_thirds
        standings = _fake_standings()
        best = select_best_thirds(standings, 8)
        slot_assignment: dict[str, str] = {}
        for g, rows in standings.items():
            slot_assignment[f"{g}1"] = rows[0]["team"]
            slot_assignment[f"{g}2"] = rows[1]["team"]
        for i, row in enumerate(best, 1):
            slot_assignment[f"T{i}"] = row["team"]
        return slot_assignment

    def _fake_elo(self):
        from oracle.ratings.elo import EloRatings
        try:
            from oracle.ingest.results import load_results
            df = load_results()
            elo = EloRatings()
            elo.fit(df)
            return elo
        except Exception:
            pytest.skip("Historical results not available for EloRatings")

    def test_returns_champion(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        rng = random.Random(42)
        result = simulate_knockout_from_template(sa, elo, rng)
        assert "champion" in result
        assert result["champion"] in ALL_TEAMS

    def test_returns_finalist(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        rng = random.Random(42)
        result = simulate_knockout_from_template(sa, elo, rng)
        assert "finalist" in result
        assert result["finalist"] in ALL_TEAMS

    def test_champion_not_finalist(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        rng = random.Random(42)
        result = simulate_knockout_from_template(sa, elo, rng)
        assert result["champion"] != result["finalist"]

    def test_results_has_5_rounds(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        rng = random.Random(42)
        result = simulate_knockout_from_template(sa, elo, rng)
        assert len(result["results"]) == 5

    def test_round_match_counts(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        rng = random.Random(42)
        result = simulate_knockout_from_template(sa, elo, rng)
        expected_counts = [16, 8, 4, 2, 1]
        for i, (round_results, expected) in enumerate(zip(result["results"], expected_counts)):
            assert len(round_results) == expected, f"Round {i}: expected {expected} matches"

    def test_round_names_correct(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        rng = random.Random(42)
        result = simulate_knockout_from_template(sa, elo, rng)
        expected_rounds = ["R32", "R16", "QF", "SF", "Final"]
        for round_results, rnd_name in zip(result["results"], expected_rounds):
            for match in round_results:
                assert match["round"] == rnd_name

    def test_wrong_slot_count_raises(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        rng = random.Random(42)
        with pytest.raises(ValueError, match="32"):
            simulate_knockout_from_template({"A1": "mexico"}, elo, rng)

    def test_reproducibility_same_seed(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        r1 = simulate_knockout_from_template(sa, elo, random.Random(99))
        r2 = simulate_knockout_from_template(sa, elo, random.Random(99))
        assert r1["champion"] == r2["champion"]

    def test_different_seeds_may_differ(self):
        from oracle.sim.bracket import simulate_knockout_from_template
        elo = self._fake_elo()
        sa = self._build_slot_assignment()
        champions = set()
        for seed in range(20):
            r = simulate_knockout_from_template(sa, elo, random.Random(seed))
            champions.add(r["champion"])
        assert len(champions) > 1


# ── tournament integration: run_tournament uses new bracket ───────────────────

class TestTournamentIntegration:
    def _fake_elo(self):
        from oracle.ratings.elo import EloRatings
        try:
            from oracle.ingest.results import load_results
            df = load_results()
            elo = EloRatings()
            elo.fit(df)
            return elo
        except Exception:
            pytest.skip("Historical results not available")

    def test_run_tournament_completes(self):
        from oracle.sim.tournament import run_tournament
        elo = self._fake_elo()
        rng = random.Random(42)
        result = run_tournament(elo, rng)
        assert "champion" in result
        assert "ko_results" in result

    def test_champion_is_wc2026_team(self):
        from oracle.sim.tournament import run_tournament
        elo = self._fake_elo()
        rng = random.Random(42)
        result = run_tournament(elo, rng)
        assert result["champion"] in ALL_TEAMS

    def test_ko_results_has_5_rounds(self):
        from oracle.sim.tournament import run_tournament
        elo = self._fake_elo()
        rng = random.Random(42)
        result = run_tournament(elo, rng)
        assert len(result["ko_results"]) == 5

    def test_best_third_selected_by_new_engine(self):
        from oracle.sim.tournament import run_tournament
        elo = self._fake_elo()
        rng = random.Random(42)
        result = run_tournament(elo, rng)
        # Exactly 8 third-place qualifiers
        thirds = [t for t, finish in result["qualified"].items() if finish == "3rd_best"]
        assert len(thirds) == 8

    def test_qualified_count_is_32(self):
        from oracle.sim.tournament import run_tournament
        elo = self._fake_elo()
        rng = random.Random(42)
        result = run_tournament(elo, rng)
        assert len(result["qualified"]) == 32

    def test_monte_carlo_small(self):
        from oracle.sim.tournament import monte_carlo
        elo = self._fake_elo()
        probs = monte_carlo(elo, n_sims=50, seed=1)
        assert "team_probs" in probs
        assert probs["n_sims"] == 50

    def test_all_48_teams_in_team_probs(self):
        from oracle.sim.tournament import monte_carlo
        elo = self._fake_elo()
        probs = monte_carlo(elo, n_sims=50, seed=1)
        assert len(probs["team_probs"]) == 48

    def test_champion_probs_sum_to_one(self):
        from oracle.sim.tournament import monte_carlo
        elo = self._fake_elo()
        probs = monte_carlo(elo, n_sims=200, seed=1)
        total = sum(v["champion"] for v in probs["team_probs"].values())
        assert abs(total - 1.0) < 0.02


# ── select_best_thirds integration ───────────────────────────────────────────

class TestBestThirdsIntegration:
    def test_select_returns_8(self):
        from oracle.bracket.third_place import select_best_thirds
        standings = _fake_standings()
        result = select_best_thirds(standings)
        assert len(result) == 8

    def test_select_all_have_group_key(self):
        from oracle.bracket.third_place import select_best_thirds
        standings = _fake_standings()
        result = select_best_thirds(standings)
        for row in result:
            assert "group" in row

    def test_select_deterministic(self):
        from oracle.bracket.third_place import select_best_thirds
        standings = _fake_standings()
        r1 = select_best_thirds(standings)
        r2 = select_best_thirds(standings)
        assert [r["team"] for r in r1] == [r["team"] for r in r2]
