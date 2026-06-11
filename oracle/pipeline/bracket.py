"""
Week 21 — Knockout bracket generation pipeline.

Builds the official FIFA 2026 R32 bracket from current group standings,
computes path difficulty for each team, and projects knockout round
win probabilities using Elo ratings.

Artifacts written:
  data/artifacts/best_thirds.json          — ranked third-place teams + selection
  data/artifacts/bracket_structure.json    — full static bracket (all rounds)
  data/artifacts/bracket_paths.json        — path difficulty per team
  data/artifacts/knockout_projection.json  — R32 win-probability projection

Usage:
    python3 -m oracle.pipeline.bracket
    make bracket
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ARTIFACTS = Path("data/artifacts")
_LOG = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read_json(path: Path, fallback: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        _LOG.debug("File not found: %s", path)
        return fallback if fallback is not None else {}
    except Exception as exc:
        _LOG.warning("Could not read %s: %s", path, exc)
        return fallback if fallback is not None else {}


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str))
    _LOG.debug("  wrote %s  (%d bytes)", path.name, path.stat().st_size)


def _load_group_standings(artifacts: Path) -> dict[str, list[dict]]:
    """Load group_standings.json and reshape to {group: [rows]}."""
    raw: list[dict] = _read_json(artifacts / "group_standings.json", [])
    by_group: dict[str, list[dict]] = {}
    for row in raw:
        g = row.get("group", "?")
        by_group.setdefault(g, []).append(row)
    # Sort by rank within each group
    for g in by_group:
        by_group[g].sort(key=lambda r: r.get("rank", 99))
    return by_group


def _build_elo_ratings_dict(artifacts: Path) -> dict[str, float]:
    """Return {team_id: elo_value} by loading and fitting EloRatings.

    Falls back to an empty dict if data is unavailable, in which case
    path difficulty Elo values will all be 0.0.
    """
    try:
        import polars as pl
        from oracle.ratings.elo import EloRatings
        from oracle.ingest.results import load_results

        df = load_results()
        elo = EloRatings()
        elo.fit(df)

        ratings_df = elo.ratings_dataframe()
        return {
            row["team"]: row["elo"]
            for row in ratings_df.iter_rows(named=True)
            if row.get("team") and row.get("elo") is not None
        }
    except Exception as exc:
        _LOG.warning("Could not build Elo ratings dict: %s", exc)
        return {}


def _predict_ko_win_prob(elo_ratings: dict[str, float], home: str, away: str) -> float:
    """Compute knockout win probability for home vs away using Elo delta.

    Uses a simplified logistic model based on Elo difference.
    In knockout matches there are no draws (resolved via AET/penalties).
    """
    elo_home = elo_ratings.get(home, 1500.0)
    elo_away = elo_ratings.get(away, 1500.0)
    # Standard Elo expected score; treat draw prob as 5% split equally
    # E = 1 / (1 + 10^((away_elo - home_elo) / 400))
    diff = elo_home - elo_away
    expected = 1.0 / (1.0 + 10 ** (-diff / 400.0))
    # Knockout: distribute draw probability (flat ~5%) proportionally
    draw_prob = 0.05
    home_win = expected * (1 - draw_prob)
    away_win = (1 - expected) * (1 - draw_prob)
    p_home_ko = home_win / (home_win + away_win) if (home_win + away_win) > 0 else 0.5
    return round(p_home_ko, 6)


# ── Main pipeline ─────────────────────────────────────────────────────────────


def run(artifacts_dir: Path = _ARTIFACTS) -> dict[str, Any]:
    """Run the bracket generation pipeline.

    Returns a summary dict with artifact counts.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    from oracle.bracket.builder import build_bracket
    from oracle.bracket.third_place import rank_third_place_teams, select_best_thirds
    from oracle.bracket.paths import compute_path_difficulty

    # ── Step 1: Load group standings ──────────────────────────────────────────
    group_standings = _load_group_standings(artifacts_dir)
    n_groups = len(group_standings)
    _LOG.info("  Loaded standings for %d groups", n_groups)

    if n_groups == 0:
        _LOG.warning(
            "No group standings found in %s. "
            "Run the tournament_state pipeline first.",
            artifacts_dir,
        )

    # ── Step 2: Rank all 12 third-place teams ────────────────────────────────
    all_thirds = rank_third_place_teams(group_standings)
    best_thirds = all_thirds[:8]

    best_thirds_artifact = {
        "generated_at":    ts,
        "n_groups":        n_groups,
        "n_thirds_ranked": len(all_thirds),
        "n_qualifying":    len(best_thirds),
        "all_thirds":      [
            {
                "rank":      i + 1,
                "team":      r.get("team"),
                "group":     r.get("group"),
                "points":    r.get("points", 0),
                "gd":        r.get("gd", 0),
                "gf":        r.get("gf", 0),
                "qualifies": i < len(best_thirds),
            }
            for i, r in enumerate(all_thirds)
        ],
        "note": (
            "Ranked by points → goal difference → goals for → fair play → alphabetical. "
            "Top 8 qualify for the knockout round."
        ),
    }
    _write_json(artifacts_dir / "best_thirds.json", best_thirds_artifact)

    # ── Step 3: Build bracket structure ──────────────────────────────────────
    bracket = build_bracket(group_standings, best_thirds, generated_at=ts)
    bracket_structure = bracket.to_dict()
    _write_json(artifacts_dir / "bracket_structure.json", bracket_structure)

    # ── Step 4: Load Elo ratings for path difficulty ──────────────────────────
    elo_ratings = _build_elo_ratings_dict(artifacts_dir)
    _LOG.info("  Elo ratings available for %d teams", len(elo_ratings))

    # ── Step 5: Compute path difficulty ──────────────────────────────────────
    path_entries = compute_path_difficulty(bracket, elo_ratings)
    bracket_paths_artifact = {
        "generated_at":   ts,
        "n_teams":        len(path_entries),
        "disclaimer":     (
            "Expected opponents are computed using the highest-Elo team in each "
            "bracket arm (greedy approximation). Actual opponents depend on match results."
        ),
        "paths": [e.to_dict() for e in path_entries],
    }
    _write_json(artifacts_dir / "bracket_paths.json", bracket_paths_artifact)

    # ── Step 6: R32 knockout projection ──────────────────────────────────────
    r32_matches = bracket.round_of_32.matches
    projection_matches = []
    for m in r32_matches:
        if m.team_a and m.team_b:
            p_a = _predict_ko_win_prob(elo_ratings, m.team_a.team, m.team_b.team)
            projected_winner = m.team_a.team if p_a >= 0.5 else m.team_b.team
            projection_matches.append({
                "match_id":      m.match_id,
                "team_a":        m.team_a.team,
                "team_b":        m.team_b.team,
                "slot_a":        m.slot_a,
                "slot_b":        m.slot_b,
                "p_a_wins":      p_a,
                "p_b_wins":      round(1.0 - p_a, 6),
                "projected_winner": projected_winner,
            })
        else:
            projection_matches.append({
                "match_id":      m.match_id,
                "team_a":        m.team_a.team if m.team_a else None,
                "team_b":        m.team_b.team if m.team_b else None,
                "slot_a":        m.slot_a,
                "slot_b":        m.slot_b,
                "p_a_wins":      None,
                "p_b_wins":      None,
                "projected_winner": None,
            })

    knockout_projection = {
        "generated_at":  ts,
        "n_r32_matches": len(projection_matches),
        "r32_matches":   projection_matches,
        "bracket_note":  bracket.bracket_note,
        "disclaimer":    (
            "Win probabilities are Elo-based estimates for neutral venue. "
            "These are projections, not predictions of actual results."
        ),
    }
    _write_json(artifacts_dir / "knockout_projection.json", knockout_projection)

    elapsed = time.perf_counter() - t0
    summary = {
        "generated_at":       ts,
        "n_groups":           n_groups,
        "n_thirds_ranked":    len(all_thirds),
        "n_qualifying_thirds": len(best_thirds),
        "n_r32_matches":      len(r32_matches),
        "n_path_entries":     len(path_entries),
        "elapsed_seconds":    round(elapsed, 3),
    }
    _LOG.info(
        "  Bracket generated: %d groups, %d best-thirds, %d R32 matches (%.2fs)",
        n_groups, len(best_thirds), len(r32_matches), elapsed,
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = run()
    print(json.dumps(result, indent=2))
