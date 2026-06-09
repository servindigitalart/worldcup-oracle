"""
Ingestion: martj42/international_results

Source: https://github.com/martj42/international_results
CSV columns: date, home_team, away_team, home_score, away_score,
             tournament, city, country, neutral

Run:
    python -m oracle.ingest.results     # prints unresolved team names
    make ingest-results

Notes on this implementation (Week 2):
  - SSL: uses certifi for macOS compatibility (Python ships without updated
    root certificates on macOS; certifi provides them).
  - neutral column: the CSV uses "TRUE"/"FALSE" strings; we cast to bool.
  - INSERT uses explicit column list to avoid position-dependent mismatches.
  - Unresolved team names are printed to stderr so the alias table can be
    extended incrementally.

TODO Week 3:
  - Incremental update: only append rows newer than MAX(date) in DuckDB.
  - HTTP retry/backoff with exponential back-off (tenacity or manual).
  - ETag / Last-Modified caching to avoid redundant downloads.
"""
from __future__ import annotations

import logging
import ssl
import urllib.request
from pathlib import Path
from typing import Optional

import certifi
import polars as pl

from oracle.db import get_conn
from oracle.teams import try_resolve_team

log = logging.getLogger(__name__)

MARTJ42_URL = (
    "https://raw.githubusercontent.com/martj42/international_results"
    "/master/results.csv"
)
RAW_DIR  = Path(__file__).parent.parent.parent / "data" / "raw" / "results"
RAW_PATH = RAW_DIR / "results.csv"

_INSERT_COLS = (
    "date, home_team, away_team, home_score, away_score, "
    "tournament, city, country, neutral, home_team_id, away_team_id"
)


def _ssl_context() -> ssl.SSLContext:
    """Return an SSL context that works reliably on macOS (uses certifi roots)."""
    return ssl.create_default_context(cafile=certifi.where())


def download_results(url: str = MARTJ42_URL, dest: Path = RAW_PATH) -> Path:
    """Download the martj42 results CSV to *dest*. Returns the local path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s → %s", url, dest)
    req = urllib.request.Request(url, headers={"User-Agent": "worldcup-oracle/0.2"})
    with urllib.request.urlopen(req, context=_ssl_context(), timeout=30) as resp:
        dest.write_bytes(resp.read())
    log.info("Downloaded %.1f KB", dest.stat().st_size / 1024)
    return dest


def load_results(path: Path = RAW_PATH) -> pl.DataFrame:
    """Read the raw CSV, cast types, and resolve team aliases to canonical IDs.

    Returns a DataFrame with all martj42 columns plus home_team_id / away_team_id.
    Unresolved team names are logged as warnings (extend oracle/teams.py to fix).
    """
    df = pl.read_csv(path, try_parse_dates=True, null_values=["", "NA", "N/A"])

    # Cast neutral: martj42 uses "TRUE" / "FALSE" strings
    if df["neutral"].dtype == pl.Utf8:
        df = df.with_columns(
            (pl.col("neutral").str.to_uppercase() == "TRUE").alias("neutral")
        )

    # Resolve aliases
    home_ids: list[Optional[str]] = []
    away_ids:  list[Optional[str]] = []
    unresolved: set[str] = set()

    for row in df.iter_rows(named=True):
        hid = try_resolve_team(row["home_team"])
        aid = try_resolve_team(row["away_team"])
        if hid is None:
            unresolved.add(row["home_team"])
        if aid is None:
            unresolved.add(row["away_team"])
        home_ids.append(hid)
        away_ids.append(aid)

    if unresolved:
        log.warning(
            "%d unresolved team names — add aliases to oracle/teams.py:\n  %s%s",
            len(unresolved),
            ", ".join(sorted(unresolved)[:30]),
            f"  … and {len(unresolved) - 30} more" if len(unresolved) > 30 else "",
        )

    return df.with_columns([
        pl.Series("home_team_id", home_ids, dtype=pl.Utf8),
        pl.Series("away_team_id", away_ids, dtype=pl.Utf8),
    ])


def report_unresolved(df: pl.DataFrame) -> None:
    """Print teams that have null canonical IDs to stdout (for alias-table review)."""
    unresolved = (
        df.filter(pl.col("home_team_id").is_null())
        .select("home_team").rename({"home_team": "team"})
        .vstack(
            df.filter(pl.col("away_team_id").is_null())
            .select("away_team").rename({"away_team": "team"})
        )
        .unique()
        .sort("team")
    )
    print(f"\nUnresolved team names ({len(unresolved)} unique):")
    for row in unresolved.iter_rows(named=True):
        print(f"  {row['team']!r}")


def ingest_results(
    db_path: Optional[str] = None,
    csv_path: Path = RAW_PATH,
    download: bool = False,
) -> int:
    """Full pipeline: (optionally download →) load CSV → write to DuckDB.

    Returns the number of rows in the results table after load.
    """
    if download or not csv_path.exists():
        download_results(dest=csv_path)

    df = load_results(csv_path)

    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM results")
        conn.execute(
            f"INSERT INTO results ({_INSERT_COLS}) "
            f"SELECT {_INSERT_COLS} FROM df"
        )
        count = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]

    log.info("Ingested %d rows into results table", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df = load_results() if RAW_PATH.exists() else load_results(download_results())
    report_unresolved(df)
    print(f"\nTotal rows: {len(df):,}")
    print(f"Date range: {df['date'].min()} → {df['date'].max()}")
    resolved = df.filter(pl.col("home_team_id").is_not_null()).height
    print(f"Rows with resolved home team: {resolved:,} / {len(df):,}")
