"""
Week 13 tournament state pipeline.

Builds a result-aware tournament state snapshot by combining:
  - Official fixtures (data/seed/wc2026_fixtures.json)
  - Known results  (data/seed/wc2026_results.json)
  - Current group standings
  - Result-conditioned Monte Carlo probabilities (10k sims)

Artifacts written:
  data/artifacts/match_results.parquet            all ingested results
  data/artifacts/match_results_summary.json       result counts by group
  data/artifacts/group_standings.parquet          live standings for all groups
  data/artifacts/group_standings.json             same as JSON array
  data/artifacts/qualification_probs.parquet      per-team stage probabilities
  data/artifacts/qualification_probs.json         same as JSON array
  data/artifacts/tournament_state_summary.json    snapshot metadata

Usage:
    python -m oracle.pipeline.state
    make tournament-state
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path

import polars as pl

from oracle.ingest.results import load_results
from oracle.ingest.results_2026 import ingest_results_2026
from oracle.ratings.dixon_coles import DixonColesRatings
from oracle.ratings.dixon_coles import MODEL_VERSION as DC_MODEL_VERSION
from oracle.ratings.elo import EloRatings
from oracle.sim.groups import load_groups
from oracle.sim.tournament import N_SIMS, monte_carlo
from oracle.state.standings import compute_standings

_ARTIFACTS = Path("data/artifacts")
_LOG = logging.getLogger(__name__)


def run(n_sims: int = N_SIMS, seed: int = 42) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    # ── Step 1: ingest 2026 results ───────────────────────────────────────────
    _LOG.info("Ingesting 2026 results …")
    result_summary = ingest_results_2026(artifacts_dir=_ARTIFACTS)
    _LOG.info(
        "  %d results total, %d finished",
        result_summary["n_results"],
        result_summary["n_finished"],
    )

    # ── Step 2: load results parquet (may be empty) ───────────────────────────
    results_df = pl.read_parquet(_ARTIFACTS / "match_results.parquet")
    finished_df = results_df.filter(pl.col("status") == "finished")

    # ── Step 3: build known_results dict for simulation ───────────────────────
    known_results: dict[tuple[str, str], tuple[int, int]] = {}
    for row in finished_df.iter_rows(named=True):
        known_results[(row["home_team"], row["away_team"])] = (
            row["home_goals"],
            row["away_goals"],
        )

    # ── Step 4: load official groups ─────────────────────────────────────────
    groups, fixture_meta = load_groups()
    _LOG.info(
        "Groups: %s  (is_official=%s, n_fixtures=%d)",
        fixture_meta.get("source"),
        fixture_meta.get("is_official"),
        fixture_meta.get("n_fixtures_loaded", 0),
    )

    # ── Step 5: compute current standings ────────────────────────────────────
    _LOG.info("Computing group standings …")
    standings_df = compute_standings(groups, results_df)
    standings_df.write_parquet(_ARTIFACTS / "group_standings.parquet")
    ((_ARTIFACTS / "group_standings.json")).write_text(
        json.dumps(standings_df.to_dicts(), indent=2)
    )
    _LOG.info("  Wrote group_standings.parquet + group_standings.json")

    # ── Step 6: train models ──────────────────────────────────────────────────
    _LOG.info("Loading historical results …")
    df = load_results()
    _LOG.info(f"  {len(df):,} matches loaded")

    elo = EloRatings()
    elo.fit(df)
    _LOG.info("Elo-full trained.")

    dc = DixonColesRatings()
    dc.fit(df)
    _LOG.info(f"Dixon-Coles trained ({DC_MODEL_VERSION}).")

    # ── Step 7: result-aware Monte Carlo ─────────────────────────────────────
    _LOG.info(
        f"Running {n_sims:,} result-aware simulations "
        f"({len(known_results)} known results locked) …"
    )
    mc = monte_carlo(
        elo,
        n_sims=n_sims,
        seed=seed,
        dc=dc,
        groups=groups,
        known_results=known_results if known_results else None,
    )
    t_sim = time.perf_counter() - t_start
    _LOG.info(f"Done in {t_sim:.1f}s.")

    # ── Step 8: write qualification_probs ─────────────────────────────────────
    team_probs = mc["team_probs"]
    rows = []
    for team, probs in team_probs.items():
        rows.append({
            "team":           team,
            "qualify":        round(probs["qualify"],       4),
            "qualify_top2":   round(probs["qualify_top2"],  4),
            "qualify_third":  round(probs["qualify_third"], 4),
            "r16":            round(probs["r16"],           4),
            "qf":             round(probs["qf"],            4),
            "sf":             round(probs["sf"],            4),
            "final":          round(probs["final"],         4),
            "champion":       round(probs["champion"],      4),
        })

    probs_df = pl.DataFrame(rows).sort("champion", descending=True)
    probs_df.write_parquet(_ARTIFACTS / "qualification_probs.parquet")
    ((_ARTIFACTS / "qualification_probs.json")).write_text(
        json.dumps(probs_df.to_dicts(), indent=2)
    )
    _LOG.info(f"  Wrote qualification_probs.parquet + qualification_probs.json ({len(probs_df)} teams)")

    # ── Step 9: tournament_state_summary.json ─────────────────────────────────
    ranked = sorted(team_probs.items(), key=lambda kv: kv[1]["champion"], reverse=True)
    state_summary = {
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "generated_date":    str(date.today()),
        "n_sims":            mc["n_sims"],
        "seed":              mc["seed"],
        "locked_model":      mc["locked_model"],
        "goals_model":       mc["goals_model"],
        "goals_model_version": DC_MODEL_VERSION,
        "n_known_results":   len(known_results),
        "n_finished":        result_summary["n_finished"],
        "fixture_source": {
            "source":         fixture_meta.get("source"),
            "is_official":    fixture_meta.get("is_official", False),
            "is_placeholder": fixture_meta.get("is_placeholder", True),
            "n_fixtures":     fixture_meta.get("n_fixtures_loaded", 0),
        },
        "disclaimers": {
            "bracket":        "Positional (seed 1 vs 32, …) — NOT the official FIFA R16 pairings.",
            "third_place":    "No official third-place bracket slot assignment implemented yet.",
            "host_advantage": "Host advantage not modelled (neutral=True for all matches).",
        },
        "top_champion_probs": [
            {"team": team, "champion": round(probs["champion"], 4)}
            for team, probs in ranked[:20]
        ],
    }
    ((_ARTIFACTS / "tournament_state_summary.json")).write_text(
        json.dumps(state_summary, indent=2)
    )
    _LOG.info("  Wrote tournament_state_summary.json")

    # ── Console summary ───────────────────────────────────────────────────────
    _LOG.info("\nTop 10 by champion probability (result-conditioned):")
    _LOG.info(f"{'Team':<22} {'Qualify':>8} {'R16':>7} {'QF':>7} {'SF':>7} {'Final':>7} {'Champion':>9}")
    _LOG.info("-" * 72)
    for row in probs_df.head(10).iter_rows(named=True):
        _LOG.info(
            f"{row['team']:<22} {row['qualify']:>8.1%} {row['r16']:>7.1%} "
            f"{row['qf']:>7.1%} {row['sf']:>7.1%} {row['final']:>7.1%} {row['champion']:>9.1%}"
        )


if __name__ == "__main__":
    run()
