"""
Snapshot movement and CLV-ready record construction.

Terminology (strict):
  "snapshot_movement" — odds drift between the opening and latest captured snapshot.
                        NOT CLV. True CLV requires a closing line at kickoff.
  "latest-vs-open"    — synonym for snapshot_movement.
  "CLV-ready"         — a CLVRecord with all needed fields populated. The
                        market_close_prob field holds the LATEST snapshot prob
                        (not a true closing line). aggregate_clv() will produce
                        meaningful stats only after kickoff captures exist.

Do NOT call anything CLV unless latest_snap was captured at kickoff.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from oracle.harness.clv import CLVRecord
from oracle.market.schema import OddsSnapshot

log = logging.getLogger(__name__)


def opening_snapshot(
    snapshots: list[OddsSnapshot],
    match_id: str,
    bookmaker: str,
    market: str,
    selection: str,
) -> Optional[OddsSnapshot]:
    """Earliest captured snapshot for a given match/bookmaker/market/selection."""
    candidates = [
        s for s in snapshots
        if s.match_id == match_id
        and s.bookmaker == bookmaker
        and s.market == market
        and s.selection == selection
    ]
    return min(candidates, key=lambda s: s.captured_at) if candidates else None


def latest_snapshot(
    snapshots: list[OddsSnapshot],
    match_id: str,
    bookmaker: str,
    market: str,
    selection: str,
) -> Optional[OddsSnapshot]:
    """Most recent snapshot for a given match/bookmaker/market/selection."""
    candidates = [
        s for s in snapshots
        if s.match_id == match_id
        and s.bookmaker == bookmaker
        and s.market == market
        and s.selection == selection
    ]
    return max(candidates, key=lambda s: s.captured_at) if candidates else None


def snapshot_movement(
    open_snap: OddsSnapshot,
    latest_snap: OddsSnapshot,
) -> dict:
    """Compute line drift between opening and latest snapshot.

    ⚠️  NOT CLV. True CLV requires a closing line captured at kickoff.
    This is "snapshot_movement" / "latest-vs-open" — pre-kickoff drift only.

    Returns dict with:
      match_id, bookmaker, market, selection,
      open_decimal_odds, latest_decimal_odds, odds_movement,
      open_devigged_prob, latest_devigged_prob, prob_movement,
      n_hours, label="snapshot_movement"
    """
    return {
        "match_id":             open_snap.match_id,
        "bookmaker":            open_snap.bookmaker,
        "market":               open_snap.market,
        "selection":            open_snap.selection,
        "open_decimal_odds":    open_snap.decimal_odds,
        "latest_decimal_odds":  latest_snap.decimal_odds,
        "odds_movement":        latest_snap.decimal_odds - open_snap.decimal_odds,
        "open_devigged_prob":   open_snap.implied_probability_devigged,
        "latest_devigged_prob": latest_snap.implied_probability_devigged,
        "prob_movement":        (
            latest_snap.implied_probability_devigged
            - open_snap.implied_probability_devigged
        ),
        "n_hours": _hours_between(open_snap.captured_at, latest_snap.captured_at),
        "label":   "snapshot_movement",  # NOT "clv"
    }


def clv_ready_record(
    match_id: str,
    selection: str,
    model_prob: float,
    open_snap: Optional[OddsSnapshot],
    latest_snap: Optional[OddsSnapshot],
    *,
    outcome: Optional[int] = None,
) -> CLVRecord:
    """Build a CLV-ready CLVRecord for one selection in one match.

    "CLV-ready" means all fields needed for CLV computation are populated.
    market_close_prob is set to latest_snap's de-vigged prob, which becomes
    a true closing-line probability only once a kickoff capture exists.

    Use snapshot_movement() to track pre-kickoff drift instead.
    """
    return CLVRecord(
        match_id=match_id,
        team=selection,
        market="1x2",
        model_prob=model_prob,
        market_open_prob=(
            open_snap.implied_probability_devigged if open_snap is not None else None
        ),
        market_close_prob=(
            latest_snap.implied_probability_devigged if latest_snap is not None else None
        ),
        outcome=outcome,
    )


def _hours_between(t1: str, t2: str) -> float:
    """Elapsed hours between two ISO 8601 UTC strings."""
    try:
        dt1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(t2.replace("Z", "+00:00"))
        return abs((dt2 - dt1).total_seconds()) / 3600.0
    except (ValueError, AttributeError):
        return 0.0
