"""
Market lifecycle checkpoint extraction — Week 20.

For each match, converts all available 1X2 odds snapshots into structured
lifecycle checkpoints: opening, 24h, 12h, 6h, 1h, and closing.

Rules:
  - Only pre-kickoff snapshots are used; post-kickoff are ignored entirely.
  - If kickoff_at is unknown, only opening and closing checkpoints are derived.
  - Checkpoints are never inferred — if no snapshot fits a window, the
    checkpoint is None.
  - Probabilities are averaged over all bookmakers at the chosen timestamp.
  - Closing checkpoint = latest pre-kickoff snapshot (by captured_at).
  - Opening checkpoint = earliest pre-kickoff snapshot (by captured_at).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from oracle.market.closing import match_snapshot_status
from oracle.market.schema import OddsSnapshot

# Checkpoint definitions: (label, target_hours_before_kickoff, tolerance_hours)
_CHECKPOINT_DEFS: list[tuple[str, float, float]] = [
    ("h24", 24.0, 6.0),   # 18h–30h before kickoff
    ("h12", 12.0, 4.0),   # 8h–16h before kickoff
    ("h6",  6.0,  2.0),   # 4h–8h before kickoff
    ("h1",  1.0,  0.75),  # 15min–1h45min before kickoff
]


@dataclass
class CheckpointSnapshot:
    """Averaged 1X2 probabilities at a single capture moment."""
    captured_at: str
    home_prob: float
    draw_prob: float
    away_prob: float

    def to_dict(self) -> dict:
        return {
            "captured_at": self.captured_at,
            "home_prob":   round(self.home_prob, 6),
            "draw_prob":   round(self.draw_prob, 6),
            "away_prob":   round(self.away_prob, 6),
        }


@dataclass
class LifecycleEntry:
    """Full market lifecycle for one match."""
    match_id:                str
    home_team:               str
    away_team:               str
    kickoff_at:              Optional[str]
    n_pre_kickoff_snapshots: int
    opening:                 Optional[CheckpointSnapshot]
    h24:                     Optional[CheckpointSnapshot]
    h12:                     Optional[CheckpointSnapshot]
    h6:                      Optional[CheckpointSnapshot]
    h1:                      Optional[CheckpointSnapshot]
    closing:                 Optional[CheckpointSnapshot]
    closing_status:          str
    generated_at:            str

    def to_dict(self) -> dict:
        return {
            "match_id":                self.match_id,
            "home_team":               self.home_team,
            "away_team":               self.away_team,
            "kickoff_at":              self.kickoff_at,
            "n_pre_kickoff_snapshots": self.n_pre_kickoff_snapshots,
            "opening":                 self.opening.to_dict() if self.opening else None,
            "h24":                     self.h24.to_dict() if self.h24 else None,
            "h12":                     self.h12.to_dict() if self.h12 else None,
            "h6":                      self.h6.to_dict() if self.h6 else None,
            "h1":                      self.h1.to_dict() if self.h1 else None,
            "closing":                 self.closing.to_dict() if self.closing else None,
            "closing_status":          self.closing_status,
            "generated_at":            self.generated_at,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _avg_probs_at(
    snapshots: list[OddsSnapshot],
    match_id: str,
    captured_at: str,
    market: str = "1x2",
) -> Optional[CheckpointSnapshot]:
    """Average 1X2 de-vigged probs across all bookmakers at exactly captured_at."""
    rows = [
        s for s in snapshots
        if s.match_id == match_id
        and s.captured_at == captured_at
        and s.market == market
        and s.selection in ("home", "draw", "away")
    ]
    if not rows:
        return None

    by_sel: dict[str, list[float]] = {"home": [], "draw": [], "away": []}
    for s in rows:
        by_sel[s.selection].append(s.implied_probability_devigged)

    if not all(by_sel.values()):
        return None

    return CheckpointSnapshot(
        captured_at=captured_at,
        home_prob=sum(by_sel["home"]) / len(by_sel["home"]),
        draw_prob=sum(by_sel["draw"]) / len(by_sel["draw"]),
        away_prob=sum(by_sel["away"]) / len(by_sel["away"]),
    )


def _nearest_timestamp(
    capture_times: list[str],
    kickoff_dt: datetime,
    target_hours: float,
    tolerance_hours: float,
) -> Optional[str]:
    """Find the captured_at timestamp closest to target_hours before kickoff.

    Only considers timestamps within [target_hours - tolerance, target_hours + tolerance]
    hours before kickoff.
    """
    target_dt = kickoff_dt - timedelta(hours=target_hours)
    lo = kickoff_dt - timedelta(hours=target_hours + tolerance_hours)
    hi = kickoff_dt - timedelta(hours=max(0.0, target_hours - tolerance_hours))

    candidates = [
        t for t in capture_times
        if lo <= _parse_dt(t) <= hi
    ]
    if not candidates:
        return None

    return min(candidates, key=lambda t: abs((_parse_dt(t) - target_dt).total_seconds()))


# ── Public API ────────────────────────────────────────────────────────────────

def build_lifecycle_entry(
    snapshots: list[OddsSnapshot],
    match_id: str,
    home_team: str,
    away_team: str,
    kickoff_at: Optional[datetime],
    generated_at: str,
    market: str = "1x2",
) -> LifecycleEntry:
    """Build a LifecycleEntry for one match from a collection of snapshots.

    Parameters
    ----------
    snapshots:    All available OddsSnapshot rows (any match — filtered internally).
    match_id:     Match identifier.
    home_team:    Home team identifier.
    away_team:    Away team identifier.
    kickoff_at:   Match kickoff time (timezone-aware UTC), or None if unknown.
    generated_at: ISO timestamp to stamp the entry.
    market:       Market type; default "1x2".
    """
    # Closing status from existing closing.py
    status_info = match_snapshot_status(
        snapshots, match_id, market=market, kickoff_at=kickoff_at
    )
    closing_status = status_info["status"]

    # All snapshots for this match and market
    match_snaps = [
        s for s in snapshots
        if s.match_id == match_id and s.market == market
    ]

    # Filter to pre-kickoff only
    if kickoff_at is not None:
        pre_koff = [s for s in match_snaps if _parse_dt(s.captured_at) < kickoff_at]
    else:
        pre_koff = match_snaps

    if not pre_koff:
        return LifecycleEntry(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            kickoff_at=kickoff_at.isoformat() if kickoff_at else None,
            n_pre_kickoff_snapshots=0,
            opening=None,
            h24=None,
            h12=None,
            h6=None,
            h1=None,
            closing=None,
            closing_status=closing_status,
            generated_at=generated_at,
        )

    distinct_times = sorted({s.captured_at for s in pre_koff})

    # Opening: earliest pre-kickoff timestamp
    opening = _avg_probs_at(snapshots, match_id, distinct_times[0], market)

    # Closing: latest pre-kickoff timestamp
    closing = _avg_probs_at(snapshots, match_id, distinct_times[-1], market)

    # Timed checkpoints — only if kickoff is known
    h24 = h12 = h6 = h1 = None
    if kickoff_at is not None:
        for label, target_h, tol_h in _CHECKPOINT_DEFS:
            ts = _nearest_timestamp(distinct_times, kickoff_at, target_h, tol_h)
            cp = _avg_probs_at(snapshots, match_id, ts, market) if ts else None
            if label == "h24":
                h24 = cp
            elif label == "h12":
                h12 = cp
            elif label == "h6":
                h6 = cp
            elif label == "h1":
                h1 = cp

    return LifecycleEntry(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        kickoff_at=kickoff_at.isoformat() if kickoff_at else None,
        n_pre_kickoff_snapshots=len(pre_koff),
        opening=opening,
        h24=h24,
        h12=h12,
        h6=h6,
        h1=h1,
        closing=closing,
        closing_status=closing_status,
        generated_at=generated_at,
    )


def build_all_lifecycles(
    snapshots: list[OddsSnapshot],
    match_ids: list[str],
    match_meta: dict[str, dict],
    generated_at: str,
    market: str = "1x2",
) -> list[LifecycleEntry]:
    """Build LifecycleEntry for every match_id in the list.

    Parameters
    ----------
    snapshots:    All available OddsSnapshot rows.
    match_ids:    Ordered list of match identifiers to process.
    match_meta:   {match_id: {"home_team": str, "away_team": str,
                               "kickoff_at": datetime | None}}
    generated_at: ISO timestamp to stamp all entries.
    market:       Market type; default "1x2".
    """
    entries: list[LifecycleEntry] = []
    for mid in match_ids:
        meta = match_meta.get(mid, {})
        entries.append(
            build_lifecycle_entry(
                snapshots=snapshots,
                match_id=mid,
                home_team=meta.get("home_team", ""),
                away_team=meta.get("away_team", ""),
                kickoff_at=meta.get("kickoff_at"),
                generated_at=generated_at,
                market=market,
            )
        )
    return entries
