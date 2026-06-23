"""
Market Intelligence data models — Week 28.

MarketIntelligenceCard is the core output: one per (match, market_type).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


MARKET_TYPES   = ("corners", "cards", "shots")
ENVIRONMENTS   = ("very_low", "low", "normal", "high", "very_high")
SIGNAL_LEVELS  = ("no_signal", "watchlist", "moderate_signal", "strong_signal")
RISK_LEVELS    = ("low", "medium", "high")
DISPLAY_TIERS  = ("featured", "secondary", "watchlist", "no_signal")
DATA_QUALITY   = ("seed", "live", "insufficient")
DIRECTIONS     = ("elevated", "neutral", "suppressed")


@dataclass
class MarketIntelligenceCard:
    """Complete market intelligence analysis for one market in one match."""
    match_id:              str
    market_type:           str              # one of MARKET_TYPES
    signal_level:          str              # one of SIGNAL_LEVELS
    confidence:            float            # 0.0–1.0
    knowledge_confidence:  float            # from knowledge activation
    market_score:          float            # 0–100 raw score
    supporting_mechanisms: list[str]        # football mechanisms driving signal
    counter_mechanisms:    list[str]        # mechanisms working against signal
    active_chains:         list[str]        # activated causal chain IDs
    active_scripts:        list[str]        # activated game script IDs
    expected_direction:    str              # one of DIRECTIONS
    environment:           str              # one of ENVIRONMENTS
    risk_level:            str              # one of RISK_LEVELS
    headline:              str
    explanation:           str
    key_risk:              str
    display_tier:          str              # one of DISPLAY_TIERS
    data_quality:          str              # one of DATA_QUALITY
    generated_at:          str

    def to_dict(self) -> dict:
        return {
            "match_id":              self.match_id,
            "market_type":           self.market_type,
            "signal_level":          self.signal_level,
            "confidence":            round(self.confidence, 4),
            "knowledge_confidence":  round(self.knowledge_confidence, 4),
            "market_score":          round(self.market_score, 2),
            "supporting_mechanisms": self.supporting_mechanisms,
            "counter_mechanisms":    self.counter_mechanisms,
            "active_chains":         self.active_chains,
            "active_scripts":        self.active_scripts,
            "expected_direction":    self.expected_direction,
            "environment":           self.environment,
            "risk_level":            self.risk_level,
            "headline":              self.headline,
            "explanation":           self.explanation,
            "key_risk":              self.key_risk,
            "display_tier":          self.display_tier,
            "data_quality":          self.data_quality,
            "generated_at":          self.generated_at,
        }


@dataclass
class MarketIntelligenceSummary:
    """Aggregate summary across all matches and market types."""
    generated_at:         str
    stage:                str
    n_matches:            int
    n_cards:              int
    n_strong_signals:     int
    n_moderate_signals:   int
    n_watchlist:          int
    n_no_signal:          int
    top_corners_signals:  list[dict]
    top_cards_signals:    list[dict]
    top_shots_signals:    list[dict]
    dominant_mechanisms:  list[str]
    notes:                list[str]

    def to_dict(self) -> dict:
        return {
            "generated_at":        self.generated_at,
            "stage":               self.stage,
            "n_matches":           self.n_matches,
            "n_cards":             self.n_cards,
            "n_strong_signals":    self.n_strong_signals,
            "n_moderate_signals":  self.n_moderate_signals,
            "n_watchlist":         self.n_watchlist,
            "n_no_signal":         self.n_no_signal,
            "top_corners_signals": self.top_corners_signals,
            "top_cards_signals":   self.top_cards_signals,
            "top_shots_signals":   self.top_shots_signals,
            "dominant_mechanisms": self.dominant_mechanisms,
            "notes":               self.notes,
        }
