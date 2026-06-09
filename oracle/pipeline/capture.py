"""
Scheduled market capture pipeline.

Run locally with `make capture-odds` for a dry-run that uses the dummy
provider (no network calls, no API key required).  In CI/CD (GitHub Actions),
set ODDS_API_KEY as a secret and the real provider is used automatically.

Steps:
  1. Ingest latest odds snapshots (real provider if ODDS_API_KEY set, dummy
     otherwise).
  2. Compute closing-line candidate status for every ingested match.
  3. Write:
       data/artifacts/market_capture_status.json
       data/artifacts/closing_line_candidates.parquet

Usage:
    python -m oracle.pipeline.capture
    make capture-odds
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.ingest.fixtures import load_kickoff_times
from oracle.ingest.odds import ingest
from oracle.market.closing import closing_line_summary
from oracle.market.snapshot import CURATED_PATH, RAW_DIR, load_snapshots
from oracle.teams import try_resolve_team

log = logging.getLogger(__name__)
_DEFAULT_ARTIFACTS = Path("data/artifacts")


def run(
    *,
    curated_path: Path = CURATED_PATH,
    raw_dir: Path = RAW_DIR,
    output_dir: Path = _DEFAULT_ARTIFACTS,
    archive_raw: bool = True,
) -> dict:
    """Run the capture pipeline.

    Parameters
    ----------
    curated_path:  Path to the curated market_snapshots.parquet.
    raw_dir:       Directory for raw JSON archive files.
    output_dir:    Directory where artifacts are written.
    archive_raw:   Whether to archive a raw JSON copy of each ingest call.

    Returns
    -------
    The capture_status dict (same content written to market_capture_status.json).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    has_api_key = bool(os.environ.get("ODDS_API_KEY"))

    # ── 1. Ingest latest snapshots ────────────────────────────────────────────
    n_new = ingest(
        curated_path=curated_path,
        raw_dir=raw_dir,
        archive_raw=archive_raw,
    )
    log.info("Ingest complete: %d new rows.", n_new)

    # ── 2. Load full curated snapshot store ───────────────────────────────────
    snapshots = load_snapshots(curated_path)
    log.info("%d total snapshot rows.", len(snapshots))

    # ── 3. Closing-line status for each match ─────────────────────────────────
    # Build kickoff_times dict from fixture seed: {snap.match_id: kickoff_dt}.
    # Matched by canonical (home_team, away_team) pair.
    # When all kickoff_at values are null (placeholder phase) this is empty
    # and every match keeps "opening_only" / "latest_available" status.
    fixture_kickoffs = load_kickoff_times()
    kickoff_times: dict[str, datetime] = {}
    if fixture_kickoffs:
        for snap in snapshots:
            home_c = try_resolve_team(snap.home_team) or snap.home_team
            away_c = try_resolve_team(snap.away_team) or snap.away_team
            ko = fixture_kickoffs.get((home_c, away_c))
            if ko is not None:
                kickoff_times[snap.match_id] = ko
        log.info(
            "Kickoff times wired: %d / %d snapshots matched a fixture kickoff.",
            len(kickoff_times), len(snapshots),
        )
    else:
        log.info(
            "No fixture kickoff times available (all null in seed). "
            "Closing-line status will remain opening_only / latest_available."
        )

    summary_rows = closing_line_summary(snapshots, kickoff_times=kickoff_times or None)

    # ── 4. Write closing_line_candidates.parquet ──────────────────────────────
    cand_path = output_dir / "closing_line_candidates.parquet"
    if summary_rows:
        pl.DataFrame(summary_rows).write_parquet(cand_path)
        log.info("Wrote %s  (%d rows)", cand_path, len(summary_rows))
    else:
        log.info("No snapshots — closing_line_candidates.parquet not written.")

    # ── 5. Build and write market_capture_status.json ─────────────────────────
    status_counts = Counter(r["status"] for r in summary_rows)
    capture_status: dict = {
        "generated_at":      datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "has_real_api_key":  has_api_key,
        "n_new_rows":        n_new,
        "n_total_snapshots": len(snapshots),
        "n_matches":         len(summary_rows),
        "by_status": {
            "no_market_data":    status_counts.get("no_market_data", 0),
            "opening_only":      status_counts.get("opening_only", 0),
            "latest_available":  status_counts.get("latest_available", 0),
            "closing_candidate": status_counts.get("closing_candidate", 0),
            "closing_locked":    status_counts.get("closing_locked", 0),
        },
        "n_closing_locked":  status_counts.get("closing_locked", 0),
        "note": (
            "closing_locked: kickoff has passed and the latest snapshot is the "
            "closing line.  True CLV can only be computed for closing_locked "
            "matches.  All other statuses reflect pre-kickoff snapshot movement."
        ),
    }
    status_path = output_dir / "market_capture_status.json"
    status_path.write_text(json.dumps(capture_status, indent=2))
    log.info("Wrote %s", status_path)

    # ── Console summary ───────────────────────────────────────────────────────
    log.info(
        "\nCapture summary:\n"
        "  API key present : %s\n"
        "  New rows        : %d\n"
        "  Total snapshots : %d\n"
        "  Matches tracked : %d",
        "yes" if has_api_key else "no (dummy provider used)",
        n_new,
        len(snapshots),
        len(summary_rows),
    )
    for status, count in sorted(status_counts.items()):
        log.info("    %-22s %d", status + ":", count)
    if not has_api_key:
        log.info(
            "  Set ODDS_API_KEY to capture real market data. "
            "Dummy provider used for this dry-run."
        )

    return capture_status


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run()
