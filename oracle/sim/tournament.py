"""
Full tournament simulation: group stage → qualification → knockout → champion.

run_tournament():
  Single simulation run.  Returns per-group standings and the champion.

monte_carlo():
  N_SIMS independent runs from the same seed.  Returns per-team probabilities
  of: qualifying from groups (top-2 or best-third), reaching R16, QF, SF,
  Final, and winning the tournament.

Qualification rules:
  - Top 2 from each of 12 groups → 24 teams.
  - Best 8 third-place teams (by points → GD → GF → random) → 8 teams.
  - Total: 32 teams advance to knockout.

The "best 8 of 12 third-place teams" selection uses the same tiebreak cascade
as within-group standings.  No conference/group-origin adjustment is applied
(those affect bracket seeding, not qualification eligibility).

Scoreline model (Week 6+):
  When a fitted DixonColesRatings is passed to monte_carlo() via dc=...,
  the 72 group-stage probability grids are precomputed once before the loop
  and reused across all simulations.  This gives realistic GD/GF distributions
  so that tiebreaks carry meaningful signal rather than always resolving randomly.
  Knockout matches continue to use Elo win probabilities (no goals needed).
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from oracle.sim.group import simulate_group
from oracle.sim.groups import BEST_THIRD_COUNT, WC2026_GROUPS
from oracle.sim.bracket import simulate_knockout
from oracle.sim.tiebreak import sort_standings

N_SIMS = 10_000
LOCKED_MODEL_VERSION = "elo-baseline-v0.2"


def run_tournament(
    elo: Any,
    rng: random.Random,
    *,
    dc_grids: dict | None = None,
) -> dict[str, Any]:
    """Run one complete tournament simulation.

    Args:
        elo:       Fitted EloRatings (used for knockout + surrogate-goal fallback).
        rng:       Seeded random.Random.
        dc_grids:  Pre-normalised DC flat arrays from precompute_group_grids().
                   When provided, group-stage scorelines are sampled from the DC
                   joint distribution instead of surrogate goals.

    Returns:
        dict with keys:
          groups:     {group_letter: [standing_rows]}
          qualified:  {team: finish}  where finish in {"1st","2nd","3rd_best"}
          champion:   team id
          finalist:   team id (runner-up)
          ko_results: list of per-round match result lists
    """
    group_standings: dict[str, list[dict]] = {}
    third_place_rows: list[dict] = []

    for letter, teams in WC2026_GROUPS.items():
        standings = simulate_group(teams, elo, rng, dc_grids=dc_grids)
        group_standings[letter] = standings
        third = standings[2]  # 3rd-place finisher (0-indexed)
        third_place_rows.append({**third, "group": letter})

    # Select best 8 of 12 third-place teams
    best_third = sort_standings(third_place_rows, rng=rng)[:BEST_THIRD_COUNT]
    best_third_teams = {r["team"] for r in best_third}

    qualified: dict[str, str] = {}
    for letter, standings in group_standings.items():
        qualified[standings[0]["team"]] = "1st"
        qualified[standings[1]["team"]] = "2nd"
        if standings[2]["team"] in best_third_teams:
            qualified[standings[2]["team"]] = "3rd_best"

    # Build seeding list: 12 group winners, 12 runners-up, 8 best-third
    # Order within each tier follows group letter order (A→L).
    group_order = list(WC2026_GROUPS.keys())
    seeds: list[str] = (
        [group_standings[g][0]["team"] for g in group_order] +
        [group_standings[g][1]["team"] for g in group_order] +
        [r["team"] for r in best_third]
    )
    assert len(seeds) == 32

    ko = simulate_knockout(seeds, elo, rng)

    return {
        "groups": group_standings,
        "qualified": qualified,
        "champion": ko["champion"],
        "finalist": ko["finalist"],
        "ko_results": ko["results"],
    }


def monte_carlo(
    elo: Any,
    n_sims: int = N_SIMS,
    seed: int = 42,
    *,
    dc: Any = None,
) -> dict[str, Any]:
    """Run n_sims independent tournament simulations and aggregate probabilities.

    Args:
        elo:     Fitted EloRatings instance.
        n_sims:  Number of Monte Carlo iterations.  Default: 10,000.
        seed:    Master RNG seed for full reproducibility.
        dc:      Optional fitted DixonColesRatings.  When provided, DC score
                 grids are precomputed once for all 72 group-stage matchups
                 before the simulation loop begins, then reused every run.
                 This replaces surrogate goals (1-0 / 1-1 / 0-1) with realistic
                 sampled scorelines, giving meaningful GD/GF for tiebreaks.

    Returns:
        dict with:
          n_sims:             int
          seed:               int
          locked_model:       LOCKED_MODEL_VERSION
          goals_model:        "dc" if DC grids active, "surrogate" otherwise
          team_probs:         {team: {qualify, r16, qf, sf, final, champion}}
          champion_counts:    {team: int}  raw champion counts
    """
    # Precompute DC grids once — 72 matchups, done before the sim loop.
    dc_grids: dict | None = None
    if dc is not None:
        from oracle.sim.dc_goals import precompute_group_grids
        dc_grids = precompute_group_grids(dc)

    master_rng = random.Random(seed)

    qualify_counts:  dict[str, int] = defaultdict(int)
    champion_counts: dict[str, int] = defaultdict(int)
    finalist_counts: dict[str, int] = defaultdict(int)
    round_wins: dict[str, dict[str, int]] = {
        "R32": defaultdict(int),
        "R16": defaultdict(int),
        "QF":  defaultdict(int),
        "SF":  defaultdict(int),
    }

    for _ in range(n_sims):
        sim_rng = random.Random(master_rng.random())
        result = run_tournament(elo, sim_rng, dc_grids=dc_grids)

        for team in result["qualified"]:
            qualify_counts[team] += 1

        champion_counts[result["champion"]] += 1
        finalist_counts[result["finalist"]] += 1
        finalist_counts[result["champion"]] += 1

        for round_results in result["ko_results"]:
            for match in round_results:
                rnd = match["round"]
                if rnd in round_wins:
                    round_wins[rnd][match["winner"]] += 1

    all_teams = [WC2026_GROUPS[g][i] for g in WC2026_GROUPS for i in range(4)]
    team_probs: dict[str, dict[str, float]] = {}
    for team in all_teams:
        team_probs[team] = {
            "qualify":  qualify_counts[team]    / n_sims,
            "r16":      round_wins["R32"][team] / n_sims,
            "qf":       round_wins["R16"][team] / n_sims,
            "sf":       round_wins["QF"][team]  / n_sims,
            "final":    finalist_counts[team]   / n_sims,
            "champion": champion_counts[team]   / n_sims,
        }

    return {
        "n_sims":          n_sims,
        "seed":            seed,
        "locked_model":    LOCKED_MODEL_VERSION,
        "goals_model":     "dc" if dc_grids is not None else "surrogate",
        "team_probs":      team_probs,
        "champion_counts": dict(champion_counts),
    }
