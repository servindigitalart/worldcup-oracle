"""
Market baseline utilities.

Convert OddsSnapshot rows into per-match 1X2 probability dicts matching the
format used by model predictions: {"home": float, "draw": float, "away": float}.

Probs1x2                — type alias used throughout oracle.market
validate_market_probs() — check sum ≈ 1.0, required keys present, values positive
market_probs_for_match() — extract de-vigged 1X2 for one match_id
all_market_probs()       — extract for all distinct match_ids in a collection
"""
from __future__ import annotations

from typing import Optional

from oracle.market.schema import OddsSnapshot

# Type alias shared across the market package
Probs1x2 = dict[str, float]  # {"home": float, "draw": float, "away": float}

REQUIRED_SELECTIONS = frozenset({"home", "draw", "away"})
_PROB_TOLERANCE = 0.02


def validate_market_probs(probs: Probs1x2, tolerance: float = _PROB_TOLERANCE) -> bool:
    """Return True iff probs has exactly keys {home, draw, away}, all positive, summing to ~1."""
    if set(probs.keys()) != REQUIRED_SELECTIONS:
        return False
    if any(p <= 0 for p in probs.values()):
        return False
    return abs(sum(probs.values()) - 1.0) <= tolerance


def market_probs_for_match(
    snapshots: list[OddsSnapshot],
    match_id: str,
    *,
    bookmaker: Optional[str] = None,
    market: str = "1x2",
    use_latest: bool = True,
) -> Optional[Probs1x2]:
    """Extract de-vigged 1X2 probabilities for one match from a snapshot collection.

    If bookmaker is None, averages de-vigged probs over all available bookmakers
    (equal-weight mean per selection).  If use_latest, retains only the latest
    captured snapshot per (bookmaker × selection) before averaging.

    Returns {"home": float, "draw": float, "away": float} or None if:
      - no matching snapshots exist
      - any selection is missing
      - the result fails validate_market_probs()
    """
    candidates = [
        s for s in snapshots
        if s.match_id == match_id
        and s.market == market
        and s.selection in REQUIRED_SELECTIONS
    ]
    if bookmaker is not None:
        candidates = [s for s in candidates if s.bookmaker == bookmaker]

    if not candidates:
        return None

    if use_latest:
        latest: dict[tuple, OddsSnapshot] = {}
        for s in candidates:
            key = (s.bookmaker, s.selection)
            if key not in latest or s.captured_at > latest[key].captured_at:
                latest[key] = s
        candidates = list(latest.values())

    by_selection: dict[str, list[float]] = {sel: [] for sel in REQUIRED_SELECTIONS}
    for s in candidates:
        by_selection[s.selection].append(s.implied_probability_devigged)

    if any(not vs for vs in by_selection.values()):
        return None

    result: Probs1x2 = {sel: sum(vs) / len(vs) for sel, vs in by_selection.items()}
    return result if validate_market_probs(result) else None


def all_market_probs(
    snapshots: list[OddsSnapshot],
    *,
    bookmaker: Optional[str] = None,
    market: str = "1x2",
    use_latest: bool = True,
) -> dict[str, Optional[Probs1x2]]:
    """Extract de-vigged 1X2 probs for all distinct match_ids in the collection.

    Returns {match_id: probs_or_None}.  None means the match_id has snapshots
    but they are incomplete or fail validation.
    """
    match_ids = sorted({s.match_id for s in snapshots if s.market == market})
    return {
        mid: market_probs_for_match(
            snapshots, mid,
            bookmaker=bookmaker,
            market=market,
            use_latest=use_latest,
        )
        for mid in match_ids
    }
