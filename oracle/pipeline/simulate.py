"""
Week 6 simulation pipeline.

Runs 10,000 Monte Carlo tournament simulations using:
  - Elo-full model for knockout-stage win probabilities and surrogate fallback.
  - Dixon-Coles (xi=0.0018) for group-stage scoreline sampling.

DC grids for all 72 group-stage matchups are precomputed once before the
simulation loop and reused across all runs, keeping total runtime ~20s.

Artifacts written:
  data/artifacts/sim_2026_summary.json
    n_sims, seed, locked_model, goals_model, champion win-probability
    table (top 20), and explicit disclaimer fields.

  data/artifacts/sim_2026_team_probs.parquet
    One row per team × all stage probabilities (qualify, r16, qf, sf,
    final, champion), sorted by champion probability descending.

Usage:
    python -m oracle.pipeline.simulate
    make simulate
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

import polars as pl

from oracle.ingest.results import load_results
from oracle.ratings.dixon_coles import DixonColesRatings
from oracle.ratings.dixon_coles import MODEL_VERSION as DC_MODEL_VERSION
from oracle.ratings.elo import EloRatings
from oracle.sim.tournament import N_SIMS, monte_carlo

_ARTIFACTS = Path("data/artifacts")
_LOG = logging.getLogger(__name__)


def run(n_sims: int = N_SIMS, seed: int = 42) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    _LOG.info("Loading results …")
    df = load_results()
    _LOG.info(f"  {len(df):,} matches loaded")

    # ── Elo-full (knockout win probabilities + surrogate-goal fallback) ────────
    elo = EloRatings()
    elo.fit(df)
    _LOG.info("Elo-full trained.")

    # ── Dixon-Coles (group-stage scoreline sampling) ──────────────────────────
    dc = DixonColesRatings()
    dc.fit(df)
    _LOG.info(f"Dixon-Coles trained ({DC_MODEL_VERSION}).")

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    _LOG.info(f"Running {n_sims:,} Monte Carlo simulations (seed={seed}) …")
    _LOG.info("  Group-stage scores: DC joint probability grid (precomputed, neutral venue)")
    _LOG.info("  Knockout outcomes:  Elo win probability (no goals needed)")
    mc = monte_carlo(elo, n_sims=n_sims, seed=seed, dc=dc)
    t_sim = time.perf_counter() - t_start
    _LOG.info(f"Done in {t_sim:.1f}s.")

    # ── Artifact 1: summary JSON ──────────────────────────────────────────────
    team_probs = mc["team_probs"]
    ranked = sorted(team_probs.items(), key=lambda kv: kv[1]["champion"], reverse=True)

    summary = {
        "generated_date":         str(date.today()),
        "n_sims":                  mc["n_sims"],
        "seed":                    mc["seed"],
        "locked_model":            mc["locked_model"],
        "goals_model":             mc["goals_model"],
        "goals_model_version":     DC_MODEL_VERSION,
        "goals_model_notes":       (
            "Group-stage scorelines sampled from Dixon-Coles joint probability "
            "grid (10×10, max_goals=10, xi=0.0018, neutral venue). "
            "Grids precomputed once; reused across all simulations. "
            "Knockout matches use Elo win probabilities (no scoreline needed)."
        ),
        "disclaimers": {
            "group_draw":      "Placeholder — NOT the official WC 2026 draw. Replace WC2026_GROUPS once announced.",
            "bracket":         "Positional (seed 1 vs 32, …) — NOT the official FIFA R16 pairings.",
            "third_place":     "No official third-place bracket slot assignment implemented yet.",
            "host_advantage":  "USA / Mexico / Canada host advantage not modelled (neutral=True for all matches).",
            "rating_uncertainty": "Elo ratings treated as point estimates; no uncertainty propagation.",
        },
        "top_champion_probs": [
            {"team": team, "champion": round(probs["champion"], 4)}
            for team, probs in ranked[:20]
        ],
    }

    summary_path = _ARTIFACTS / "sim_2026_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    _LOG.info(f"Wrote {summary_path}")

    # ── Artifact 2: team_probs parquet ────────────────────────────────────────
    rows = [
        {
            "team":     team,
            "qualify":  round(probs["qualify"],  4),
            "r16":      round(probs["r16"],      4),
            "qf":       round(probs["qf"],       4),
            "sf":       round(probs["sf"],       4),
            "final":    round(probs["final"],    4),
            "champion": round(probs["champion"], 4),
        }
        for team, probs in team_probs.items()
    ]
    probs_df = pl.DataFrame(rows).sort("champion", descending=True)
    probs_path = _ARTIFACTS / "sim_2026_team_probs.parquet"
    probs_df.write_parquet(probs_path)
    _LOG.info(f"Wrote {probs_path}  ({len(probs_df)} teams)")

    # ── Console summary ───────────────────────────────────────────────────────
    _LOG.info("\nTop 10 teams by champion probability:")
    _LOG.info(f"{'Team':<22} {'Qualify':>8} {'R16':>7} {'QF':>7} {'SF':>7} {'Final':>7} {'Champion':>9}")
    _LOG.info("-" * 72)
    for row in probs_df.head(10).iter_rows(named=True):
        _LOG.info(
            f"{row['team']:<22} {row['qualify']:>8.1%} {row['r16']:>7.1%} "
            f"{row['qf']:>7.1%} {row['sf']:>7.1%} {row['final']:>7.1%} {row['champion']:>9.1%}"
        )


if __name__ == "__main__":
    run()
