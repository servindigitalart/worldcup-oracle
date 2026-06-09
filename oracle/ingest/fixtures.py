"""
Ingestion skeleton: 2026 FIFA World Cup fixtures.

Source (placeholder): a hand-curated JSON file in data/raw/fixtures/.
  The official group draw happened in December 2024; venue schedule is
  published by FIFA. We store it as a simple JSON and load into DuckDB.

TODO Week 2:
  - Replace placeholder JSON with real fixture data (football-data.org
    or a manually curated CSV once the full schedule is confirmed).
  - Map team names through oracle.teams.resolve_team().
  - Add venue / host-country metadata (important for host advantage modeling).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import polars as pl

from oracle.db import get_conn

log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "fixtures"
PLACEHOLDER_PATH = RAW_DIR / "wc2026_fixtures_placeholder.json"


def load_fixtures(path: Path = PLACEHOLDER_PATH) -> pl.DataFrame:
    """Read fixtures JSON into a Polars DataFrame."""
    with path.open() as fh:
        data = json.load(fh)
    return pl.DataFrame(data["fixtures"])


def ingest_fixtures(
    db_path: Optional[str] = None,
    json_path: Path = PLACEHOLDER_PATH,
) -> int:
    """Load fixtures JSON → DuckDB. Returns row count."""
    df = load_fixtures(json_path)

    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM fixtures")
        conn.execute("INSERT INTO fixtures SELECT * FROM df")
        count = conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]

    log.info("Loaded %d fixtures into DuckDB", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not PLACEHOLDER_PATH.exists():
        log.warning("Placeholder fixtures file not found: %s", PLACEHOLDER_PATH)
        log.warning("Run: python -m oracle.ingest.fixtures after creating it.")
    else:
        ingest_fixtures()
