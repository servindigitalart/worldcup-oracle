"""
Tests for oracle.sim.dc_goals — Dixon-Coles scoreline sampling.

Coverage:
  - precompute_group_grids: key count, probability validity, graceful failure
  - sample_scoreline:       in-range, reproducibility, variation, deterministic grid
  - simulate_group + DC:    GD conservation, points conservation, variable scorelines
  - simulate_group fallback: surrogate goals still produce valid and bounded results
  - monte_carlo + DC:       reproducibility, champion probs sum to ~1, monotone stages
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from oracle.sim.dc_goals import precompute_group_grids, sample_scoreline
from oracle.sim.group import simulate_group
from oracle.sim.groups import WC2026_GROUPS
from oracle.sim.tournament import LOCKED_MODEL_VERSION, monte_carlo


# ── Stubs ────────────────────────────────────────────────────────────────────

class _FakeGrid:
    """Duck-type stub matching the .grid attribute dc_goals reads."""
    def __init__(self, arr: np.ndarray):
        self.grid = arr


class _UniformDC:
    """Returns a uniform 10×10 probability grid for any team pair."""
    MAX_GOALS = 10

    def predict_grid(self, home, away, neutral=True):
        return _FakeGrid(np.full((10, 10), 1 / 100, dtype=np.float64))


class _FailDC:
    """Always raises on predict_grid — simulates thin-data failure."""
    MAX_GOALS = 10

    def predict_grid(self, home, away, neutral=True):
        raise ValueError("Simulated DC failure")


class _EqualElo:
    """Stub Elo: all outcomes equally likely."""
    def predict(self, home, away, neutral=True):
        return {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}

    def get_rating(self, team_id):
        return 1500.0


_GROUP_A = list(WC2026_GROUPS["A"])  # 4 canonical IDs
_UNIFORM_FLAT = np.full(100, 1 / 100, dtype=np.float64)


# ── precompute_group_grids ────────────────────────────────────────────────────

class TestPrecomputeGroupGrids:
    def test_returns_72_entries(self):
        # 12 groups × C(4,2) = 72 matchups
        assert len(precompute_group_grids(_UniformDC())) == 72

    def test_keys_are_pair_tuples(self):
        grids = precompute_group_grids(_UniformDC())
        for k in grids:
            assert isinstance(k, tuple) and len(k) == 2

    def test_arrays_sum_to_one(self):
        grids = precompute_group_grids(_UniformDC())
        for flat in grids.values():
            assert abs(flat.sum() - 1.0) < 1e-6

    def test_arrays_non_negative(self):
        grids = precompute_group_grids(_UniformDC())
        for flat in grids.values():
            assert (flat >= 0).all()

    def test_arrays_length_100(self):
        # 10 × 10 grid flattened
        grids = precompute_group_grids(_UniformDC())
        for flat in grids.values():
            assert len(flat) == 100

    def test_failed_dc_returns_empty_dict(self):
        """A DC model that always fails should return {} without raising."""
        assert precompute_group_grids(_FailDC()) == {}

    def test_keys_match_combinations_order(self):
        """Keys must follow combinations(teams, 2) order — same as simulate_group."""
        from itertools import combinations
        grids = precompute_group_grids(_UniformDC())
        for letter, teams in WC2026_GROUPS.items():
            for home, away in combinations(teams, 2):
                assert (home, away) in grids, f"Missing key ({home}, {away}) for group {letter}"


# ── sample_scoreline ─────────────────────────────────────────────────────────

class TestSampleScoreline:
    def test_goals_in_range(self):
        rng = random.Random(1)
        for _ in range(200):
            h, a = sample_scoreline(_UNIFORM_FLAT.copy(), rng)
            assert 0 <= h < 10
            assert 0 <= a < 10

    def test_reproducible_same_seed(self):
        flat = _UNIFORM_FLAT.copy()
        h1, a1 = sample_scoreline(flat, random.Random(42))
        h2, a2 = sample_scoreline(flat, random.Random(42))
        assert h1 == h2 and a1 == a2

    def test_varies_across_seeds(self):
        flat = _UNIFORM_FLAT.copy()
        results = {sample_scoreline(flat, random.Random(s)) for s in range(50)}
        assert len(results) > 5

    def test_concentrated_on_2_1(self):
        """A grid where only (2,1) has probability should always return (2,1)."""
        flat = np.zeros(100, dtype=np.float64)
        flat[2 * 10 + 1] = 1.0
        for seed in range(10):
            h, a = sample_scoreline(flat, random.Random(seed))
            assert (h, a) == (2, 1)

    def test_single_rng_call_per_sample(self):
        """sample_scoreline must consume exactly one rng.random() call."""
        class _CountingRng:
            def __init__(self, base):
                self._rng = random.Random(base)
                self.calls = 0
            def random(self):
                self.calls += 1
                return self._rng.random()

        crng = _CountingRng(0)
        sample_scoreline(_UNIFORM_FLAT.copy(), crng)
        assert crng.calls == 1


# ── simulate_group with DC grids ─────────────────────────────────────────────

class TestSimulateGroupWithDC:
    def _grids(self):
        return precompute_group_grids(_UniformDC())

    def test_returns_four_rows(self):
        standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(1), dc_grids=self._grids())
        assert len(standings) == 4

    def test_gd_sums_to_zero(self):
        for seed in range(10):
            standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(seed), dc_grids=self._grids())
            assert sum(r["gd"] for r in standings) == 0

    def test_points_in_valid_range(self):
        standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(2), dc_grids=self._grids())
        for row in standings:
            assert 0 <= row["points"] <= 9

    def test_total_points_conservation(self):
        # 6 matches, each gives 2 (draw) or 3 (decisive) points
        standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(3), dc_grids=self._grids())
        total = sum(r["points"] for r in standings)
        assert 12 <= total <= 18

    def test_positions_one_to_four(self):
        standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(4), dc_grids=self._grids())
        assert sorted(r["position"] for r in standings) == [1, 2, 3, 4]

    def test_variable_gd_vs_surrogate_cap(self):
        """DC grids should produce |GD| > 3 over multiple runs.

        With surrogate goals (1-0 wins only), max team GD over 3 games = ±3.
        With the uniform 10×10 DC grid, margins of 4+ are common.
        """
        grids = self._grids()
        max_gd = 0
        for seed in range(50):
            standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(seed), dc_grids=grids)
            for row in standings:
                max_gd = max(max_gd, abs(row["gd"]))
        assert max_gd > 3, f"Expected |GD| > 3 with DC sampling, got max={max_gd}"

    def test_reproducible_with_same_seed(self):
        grids = self._grids()
        s1 = simulate_group(_GROUP_A, _EqualElo(), random.Random(99), dc_grids=grids)
        s2 = simulate_group(_GROUP_A, _EqualElo(), random.Random(99), dc_grids=grids)
        assert [r["team"] for r in s1] == [r["team"] for r in s2]
        assert [r["points"] for r in s1] == [r["points"] for r in s2]


# ── Fallback: surrogate goals ─────────────────────────────────────────────────

class TestSurrogateGoalFallback:
    def test_none_grids_produces_valid_standings(self):
        standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(1), dc_grids=None)
        assert len(standings) == 4
        assert sorted(r["position"] for r in standings) == [1, 2, 3, 4]

    def test_empty_dict_falls_back_for_all_matches(self):
        """Empty grids dict → no DC keys found → all matches use surrogate."""
        standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(2), dc_grids={})
        assert len(standings) == 4

    def test_surrogate_max_team_gd_bounded_by_3(self):
        """With 1-0 / 1-1 / 0-1 scorelines, max |GD| per team over 3 games = 3."""
        max_gd = 0
        for seed in range(50):
            standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(seed), dc_grids=None)
            for row in standings:
                max_gd = max(max_gd, abs(row["gd"]))
        assert max_gd <= 3, f"Surrogate max |GD| = {max_gd}, expected ≤ 3"

    def test_surrogate_gd_sums_to_zero(self):
        standings = simulate_group(_GROUP_A, _EqualElo(), random.Random(5), dc_grids=None)
        assert sum(r["gd"] for r in standings) == 0


# ── monte_carlo with DC ───────────────────────────────────────────────────────

class TestMonteCarloWithDC:
    """Fast smoke tests (n=200) — correctness only, not convergence."""

    def _mc(self, n=200, seed=42):
        return monte_carlo(_EqualElo(), n_sims=n, seed=seed, dc=_UniformDC())

    def test_goals_model_recorded_as_dc(self):
        mc = self._mc(n=50)
        assert mc["goals_model"] == "dc"

    def test_locked_model_still_present(self):
        mc = self._mc(n=50)
        assert mc["locked_model"] == LOCKED_MODEL_VERSION

    def test_champion_probs_sum_to_one(self):
        mc = self._mc(n=500)
        total = sum(v["champion"] for v in mc["team_probs"].values())
        assert abs(total - 1.0) < 0.02

    def test_reproducible(self):
        mc1 = self._mc(n=200, seed=7)
        mc2 = self._mc(n=200, seed=7)
        for team in mc1["team_probs"]:
            assert mc1["team_probs"][team]["champion"] == mc2["team_probs"][team]["champion"]

    def test_stage_probs_monotone(self):
        mc = self._mc(n=300)
        for team, probs in mc["team_probs"].items():
            stages = [probs["qualify"], probs["r16"], probs["qf"],
                      probs["sf"], probs["final"], probs["champion"]]
            for i in range(len(stages) - 1):
                assert stages[i] >= stages[i + 1] - 1e-9, (
                    f"{team}: stage[{i}]={stages[i]:.4f} < stage[{i+1}]={stages[i+1]:.4f}"
                )

    def test_all_48_teams_have_probs(self):
        mc = self._mc(n=50)
        all_teams = {t for members in WC2026_GROUPS.values() for t in members}
        assert set(mc["team_probs"].keys()) == all_teams


# ── predict_grid on real (synthetic) DC model ─────────────────────────────────

class TestPredictGrid:
    """Verify DixonColesRatings.predict_grid() using a tiny synthetic dataset."""

    @pytest.fixture(scope="class")
    def fitted_dc(self):
        from oracle.ratings.dixon_coles import DixonColesRatings
        import numpy as np

        rng = np.random.default_rng(0)
        teams = ["france", "germany", "spain", "brazil", "argentina"]
        home_list, away_list, gh, ga = [], [], [], []
        for _ in range(300):
            h, a = rng.choice(teams, size=2, replace=False)
            home_list.append(h)
            away_list.append(a)
            gh.append(int(rng.poisson(1.4)))
            ga.append(int(rng.poisson(1.1)))

        import polars as pl
        from datetime import date, timedelta
        base = date(2020, 1, 1)
        records = [
            {"date": base + timedelta(days=i), "home_team": h, "away_team": a,
             "home_score": g_h, "away_score": g_a}
            for i, (h, a, g_h, g_a) in enumerate(zip(home_list, away_list, gh, ga))
        ]
        df = pl.DataFrame(records)
        dc = DixonColesRatings()
        dc.fit(df)
        return dc

    def test_grid_shape(self, fitted_dc):
        grid = fitted_dc.predict_grid("france", "germany", neutral=True)
        assert grid.grid.shape == (10, 10)

    def test_grid_sums_to_one(self, fitted_dc):
        grid = fitted_dc.predict_grid("france", "germany", neutral=True)
        assert abs(grid.grid.sum() - 1.0) < 1e-5

    def test_grid_non_negative(self, fitted_dc):
        grid = fitted_dc.predict_grid("france", "germany", neutral=True)
        assert grid.grid.min() >= -1e-9

    def test_grid_has_goal_expectations(self, fitted_dc):
        grid = fitted_dc.predict_grid("france", "germany", neutral=True)
        assert 0.1 < grid.home_goal_expectation < 10.0
        assert 0.1 < grid.away_goal_expectation < 10.0

    def test_1x2_consistent_with_predict(self, fitted_dc):
        """predict_grid() 1X2 should match predict() 1X2."""
        grid_obj = fitted_dc.predict_grid("france", "germany", neutral=True)
        h_g, d_g, a_g = grid_obj.home_draw_away
        probs = fitted_dc.predict("france", "germany", neutral=True)
        assert abs(probs["home"] - h_g) < 1e-6
        assert abs(probs["draw"] - d_g) < 1e-6
        assert abs(probs["away"] - a_g) < 1e-6

    def test_neutral_flips_symmetry(self, fitted_dc):
        """neutral=True should make france-germany ≈ germany-france probabilities."""
        fg = fitted_dc.predict_grid("france", "germany", neutral=True)
        gf = fitted_dc.predict_grid("germany", "france", neutral=True)
        # Home-win prob of fg ≈ away-win prob of gf (mirrored)
        assert abs(fg.home_draw_away[0] - gf.home_draw_away[2]) < 0.05
