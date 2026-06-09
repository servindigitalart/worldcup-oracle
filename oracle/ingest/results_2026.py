"""
Ingest WC 2026 match results from the canonical seed file into DuckDB.

Seed file: data/seed/wc2026_results.json
  - Initially empty; populate as matches finish.
  - Each result references a match_id from wc2026_fixtures.json.
  - Valid statuses: scheduled, live, finished, postponed, cancelled.

Validation:
  - match_id must exist in the fixture seed.
  - home_team / away_team must match the fixture record.
  - home_goals / away_goals must be non-negative integers (required when status=finished).
  - No duplicate match_id entries in the results seed.

Usage:
    python -m oracle.ingest.results_2026
    make ingest-results-2026
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from oracle.db import get_conn

log = logging.getLogger(__name__)

RESULTS_SEED_PATH  = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_results.json"
FIXTURE_SEED_PATH  = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_fixtures.json"
ARTIFACTS_DIR      = Path(__file__).parent.parent.parent / "data" / "artifacts"

VALID_STATUSES = {"scheduled", "live", "finished", "postponed", "cancelled"}


class ResultValidationError(ValueError):
    """Raised when the results seed file fails structural validation."""


def load_results_2026(
    path: Path = RESULTS_SEED_PATH,
    fixture_path: Path = FIXTURE_SEED_PATH,
) -> pl.DataFrame:
    """Read and validate the results seed file.

    Returns a Polars DataFrame with columns:
        match_id, home_team, away_team, group, home_goals, away_goals, status

    Raises ResultValidationError on structural problems.
    Returns an empty DataFrame when results list is empty.
    """
    with path.open() as fh:
        data = json.load(fh)

    results: list[dict[str, Any]] = data.get("results", [])

    if not results:
        return pl.DataFrame(schema={
            "match_id":   pl.Utf8,
            "home_team":  pl.Utf8,
            "away_team":  pl.Utf8,
            "group":      pl.Utf8,
            "home_goals": pl.Int32,
            "away_goals": pl.Int32,
            "status":     pl.Utf8,
        })

    # Load fixture index for cross-validation
    with fixture_path.open() as fh:
        fixture_data = json.load(fh)

    fixture_index: dict[str, dict] = {
        f["match_id"]: f
        for f in fixture_data.get("fixtures", [])
    }

    seen_ids: set[str] = set()
    rows: list[dict[str, Any]] = []

    for i, r in enumerate(results):
        mid = r.get("match_id")
        if not mid:
            raise ResultValidationError(f"Result at index {i} missing match_id")

        if mid in seen_ids:
            raise ResultValidationError(f"Duplicate match_id: {mid}")
        seen_ids.add(mid)

        if mid not in fixture_index:
            raise ResultValidationError(f"match_id {mid!r} not found in fixture seed")

        fixture = fixture_index[mid]
        status = r.get("status", "finished")
        if status not in VALID_STATUSES:
            raise ResultValidationError(
                f"match_id {mid!r}: invalid status {status!r}. "
                f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )

        home_team = r.get("home_team", fixture["home_team"])
        away_team = r.get("away_team", fixture["away_team"])

        if home_team != fixture["home_team"] or away_team != fixture["away_team"]:
            raise ResultValidationError(
                f"match_id {mid!r}: teams {home_team!r} vs {away_team!r} "
                f"don't match fixture ({fixture['home_team']!r} vs {fixture['away_team']!r})"
            )

        home_goals: int | None = r.get("home_goals")
        away_goals: int | None = r.get("away_goals")

        if status == "finished":
            if home_goals is None or away_goals is None:
                raise ResultValidationError(
                    f"match_id {mid!r}: status=finished requires home_goals and away_goals"
                )
            if not isinstance(home_goals, int) or home_goals < 0:
                raise ResultValidationError(
                    f"match_id {mid!r}: home_goals must be a non-negative integer"
                )
            if not isinstance(away_goals, int) or away_goals < 0:
                raise ResultValidationError(
                    f"match_id {mid!r}: away_goals must be a non-negative integer"
                )

        rows.append({
            "match_id":   mid,
            "home_team":  home_team,
            "away_team":  away_team,
            "group":      fixture["group"],
            "home_goals": home_goals,
            "away_goals": away_goals,
            "status":     status,
        })

    return pl.DataFrame(rows, schema={
        "match_id":   pl.Utf8,
        "home_team":  pl.Utf8,
        "away_team":  pl.Utf8,
        "group":      pl.Utf8,
        "home_goals": pl.Int32,
        "away_goals": pl.Int32,
        "status":     pl.Utf8,
    })


def ingest_results_2026(
    results_path: Path = RESULTS_SEED_PATH,
    fixture_path: Path = FIXTURE_SEED_PATH,
    artifacts_dir: Path = ARTIFACTS_DIR,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Load, validate, and persist 2026 match results.

    Writes:
        data/artifacts/match_results.parquet
        data/artifacts/match_results_summary.json

    Returns summary dict.
    """
    import json as _json
    from datetime import datetime, timezone

    df = load_results_2026(results_path, fixture_path)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    df.write_parquet(artifacts_dir / "match_results.parquet")

    finished = df.filter(pl.col("status") == "finished")
    n_finished = len(finished)
    n_total    = len(df)

    by_group: dict[str, int] = {}
    if n_finished > 0:
        for row in finished.iter_rows(named=True):
            g = row["group"]
            by_group[g] = by_group.get(g, 0) + 1

    summary = {
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "n_results":     n_total,
        "n_finished":    n_finished,
        "n_live":        int((df["status"] == "live").sum()) if n_total else 0,
        "n_scheduled":   int((df["status"] == "scheduled").sum()) if n_total else 0,
        "by_group":      by_group,
    }

    (artifacts_dir / "match_results_summary.json").write_text(
        _json.dumps(summary, indent=2)
    )

    if db_path:
        _write_to_db(df, db_path)

    log.info("ingest_results_2026: %d results (%d finished)", n_total, n_finished)
    return summary


def _write_to_db(df: pl.DataFrame, db_path: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_results_2026 (
                match_id   VARCHAR PRIMARY KEY,
                home_team  VARCHAR NOT NULL,
                away_team  VARCHAR NOT NULL,
                "group"    VARCHAR NOT NULL,
                home_goals INTEGER,
                away_goals INTEGER,
                status     VARCHAR NOT NULL
            )
        """)
        conn.execute("DELETE FROM match_results_2026")
        if len(df) > 0:
            conn.execute("INSERT INTO match_results_2026 SELECT * FROM df")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = ingest_results_2026()
    print(f"Ingested {summary['n_results']} results ({summary['n_finished']} finished).")
