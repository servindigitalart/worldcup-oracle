"""
Responsible Recommendation Engine — data models.

Language policy
---------------
FORBIDDEN terms (must never appear in reason / warnings / labels):
  guaranteed, lock, sure bet, can't lose, free money, profit,
  must bet, bet this now, high certainty

ALLOWED terms:
  model gap detected, watch, avoid, no recommendation, market-aligned,
  low confidence, data incomplete, educational only, probability signal

Default posture: conservative.
Most matches should produce no_recommendation, watch, or market_aligned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Allowed enum values ────────────────────────────────────────────────────────

RECOMMENDATION_TYPES: frozenset[str] = frozenset({
    "no_recommendation",
    "model_gap_detected",
    "market_aligned",
    "avoid",
    "watch",
})

RISK_LABELS: frozenset[str] = frozenset({"low", "medium", "high", "unknown"})
CONFIDENCE_LEVELS: frozenset[str] = frozenset({"low", "medium", "high", "unknown"})
DATA_QUALITY_LEVELS: frozenset[str] = frozenset({
    "complete", "partial", "missing_market", "placeholder", "stale", "unknown",
})
STATUSES: frozenset[str] = frozenset({"pre_match", "live", "finished", "unavailable"})

# Edge confidence — how large is the model-market gap?
# Thresholds: 0-3pp=low, 3-6pp=medium, 6-10pp=high, 10%+=very_high, none=no gap
EDGE_CONFIDENCE_LEVELS: frozenset[str] = frozenset({
    "low", "medium", "high", "very_high", "none",
})

# ── Language policy ────────────────────────────────────────────────────────────

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
})

SAFE_TERMS: list[str] = [
    "educational only",
    "probability signal",
    "model gap detected",
    "watch",
    "avoid",
    "no recommendation",
    "market-aligned",
    "low confidence",
    "data incomplete",
]

STANDARD_WARNINGS: list[str] = [
    "Educational signal only — not betting advice.",
    "A model-market gap is not evidence of value.",
    "Market odds may be more accurate than model probabilities.",
]


def check_language(text: str) -> list[str]:
    """Return list of forbidden terms found in text (case-insensitive)."""
    lower = text.lower()
    return [term for term in FORBIDDEN_TERMS if term in lower]


# ── Input model ────────────────────────────────────────────────────────────────

@dataclass
class RecommendationInput:
    """All data needed to generate a recommendation for one match."""

    match_id: str
    home_team: str
    away_team: str
    group: str
    kickoff_at: Optional[str]

    # Model (Elo) 1X2 probabilities
    model_home: float
    model_draw: float
    model_away: float

    # Market (de-vigged) 1X2 probabilities — None if unavailable
    market_home: Optional[float]
    market_draw: Optional[float]
    market_away: Optional[float]

    # Blended probabilities
    blend_home: float
    blend_draw: float
    blend_away: float

    has_market_data: bool

    # "no_market_data" | "opening_only" | "latest_available" |
    # "closing_candidate" | "closing_locked" | "unknown"
    capture_status: str

    # "official" or "placeholder"
    fixture_status: str

    # "scheduled" | "live" | "finished" | "postponed" | "cancelled" | None
    result_status: Optional[str]


# ── Output model ───────────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    """A single responsible recommendation for one match."""

    match_id: str
    home_team: str
    away_team: str
    group: str
    kickoff_at: Optional[str]

    recommendation_type: str   # from RECOMMENDATION_TYPES
    market: str                # always "1x2" for now
    selection: Optional[str]   # "home_win" | "draw" | "away_win" | None

    model_probability: Optional[float]
    market_probability: Optional[float]
    blended_probability: Optional[float]
    model_market_gap: Optional[float]  # signed: model − market

    confidence: str    # from CONFIDENCE_LEVELS
    risk_label: str    # from RISK_LABELS
    data_quality: str  # from DATA_QUALITY_LEVELS
    status: str        # from STATUSES

    reason: str
    warnings: list[str] = field(default_factory=list)
    is_actionable: bool = False
    generated_at: str = ""
    # Edge confidence: how large is the model-market gap (independently of data quality)
    # "none" when there is no gap to classify (no market data, or finished match)
    edge_confidence: str = "none"

    def __post_init__(self) -> None:
        assert self.recommendation_type in RECOMMENDATION_TYPES, (
            f"Invalid recommendation_type: {self.recommendation_type!r}"
        )
        assert self.risk_label in RISK_LABELS, f"Invalid risk_label: {self.risk_label!r}"
        assert self.confidence in CONFIDENCE_LEVELS, f"Invalid confidence: {self.confidence!r}"
        assert self.data_quality in DATA_QUALITY_LEVELS, (
            f"Invalid data_quality: {self.data_quality!r}"
        )
        assert self.status in STATUSES, f"Invalid status: {self.status!r}"
        assert self.edge_confidence in EDGE_CONFIDENCE_LEVELS, (
            f"Invalid edge_confidence: {self.edge_confidence!r}"
        )
        violations = check_language(self.reason)
        for w in self.warnings:
            violations.extend(check_language(w))
        assert not violations, (
            f"Forbidden language in recommendation {self.match_id!r}: {violations}"
        )

    def to_dict(self) -> dict:
        return {
            "match_id":            self.match_id,
            "home_team":           self.home_team,
            "away_team":           self.away_team,
            "group":               self.group,
            "kickoff_at":          self.kickoff_at,
            "recommendation_type": self.recommendation_type,
            "market":              self.market,
            "selection":           self.selection,
            "model_probability":   self.model_probability,
            "market_probability":  self.market_probability,
            "blended_probability": self.blended_probability,
            "model_market_gap":    self.model_market_gap,
            "confidence":          self.confidence,
            "risk_label":          self.risk_label,
            "data_quality":        self.data_quality,
            "status":              self.status,
            "reason":              self.reason,
            "warnings":            self.warnings,
            "is_actionable":       self.is_actionable,
            "edge_confidence":     self.edge_confidence,
            "generated_at":        self.generated_at,
        }
