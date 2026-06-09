"""
Group standings engine.

compute_standings():
  Given the official group draw and a DataFrame of finished results,
  returns a Polars DataFrame of current standings for all 12 groups.

Sort order (deterministic, no randomness):
  1. Points (desc)
  2. Goal difference (desc)
  3. Goals for (desc)
  4. Canonical team ID (asc) — alphabetical tiebreaker

Status labels:
  qualified_top2  — rank 1 or 2 AND all 6 group matches are finished
  eliminated      — rank 4 AND all 6 group matches are finished
  alive           — some matches played but group is not complete
  unknown         — no matches played yet
"""
from __future__ import annotations

from typing import Any

import polars as pl

_MATCHES_PER_GROUP = 6  # C(4,2)


def compute_standings(
    groups: dict[str, list[str]],
    finished_results: pl.DataFrame,
) -> pl.DataFrame:
    """Compute group standings from known finished results.

    Args:
        groups:           {group_letter: [team_id, team_id, team_id, team_id]}
        finished_results: DataFrame with columns
                          match_id, home_team, away_team, group,
                          home_goals, away_goals, status
                          (only rows with status='finished' are used)

    Returns:
        Polars DataFrame with columns:
          group, team, played, won, drawn, lost,
          gf, ga, gd, points, rank, status_label
        Ordered by group → rank.
    """
    finished = finished_results.filter(pl.col("status") == "finished")

    rows: list[dict[str, Any]] = []

    for letter, teams in sorted(groups.items()):
        group_finished = finished.filter(pl.col("group") == letter)
        n_played_in_group = len(group_finished)

        stats: dict[str, dict[str, int]] = {
            t: {"played": 0, "won": 0, "drawn": 0, "lost": 0,
                "gf": 0, "ga": 0, "gd": 0, "points": 0}
            for t in teams
        }

        for match in group_finished.iter_rows(named=True):
            ht = match["home_team"]
            at = match["away_team"]
            hg = match["home_goals"]
            ag = match["away_goals"]

            if ht not in stats or at not in stats:
                continue

            stats[ht]["played"] += 1
            stats[at]["played"] += 1
            stats[ht]["gf"]     += hg
            stats[ht]["ga"]     += ag
            stats[ht]["gd"]     += hg - ag
            stats[at]["gf"]     += ag
            stats[at]["ga"]     += hg
            stats[at]["gd"]     += ag - hg

            if hg > ag:
                stats[ht]["won"]    += 1
                stats[ht]["points"] += 3
                stats[at]["lost"]   += 1
            elif hg == ag:
                stats[ht]["drawn"]  += 1
                stats[ht]["points"] += 1
                stats[at]["drawn"]  += 1
                stats[at]["points"] += 1
            else:
                stats[at]["won"]    += 1
                stats[at]["points"] += 3
                stats[ht]["lost"]   += 1

        sorted_teams = _sort_group(stats)

        group_complete = (n_played_in_group == _MATCHES_PER_GROUP)

        for rank, team in enumerate(sorted_teams, start=1):
            s = stats[team]
            if s["played"] == 0:
                label = "unknown"
            elif not group_complete:
                label = "alive"
            elif rank <= 2:
                label = "qualified_top2"
            elif rank == 4:
                label = "eliminated"
            else:
                label = "alive"

            rows.append({
                "group":        letter,
                "team":         team,
                "played":       s["played"],
                "won":          s["won"],
                "drawn":        s["drawn"],
                "lost":         s["lost"],
                "gf":           s["gf"],
                "ga":           s["ga"],
                "gd":           s["gd"],
                "points":       s["points"],
                "rank":         rank,
                "status_label": label,
            })

    return pl.DataFrame(rows, schema={
        "group":        pl.Utf8,
        "team":         pl.Utf8,
        "played":       pl.Int32,
        "won":          pl.Int32,
        "drawn":        pl.Int32,
        "lost":         pl.Int32,
        "gf":           pl.Int32,
        "ga":           pl.Int32,
        "gd":           pl.Int32,
        "points":       pl.Int32,
        "rank":         pl.Int32,
        "status_label": pl.Utf8,
    })


def _sort_group(stats: dict[str, dict[str, int]]) -> list[str]:
    """Sort teams deterministically: points→GD→GF→team_id (alphabetical)."""
    return sorted(
        stats.keys(),
        key=lambda t: (
            -stats[t]["points"],
            -stats[t]["gd"],
            -stats[t]["gf"],
            t,  # alphabetical tiebreaker (canonical team ID)
        ),
    )
