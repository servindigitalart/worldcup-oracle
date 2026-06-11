"""
Closing lines pipeline — Week 20.

Reads market_snapshots.parquet, builds LifecycleEntry for every tracked match,
and writes two artifacts:

  data/artifacts/closing_lines.parquet     — one row per match, checkpoints flattened
  data/artifacts/closing_line_summary.json — aggregate counts by closing_status

Usage:
    python3 -m oracle.pipeline.closing_lines
    make closing-lines
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl

from oracle.market.lifecycle import LifecycleEntry, build_all_lifecycles
from oracle.market.movement_analysis import build_market_movement
from oracle.market.schema import OddsSnapshot, df_to_snapshots
from oracle.market.validation import validate_all

log = logging.getLogger(__name__)

_ARTIFACTS = Path("data/artifacts")

_CLOSING_LINES_SCHEMA: dict[str, pl.PolarsDataType] = {
    "match_id":                    pl.Utf8,
    "home_team":                   pl.Utf8,
    "away_team":                   pl.Utf8,
    "kickoff_at":                  pl.Utf8,
    "n_pre_kickoff_snapshots":     pl.Int32,
    "closing_status":              pl.Utf8,
    # Opening checkpoint
    "opening_captured_at":         pl.Utf8,
    "opening_home_prob":           pl.Float64,
    "opening_draw_prob":           pl.Float64,
    "opening_away_prob":           pl.Float64,
    # 24h checkpoint
    "h24_captured_at":             pl.Utf8,
    "h24_home_prob":               pl.Float64,
    "h24_draw_prob":               pl.Float64,
    "h24_away_prob":               pl.Float64,
    # 12h checkpoint
    "h12_captured_at":             pl.Utf8,
    "h12_home_prob":               pl.Float64,
    "h12_draw_prob":               pl.Float64,
    "h12_away_prob":               pl.Float64,
    # 6h checkpoint
    "h6_captured_at":              pl.Utf8,
    "h6_home_prob":                pl.Float64,
    "h6_draw_prob":                pl.Float64,
    "h6_away_prob":                pl.Float64,
    # 1h checkpoint
    "h1_captured_at":              pl.Utf8,
    "h1_home_prob":                pl.Float64,
    "h1_draw_prob":                pl.Float64,
    "h1_away_prob":                pl.Float64,
    # Closing checkpoint
    "closing_captured_at":         pl.Utf8,
    "closing_home_prob":           pl.Float64,
    "closing_draw_prob":           pl.Float64,
    "closing_away_prob":           pl.Float64,
    "generated_at":                pl.Utf8,
}


def _entry_to_row(entry: LifecycleEntry) -> dict:
    """Flatten a LifecycleEntry into a single parquet-compatible row dict."""

    def _cp(cp, field: str):
        return getattr(cp, field) if cp is not None else None

    return {
        "match_id":                entry.match_id,
        "home_team":               entry.home_team,
        "away_team":               entry.away_team,
        "kickoff_at":              entry.kickoff_at,
        "n_pre_kickoff_snapshots": entry.n_pre_kickoff_snapshots,
        "closing_status":          entry.closing_status,
        "opening_captured_at":     _cp(entry.opening, "captured_at"),
        "opening_home_prob":       _cp(entry.opening, "home_prob"),
        "opening_draw_prob":       _cp(entry.opening, "draw_prob"),
        "opening_away_prob":       _cp(entry.opening, "away_prob"),
        "h24_captured_at":         _cp(entry.h24, "captured_at"),
        "h24_home_prob":           _cp(entry.h24, "home_prob"),
        "h24_draw_prob":           _cp(entry.h24, "draw_prob"),
        "h24_away_prob":           _cp(entry.h24, "away_prob"),
        "h12_captured_at":         _cp(entry.h12, "captured_at"),
        "h12_home_prob":           _cp(entry.h12, "home_prob"),
        "h12_draw_prob":           _cp(entry.h12, "draw_prob"),
        "h12_away_prob":           _cp(entry.h12, "away_prob"),
        "h6_captured_at":          _cp(entry.h6, "captured_at"),
        "h6_home_prob":            _cp(entry.h6, "home_prob"),
        "h6_draw_prob":            _cp(entry.h6, "draw_prob"),
        "h6_away_prob":            _cp(entry.h6, "away_prob"),
        "h1_captured_at":          _cp(entry.h1, "captured_at"),
        "h1_home_prob":            _cp(entry.h1, "home_prob"),
        "h1_draw_prob":            _cp(entry.h1, "draw_prob"),
        "h1_away_prob":            _cp(entry.h1, "away_prob"),
        "closing_captured_at":     _cp(entry.closing, "captured_at"),
        "closing_home_prob":       _cp(entry.closing, "home_prob"),
        "closing_draw_prob":       _cp(entry.closing, "draw_prob"),
        "closing_away_prob":       _cp(entry.closing, "away_prob"),
        "generated_at":            entry.generated_at,
    }


def _load_snapshots(artifacts_dir: Path) -> list[OddsSnapshot]:
    snap_path = artifacts_dir / "market_snapshots.parquet"
    if not snap_path.exists():
        log.info("closing_lines: no market_snapshots.parquet — no lifecycle data")
        return []
    try:
        df = pl.read_parquet(snap_path)
        return df_to_snapshots(df)
    except Exception as exc:
        log.warning("closing_lines: could not load snapshots: %s", exc)
        return []


def _load_fixture_kickoffs(artifacts_dir: Path) -> dict[str, Optional[datetime]]:
    """Load {match_id: kickoff_at} from blended_predictions.parquet (best available)."""
    kickoff_map: dict[str, Optional[datetime]] = {}

    # Try recommendations.parquet which has kickoff_at
    for parquet_name in ("recommendations.parquet", "blended_predictions.parquet"):
        p = artifacts_dir / parquet_name
        if not p.exists():
            continue
        try:
            df = pl.read_parquet(p)
            if "kickoff_at" not in df.columns:
                continue
            for row in df.select(["match_id", "home_team", "away_team", "kickoff_at"]).iter_rows(named=True):
                mid = row["match_id"]
                if mid in kickoff_map:
                    continue
                ko = row.get("kickoff_at")
                if ko and isinstance(ko, str):
                    try:
                        kickoff_map[mid] = datetime.fromisoformat(ko.replace("Z", "+00:00"))
                    except ValueError:
                        kickoff_map[mid] = None
                else:
                    kickoff_map[mid] = None
            break
        except Exception as exc:
            log.warning("closing_lines: could not read %s: %s", parquet_name, exc)

    return kickoff_map


def _load_match_meta(artifacts_dir: Path) -> dict[str, dict]:
    """Load {match_id: {home_team, away_team, kickoff_at}} from available artifacts."""
    meta: dict[str, dict] = {}
    kickoffs = _load_fixture_kickoffs(artifacts_dir)

    for parquet_name in ("blended_predictions.parquet", "recommendations.parquet"):
        p = artifacts_dir / parquet_name
        if not p.exists():
            continue
        try:
            df = pl.read_parquet(p)
            cols = set(df.columns)
            for row in df.select([c for c in ["match_id", "home_team", "away_team"] if c in cols]).unique("match_id").iter_rows(named=True):
                mid = row["match_id"]
                if mid not in meta:
                    meta[mid] = {
                        "home_team": row.get("home_team", ""),
                        "away_team": row.get("away_team", ""),
                        "kickoff_at": kickoffs.get(mid),
                    }
            break
        except Exception as exc:
            log.warning("closing_lines: could not load match meta from %s: %s", parquet_name, exc)

    return meta


def run(artifacts_dir: Path = _ARTIFACTS) -> dict:
    """Build closing-line lifecycle artifacts for all tracked matches.

    Returns
    -------
    Summary dict.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ts = datetime.now(timezone.utc).isoformat()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    snapshots = _load_snapshots(artifacts_dir)
    log.info("closing_lines: loaded %d snapshots", len(snapshots))

    # Infer match_ids from snapshots + artifact metadata
    snap_match_ids = sorted({s.match_id for s in snapshots})
    match_meta = _load_match_meta(artifacts_dir)

    # Union match IDs from both sources
    all_match_ids = sorted(set(snap_match_ids) | set(match_meta.keys()))

    # Build lifecycle entries
    entries = build_all_lifecycles(
        snapshots=snapshots,
        match_ids=all_match_ids,
        match_meta=match_meta,
        generated_at=ts,
    )
    log.info("closing_lines: built %d lifecycle entries", len(entries))

    # Validate
    val = validate_all(entries)
    if val["n_with_warnings"] > 0:
        for w in val["warnings"]:
            log.warning("  %s", w)

    # Write parquet
    rows = [_entry_to_row(e) for e in entries]
    if rows:
        df = pl.DataFrame(rows, schema=_CLOSING_LINES_SCHEMA)
    else:
        df = pl.DataFrame(schema=_CLOSING_LINES_SCHEMA)

    cl_path = artifacts_dir / "closing_lines.parquet"
    df.write_parquet(cl_path)
    log.info("closing_lines: wrote closing_lines.parquet (%d rows)", len(df))

    # Counts by closing_status
    status_counts: dict[str, int] = {
        "no_market_data":    0,
        "opening_only":      0,
        "latest_available":  0,
        "closing_candidate": 0,
        "closing_locked":    0,
    }
    for e in entries:
        key = e.closing_status
        if key in status_counts:
            status_counts[key] += 1
        else:
            status_counts[key] = status_counts.get(key, 0) + 1

    n_locked = status_counts.get("closing_locked", 0)
    n_with_opening = sum(1 for e in entries if e.opening is not None)
    n_with_closing = sum(1 for e in entries if e.closing is not None)
    n_with_h24     = sum(1 for e in entries if e.h24 is not None)

    summary = {
        "generated_at":       ts,
        "n_matches":          len(entries),
        "n_with_opening":     n_with_opening,
        "n_with_closing":     n_with_closing,
        "n_with_h24":         n_with_h24,
        "n_closing_locked":   n_locked,
        "by_closing_status":  status_counts,
        "validation": {
            "n_valid":         val["n_valid"],
            "n_with_warnings": val["n_with_warnings"],
            "warnings":        val["warnings"],
        },
        "note": (
            "closing_locked means kickoff has passed and the latest snapshot "
            "is a true closing line. Only closing_locked entries support True CLV."
        ),
    }
    (artifacts_dir / "closing_line_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    log.info(
        "closing_lines: n_locked=%d  n_with_closing=%d  validation_warnings=%d",
        n_locked, n_with_closing, val["n_with_warnings"],
    )

    # ── market_movement.json ──────────────────────────────────────────────────
    movement = build_market_movement(entries)
    movement["generated_at"] = ts
    (artifacts_dir / "market_movement.json").write_text(
        json.dumps(movement, indent=2)
    )
    log.info(
        "closing_lines: wrote market_movement.json (%d matches with movement)",
        movement["n_matches_with_movement"],
    )

    return summary


if __name__ == "__main__":
    run()
