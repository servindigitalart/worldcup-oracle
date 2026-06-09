"""
Group standings tiebreak cascade.

Order of precedence (simplified FIFA rules):
  1. Points (3W / 1D / 0L)
  2. Goal difference (across all group games)
  3. Goals scored (across all group games)
  4. Random (true FIFA: head-to-head subdraw then lots; we use seeded RNG)

TODO: Implement full FIFA head-to-head subdraw:
  - Head-to-head points between tied teams
  - Head-to-head GD between tied teams
  - Head-to-head GF between tied teams
  - Drawing of lots (random) only as last resort
"""
from __future__ import annotations

import random
from typing import Any


def sort_standings(rows: list[dict[str, Any]], rng: random.Random | None = None) -> list[dict[str, Any]]:
    """Sort group standing rows by points → GD → GF → random.

    Each row must have keys: team, points, gd (goal difference), gf (goals for).
    Returns a new sorted list (highest first = group winner).
    """
    _rng = rng or random.Random()

    def _sort_key(row: dict[str, Any]) -> tuple:
        # Negate so that higher is sorted first; random tiebreaker uses consistent noise.
        return (-row["points"], -row["gd"], -row["gf"], _rng.random())

    return sorted(rows, key=_sort_key)
