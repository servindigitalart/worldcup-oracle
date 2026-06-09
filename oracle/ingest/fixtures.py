"""
Ingest WC 2026 fixtures from the canonical seed file into DuckDB.

Seed file: data/seed/wc2026_fixtures.json
  - 72 group-stage fixtures derived from the placeholder group draw.
  - All rows have is_placeholder=true until official FIFA data is added.
  - Kickoff times are null in the placeholder; update them when available.

Schema validated on load:
  - Required fields: match_id, stage, group, home_team, away_team,
    kickoff_at, venue, city, host_country, source, is_placeholder
  - All team IDs resolved through oracle.teams (raises on unknown team)
  - Exactly 12 groups for a complete group-stage set
  - Exactly 4 teams per group
  - Exactly 72 group-stage fixtures (when complete)
  - No duplicate match_id values

Usage:
    python -m oracle.ingest.fixtures
    make ingest-fixtures
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

import polars as pl

from oracle.db import get_conn
from oracle.teams import resolve_team

log = logging.getLogger(__name__)

SEED_PATH = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_fixtures.json"

_REQUIRED_FIELDS = {
    "match_id", "stage", "group", "home_team", "away_team",
    "kickoff_at", "venue", "city", "host_country", "source", "is_placeholder",
}

_EXPECTED_GROUP_COUNT   = 12
_EXPECTED_TEAMS_PER_GROUP = 4
_EXPECTED_GROUP_FIXTURES  = 72  # C(4,2) × 12 groups


class FixtureValidationError(ValueError):
    """Raised when the fixture seed file fails structural validation."""


def load_fixtures(path: Path = SEED_PATH) -> pl.DataFrame:
    """Read and validate the fixture seed file.

    Returns a Polars DataFrame ready for DuckDB insertion.
    Raises FixtureValidationError on any structural problem.
    Raises KeyError (from resolve_team) on unknown team IDs.
    """
    with path.open() as fh:
        data = json.load(fh)

    raw: list[dict] = data.get("fixtures", [])
    if not raw:
        raise FixtureValidationError(f"No fixtures found in {path}")

    # ── Field presence ────────────────────────────────────────────────────────
    for i, fix in enumerate(raw):
        missing = _REQUIRED_FIELDS - fix.keys()
        if missing:
            raise FixtureValidationError(
                f"Fixture at index {i} (match_id={fix.get('match_id', '?')}) "
                f"is missing required fields: {sorted(missing)}"
            )

    # ── Duplicate match_id ────────────────────────────────────────────────────
    seen_ids: set[str] = set()
    for fix in raw:
        mid = fix["match_id"]
        if mid in seen_ids:
            raise FixtureValidationError(f"Duplicate match_id: {mid!r}")
        seen_ids.add(mid)

    # ── Team resolution (raises KeyError on unknown team) ─────────────────────
    for fix in raw:
        for field in ("home_team", "away_team"):
            raw_id = fix[field]
            try:
                resolved = resolve_team(raw_id)
            except KeyError:
                raise KeyError(
                    f"match_id={fix['match_id']!r}: unresolved team {field}={raw_id!r}. "
                    "Add it to oracle/teams.py CANONICAL_TEAMS or _ALIAS_MAP."
                )
            if resolved != raw_id:
                log.warning(
                    "match_id=%s: %s %r resolved to canonical %r",
                    fix["match_id"], field, raw_id, resolved,
                )
                fix[field] = resolved

    # ── Group-stage structural validation ─────────────────────────────────────
    group_fixtures = [f for f in raw if f["stage"] == "group"]
    if group_fixtures:
        # Count teams per group
        teams_by_group: dict[str, set[str]] = defaultdict(set)
        for fix in group_fixtures:
            g = fix["group"]
            teams_by_group[g].add(fix["home_team"])
            teams_by_group[g].add(fix["away_team"])

        n_groups = len(teams_by_group)
        bad_groups = {g: len(t) for g, t in teams_by_group.items() if len(t) != _EXPECTED_TEAMS_PER_GROUP}

        # Only enforce the full structural rules when fixture set looks complete
        if len(group_fixtures) == _EXPECTED_GROUP_FIXTURES:
            if n_groups != _EXPECTED_GROUP_COUNT:
                raise FixtureValidationError(
                    f"Expected {_EXPECTED_GROUP_COUNT} groups, found {n_groups}."
                )
            if bad_groups:
                raise FixtureValidationError(
                    f"Groups with wrong team count (expected {_EXPECTED_TEAMS_PER_GROUP}): {bad_groups}"
                )
            all_group_teams = [t for teams in teams_by_group.values() for t in teams]
            if len(set(all_group_teams)) != len(all_group_teams):
                raise FixtureValidationError("Duplicate team appears in more than one group.")
        else:
            log.warning(
                "Fixture set is incomplete: %d group-stage rows (expected %d). "
                "Structural group/team-count checks skipped.",
                len(group_fixtures), _EXPECTED_GROUP_FIXTURES,
            )

    # ── Build Polars DataFrame ─────────────────────────────────────────────────
    rows = [
        {
            "match_id":       fix["match_id"],
            "stage":          fix["stage"],
            "group_name":     fix.get("group"),       # JSON key is "group"; DB column is "group_name"
            "home_team":      fix["home_team"],
            "away_team":      fix["away_team"],
            "kickoff_at":     fix["kickoff_at"],       # None → null in DB
            "venue":          fix["venue"],
            "city":           fix["city"],
            "host_country":   fix["host_country"],
            "source":         fix["source"],
            "is_placeholder": fix["is_placeholder"],
        }
        for fix in raw
    ]
    return pl.DataFrame(rows)


def ingest_fixtures(
    db_path: Optional[str] = None,
    seed_path: Path = SEED_PATH,
) -> int:
    """Load fixture seed file → DuckDB.  Returns row count inserted.

    Drops the fixtures table and recreates it to handle schema migrations
    between weeks.  Safe to run repeatedly.
    """
    df = load_fixtures(seed_path)

    with get_conn(db_path) as conn:
        # Migration: drop legacy schema if column names have changed.
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(fixtures)").fetchall()}
        except Exception:
            cols = set()

        if "fixture_id" in cols or "match_date" in cols or "home_team_id" in cols:
            log.info("Dropping legacy fixtures table (schema migration).")
            conn.execute("DROP TABLE IF EXISTS fixtures")
            conn.execute("""
                CREATE TABLE fixtures (
                    match_id        TEXT PRIMARY KEY,
                    stage           TEXT,
                    group_name      TEXT,
                    home_team       TEXT,
                    away_team       TEXT,
                    kickoff_at      TIMESTAMP,
                    venue           TEXT,
                    city            TEXT,
                    host_country    TEXT,
                    source          TEXT,
                    is_placeholder  BOOLEAN
                )
            """)

        conn.execute("DELETE FROM fixtures")
        conn.execute("INSERT INTO fixtures SELECT * FROM df")
        count = conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]

    is_ph = df["is_placeholder"].to_list()
    n_placeholder = sum(1 for v in is_ph if v)
    n_official    = len(is_ph) - n_placeholder
    log.info(
        "Loaded %d fixtures into DuckDB  (%d placeholder, %d official).",
        count, n_placeholder, n_official,
    )
    return count


def load_kickoff_times(
    seed_path: Path = SEED_PATH,
) -> dict[tuple[str, str], datetime]:
    """Return {(home_team, away_team): kickoff_at} for fixtures with non-null kickoffs.

    Used by the capture pipeline to wire real kickoff timestamps into the
    closing-line status classifier.  Returns an empty dict when kickoff_at is
    null for all fixtures (i.e. during the placeholder phase).

    The returned dict is keyed by canonical team-ID pairs so that callers can
    match against snapshot home/away fields after running try_resolve_team().
    """
    from datetime import datetime, timezone

    if not seed_path.exists():
        log.debug("Seed file not found at %s — returning empty kickoff dict.", seed_path)
        return {}

    with seed_path.open() as fh:
        data = json.load(fh)

    result: dict[tuple[str, str], datetime] = {}
    for fix in data.get("fixtures", []):
        raw_ko = fix.get("kickoff_at")
        if raw_ko is None:
            continue
        try:
            ko_dt = datetime.fromisoformat(raw_ko.replace("Z", "+00:00"))
            if ko_dt.tzinfo is None:
                ko_dt = ko_dt.replace(tzinfo=timezone.utc)
            result[(fix["home_team"], fix["away_team"])] = ko_dt
        except (ValueError, AttributeError) as exc:
            log.warning("Could not parse kickoff_at %r for %s: %s", raw_ko, fix.get("match_id"), exc)

    log.debug("Loaded %d non-null kickoff times from %s.", len(result), seed_path)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not SEED_PATH.exists():
        log.error("Seed file not found: %s", SEED_PATH)
        raise SystemExit(1)
    n = ingest_fixtures()
    log.info("Done — %d fixtures ingested.", n)
