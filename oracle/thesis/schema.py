"""
Betting Thesis data model — Week 25D MVP.

Kept flat (no nested dicts) so every thesis serialises directly to a
Parquet row.  The list-valued fields (supporting_factors, etc.) are stored
as JSON strings for Parquet compatibility and decoded by consumers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────────────

DATA_STAGE: str = "stage_1"
MODEL_VERSION: str = "oracle-v2-stage1"

DISPLAY_TIERS: frozenset[str] = frozenset({
    "featured",
    "secondary",
    "watchlist",
    "hidden",
})

CONTRARIAN_CLASSIFICATIONS: frozenset[str] = frozenset({
    "model_only",
    "aligned",
    "slight_edge",
    "moderate_edge",
    "strong_edge",
    "extreme_edge",
})

CONFIDENCE_LABELS: frozenset[str] = frozenset({
    "very_low",
    "low",
    "medium",
    "high",
    "very_high",
})

RISK_LEVELS: frozenset[str] = frozenset({
    "low",
    "medium",
    "high",
    "very_high",
})

MARKET_QUALITY: frozenset[str] = frozenset({
    "sufficient",
    "thin",
    "unavailable",
})

# Correlation groups for diversification
CORRELATION_GROUPS: dict[str, str] = {
    # 1X2 outcome directions
    "1x2:home_win":         "outcome_home",
    "1x2:draw":             "outcome_draw",
    "1x2:away_win":         "outcome_away",
    # Double chance
    "double_chance:home_or_draw":   "outcome_home",
    "double_chance:home_or_away":   "outcome_home",  # leans home
    "double_chance:draw_or_away":   "outcome_away",
    # Draw no bet
    "draw_no_bet:home_win": "outcome_home",
    "draw_no_bet:away_win": "outcome_away",
    # Goal markets
    "over_under_1_5:over":  "goals_over",
    "over_under_1_5:under": "goals_under",
    "over_under_2_5:over":  "goals_over",
    "over_under_2_5:under": "goals_under",
    "over_under_3_5:over":  "goals_over",
    "over_under_3_5:under": "goals_under",
    # BTTS
    "btts:yes":             "btts",
    "btts:no":              "btts",
    # Correct score
    "correct_score:*":      "correct_score",
}

# Primary markets we generate theses for (limits noise)
PRIMARY_MARKETS: frozenset[str] = frozenset({
    "1x2",
    "double_chance",
    "draw_no_bet",
    "over_under_2_5",
    "btts",
    "correct_score",
})

# Forbidden language (mirrors oracle.betting.schema)
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
    "bet this",
    "sure thing",
})


def check_language(text: str) -> list[str]:
    """Return list of forbidden terms found in text (case-insensitive)."""
    lower = text.lower()
    return [t for t in FORBIDDEN_TERMS if t in lower]


def correlation_group(market_type: str, selection: str) -> str:
    """Return correlation group key for diversification."""
    key = f"{market_type}:{selection}"
    if key in CORRELATION_GROUPS:
        return CORRELATION_GROUPS[key]
    # correct_score wildcard
    if market_type == "correct_score":
        return "correct_score"
    return f"{market_type}:{selection}"


# ── Main dataclass ─────────────────────────────────────────────────────────────

@dataclass
class BettingThesis:
    """
    MVP Betting Thesis — one market/selection for one match.

    Nested fields (supporting_factors, counter_factors, active_game_scripts,
    active_causal_chains) are stored as JSON strings for Parquet compat.
    """
    thesis_id: str
    match_id: str
    generated_at: str
    model_version: str
    data_stage: str

    # ── Market identity ────────────────────────────────────────────────────
    market_type: str
    selection: str
    line: Optional[float]           # e.g. 2.5 for O/U; None for 1x2

    # ── Model estimate ────────────────────────────────────────────────────
    model_probability: float
    market_implied_probability: Optional[float]
    raw_edge: Optional[float]       # model_prob - market_implied_prob
    edge_pct: Optional[float]       # raw_edge × 100
    fair_odds: float                # 1 / model_probability

    # ── Classification ────────────────────────────────────────────────────
    market_quality: str             # from MARKET_QUALITY
    contrarian_classification: str  # from CONTRARIAN_CLASSIFICATIONS
    contrarian_score: float         # 0.0–1.0

    # ── Confidence & risk ─────────────────────────────────────────────────
    confidence_score: float         # 0.0–1.0 overall
    confidence_label: str           # from CONFIDENCE_LABELS
    risk_level: str                 # from RISK_LEVELS

    # ── Evidence (JSON strings) ──────────────────────────────────────────
    supporting_factors: str         # JSON list[dict]
    counter_factors: str            # JSON list[dict]
    active_game_scripts: str        # JSON list[dict]  (Stage 1: empty)
    active_causal_chains: str       # JSON list[dict]  (Stage 1: empty)

    # ── Human explanation ─────────────────────────────────────────────────
    human_headline: str
    human_body: str
    key_risk_statement: str

    # ── Ranking ────────────────────────────────────────────────────────────
    opportunity_score: int          # 0–100
    rank: int                       # position in match's ranked list
    display_tier: str               # from DISPLAY_TIERS

    def __post_init__(self) -> None:
        assert self.display_tier in DISPLAY_TIERS, \
            f"Invalid display_tier: {self.display_tier!r}"
        assert self.contrarian_classification in CONTRARIAN_CLASSIFICATIONS, \
            f"Invalid contrarian_classification: {self.contrarian_classification!r}"
        assert self.confidence_label in CONFIDENCE_LABELS, \
            f"Invalid confidence_label: {self.confidence_label!r}"
        assert self.risk_level in RISK_LEVELS, \
            f"Invalid risk_level: {self.risk_level!r}"
        assert self.market_quality in MARKET_QUALITY, \
            f"Invalid market_quality: {self.market_quality!r}"

        for field_name, text in [
            ("human_headline", self.human_headline),
            ("human_body", self.human_body),
            ("key_risk_statement", self.key_risk_statement),
        ]:
            violations = check_language(text)
            assert not violations, (
                f"Forbidden language in {field_name} for "
                f"{self.match_id}/{self.market_type}/{self.selection}: {violations}"
            )

    def to_dict(self) -> dict:
        return {
            "thesis_id":                  self.thesis_id,
            "match_id":                   self.match_id,
            "generated_at":               self.generated_at,
            "model_version":              self.model_version,
            "data_stage":                 self.data_stage,
            "market_type":                self.market_type,
            "selection":                  self.selection,
            "line":                       self.line,
            "model_probability":          round(self.model_probability, 4),
            "market_implied_probability": (
                round(self.market_implied_probability, 4)
                if self.market_implied_probability is not None else None
            ),
            "raw_edge":       (round(self.raw_edge, 4)   if self.raw_edge   is not None else None),
            "edge_pct":       (round(self.edge_pct, 2)   if self.edge_pct   is not None else None),
            "fair_odds":      round(self.fair_odds, 2),
            "market_quality": self.market_quality,
            "contrarian_classification": self.contrarian_classification,
            "contrarian_score":          round(self.contrarian_score, 3),
            "confidence_score":          round(self.confidence_score, 3),
            "confidence_label":          self.confidence_label,
            "risk_level":                self.risk_level,
            "supporting_factors":        self.supporting_factors,
            "counter_factors":           self.counter_factors,
            "active_game_scripts":       self.active_game_scripts,
            "active_causal_chains":      self.active_causal_chains,
            "human_headline":            self.human_headline,
            "human_body":                self.human_body,
            "key_risk_statement":        self.key_risk_statement,
            "opportunity_score":         self.opportunity_score,
            "rank":                      self.rank,
            "display_tier":              self.display_tier,
        }


@dataclass
class MatchThesisSummary:
    """Top-level per-match thesis summary."""
    match_id: str
    home_team: str
    away_team: str
    group: str
    n_theses_generated: int
    n_featured: int
    n_secondary: int
    n_watchlist: int
    n_hidden: int
    top_opportunity_score: int
    has_market_data: bool
    no_opportunity_reason: str      # non-empty when no featured/secondary/watchlist
    top_thesis: Optional[dict]      # to_dict() of rank=1 thesis, or None
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "match_id":              self.match_id,
            "home_team":             self.home_team,
            "away_team":             self.away_team,
            "group":                 self.group,
            "n_theses_generated":    self.n_theses_generated,
            "n_featured":            self.n_featured,
            "n_secondary":           self.n_secondary,
            "n_watchlist":           self.n_watchlist,
            "n_hidden":              self.n_hidden,
            "top_opportunity_score": self.top_opportunity_score,
            "has_market_data":       self.has_market_data,
            "no_opportunity_reason": self.no_opportunity_reason,
            "top_thesis":            self.top_thesis,
            "generated_at":          self.generated_at,
        }
