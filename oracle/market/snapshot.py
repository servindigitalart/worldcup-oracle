"""
Append-only market snapshot persistence.

save_snapshots():
  Append new OddsSnapshot rows to a growing Parquet file.
  Existing rows (same snapshot_id) are never modified or removed.
  Duplicate snapshot_ids are deduplicated on append.

load_snapshots():
  Read all curated rows from Parquet. Returns [] if the file doesn't exist.

Raw JSON archival (archive_raw=True):
  Each call saves a timestamped JSON file to data/raw/odds/.
  Files are named YYYYMMDD_HHMMSS_<label>.json and never overwritten.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from oracle.market.schema import OddsSnapshot, df_to_snapshots, snapshots_to_df

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURATED_PATH = _REPO_ROOT / "data" / "curated" / "market_snapshots.parquet"
RAW_DIR = _REPO_ROOT / "data" / "raw" / "odds"


def save_snapshots(
    snapshots: list[OddsSnapshot],
    curated_path: Path = CURATED_PATH,
    *,
    archive_raw: bool = False,
    raw_dir: Path = RAW_DIR,
    raw_label: Optional[str] = None,
) -> int:
    """Append new snapshots to the curated Parquet store.

    Never modifies or deletes existing rows. Deduplicates by snapshot_id.

    Returns:
        Number of genuinely new rows appended.
    """
    if not snapshots:
        return 0

    new_df = snapshots_to_df(snapshots)

    import polars as pl

    if curated_path.exists():
        existing_df = pl.read_parquet(curated_path)
        existing_ids = set(existing_df["snapshot_id"].to_list())
        new_rows = new_df.filter(~pl.col("snapshot_id").is_in(existing_ids))
        if len(new_rows) == 0:
            log.info(
                "No new snapshots to append — all %d are duplicates.", len(snapshots)
            )
            return 0
        combined = pl.concat([existing_df, new_rows])
    else:
        curated_path.parent.mkdir(parents=True, exist_ok=True)
        combined = new_df
        new_rows = new_df

    combined.write_parquet(curated_path)
    n_new = len(new_rows)
    log.info("Appended %d new snapshot rows to %s.", n_new, curated_path)

    if archive_raw:
        _archive_raw_json(snapshots, raw_dir, raw_label or "snapshot")

    return n_new


def load_snapshots(path: Path = CURATED_PATH) -> list[OddsSnapshot]:
    """Load all curated OddsSnapshot rows from Parquet.

    Returns an empty list if the file does not exist.
    """
    if not path.exists():
        return []
    import polars as pl
    df = pl.read_parquet(path)
    return df_to_snapshots(df)


def _archive_raw_json(
    snapshots: list[OddsSnapshot],
    raw_dir: Path,
    label: str,
) -> Path:
    """Write snapshot rows as timestamped JSON. Never overwrites existing files."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = raw_dir / f"{ts}_{label}.json"
    counter = 1
    while path.exists():
        path = raw_dir / f"{ts}_{label}_{counter}.json"
        counter += 1
    path.write_text(json.dumps([s.to_dict() for s in snapshots], indent=2))
    log.info("Archived raw snapshot to %s.", path)
    return path
