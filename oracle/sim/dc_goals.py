"""
Dixon-Coles scoreline sampling for group-stage simulation.

Public API
----------
precompute_group_grids(dc) -> dict[(home, away): np.ndarray]
    Build flat normalized CDF arrays for every group-stage matchup, once,
    before the Monte Carlo loop.

sample_scoreline(flat_grid, rng) -> (int, int)
    Draw (home_goals, away_goals) from a precomputed flat array using a
    single rng.random() call — keeps the entire simulator on Python's
    random.Random so the seeding contract is preserved.

Why precompute
--------------
The WC 2026 group draw is fixed between simulations, and the DC model is
fitted once before the loop.  All 72 group-stage probability grids are
therefore identical across all 10,000 simulations.  Calling
dc.predict_grid() 72 times × 10,000 sims = 720,000 calls (~34 s) would
dominate runtime.  Precomputing reduces that to 72 calls (~4 ms) plus
cheap array sampling inside each sim (~13 s total for 10k sims).

Why sample from the joint grid, not the marginals
--------------------------------------------------
DC applies a low-scoring correction (rho parameter) that adjusts the
joint probabilities of (0-0), (1-0), (0-1), and (1-1) relative to the
independent Poisson product.  Sampling home goals and away goals
independently from the marginals discards this correction.  Sampling
from the flat joint array preserves it.

Fallback
--------
Any matchup where DC prediction fails (thin-data teams producing
NaN or negative probability matrices) is omitted from the returned dict.
simulate_group() silently falls back to Elo surrogate goals for those
matches.
"""
from __future__ import annotations

import logging
import random
from itertools import combinations

import numpy as np

from oracle.sim.groups import WC2026_GROUPS

_LOG = logging.getLogger(__name__)

# Must match DixonColesRatings.MAX_GOALS.
_MAX_GOALS = 10
_GRID_CELLS = _MAX_GOALS * _MAX_GOALS  # 100


def precompute_group_grids(dc) -> dict[tuple[str, str], np.ndarray]:
    """Return pre-normalized flat CDF arrays for all 72 group-stage matchups.

    Keys are (home_team_id, away_team_id) following the iteration order of
    itertools.combinations over each group's team list — the same order used
    in simulate_group(), so key lookups always hit.

    Values are float64 numpy arrays of length MAX_GOALS² (100), non-negative,
    summing to 1.0, ready for use with sample_scoreline().

    Matchups where dc.predict_grid() raises are silently omitted; those
    matches fall back to Elo-based surrogate goals.
    """
    grids: dict[tuple[str, str], np.ndarray] = {}
    n_ok = n_fail = 0

    for teams in WC2026_GROUPS.values():
        for home, away in combinations(teams, 2):
            try:
                grid_obj = dc.predict_grid(home, away, neutral=True)
                flat = np.maximum(grid_obj.grid.ravel(), 0.0)
                total = flat.sum()
                if total <= 0.0:
                    raise ValueError("Grid sums to zero after clamping negatives")
                flat = flat / total  # normalize
                grids[(home, away)] = flat
                n_ok += 1
            except Exception as exc:
                _LOG.debug("DC grid failed for (%s, %s): %s", home, away, exc)
                n_fail += 1

    if n_fail:
        _LOG.warning(
            "DC precompute: %d/%d matchups failed — those matches use surrogate goals.",
            n_fail, n_ok + n_fail,
        )
    else:
        _LOG.info("DC precompute: all %d group-stage grids ready.", n_ok)

    return grids


def sample_scoreline(
    flat_grid: np.ndarray,
    rng: random.Random,
    *,
    max_goals: int = _MAX_GOALS,
) -> tuple[int, int]:
    """Sample (home_goals, away_goals) from a flat normalized probability array.

    Uses CDF inversion via np.searchsorted so that a single rng.random() call
    drives the sample.  This keeps the simulator on Python's random.Random
    throughout, preserving the seeding contract.

    Args:
        flat_grid:  1-D float64 array of length max_goals², pre-normalized.
        rng:        Seeded random.Random instance.
        max_goals:  Grid side length (default 10, matching MAX_GOALS=10).

    Returns:
        (home_goals, away_goals), each in [0, max_goals - 1].
    """
    cdf = np.cumsum(flat_grid)
    cdf[-1] = 1.0  # guard against floating-point making the last element < 1
    idx = int(np.searchsorted(cdf, rng.random(), side="right"))
    idx = min(idx, len(flat_grid) - 1)  # clamp to valid range
    return idx // max_goals, idx % max_goals
