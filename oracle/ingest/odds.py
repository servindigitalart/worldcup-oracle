"""
Market odds snapshot ingestion.

Fetches 1X2 odds from a configured provider and writes append-only to:
  data/curated/market_snapshots.parquet  — normalised, de-vigged rows
  data/raw/odds/<timestamp>_<source>.json  — raw archive (optional)

Provider selection:
  - ODDS_API_KEY set → TheOddsAPIProvider (real data).
  - Otherwise       → DummyOddsProvider (placeholder for dry-runs and CI).

Usage:
    python -m oracle.ingest.odds
    make ingest-odds
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from oracle.market.provider import DummyOddsProvider, OddsAPIKeyMissing, TheOddsAPIProvider
from oracle.market.snapshot import CURATED_PATH, RAW_DIR, save_snapshots

log = logging.getLogger(__name__)


def ingest(
    *,
    curated_path: Path = CURATED_PATH,
    raw_dir: Path = RAW_DIR,
    archive_raw: bool = True,
    bookmakers: Optional[list[str]] = None,
) -> int:
    """Fetch and persist the latest 1X2 odds snapshots.

    Falls back to DummyOddsProvider if ODDS_API_KEY is missing.

    Returns:
        Number of new rows appended to the curated Parquet store.
    """
    try:
        provider = TheOddsAPIProvider()
        source_label = "the-odds-api"
    except OddsAPIKeyMissing:
        log.info(
            "ODDS_API_KEY not set — using DummyOddsProvider. "
            "Set ODDS_API_KEY to fetch real market data."
        )
        provider = DummyOddsProvider()
        source_label = "dummy"

    snapshots = provider.fetch_upcoming_1x2(bookmakers=bookmakers)
    if not snapshots:
        log.warning("Provider returned 0 snapshots.")
        return 0

    n_new = save_snapshots(
        snapshots,
        curated_path=curated_path,
        archive_raw=archive_raw,
        raw_dir=raw_dir,
        raw_label=source_label,
    )
    log.info("Ingest complete: %d new rows from '%s'.", n_new, source_label)
    return n_new


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ingest()
