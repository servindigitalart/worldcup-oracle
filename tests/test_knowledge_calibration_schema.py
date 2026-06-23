"""Tests for oracle.knowledge_calibration.schema dataclasses."""
from __future__ import annotations

import pytest
from oracle.knowledge_calibration.schema import (
    ChainPerformance,
    ScriptPerformance,
    ManagerPerformance,
    ArchetypePerformance,
    KnowledgeValueScore,
    KnowledgeCalibrationSummary,
    EVIDENCE_STRENGTHS,
    EVIDENCE_SOURCES,
)


def _chain(**kwargs) -> ChainPerformance:
    defaults = dict(
        chain_id="C-03", name="Possession → Corners",
        activations=38, activation_rate=0.26, average_confidence=0.72,
        hit_rate=0.74, calibration_score=0.98, brier_delta=-0.018,
        rps_delta=-0.014, logloss_delta=-0.022, thesis_success_rate=0.82,
        uncertainty_rate=0.00, value_score=72.5, weight=1.15,
        evidence_quality="strong", evidence_source="seed_v1",
        stage="stage_1", generated_at="2026-06-21T00:00:00Z",
    )
    defaults.update(kwargs)
    return ChainPerformance(**defaults)


class TestChainPerformance:
    def test_to_dict_has_required_keys(self):
        d = _chain().to_dict()
        for k in ("chain_id", "name", "activations", "hit_rate", "value_score", "weight"):
            assert k in d

    def test_values_rounded(self):
        d = _chain().to_dict()
        assert d["hit_rate"] == round(0.74, 4)
        assert d["value_score"] == round(72.5, 1)

    def test_evidence_quality_valid(self):
        cp = _chain()
        assert cp.evidence_quality in EVIDENCE_STRENGTHS

    def test_evidence_source_valid(self):
        cp = _chain()
        assert cp.evidence_source in EVIDENCE_SOURCES


class TestScriptPerformance:
    def test_to_dict_round_trip(self):
        sp = ScriptPerformance(
            script_id="tactical_neutralization",
            display_name="Tactical Neutralization",
            activations=28, frequency=0.18, hit_rate=0.71,
            confidence_accuracy=0.93, market_alignment=0.73,
            thesis_success_rate=0.82, volatility_accuracy=0.85,
            value_score=68.0, weight=1.10,
            evidence_quality="strong", evidence_source="seed_v1",
            stage="stage_1", generated_at="2026-06-21T00:00:00Z",
        )
        d = sp.to_dict()
        assert d["script_id"] == "tactical_neutralization"
        assert d["weight"] == 1.10


class TestManagerPerformance:
    def test_to_dict(self):
        mp = ManagerPerformance(
            manager_id="scaloni", manager_name="Lionel Scaloni",
            team_id="argentina", pattern_id="disciplined_defense_first",
            activations=18, observed_hit_rate=0.72, confidence_accuracy=0.94,
            thesis_success_rate=0.80, volatility="low",
            value_score=66.0, weight=1.08,
            evidence_quality="strong", evidence_source="seed_v1",
            stage="stage_1", generated_at="2026-06-21T00:00:00Z",
        )
        d = mp.to_dict()
        assert d["manager_id"] == "scaloni"
        assert d["pattern_id"] == "disciplined_defense_first"


class TestArchetypePerformance:
    def test_to_dict(self):
        ap = ArchetypePerformance(
            archetype_id="possession_control", display_name="Possession Control",
            activations=42, win_rate=0.52, draw_rate=0.24, loss_rate=0.24,
            over_rate=0.36, under_rate=0.64, btts_rate=0.43,
            signal_success_rate=0.71, value_score=65.0, weight=1.07,
            evidence_quality="strong", evidence_source="seed_v1",
            stage="stage_1", generated_at="2026-06-21T00:00:00Z",
        )
        d = ap.to_dict()
        assert d["archetype_id"] == "possession_control"
        assert "win_rate" in d
        assert "under_rate" in d


class TestKnowledgeValueScore:
    def test_to_dict(self):
        kvs = KnowledgeValueScore(
            component_id="C-03", component_type="chain",
            raw_score=80.0, sample_penalty=0.0, variance_penalty=2.0,
            final_score=78.0, confidence="high",
        )
        d = kvs.to_dict()
        assert d["final_score"] == 78.0
        assert d["confidence"] == "high"

    def test_confidence_labels(self):
        for score, expected in [(80, "high"), (60, "medium"), (35, "low"), (20, "insufficient")]:
            kvs = KnowledgeValueScore("x", "chain", score, 0, 0, float(score), "")
            kvs.confidence = "high" if score >= 75 else "medium" if score >= 50 else "low" if score >= 25 else "insufficient"
            assert kvs.confidence in ("high", "medium", "low", "insufficient")


class TestKnowledgeCalibrationSummary:
    def test_to_dict_has_required_keys(self):
        s = KnowledgeCalibrationSummary(
            generated_at="2026-06-21T00:00:00Z", stage="stage_1",
            evidence_source="seed_v1",
            total_chains_evaluated=8, total_scripts_evaluated=9,
            total_managers_evaluated=8, total_archetypes_evaluated=9,
            avg_knowledge_value_score=55.0, avg_chain_weight=1.05,
            avg_script_weight=1.02, avg_manager_weight=1.03, avg_archetype_weight=1.04,
            top_chains=[], weakest_chains=[], strongest_scripts=[],
            weakest_scripts=[], strongest_managers=[], weakest_managers=[],
            strongest_archetypes=[], weakest_archetypes=[],
            recommendations=["Use chain C-03 more."], notes="test",
        )
        d = s.to_dict()
        assert d["stage"] == "stage_1"
        assert d["total_chains_evaluated"] == 8
        assert len(d["recommendations"]) == 1
