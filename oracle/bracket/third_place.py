"""
Third-place qualification engine for FIFA 2026.

Ranks all 12 third-place finishers across groups A–L to select the best 8 who
advance to the knockout stage.

Tiebreak cascade:
  1. Points (desc)
  2. Goal difference (desc)
  3. Goals for (desc)
  4. Fair play score (asc — lower = fewer disciplinary points = better)
     Defaults to 0 when not tracked (simulation context).
  5. Alphabetical team ID (deterministic final resort)
  6. Random noise (optional, for Monte Carlo simulation only)

Note: the official FIFA tiebreaker uses head-to-head records among tied
third-place teams across their respective groups.  This simplified cascade
is appropriate for Monte Carlo simulation and static bracket projection.
When fair_play_score is unavailable (0 for all), step 5 (alphabetical)
ensures full determinism without rng.
"""
from __future__ import annotations

import random
from typing import Any


def rank_third_place_teams(
    group_standings: dict[str, list[dict[str, Any]]],
    *,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    """Extract and rank all 12 third-place teams from group standings.

    Args:
        group_standings: {group_letter: [row0, row1, row2, row3]}.
                         row2 (index 2) is the third-place finisher.
                         Each row must have: team, points, gd, gf.
        rng:             Optional RNG for a random tiebreak as final resort
                         in Monte Carlo simulation.  Omit for deterministic
                         static bracket generation.

    Returns:
        Sorted list of up to 12 third-place rows, best first.
        Each row is augmented with ``group`` and ``fair_play_score``
        keys if not already present.
    """
    thirds: list[dict[str, Any]] = []
    for group, standings in group_standings.items():
        if len(standings) >= 3:
            row = dict(standings[2])
            row.setdefault("group", group)
            row.setdefault("fair_play_score", 0)
            thirds.append(row)

    def _sort_key(row: dict) -> tuple:
        # When rng is None, random_noise=0.0 for all rows → alphabetical resolves ties.
        # When rng is provided (Monte Carlo), random_noise varies per row and provides
        # stochasticity; alphabetical only applies when two rows share the same noise
        # value (astronomically unlikely with float64 random).
        random_noise = rng.random() if rng else 0.0
        return (
            -row.get("points", 0),
            -row.get("gd", 0),
            -row.get("gf", 0),
            row.get("fair_play_score", 0),   # asc: fewer cards = better
            random_noise,                    # stochastic in MC; 0.0 → deterministic
            row.get("team", "zzz"),          # alphabetical final resort (no rng)
        )

    return sorted(thirds, key=_sort_key)


def select_best_thirds(
    group_standings: dict[str, list[dict[str, Any]]],
    n: int = 8,
    *,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    """Return the n best third-place teams from group_standings.

    Args:
        group_standings: See rank_third_place_teams().
        n:               Number of best-third teams to select (default 8).
        rng:             Optional RNG for random tiebreak (simulation only).

    Returns:
        List of n rows, sorted best-first, each with ``group`` key.
    """
    return rank_third_place_teams(group_standings, rng=rng)[:n]
