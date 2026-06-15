"""
Signal classification and betting card builder — Week 22.

Signal levels (from markets.py _classify_signal):
  no_signal           — gap < 3pp  (within model noise)
  watch               — gap 3–6pp
  moderate_signal     — gap 6–10pp (model edge detected)
  strong_signal       — gap > 10pp (large model edge detected)
  model_probability_only — no market data

These are educational signals only. Not betting advice.
"""
from __future__ import annotations

from typing import Optional

from oracle.betting.schema import BetMarketProbability, MatchBettingCard

_SIGNAL_ORDER: dict[str, int] = {
    "strong_signal":          0,
    "moderate_signal":        1,
    "watch":                  2,
    "no_signal":              3,
    "model_probability_only": 4,
}


def rank_signals(markets: list[BetMarketProbability]) -> list[BetMarketProbability]:
    """Sort markets by signal strength descending, then by gap magnitude."""
    return sorted(markets, key=lambda m: (
        _SIGNAL_ORDER.get(m.signal_level, 99),
        -(abs(m.market_gap) if m.market_gap is not None else 0.0),
    ))


def top_signals(
    markets: list[BetMarketProbability],
    *,
    max_signals: int = 3,
    min_level: str = "watch",
) -> list[BetMarketProbability]:
    """Return top N signals at or above min_level (by signal strength)."""
    threshold = _SIGNAL_ORDER.get(min_level, 99)
    filtered = [
        m for m in markets
        if _SIGNAL_ORDER.get(m.signal_level, 99) <= threshold
    ]
    return rank_signals(filtered)[:max_signals]


def no_signal_reason(
    has_market_data: bool,
    is_finished: bool,
    *,
    n_markets: int = 0,
) -> str:
    if is_finished:
        return "Match has finished — signals are for pre-match use only."
    if not has_market_data:
        return (
            "No market odds available — model probabilities shown for reference only. "
            "Signals require market data to compute gaps."
        )
    if n_markets == 0:
        return "No markets computed."
    return (
        "No significant model-market gap detected. "
        "Model and market probabilities are aligned (gap < 3pp)."
    )


def build_betting_card(
    match_id: str,
    group: str,
    home_team: str,
    away_team: str,
    markets: list[BetMarketProbability],
    *,
    kickoff_at: Optional[str] = None,
    venue: Optional[str] = None,
    city: Optional[str] = None,
    has_market_data: bool = False,
    is_finished: bool = False,
    generated_at: str = "",
) -> MatchBettingCard:
    signals = top_signals(markets)
    reason = "" if signals else no_signal_reason(
        has_market_data, is_finished, n_markets=len(markets),
    )
    return MatchBettingCard(
        match_id=match_id,
        group=group,
        kickoff_at=kickoff_at,
        venue=venue,
        city=city,
        home_team=home_team,
        away_team=away_team,
        markets=markets,
        top_signals=signals,
        no_signal_reason=reason,
        generated_at=generated_at,
    )
