"""
Betting intelligence data models — Week 22.

Language policy
---------------
FORBIDDEN terms (must never appear in reason / warnings / labels):
  guaranteed, lock, sure bet, can't lose, free money, profit,
  must bet, bet this now, high certainty, risk-free

ALLOWED terms:
  signal, model probability, market gap, watch, no signal, risk,
  confidence, data support, educational only, model edge detected
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

MARKET_TYPES: frozenset[str] = frozenset({
    "1x2",
    "double_chance",
    "draw_no_bet",
    "over_under_1_5",
    "over_under_2_5",
    "over_under_3_5",
    "btts",
    "correct_score",
})

SIGNAL_LEVELS: frozenset[str] = frozenset({
    "no_signal",
    "watch",
    "moderate_signal",
    "strong_signal",
    "model_probability_only",
})

FORBIDDEN_TERMS: frozenset[str] = frozenset({
    "guaranteed",
    "lock",
    "sure bet",
    "can't lose",
    "free money",
    "profit",
    "must bet",
    "bet this now",
    "high certainty",
    "risk-free",
})


def check_language(text: str) -> list[str]:
    """Return list of forbidden terms found in text (case-insensitive)."""
    lower = text.lower()
    return [t for t in FORBIDDEN_TERMS if t in lower]


@dataclass
class BetMarketProbability:
    """Probability and signal for one market/selection combination."""

    match_id: str
    market_type: str            # from MARKET_TYPES
    selection: str              # e.g. "home_win", "over", "1-0"
    probability: float          # model probability [0, 1]
    fair_decimal_odds: Optional[float]  # 1/probability; None when prob==0
    model_source: str           # "elo_blend" | "dixon_coles" | "dc_grid"
    confidence: str             # "low" | "medium" | "high" | "unknown"
    risk_label: str             # "low" | "medium" | "high"
    data_quality: str           # "complete" | "model_only"
    signal_level: str           # from SIGNAL_LEVELS
    market_probability: Optional[float] = None  # de-vigged market prob
    market_gap: Optional[float] = None          # model − market (signed)
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        assert self.signal_level in SIGNAL_LEVELS, (
            f"Invalid signal_level: {self.signal_level!r}"
        )
        violations = check_language(self.reason)
        for w in self.warnings:
            violations.extend(check_language(w))
        assert not violations, (
            f"Forbidden language in BetMarketProbability "
            f"{self.match_id!r} {self.market_type}/{self.selection}: {violations}"
        )

    def to_dict(self) -> dict:
        return {
            "match_id":           self.match_id,
            "market_type":        self.market_type,
            "selection":          self.selection,
            "probability":        round(self.probability, 4),
            "fair_decimal_odds":  (
                round(self.fair_decimal_odds, 2)
                if self.fair_decimal_odds is not None else None
            ),
            "model_source":       self.model_source,
            "confidence":         self.confidence,
            "risk_label":         self.risk_label,
            "data_quality":       self.data_quality,
            "signal_level":       self.signal_level,
            "market_probability": (
                round(self.market_probability, 4)
                if self.market_probability is not None else None
            ),
            "market_gap": (
                round(self.market_gap, 4)
                if self.market_gap is not None else None
            ),
            "reason":       self.reason,
            "warnings":     self.warnings,
            "generated_at": self.generated_at,
        }


@dataclass
class MatchBettingCard:
    """All market signals for one group-stage match."""

    match_id: str
    group: str
    kickoff_at: Optional[str]
    venue: Optional[str]
    city: Optional[str]
    home_team: str
    away_team: str
    markets: list[BetMarketProbability] = field(default_factory=list)
    top_signals: list[BetMarketProbability] = field(default_factory=list)
    no_signal_reason: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict:
        n_signals = sum(
            1 for m in self.markets
            if m.signal_level not in ("no_signal", "model_probability_only")
        )
        return {
            "match_id":        self.match_id,
            "group":           self.group,
            "kickoff_at":      self.kickoff_at,
            "venue":           self.venue,
            "city":            self.city,
            "home_team":       self.home_team,
            "away_team":       self.away_team,
            "n_markets":       len(self.markets),
            "n_signals":       n_signals,
            "markets":         [m.to_dict() for m in self.markets],
            "top_signals":     [m.to_dict() for m in self.top_signals],
            "no_signal_reason": self.no_signal_reason,
            "generated_at":    self.generated_at,
        }
