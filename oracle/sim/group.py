"""
Single group simulation.

simulate_group():
  Plays all 6 round-robin matches (C(4,2)) and returns standings.

Scoreline modes
---------------
DC grid (default when dc_grids is provided):
  Home goals and away goals are sampled jointly from the precomputed
  Dixon-Coles probability grid for the matchup.  Produces realistic score
  margins (e.g. 3-1, 0-2) so that GD and GF carry genuine tiebreak
  information.

Surrogate fallback (dc_grids=None or key missing from dc_grids):
  Match outcome (W/D/L) is sampled from the Elo 1X2 distribution, then
  mapped to a fixed scoreline:
    Win  → 1-0   (GD +1)
    Draw → 1-1   (GD  0)
    Loss → 0-1   (GD -1)
  ⚠️  APPROXIMATE: every team sharing the same points total will have
  the same GD, so tiebreaks collapse to random.  Use DC grids instead.
"""
from __future__ import annotations

import random
from itertools import combinations
from typing import Any

import numpy as np

from oracle.sim.dc_goals import sample_scoreline as _dc_sample
from oracle.sim.tiebreak import sort_standings

# Surrogate scorelines (fallback only)
_WIN_SCORE  = (1, 0)
_DRAW_SCORE = (1, 1)
_LOSS_SCORE = (0, 1)


def simulate_group(
    teams: list[str],
    elo: Any,
    rng: random.Random,
    *,
    dc_grids: dict[tuple[str, str], np.ndarray] | None = None,
    known_results: dict[tuple[str, str], tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    """Simulate a group of 4 teams and return standings (sorted 1st→4th).

    Args:
        teams:         4 canonical team IDs.
        elo:           Fitted EloRatings with a .predict(home, away) method.
                       Used only when dc_grids is None or a matchup key is absent.
        rng:           Seeded random.Random for reproducibility.
        dc_grids:      Optional dict of pre-normalised flat DC probability arrays
                       keyed by (home_team_id, away_team_id).  When present and
                       the key exists, scorelines are sampled from the DC joint
                       distribution.  Missing keys fall back to Elo surrogate goals.
        known_results: Optional dict mapping (home_team, away_team) → (home_goals,
                       away_goals) for already-finished matches.  Keyed by fixture
                       home/away designation; bidirectional lookup handles reversed
                       combinations() ordering automatically.

    Returns:
        List of 4 dicts ordered best→worst, each with:
          team, points, gd, gf, position (1-indexed)
    """
    if len(teams) != 4:
        raise ValueError(f"Expected 4 teams, got {len(teams)}")

    stats: dict[str, dict[str, int]] = {
        t: {"points": 0, "gd": 0, "gf": 0} for t in teams
    }

    for home, away in combinations(teams, 2):
        known = _get_known_result(home, away, known_results)
        if known is not None:
            gf_h, gf_a = known
        elif dc_grids is not None and (home, away) in dc_grids:
            gf_h, gf_a = _dc_sample(dc_grids[(home, away)], rng)
        else:
            # ⚠️ Surrogate fallback — tiebreaks degenerate within each points tier.
            probs = elo.predict(home, away, neutral=True)
            outcome = _sample_outcome(probs["home"], probs["draw"], probs["away"], rng)
            if outcome == "home":
                gf_h, gf_a = _WIN_SCORE
            elif outcome == "draw":
                gf_h, gf_a = _DRAW_SCORE
            else:
                gf_h, gf_a = _LOSS_SCORE

        _apply_result(stats[home], stats[away], gf_h, gf_a)

    rows = [
        {"team": t, "points": s["points"], "gd": s["gd"], "gf": s["gf"]}
        for t, s in stats.items()
    ]
    sorted_rows = sort_standings(rows, rng=rng)
    for pos, row in enumerate(sorted_rows, start=1):
        row["position"] = pos
    return sorted_rows


def _get_known_result(
    home: str,
    away: str,
    known_results: dict[tuple[str, str], tuple[int, int]] | None,
) -> tuple[int, int] | None:
    """Look up a known result bidirectionally, flipping goals if order is reversed."""
    if known_results is None:
        return None
    if (home, away) in known_results:
        return known_results[(home, away)]
    if (away, home) in known_results:
        ag, hg = known_results[(away, home)]
        return hg, ag  # flip: home/away swapped from fixture designation
    return None


def _sample_outcome(p_home: float, p_draw: float, p_away: float, rng: random.Random) -> str:
    r = rng.random()
    if r < p_home:
        return "home"
    if r < p_home + p_draw:
        return "draw"
    return "away"


def _apply_result(home_stats: dict, away_stats: dict, gf_h: int, gf_a: int) -> None:
    home_stats["gf"] += gf_h
    away_stats["gf"] += gf_a
    home_stats["gd"] += gf_h - gf_a
    away_stats["gd"] += gf_a - gf_h

    if gf_h > gf_a:
        home_stats["points"] += 3
    elif gf_h == gf_a:
        home_stats["points"] += 1
        away_stats["points"] += 1
    else:
        away_stats["points"] += 3
