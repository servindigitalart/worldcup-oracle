"""
Knowledge Engine data models — Week 25E.

All dataclasses are JSON-serializable via .to_dict().
No Parquet requirement for knowledge activations (nested structure retained).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Team Identity ──────────────────────────────────────────────────────────────

@dataclass
class TeamIdentityProfile:
    team_id: str
    display_name: str
    primary_archetype: str          # e.g. "possession_control"
    secondary_archetype: str        # e.g. "set_piece_heavy"  or "none"
    identity_confidence: float      # 0.30–0.95
    tempo: str                      # "slow" | "medium" | "high" | "variable"
    possession_style: str           # "dominant" | "balanced" | "pragmatic" | "reactive"
    pressing_intensity: str         # "high" | "medium" | "low" | "variable"
    defensive_block: str            # "high_line" | "mid_block" | "low_block" | "variable"
    transition_tendency: str        # "quick" | "measured" | "hybrid"
    set_piece_reliance: str         # "high" | "medium" | "low"
    aerial_reliance: str            # "high" | "medium" | "low"
    risk_profile: str               # "aggressive" | "balanced" | "conservative"
    known_strengths: list[str]
    known_weaknesses: list[str]
    profile_source: str = "seed_v1"

    def to_dict(self) -> dict:
        return {
            "team_id":             self.team_id,
            "display_name":        self.display_name,
            "primary_archetype":   self.primary_archetype,
            "secondary_archetype": self.secondary_archetype,
            "identity_confidence": self.identity_confidence,
            "tempo":               self.tempo,
            "possession_style":    self.possession_style,
            "pressing_intensity":  self.pressing_intensity,
            "defensive_block":     self.defensive_block,
            "transition_tendency": self.transition_tendency,
            "set_piece_reliance":  self.set_piece_reliance,
            "aerial_reliance":     self.aerial_reliance,
            "risk_profile":        self.risk_profile,
            "known_strengths":     self.known_strengths,
            "known_weaknesses":    self.known_weaknesses,
            "profile_source":      self.profile_source,
        }


# ── Manager Profile ────────────────────────────────────────────────────────────

@dataclass
class ManagerProfile:
    manager_id: str
    name: str
    team_id: str
    profile_confidence: float
    preferred_style: str
    first_half_behavior: str     # "cautious" | "attacking" | "balanced"
    lead_behavior: str           # "protect" | "extend" | "variable"
    trailing_behavior: str       # "open_up" | "patient" | "panic"
    substitution_pattern: str    # "early" | "late" | "reactive"
    known_patterns: list[dict]   # [{pattern, supports_markets, confidence}]

    def to_dict(self) -> dict:
        return {
            "manager_id":          self.manager_id,
            "name":                self.name,
            "team_id":             self.team_id,
            "profile_confidence":  self.profile_confidence,
            "preferred_style":     self.preferred_style,
            "first_half_behavior": self.first_half_behavior,
            "lead_behavior":       self.lead_behavior,
            "trailing_behavior":   self.trailing_behavior,
            "substitution_pattern": self.substitution_pattern,
            "known_patterns":      self.known_patterns,
        }


# ── Tactical Archetype ─────────────────────────────────────────────────────────

@dataclass
class TacticalArchetype:
    archetype_id: str
    display_name: str
    description: str
    strengths: list[str]
    weaknesses: list[str]
    markets_affected: list[str]
    common_scripts: list[str]

    def to_dict(self) -> dict:
        return {
            "archetype_id":    self.archetype_id,
            "display_name":    self.display_name,
            "description":     self.description,
            "strengths":       self.strengths,
            "weaknesses":      self.weaknesses,
            "markets_affected": self.markets_affected,
            "common_scripts":  self.common_scripts,
        }


# ── Causal Chain ───────────────────────────────────────────────────────────────

@dataclass
class CausalChain:
    chain_id: str
    name: str
    trigger_description: str
    sequence: list[str]
    terminal_outcome: str
    markets_affected: list[str]
    base_confidence: float
    stage_required: str            # "stage_1" | "stage_2"
    explanation_snippet: str

    def to_dict(self) -> dict:
        return {
            "chain_id":            self.chain_id,
            "name":                self.name,
            "trigger_description": self.trigger_description,
            "sequence":            self.sequence,
            "terminal_outcome":    self.terminal_outcome,
            "markets_affected":    self.markets_affected,
            "base_confidence":     self.base_confidence,
            "stage_required":      self.stage_required,
            "explanation_snippet": self.explanation_snippet,
        }


# ── Game Script ────────────────────────────────────────────────────────────────

@dataclass
class GameScript:
    script_id: str
    display_name: str
    description: str
    trigger_conditions: list[str]
    markets_impacted: dict[str, str]  # {market: direction}  "up"/"down"/"neutral"
    volatility: str                   # "low" | "medium" | "high"
    base_probability: float

    def to_dict(self) -> dict:
        return {
            "script_id":         self.script_id,
            "display_name":      self.display_name,
            "description":       self.description,
            "trigger_conditions": self.trigger_conditions,
            "markets_impacted":  self.markets_impacted,
            "volatility":        self.volatility,
            "base_probability":  self.base_probability,
        }


# ── Activated Chain ────────────────────────────────────────────────────────────

@dataclass
class ActivatedChain:
    chain_id: str
    name: str
    activation_confidence: float
    markets_affected: list[str]
    explanation_snippet: str

    def to_dict(self) -> dict:
        return {
            "chain_id":             self.chain_id,
            "name":                 self.name,
            "activation_confidence": self.activation_confidence,
            "markets_affected":     self.markets_affected,
            "explanation_snippet":  self.explanation_snippet,
        }


# ── Activated Script ──────────────────────────────────────────────────────────

@dataclass
class ActivatedScript:
    script_id: str
    display_name: str
    probability: float
    markets_impacted: dict[str, str]
    volatility: str

    def to_dict(self) -> dict:
        return {
            "script_id":        self.script_id,
            "display_name":     self.display_name,
            "probability":      self.probability,
            "markets_impacted": self.markets_impacted,
            "volatility":       self.volatility,
        }


# ── Knowledge Activation ──────────────────────────────────────────────────────

@dataclass
class KnowledgeActivation:
    match_id: str
    home_team: str
    away_team: str
    home_archetype: str
    away_archetype: str
    home_confidence: float
    away_confidence: float
    activated_archetypes: list[str]
    activated_manager_patterns: list[dict]
    activated_chains: list[ActivatedChain]
    activated_scripts: list[ActivatedScript]
    supporting_context: list[str]
    counter_context: list[str]
    knowledge_confidence: float
    data_stage: str
    warnings: list[str]
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "match_id":                   self.match_id,
            "home_team":                  self.home_team,
            "away_team":                  self.away_team,
            "home_archetype":             self.home_archetype,
            "away_archetype":             self.away_archetype,
            "home_confidence":            self.home_confidence,
            "away_confidence":            self.away_confidence,
            "activated_archetypes":       self.activated_archetypes,
            "activated_manager_patterns": self.activated_manager_patterns,
            "activated_chains":           [c.to_dict() for c in self.activated_chains],
            "activated_scripts":          [s.to_dict() for s in self.activated_scripts],
            "supporting_context":         self.supporting_context,
            "counter_context":            self.counter_context,
            "knowledge_confidence":       self.knowledge_confidence,
            "data_stage":                 self.data_stage,
            "warnings":                   self.warnings,
            "generated_at":               self.generated_at,
        }
