"""
Closing-line candidate classification.

For each match, determines the snapshot status relative to kickoff time.
Five exclusive statuses:

  no_market_data    — no OddsSnapshot rows for this match
  opening_only      — exactly one distinct timestamp across all bookmakers
  latest_available  — multiple timestamps; kickoff unknown or far in future
  closing_candidate — latest snapshot within `closing_window_hours` of kickoff
  closing_locked    — kickoff has passed; latest snapshot is the closing line

True CLV (model_prob − market_close_prob_devigged) may only be computed
when status == "closing_locked".  All other statuses reflect pre-kickoff
drift only — use snapshot_movement() for that.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from oracle.harness.clv import CLVRecord
from oracle.market.schema import OddsSnapshot

CLOSING_WINDOW_HOURS: float = 2.0


def match_snapshot_status(
    snapshots: list[OddsSnapshot],
    match_id: str,
    market: str = "1x2",
    kickoff_at: Optional[datetime] = None,
    *,
    closing_window_hours: float = CLOSING_WINDOW_HOURS,
    now: Optional[datetime] = None,
) -> dict:
    """Closing-line status for one match, aggregated over all bookmakers.

    Parameters
    ----------
    snapshots:             All available OddsSnapshot rows.
    match_id:              Match identifier to filter on.
    market:                Market type; default "1x2".
    kickoff_at:            Known kickoff datetime (timezone-aware UTC).
                           Pass None if unknown.
    closing_window_hours:  Snapshot must be within this many hours before
                           kickoff to qualify as `closing_candidate`.
    now:                   Injectable "current time" for deterministic tests.
                           Defaults to datetime.now(timezone.utc).

    Returns
    -------
    dict with keys:
      match_id, status, n_snapshots, opening_captured_at,
      latest_captured_at, hours_of_coverage, has_closing_line
    """
    candidates = [
        s for s in snapshots
        if s.match_id == match_id and s.market == market
    ]

    if not candidates:
        return {
            "match_id":            match_id,
            "status":              "no_market_data",
            "n_snapshots":         0,
            "opening_captured_at": None,
            "latest_captured_at":  None,
            "hours_of_coverage":   0.0,
            "has_closing_line":    False,
        }

    earliest_at = min(s.captured_at for s in candidates)
    latest_at   = max(s.captured_at for s in candidates)
    hours_cov   = _hours_between_str(earliest_at, latest_at)

    status = _classify(
        earliest_at, latest_at, kickoff_at,
        closing_window_hours=closing_window_hours,
        now=now,
    )

    return {
        "match_id":            match_id,
        "status":              status,
        "n_snapshots":         len(candidates),
        "opening_captured_at": earliest_at,
        "latest_captured_at":  latest_at,
        "hours_of_coverage":   hours_cov,
        "has_closing_line":    status == "closing_locked",
    }


def closing_line_summary(
    snapshots: list[OddsSnapshot],
    match_ids: Optional[list[str]] = None,
    market: str = "1x2",
    kickoff_times: Optional[dict[str, datetime]] = None,
    *,
    closing_window_hours: float = CLOSING_WINDOW_HOURS,
    now: Optional[datetime] = None,
) -> list[dict]:
    """One status row per match_id.

    If `match_ids` is None, infers from the provided snapshots.
    Matches listed in `match_ids` that have no snapshots appear with
    status="no_market_data".
    """
    if match_ids is None:
        match_ids = sorted({s.match_id for s in snapshots})

    return [
        match_snapshot_status(
            snapshots, mid,
            market=market,
            kickoff_at=(kickoff_times or {}).get(mid),
            closing_window_hours=closing_window_hours,
            now=now,
        )
        for mid in match_ids
    ]


def closing_line_clv_record(
    match_id: str,
    selection: str,
    model_prob: float,
    open_snap: Optional[OddsSnapshot],
    latest_snap: Optional[OddsSnapshot],
    closing_status: str,
    *,
    outcome: Optional[int] = None,
) -> CLVRecord:
    """Build a CLVRecord that respects the closing-line status.

    market_close_prob is populated ONLY when closing_status == "closing_locked".
    For every other status the field is None, so aggregate_clv() will skip
    this record — the correct behaviour before kickoff.

    Do NOT label results as CLV unless closing_status == "closing_locked".
    """
    is_locked = closing_status == "closing_locked"
    return CLVRecord(
        match_id=match_id,
        team=selection,
        market="1x2",
        model_prob=model_prob,
        market_open_prob=(
            open_snap.implied_probability_devigged if open_snap is not None else None
        ),
        market_close_prob=(
            latest_snap.implied_probability_devigged
            if (latest_snap is not None and is_locked)
            else None
        ),
        outcome=outcome,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _classify(
    earliest_at: str,
    latest_at: str,
    kickoff_at: Optional[datetime],
    *,
    closing_window_hours: float,
    now: Optional[datetime],
) -> str:
    if kickoff_at is None:
        return "opening_only" if earliest_at == latest_at else "latest_available"

    now_dt     = now or datetime.now(timezone.utc)
    latest_dt  = _parse_dt(latest_at)

    if kickoff_at <= now_dt:
        return "closing_locked"

    time_to_kickoff_h = (kickoff_at - latest_dt).total_seconds() / 3600
    if 0 <= time_to_kickoff_h <= closing_window_hours:
        return "closing_candidate"

    return "latest_available" if earliest_at != latest_at else "opening_only"


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _hours_between_str(t1: str, t2: str) -> float:
    try:
        return abs((_parse_dt(t2) - _parse_dt(t1)).total_seconds()) / 3600.0
    except (ValueError, AttributeError):
        return 0.0
