"""
Odds snapshot schema: the canonical normalised row for one market outcome.

OddsSnapshot is one row: one (bookmaker × match × market × selection) capture.
De-vigged probabilities are computed on ingest; raw decimal odds are preserved.

build_1x2_snapshots() is the primary constructor — it handles de-vig for all
three 1X2 outcomes together (Shin de-vig needs all outcomes simultaneously).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from oracle.scoring.devig import devig


@dataclass
class OddsSnapshot:
    """One normalised, de-vigged market odds row."""
    snapshot_id: str
    bookmaker: str
    market: str             # '1x2', 'ou25', etc.
    match_id: str           # fixture_id or provider event ID
    home_team: str
    away_team: str
    selection: str          # 'home', 'draw', 'away', 'over', 'under', …
    decimal_odds: float
    implied_probability_raw: float       # 1 / decimal_odds (overround-inclusive)
    implied_probability_devigged: float  # after Shin/power de-vig
    devig_method: str                   # 'shin', 'power', 'naive'
    captured_at: str        # ISO 8601 UTC, e.g. "2026-06-14T16:00:00Z"
    source: str             # 'the-odds-api', 'dummy', 'manual', …
    source_event_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "snapshot_id":                self.snapshot_id,
            "bookmaker":                  self.bookmaker,
            "market":                     self.market,
            "match_id":                   self.match_id,
            "home_team":                  self.home_team,
            "away_team":                  self.away_team,
            "selection":                  self.selection,
            "decimal_odds":               self.decimal_odds,
            "implied_probability_raw":    self.implied_probability_raw,
            "implied_probability_devigged": self.implied_probability_devigged,
            "devig_method":               self.devig_method,
            "captured_at":                self.captured_at,
            "source":                     self.source,
            "source_event_id":            self.source_event_id,
        }


def build_1x2_snapshots(
    *,
    match_id: str,
    home_team: str,
    away_team: str,
    bookmaker: str,
    odds_1x2: dict[str, float],  # {"home": 2.25, "draw": 3.50, "away": 3.20}
    captured_at: str,
    source: str,
    devig_method: str = "shin",
    source_event_id: Optional[str] = None,
) -> list[OddsSnapshot]:
    """Build three OddsSnapshot rows from raw 1X2 decimal odds.

    De-vigs all three outcomes together (Shin/power methods need the full set).
    Returns one row each for 'home', 'draw', 'away'.
    """
    expected = {"home", "draw", "away"}
    if set(odds_1x2.keys()) != expected:
        raise ValueError(
            f"odds_1x2 must have exactly keys {expected}, got {set(odds_1x2.keys())}"
        )

    devigged = devig(odds_1x2, method=devig_method)
    snapshot_id = str(uuid.uuid4())  # shared across all 3 rows for this capture
    rows = []
    for selection in ("home", "draw", "away"):
        raw_odds = float(odds_1x2[selection])
        rows.append(OddsSnapshot(
            snapshot_id=snapshot_id,
            bookmaker=bookmaker,
            market="1x2",
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            selection=selection,
            decimal_odds=raw_odds,
            implied_probability_raw=1.0 / raw_odds,
            implied_probability_devigged=float(devigged[selection]),
            devig_method=devig_method,
            captured_at=captured_at,
            source=source,
            source_event_id=source_event_id,
        ))
    return rows


def snapshots_to_df(snapshots: list[OddsSnapshot]):
    """Convert a list of OddsSnapshot rows to a Polars DataFrame."""
    import polars as pl
    if not snapshots:
        return pl.DataFrame(
            schema={
                "snapshot_id": pl.Utf8,
                "bookmaker": pl.Utf8,
                "market": pl.Utf8,
                "match_id": pl.Utf8,
                "home_team": pl.Utf8,
                "away_team": pl.Utf8,
                "selection": pl.Utf8,
                "decimal_odds": pl.Float64,
                "implied_probability_raw": pl.Float64,
                "implied_probability_devigged": pl.Float64,
                "devig_method": pl.Utf8,
                "captured_at": pl.Utf8,
                "source": pl.Utf8,
                "source_event_id": pl.Utf8,
            }
        )
    return pl.DataFrame([s.to_dict() for s in snapshots])


def df_to_snapshots(df) -> list[OddsSnapshot]:
    """Convert a Polars DataFrame back to OddsSnapshot objects."""
    return [OddsSnapshot(**row) for row in df.iter_rows(named=True)]
