"""
Betting Thesis pipeline — Week 25D MVP.

Reads:    data/artifacts/match_betting_cards.json
Writes:   data/artifacts/betting_theses.json
          data/artifacts/betting_theses.parquet
          data/artifacts/thesis_summary.json

Exports:  frontend/src/data/betting_theses.json
          frontend/src/data/thesis_summary.json

Usage:
    python -m oracle.pipeline.thesis
    make thesis
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.thesis.generator import generate_all_theses
from oracle.thesis.schema import BettingThesis, MatchThesisSummary

log = logging.getLogger(__name__)

_ARTIFACTS   = Path("data/artifacts")
_FRONTEND    = Path("frontend/src/data")

_DISCLAIMER = (
    "These are educational probability signals only. Not betting advice. "
    "A model-market gap does not imply value or a winning selection. "
    "Market odds may be more accurate than model estimates."
)

_LANGUAGE_POLICY = {
    "safe_terms": [
        "signal detected", "model edge", "watchlist", "no opportunity",
        "market aligned", "high variance", "insufficient data",
        "model estimate", "model-only",
    ],
    "forbidden_terms": [
        "bet this", "lock", "guaranteed", "sure thing", "profit",
        "free money", "must bet", "bet this now", "risk-free",
    ],
}


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _thesis_rows(theses: list[BettingThesis]) -> list[dict]:
    return [t.to_dict() for t in theses]


def _summary_payload(
    theses: list[BettingThesis],
    match_summaries: list[MatchThesisSummary],
    generated_at: str,
) -> dict:
    n_featured   = sum(1 for t in theses if t.display_tier == "featured")
    n_secondary  = sum(1 for t in theses if t.display_tier == "secondary")
    n_watchlist  = sum(1 for t in theses if t.display_tier == "watchlist")
    n_hidden     = sum(1 for t in theses if t.display_tier == "hidden")
    n_model_only = sum(1 for t in theses if t.contrarian_classification == "model_only")
    n_market_edge = sum(
        1 for t in theses
        if t.contrarian_classification not in ("model_only", "aligned")
        and t.market_quality != "unavailable"
    )
    has_market = sum(1 for ms in match_summaries if ms.has_market_data)

    markets_supported = [
        "1x2", "double_chance", "draw_no_bet",
        "over_under_2_5", "btts", "correct_score",
    ]
    markets_unavailable = [
        "corners", "cards", "shots", "player_props",
        "anytime_scorer", "over_under_1_5", "over_under_3_5",
    ]

    return {
        "generated_at":          generated_at,
        "data_stage":            "stage_1",
        "n_matches":             len(match_summaries),
        "n_matches_with_market": has_market,
        "n_theses":              len(theses),
        "n_featured":            n_featured,
        "n_secondary":           n_secondary,
        "n_watchlist":           n_watchlist,
        "n_hidden":              n_hidden,
        "n_model_only":          n_model_only,
        "n_market_edge":         n_market_edge,
        "markets_supported":     markets_supported,
        "markets_unavailable":   markets_unavailable,
        "disclaimer":            _DISCLAIMER,
        "language_policy":       _LANGUAGE_POLICY,
        "match_summaries":       [ms.to_dict() for ms in match_summaries],
    }


# ── Writers ───────────────────────────────────────────────────────────────────

def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    kb = path.stat().st_size / 1024
    log.info("  wrote %s  (%.1f KB)", path, kb)


def _write_parquet(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        log.warning("No thesis rows — writing empty parquet")
        pl.DataFrame().write_parquet(path)
        return
    df = pl.DataFrame(rows)
    df.write_parquet(path)
    log.info("  wrote %s  (%d rows)", path, len(rows))


# ── Main run ──────────────────────────────────────────────────────────────────

def run() -> dict:
    """
    Generate, write, and export all betting theses.

    Returns the summary payload dict.
    """
    log.info("Betting Thesis pipeline starting…")

    theses, match_summaries = generate_all_theses()
    generated_at = datetime.now(timezone.utc).isoformat()

    rows        = _thesis_rows(theses)
    summary     = _summary_payload(theses, match_summaries, generated_at)

    # ── Artifacts ──────────────────────────────────────────────────────────
    _write_json(_ARTIFACTS / "betting_theses.json",    rows)
    _write_json(_ARTIFACTS / "thesis_summary.json",    summary)
    _write_parquet(_ARTIFACTS / "betting_theses.parquet", rows)

    # ── Frontend exports ───────────────────────────────────────────────────
    _write_json(_FRONTEND / "betting_theses.json",  rows)
    _write_json(_FRONTEND / "thesis_summary.json",  summary)

    log.info(
        "Thesis pipeline complete: %d matches, %d theses "
        "(%d featured, %d secondary, %d watchlist, %d hidden)",
        summary["n_matches"],
        summary["n_theses"],
        summary["n_featured"],
        summary["n_secondary"],
        summary["n_watchlist"],
        summary["n_hidden"],
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    result = run()
    print(json.dumps(
        {k: v for k, v in result.items() if k != "match_summaries"},
        indent=2,
    ))
