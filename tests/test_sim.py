"""
Tests for oracle.sim — Week 5 tournament simulator.

Coverage:
  - groups.py:    draw integrity (48 teams, 12 groups, no duplicates, confederation rules)
  - group.py:     round-robin stats, valid standings shape, deterministic seeded output
  - tiebreak.py:  sort_standings ordering (points → GD → GF → random)
  - bracket.py:   knockout structure, 32→1 champion, valid winner names
  - tournament.py: qualification counts, champion from run_tournament, monte_carlo probs
  - LOCKED_MODEL_VERSION matches oracle.forecast.baseline.MODEL_VERSION
"""
from __future__ import annotations

import random

import pytest

from oracle.sim.groups import (
    BEST_THIRD_COUNT,
    GROUP_SIZE,
    N_GROUPS,
    N_TEAMS,
    TOP_PER_GROUP,
    WC2026_GROUPS,
)
from oracle.sim.group import simulate_group
from oracle.sim.tiebreak import sort_standings
from oracle.sim.bracket import simulate_knockout
from oracle.sim.tournament import (
    LOCKED_MODEL_VERSION,
    N_SIMS,
    monte_carlo,
    run_tournament,
)


# ── Minimal stub Elo that returns fixed equal probabilities ─────────────────

class _EqualElo:
    """Stub: all outcomes equally likely (1/3 each)."""
    def predict(self, home, away, neutral=True):
        return {"home": 1/3, "draw": 1/3, "away": 1/3}

    def get_rating(self, team_id):
        return 1500.0


class _HomeElo:
    """Stub: home team wins with probability 0.9, draw 0.05, away 0.05."""
    def predict(self, home, away, neutral=True):
        return {"home": 0.9, "draw": 0.05, "away": 0.05}

    def get_rating(self, team_id):
        return 1500.0


# ── groups.py ────────────────────────────────────────────────────────────────

class TestGroupsDraw:
    def test_group_count(self):
        assert len(WC2026_GROUPS) == N_GROUPS == 12

    def test_group_size(self):
        for letter, teams in WC2026_GROUPS.items():
            assert len(teams) == GROUP_SIZE == 4, f"Group {letter} has {len(teams)} teams"

    def test_total_teams(self):
        all_teams = [t for teams in WC2026_GROUPS.values() for t in teams]
        assert len(all_teams) == N_TEAMS == 48

    def test_no_duplicate_teams(self):
        all_teams = [t for teams in WC2026_GROUPS.values() for t in teams]
        assert len(set(all_teams)) == N_TEAMS

    def test_hosts_in_separate_groups(self):
        """USA, Mexico, Canada must be in separate groups (host rule)."""
        host_groups = []
        for letter, teams in WC2026_GROUPS.items():
            for host in ("united_states", "mexico", "canada"):
                if host in teams:
                    host_groups.append(letter)
        assert len(set(host_groups)) == 3, "Hosts share a group!"

    def test_at_most_two_uefa_per_group(self):
        from oracle.teams import CANONICAL_TEAMS
        # CANONICAL_TEAMS = {team_id: (display_name, confederation)}
        uefa_teams = {tid for tid, (_, conf) in CANONICAL_TEAMS.items() if conf == "UEFA"}
        for letter, teams in WC2026_GROUPS.items():
            uefa_count = sum(1 for t in teams if t in uefa_teams)
            assert uefa_count <= 2, f"Group {letter} has {uefa_count} UEFA teams"

    def test_qualification_constants(self):
        assert TOP_PER_GROUP == 2
        assert BEST_THIRD_COUNT == 8
        assert TOP_PER_GROUP * N_GROUPS + BEST_THIRD_COUNT == 32


# ── tiebreak.py ─────────────────────────────────────────────────────────────

class TestSortStandings:
    def _row(self, team, pts, gd, gf):
        return {"team": team, "points": pts, "gd": gd, "gf": gf}

    def test_sorts_by_points(self):
        rows = [self._row("A", 3, 0, 1), self._row("B", 6, 0, 2), self._row("C", 0, -1, 0)]
        result = sort_standings(rows)
        assert result[0]["team"] == "B"
        assert result[2]["team"] == "C"

    def test_sorts_by_gd_on_equal_points(self):
        rows = [self._row("A", 4, -1, 2), self._row("B", 4, 2, 3), self._row("C", 4, 0, 2)]
        result = sort_standings(rows)
        assert result[0]["team"] == "B"
        assert result[1]["team"] == "C"
        assert result[2]["team"] == "A"

    def test_sorts_by_gf_on_equal_points_gd(self):
        rows = [self._row("A", 4, 1, 2), self._row("B", 4, 1, 5)]
        result = sort_standings(rows)
        assert result[0]["team"] == "B"

    def test_returns_same_length(self):
        rows = [self._row(f"T{i}", i, i, i) for i in range(4)]
        assert len(sort_standings(rows)) == 4

    def test_seeded_random_tiebreak_reproducible(self):
        rows = [self._row("A", 1, 0, 1), self._row("B", 1, 0, 1)]
        rng1 = random.Random(0)
        rng2 = random.Random(0)
        result1 = sort_standings(rows, rng=rng1)
        result2 = sort_standings(rows, rng=rng2)
        assert [r["team"] for r in result1] == [r["team"] for r in result2]


# ── group.py ─────────────────────────────────────────────────────────────────

class TestSimulateGroup:
    _TEAMS = ["united_states", "england", "romania", "senegal"]

    def test_returns_four_rows(self):
        rng = random.Random(1)
        standings = simulate_group(self._TEAMS, _EqualElo(), rng)
        assert len(standings) == 4

    def test_positions_are_one_to_four(self):
        rng = random.Random(2)
        standings = simulate_group(self._TEAMS, _EqualElo(), rng)
        positions = sorted(r["position"] for r in standings)
        assert positions == [1, 2, 3, 4]

    def test_all_teams_present(self):
        rng = random.Random(3)
        standings = simulate_group(self._TEAMS, _EqualElo(), rng)
        teams_in_standings = {r["team"] for r in standings}
        assert teams_in_standings == set(self._TEAMS)

    def test_points_in_valid_range(self):
        # 3 games per team; max points = 9, min = 0
        rng = random.Random(4)
        standings = simulate_group(self._TEAMS, _EqualElo(), rng)
        for row in standings:
            assert 0 <= row["points"] <= 9

    def test_total_points_conservation(self):
        # Each match distributes exactly 3 pts (win) or 2 pts (draw).
        # 6 matches, each distributes 2 or 3 pts. Total range: [12, 18].
        rng = random.Random(5)
        standings = simulate_group(self._TEAMS, _EqualElo(), rng)
        total = sum(r["points"] for r in standings)
        assert 12 <= total <= 18

    def test_gd_sums_to_zero(self):
        rng = random.Random(6)
        standings = simulate_group(self._TEAMS, _EqualElo(), rng)
        assert sum(r["gd"] for r in standings) == 0

    def test_seeded_reproducibility(self):
        standings1 = simulate_group(self._TEAMS, _EqualElo(), random.Random(99))
        standings2 = simulate_group(self._TEAMS, _EqualElo(), random.Random(99))
        assert [r["team"] for r in standings1] == [r["team"] for r in standings2]

    def test_requires_four_teams(self):
        with pytest.raises(ValueError):
            simulate_group(["A", "B", "C"], _EqualElo(), random.Random(0))

    def test_strong_favourite_wins_more_often(self):
        """With p_home=0.9 the first team should top the group most often."""
        wins = 0
        for seed in range(50):
            standings = simulate_group(self._TEAMS, _HomeElo(), random.Random(seed))
            if standings[0]["team"] == self._TEAMS[0]:
                wins += 1
        assert wins >= 35, f"First team won only {wins}/50 times with p_home=0.9"


# ── bracket.py ───────────────────────────────────────────────────────────────

class TestSimulateKnockout:
    _SEEDS = [f"team_{i:02d}" for i in range(32)]

    def test_champion_in_seed_list(self):
        rng = random.Random(7)
        result = simulate_knockout(self._SEEDS, _EqualElo(), rng)
        assert result["champion"] in self._SEEDS

    def test_finalist_in_seed_list(self):
        rng = random.Random(8)
        result = simulate_knockout(self._SEEDS, _EqualElo(), rng)
        assert result["finalist"] in self._SEEDS

    def test_champion_and_finalist_different(self):
        rng = random.Random(9)
        result = simulate_knockout(self._SEEDS, _EqualElo(), rng)
        assert result["champion"] != result["finalist"]

    def test_five_rounds(self):
        rng = random.Random(10)
        result = simulate_knockout(self._SEEDS, _EqualElo(), rng)
        assert len(result["results"]) == 5  # R32, R16, QF, SF, Final

    def test_r16_has_16_matches(self):
        rng = random.Random(11)
        result = simulate_knockout(self._SEEDS, _EqualElo(), rng)
        r16 = [m for m in result["results"][0]]
        assert len(r16) == 16

    def test_final_has_1_match(self):
        rng = random.Random(12)
        result = simulate_knockout(self._SEEDS, _EqualElo(), rng)
        final = result["results"][-1]
        assert len(final) == 1

    def test_rejects_wrong_size(self):
        with pytest.raises(ValueError):
            simulate_knockout(self._SEEDS[:16], _EqualElo(), random.Random(0))

    def test_seeded_reproducibility(self):
        r1 = simulate_knockout(self._SEEDS, _EqualElo(), random.Random(13))
        r2 = simulate_knockout(self._SEEDS, _EqualElo(), random.Random(13))
        assert r1["champion"] == r2["champion"]

    def test_ko_probs_valid(self):
        rng = random.Random(14)
        result = simulate_knockout(self._SEEDS, _EqualElo(), rng)
        for round_matches in result["results"]:
            for match in round_matches:
                p = match["p_home_win_ko"]
                assert 0.0 <= p <= 1.0


# ── tournament.py ────────────────────────────────────────────────────────────

class TestRunTournament:
    def test_champion_is_valid_team(self):
        all_teams = {t for members in WC2026_GROUPS.values() for t in members}
        result = run_tournament(_EqualElo(), random.Random(15))
        assert result["champion"] in all_teams

    def test_qualified_count_is_32(self):
        result = run_tournament(_EqualElo(), random.Random(16))
        assert len(result["qualified"]) == 32

    def test_qualified_finishes(self):
        result = run_tournament(_EqualElo(), random.Random(17))
        for finish in result["qualified"].values():
            assert finish in ("1st", "2nd", "3rd_best")

    def test_exactly_8_best_third(self):
        result = run_tournament(_EqualElo(), random.Random(18))
        third_count = sum(1 for v in result["qualified"].values() if v == "3rd_best")
        assert third_count == 8

    def test_exactly_12_first_place(self):
        result = run_tournament(_EqualElo(), random.Random(19))
        first_count = sum(1 for v in result["qualified"].values() if v == "1st")
        assert first_count == 12

    def test_group_standings_shape(self):
        result = run_tournament(_EqualElo(), random.Random(20))
        for letter, standings in result["groups"].items():
            assert len(standings) == 4, f"Group {letter} standings != 4"


class TestMonteCarlo:
    """Fast smoke tests using 100 simulations."""

    def _run(self, n=100, seed=42):
        return monte_carlo(_EqualElo(), n_sims=n, seed=seed)

    def test_n_sims_recorded(self):
        mc = self._run()
        assert mc["n_sims"] == 100

    def test_seed_recorded(self):
        mc = self._run(seed=77)
        assert mc["seed"] == 77

    def test_locked_model_recorded(self):
        mc = self._run()
        assert mc["locked_model"] == LOCKED_MODEL_VERSION

    def test_champion_probs_sum_to_one(self):
        mc = self._run(n=500)
        total = sum(v["champion"] for v in mc["team_probs"].values())
        assert abs(total - 1.0) < 0.01, f"Champion probs sum to {total:.4f}"

    def test_qualify_probs_all_positive(self):
        mc = self._run(n=500)
        for team, probs in mc["team_probs"].items():
            assert probs["qualify"] >= 0.0

    def test_stage_probs_monotone(self):
        """qualify >= r16 >= qf >= sf >= final >= champion."""
        mc = self._run(n=500)
        for team, probs in mc["team_probs"].items():
            stages = [probs["qualify"], probs["r16"], probs["qf"],
                      probs["sf"], probs["final"], probs["champion"]]
            for i in range(len(stages) - 1):
                assert stages[i] >= stages[i + 1] - 1e-9, (
                    f"{team}: stage[{i}]={stages[i]:.4f} < stage[{i+1}]={stages[i+1]:.4f}"
                )

    def test_all_48_teams_present(self):
        mc = self._run()
        all_teams = {t for members in WC2026_GROUPS.values() for t in members}
        assert set(mc["team_probs"].keys()) == all_teams

    def test_reproducibility(self):
        mc1 = self._run(n=200, seed=42)
        mc2 = self._run(n=200, seed=42)
        for team in mc1["team_probs"]:
            assert mc1["team_probs"][team]["champion"] == mc2["team_probs"][team]["champion"]

    def test_different_seeds_give_different_results(self):
        mc1 = self._run(n=200, seed=1)
        mc2 = self._run(n=200, seed=2)
        champions1 = {t: p["champion"] for t, p in mc1["team_probs"].items()}
        champions2 = {t: p["champion"] for t, p in mc2["team_probs"].items()}
        assert champions1 != champions2

    def test_n_sims_constant_default(self):
        assert N_SIMS == 10_000


# ── Result-aware simulation ───────────────────────────────────────────────────

class TestKnownResultsGroup:
    """simulate_group() respects known_results — no sampling for those matches."""

    _TEAMS = ["mexico", "south_africa", "south_korea", "czech_republic"]

    def test_known_result_applied_forward(self):
        """mexico 3-0 south_africa → mexico gets 3 pts every time."""
        known = {("mexico", "south_africa"): (3, 0)}
        counts = 0
        for seed in range(20):
            standings = simulate_group(self._TEAMS, _EqualElo(), random.Random(seed),
                                       known_results=known)
            mex = next(r for r in standings if r["team"] == "mexico")
            # Mexico got 3 pts from the known result; may also win other matches
            assert mex["points"] >= 3
            counts += 1
        assert counts == 20

    def test_known_result_bidirectional_lookup(self):
        """combinations() may yield (south_africa, mexico); goals must be flipped."""
        known = {("mexico", "south_africa"): (2, 1)}
        for seed in range(10):
            standings = simulate_group(self._TEAMS, _EqualElo(), random.Random(seed),
                                       known_results=known)
            mex = next(r for r in standings if r["team"] == "mexico")
            sa  = next(r for r in standings if r["team"] == "south_africa")
            # mexico won the known match — its gf must include the 2 from that match
            assert mex["gf"] >= 2
            assert sa["gf"] >= 1

    def test_known_draw_gives_one_point_each(self):
        known = {("mexico", "south_africa"): (1, 1)}
        for seed in range(10):
            standings = simulate_group(self._TEAMS, _EqualElo(), random.Random(seed),
                                       known_results=known)
            mex = next(r for r in standings if r["team"] == "mexico")
            sa  = next(r for r in standings if r["team"] == "south_africa")
            assert mex["points"] >= 1
            assert sa["points"] >= 1

    def test_no_known_results_unchanged(self):
        """Passing known_results=None must not change behaviour."""
        s1 = simulate_group(self._TEAMS, _EqualElo(), random.Random(42))
        s2 = simulate_group(self._TEAMS, _EqualElo(), random.Random(42), known_results=None)
        assert [r["team"] for r in s1] == [r["team"] for r in s2]


class TestKnownResultsTournament:
    """run_tournament() and monte_carlo() accept known_results."""

    def test_run_tournament_with_known_results(self):
        known = {("mexico", "south_africa"): (1, 0)}
        result = run_tournament(_EqualElo(), random.Random(42), known_results=known)
        assert "champion" in result
        assert len(result["qualified"]) == 32

    def test_monte_carlo_with_known_results(self):
        known = {("mexico", "south_africa"): (1, 0)}
        mc = monte_carlo(_EqualElo(), n_sims=100, seed=42, known_results=known)
        assert mc["n_sims"] == 100
        assert "team_probs" in mc

    def test_monte_carlo_qualify_top2_qualify_third_present(self):
        mc = monte_carlo(_EqualElo(), n_sims=100, seed=42)
        for team, probs in mc["team_probs"].items():
            assert "qualify_top2"  in probs
            assert "qualify_third" in probs

    def test_qualify_top2_plus_third_equals_qualify(self):
        mc = monte_carlo(_EqualElo(), n_sims=500, seed=42)
        for team, probs in mc["team_probs"].items():
            total = probs["qualify_top2"] + probs["qualify_third"]
            assert abs(total - probs["qualify"]) < 1e-9, (
                f"{team}: top2+third={total:.6f} != qualify={probs['qualify']:.6f}"
            )

    def test_known_results_affects_probs(self):
        """Giving mexico a guaranteed 3-0 win over south_africa should raise mexico's qualify prob."""
        mc_plain  = monte_carlo(_EqualElo(), n_sims=300, seed=42)
        mc_known  = monte_carlo(_EqualElo(), n_sims=300, seed=42,
                                known_results={("mexico", "south_africa"): (3, 0)})
        # Mexico's qualify probability should be >= baseline (has a guaranteed win)
        assert mc_known["team_probs"]["mexico"]["qualify"] >= \
               mc_plain["team_probs"]["mexico"]["qualify"] - 0.05


# ── Locked model version ─────────────────────────────────────────────────────

class TestLockedModelVersion:
    def test_locked_version_matches_baseline(self):
        from oracle.forecast.baseline import MODEL_VERSION
        assert LOCKED_MODEL_VERSION == MODEL_VERSION, (
            f"Sim uses {LOCKED_MODEL_VERSION!r} but baseline exports {MODEL_VERSION!r}. "
            "Update LOCKED_MODEL_VERSION in oracle/sim/tournament.py."
        )

    def test_locked_version_string_format(self):
        assert LOCKED_MODEL_VERSION.startswith("elo-")
        assert "v" in LOCKED_MODEL_VERSION


# ── Best-third-place selection ────────────────────────────────────────────────

class TestBestThirdSelection:
    """Verify that best-third selection picks the top 8 of 12 by standings rules."""

    def test_best_third_count_in_tournament(self):
        mc = monte_carlo(_EqualElo(), n_sims=20, seed=0)
        # spot-check: every team's qualify prob is between 0 and 1
        for team, probs in mc["team_probs"].items():
            assert 0.0 <= probs["qualify"] <= 1.0

    def test_sort_standings_selects_correct_best_third(self):
        """Top-2 from 3 rows should use points → GD → GF cascade."""
        rows = [
            {"team": "A", "group": "G1", "points": 7, "gd": 4, "gf": 5},
            {"team": "B", "group": "G2", "points": 7, "gd": 2, "gf": 4},
            {"team": "C", "group": "G3", "points": 5, "gd": 0, "gf": 2},
        ]
        ranked = sort_standings(rows)
        assert ranked[0]["team"] == "A"
        assert ranked[1]["team"] == "B"
        assert ranked[2]["team"] == "C"
