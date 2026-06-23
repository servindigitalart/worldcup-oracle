"""
Learning system data models — Week 27.

Evidence = what Oracle believed before the match.
Outcome  = what actually happened.
Never mixed in the same record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


EVIDENCE_STRENGTHS = ("minimal", "small", "moderate", "full")
LEARNING_SOURCES   = ("bootstrap_2014", "bootstrap_2018", "bootstrap_2022", "live_2026")
CONTRIBUTION_DIRECTIONS = ("supported", "neutral", "contradicted")


@dataclass
class EvidenceEntry:
    """One evidence record per completed match — append-only."""
    entry_id: str
    match_id: str
    date: str
    home_team: str
    away_team: str
    activated_chain_ids: list[str]
    activated_script_ids: list[str]
    activated_manager_patterns: list[str]   # "manager_id:pattern_id"
    activated_archetype_ids: list[str]
    knowledge_confidence: float
    top_thesis_market: str
    top_opportunity_score: int
    data_source: str                         # one of LEARNING_SOURCES
    recorded_at: str

    def to_dict(self) -> dict:
        return {
            "entry_id":                   self.entry_id,
            "match_id":                   self.match_id,
            "date":                       self.date,
            "home_team":                  self.home_team,
            "away_team":                  self.away_team,
            "activated_chain_ids":        self.activated_chain_ids,
            "activated_script_ids":       self.activated_script_ids,
            "activated_manager_patterns": self.activated_manager_patterns,
            "activated_archetype_ids":    self.activated_archetype_ids,
            "knowledge_confidence":       round(self.knowledge_confidence, 4),
            "top_thesis_market":          self.top_thesis_market,
            "top_opportunity_score":      self.top_opportunity_score,
            "data_source":                self.data_source,
            "recorded_at":                self.recorded_at,
        }


@dataclass
class OutcomeRecord:
    """Observed result for a completed match — separate from evidence."""
    entry_id: str
    match_id: str
    outcome_1x2: str          # "home" | "draw" | "away"
    home_goals: int
    away_goals: int
    total_goals: int
    btts: bool
    over_1_5: bool
    over_2_5: bool
    over_3_5: bool
    correct_score: str        # "2-1" format
    thesis_hit: Optional[bool]
    market_aligned: Optional[bool]
    knowledge_aligned: Optional[bool]
    recorded_at: str

    def to_dict(self) -> dict:
        return {
            "entry_id":        self.entry_id,
            "match_id":        self.match_id,
            "outcome_1x2":     self.outcome_1x2,
            "home_goals":      self.home_goals,
            "away_goals":      self.away_goals,
            "total_goals":     self.total_goals,
            "btts":            self.btts,
            "over_1_5":        self.over_1_5,
            "over_2_5":        self.over_2_5,
            "over_3_5":        self.over_3_5,
            "correct_score":   self.correct_score,
            "thesis_hit":      self.thesis_hit,
            "market_aligned":  self.market_aligned,
            "knowledge_aligned": self.knowledge_aligned,
            "recorded_at":     self.recorded_at,
        }


@dataclass
class ContributionScore:
    """Whether a knowledge component helped for one match. Range: -1.0 to +1.0."""
    component_id: str
    component_type: str          # "chain" | "script" | "manager" | "archetype"
    match_id: str
    raw_score: float             # -1.0 to +1.0
    confidence: float            # activation confidence
    direction: str               # one of CONTRIBUTION_DIRECTIONS
    market_type: str
    explanation: str

    def to_dict(self) -> dict:
        return {
            "component_id":   self.component_id,
            "component_type": self.component_type,
            "match_id":       self.match_id,
            "raw_score":      round(self.raw_score, 4),
            "confidence":     round(self.confidence, 4),
            "direction":      self.direction,
            "market_type":    self.market_type,
            "explanation":    self.explanation,
        }


@dataclass
class WeightUpdate:
    """One weight update event per component per learning cycle."""
    component_id: str
    component_type: str
    old_weight: float
    new_weight: float
    delta: float
    evidence_count: int
    evidence_strength: str      # one of EVIDENCE_STRENGTHS
    mean_contribution: float
    reason: str
    timestamp: str
    source: str                 # "bootstrap" | "live" | "cycle_N"

    def to_dict(self) -> dict:
        return {
            "component_id":      self.component_id,
            "component_type":    self.component_type,
            "old_weight":        round(self.old_weight, 4),
            "new_weight":        round(self.new_weight, 4),
            "delta":             round(self.delta, 4),
            "evidence_count":    self.evidence_count,
            "evidence_strength": self.evidence_strength,
            "mean_contribution": round(self.mean_contribution, 4),
            "reason":            self.reason,
            "timestamp":         self.timestamp,
            "source":            self.source,
        }


@dataclass
class LearningHistoryEntry:
    """One row in the immutable audit trail per (component, timestamp)."""
    component_id: str
    component_type: str
    timestamp: str
    weight: float
    evidence_count: int
    cumulative_evidence: int
    stage: str                   # "bootstrap_2014" | "bootstrap_2018" | ... | "live"
    source: str
    delta: float = 0.0

    def to_dict(self) -> dict:
        return {
            "component_id":        self.component_id,
            "component_type":      self.component_type,
            "timestamp":           self.timestamp,
            "weight":              round(self.weight, 4),
            "evidence_count":      self.evidence_count,
            "cumulative_evidence": self.cumulative_evidence,
            "stage":               self.stage,
            "source":              self.source,
            "delta":               round(self.delta, 4),
        }
