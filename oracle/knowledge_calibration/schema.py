"""
Calibration data models — Week 26.

All dataclasses represent measured (or seed-estimated) performance of
knowledge components. evidence_source distinguishes seed from measured data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


EVIDENCE_STRENGTHS = ("strong", "moderate", "weak", "insufficient")
EVIDENCE_SOURCES   = ("seed_v1", "measured")


@dataclass
class ChainPerformance:
    chain_id: str
    name: str
    activations: int                # total activation events in evaluated corpus
    activation_rate: float          # activations / total_matches_evaluated
    average_confidence: float       # mean confidence at activation time
    hit_rate: float                 # fraction where predicted market signal proved correct
    calibration_score: float        # 1 - abs(average_confidence - hit_rate), 0–1
    brier_delta: float              # improvement over uniform baseline (negative = better)
    rps_delta: float                # RPS improvement over uniform baseline
    logloss_delta: float            # log-loss improvement over baseline
    thesis_success_rate: float      # fraction of theses using this chain that hit display tier
    uncertainty_rate: float         # fraction of activations with insufficient evidence
    value_score: float              # KnowledgeValueScore 0–100
    weight: float                   # adaptive weight 0.50–1.50
    evidence_quality: str           # one of EVIDENCE_STRENGTHS
    evidence_source: str            # "seed_v1" | "measured"
    stage: str
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "chain_id":             self.chain_id,
            "name":                 self.name,
            "activations":          self.activations,
            "activation_rate":      round(self.activation_rate, 4),
            "average_confidence":   round(self.average_confidence, 4),
            "hit_rate":             round(self.hit_rate, 4),
            "calibration_score":    round(self.calibration_score, 4),
            "brier_delta":          round(self.brier_delta, 4),
            "rps_delta":            round(self.rps_delta, 4),
            "logloss_delta":        round(self.logloss_delta, 4),
            "thesis_success_rate":  round(self.thesis_success_rate, 4),
            "uncertainty_rate":     round(self.uncertainty_rate, 4),
            "value_score":          round(self.value_score, 1),
            "weight":               round(self.weight, 4),
            "evidence_quality":     self.evidence_quality,
            "evidence_source":      self.evidence_source,
            "stage":                self.stage,
            "generated_at":         self.generated_at,
        }


@dataclass
class ScriptPerformance:
    script_id: str
    display_name: str
    activations: int
    frequency: float                # mean probability assigned across all activations
    hit_rate: float                 # proxy: fraction where script-aligned market moved correctly
    confidence_accuracy: float      # 1 - mean(abs(assigned_prob - base_probability))
    market_alignment: float         # fraction of market signals aligned with script direction
    thesis_success_rate: float
    volatility_accuracy: float      # does reported volatility match observed outcome volatility
    value_score: float
    weight: float
    evidence_quality: str
    evidence_source: str
    stage: str
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "script_id":            self.script_id,
            "display_name":         self.display_name,
            "activations":          self.activations,
            "frequency":            round(self.frequency, 4),
            "hit_rate":             round(self.hit_rate, 4),
            "confidence_accuracy":  round(self.confidence_accuracy, 4),
            "market_alignment":     round(self.market_alignment, 4),
            "thesis_success_rate":  round(self.thesis_success_rate, 4),
            "volatility_accuracy":  round(self.volatility_accuracy, 4),
            "value_score":          round(self.value_score, 1),
            "weight":               round(self.weight, 4),
            "evidence_quality":     self.evidence_quality,
            "evidence_source":      self.evidence_source,
            "stage":                self.stage,
            "generated_at":         self.generated_at,
        }


@dataclass
class ManagerPerformance:
    manager_id: str
    manager_name: str
    team_id: str
    pattern_id: str
    activations: int
    observed_hit_rate: float        # fraction of activations where pattern held
    confidence_accuracy: float
    thesis_success_rate: float
    volatility: str                 # "low" | "medium" | "high"
    value_score: float
    weight: float
    evidence_quality: str
    evidence_source: str
    stage: str
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "manager_id":           self.manager_id,
            "manager_name":         self.manager_name,
            "team_id":              self.team_id,
            "pattern_id":           self.pattern_id,
            "activations":          self.activations,
            "observed_hit_rate":    round(self.observed_hit_rate, 4),
            "confidence_accuracy":  round(self.confidence_accuracy, 4),
            "thesis_success_rate":  round(self.thesis_success_rate, 4),
            "volatility":           self.volatility,
            "value_score":          round(self.value_score, 1),
            "weight":               round(self.weight, 4),
            "evidence_quality":     self.evidence_quality,
            "evidence_source":      self.evidence_source,
            "stage":                self.stage,
            "generated_at":         self.generated_at,
        }


@dataclass
class ArchetypePerformance:
    archetype_id: str
    display_name: str
    activations: int
    win_rate: float
    draw_rate: float
    loss_rate: float
    over_rate: float                # over 2.5 goals rate when archetype is home team
    under_rate: float
    btts_rate: float
    signal_success_rate: float      # fraction of archetype-driven thesis signals that hit
    value_score: float
    weight: float
    evidence_quality: str
    evidence_source: str
    stage: str
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "archetype_id":         self.archetype_id,
            "display_name":         self.display_name,
            "activations":          self.activations,
            "win_rate":             round(self.win_rate, 4),
            "draw_rate":            round(self.draw_rate, 4),
            "loss_rate":            round(self.loss_rate, 4),
            "over_rate":            round(self.over_rate, 4),
            "under_rate":           round(self.under_rate, 4),
            "btts_rate":            round(self.btts_rate, 4),
            "signal_success_rate":  round(self.signal_success_rate, 4),
            "value_score":          round(self.value_score, 1),
            "weight":               round(self.weight, 4),
            "evidence_quality":     self.evidence_quality,
            "evidence_source":      self.evidence_source,
            "stage":                self.stage,
            "generated_at":         self.generated_at,
        }


@dataclass
class KnowledgeValueScore:
    component_id: str
    component_type: str         # "chain" | "script" | "manager" | "archetype"
    raw_score: float            # 0–100 before penalties
    sample_penalty: float       # 0–20 reduction for small sample
    variance_penalty: float     # 0–10 reduction for high variance
    final_score: float          # 0–100 clamped
    confidence: str             # "high" | "medium" | "low" | "insufficient"

    def to_dict(self) -> dict:
        return {
            "component_id":   self.component_id,
            "component_type": self.component_type,
            "raw_score":      round(self.raw_score, 1),
            "sample_penalty": round(self.sample_penalty, 1),
            "variance_penalty": round(self.variance_penalty, 1),
            "final_score":    round(self.final_score, 1),
            "confidence":     self.confidence,
        }


@dataclass
class KnowledgeCalibrationSummary:
    generated_at: str
    stage: str
    evidence_source: str
    total_chains_evaluated: int
    total_scripts_evaluated: int
    total_managers_evaluated: int
    total_archetypes_evaluated: int
    avg_knowledge_value_score: float
    avg_chain_weight: float
    avg_script_weight: float
    avg_manager_weight: float
    avg_archetype_weight: float
    top_chains: list[dict]
    weakest_chains: list[dict]
    strongest_scripts: list[dict]
    weakest_scripts: list[dict]
    strongest_managers: list[dict]
    weakest_managers: list[dict]
    strongest_archetypes: list[dict]
    weakest_archetypes: list[dict]
    recommendations: list[str]
    notes: str

    def to_dict(self) -> dict:
        return {
            "generated_at":                self.generated_at,
            "stage":                       self.stage,
            "evidence_source":             self.evidence_source,
            "total_chains_evaluated":      self.total_chains_evaluated,
            "total_scripts_evaluated":     self.total_scripts_evaluated,
            "total_managers_evaluated":    self.total_managers_evaluated,
            "total_archetypes_evaluated":  self.total_archetypes_evaluated,
            "avg_knowledge_value_score":   round(self.avg_knowledge_value_score, 1),
            "avg_chain_weight":            round(self.avg_chain_weight, 4),
            "avg_script_weight":           round(self.avg_script_weight, 4),
            "avg_manager_weight":          round(self.avg_manager_weight, 4),
            "avg_archetype_weight":        round(self.avg_archetype_weight, 4),
            "top_chains":                  self.top_chains,
            "weakest_chains":              self.weakest_chains,
            "strongest_scripts":           self.strongest_scripts,
            "weakest_scripts":             self.weakest_scripts,
            "strongest_managers":          self.strongest_managers,
            "weakest_managers":            self.weakest_managers,
            "strongest_archetypes":        self.strongest_archetypes,
            "weakest_archetypes":          self.weakest_archetypes,
            "recommendations":             self.recommendations,
            "notes":                       self.notes,
        }
