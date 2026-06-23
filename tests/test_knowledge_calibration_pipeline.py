"""Tests for oracle.pipeline.knowledge_calibration — artifact generation."""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch


class TestKnowledgeCalibrationPipeline:
    def test_pipeline_writes_all_six_artifacts(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()

        expected = [
            "knowledge_chain_performance.json",
            "knowledge_script_performance.json",
            "knowledge_manager_performance.json",
            "knowledge_archetype_performance.json",
            "knowledge_weights.json",
            "knowledge_calibration_summary.json",
        ]
        for fname in expected:
            assert (tmp_path / fname).exists(), f"Missing: {fname}"

    def test_chain_performance_is_list(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        data = json.loads((tmp_path / "knowledge_chain_performance.json").read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_script_performance_is_list(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        data = json.loads((tmp_path / "knowledge_script_performance.json").read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_manager_performance_is_list(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        data = json.loads((tmp_path / "knowledge_manager_performance.json").read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_archetype_performance_is_list(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        data = json.loads((tmp_path / "knowledge_archetype_performance.json").read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_weights_has_expected_structure(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        weights = json.loads((tmp_path / "knowledge_weights.json").read_text())
        assert "chains" in weights
        assert "scripts" in weights
        assert "managers" in weights
        assert "archetypes" in weights
        assert "meta" in weights

    def test_weights_no_zero_values(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        weights = json.loads((tmp_path / "knowledge_weights.json").read_text())
        for section in ("chains", "scripts", "archetypes"):
            for k, v in weights[section].items():
                assert v > 0.0, f"{section}[{k}] = {v}"

    def test_weights_bounded(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        weights = json.loads((tmp_path / "knowledge_weights.json").read_text())
        for section in ("chains", "scripts", "archetypes"):
            for k, v in weights[section].items():
                assert 0.50 <= v <= 1.50, f"{section}[{k}] = {v} out of bounds"

    def test_summary_has_required_fields(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        summary = json.loads((tmp_path / "knowledge_calibration_summary.json").read_text())
        for field in (
            "stage", "evidence_source", "total_chains_evaluated",
            "avg_knowledge_value_score", "top_chains", "recommendations", "notes",
        ):
            assert field in summary, f"Missing field: {field}"

    def test_summary_stage_is_stage1(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        summary = json.loads((tmp_path / "knowledge_calibration_summary.json").read_text())
        assert summary["stage"] == "stage_1"

    def test_summary_has_recommendations(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        summary = json.loads((tmp_path / "knowledge_calibration_summary.json").read_text())
        assert isinstance(summary["recommendations"], list)
        assert len(summary["recommendations"]) > 0

    def test_chain_performance_required_fields(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        data = json.loads((tmp_path / "knowledge_chain_performance.json").read_text())
        required = {"chain_id", "name", "activations", "hit_rate", "value_score", "weight"}
        for item in data:
            missing = required - set(item.keys())
            assert not missing, f"Missing keys: {missing}"

    def test_avg_value_score_reasonable(self, tmp_path):
        import oracle.pipeline.knowledge_calibration as kc_pipe
        with patch.object(kc_pipe, "_ARTIFACTS", tmp_path):
            kc_pipe.run()
        summary = json.loads((tmp_path / "knowledge_calibration_summary.json").read_text())
        avg = summary["avg_knowledge_value_score"]
        assert 0.0 <= avg <= 100.0


class TestConfidenceCap:
    """Test that confidence adjustment is capped at ±0.10."""

    def test_weight_adjusted_confidence_capped(self):
        import json
        from oracle.thesis.generator import _enrich_thesis_with_knowledge
        from oracle.thesis.schema import BettingThesis

        thesis = BettingThesis(
            thesis_id="cap_test", match_id="test", generated_at="2026-06-21T00:00:00Z",
            model_version="v1", data_stage="stage_1",
            market_type="match_result", selection="home", line=None,
            model_probability=0.45, market_implied_probability=0.38,
            raw_edge=0.07, edge_pct=7.0, fair_odds=2.22,
            market_quality="sufficient", contrarian_classification="moderate_edge",
            contrarian_score=0.175, confidence_score=0.62, confidence_label="medium",
            risk_level="low",
            supporting_factors=json.dumps([]),
            counter_factors=json.dumps([]),
            active_game_scripts=json.dumps([]),
            active_causal_chains=json.dumps([]),
            human_headline="Test headline",
            human_body="Test body.",
            key_risk_statement="Test risk.",
            opportunity_score=55, rank=1, display_tier="watchlist",
        )

        # Activation with high knowledge confidence to trigger adjustment
        from oracle.knowledge.resolver import resolve_knowledge_for_match
        activation = resolve_knowledge_for_match(
            "test", "spain", "brazil", "2026-06-21T00:00:00Z"
        ).to_dict()

        # Apply very aggressive weights (weight=1.50 = max)
        high_weights = {
            "chains":  {"C-03": 1.50, "G-07": 1.50},
            "scripts": {"tactical_neutralization": 1.50},
        }

        original_conf = thesis.confidence_score
        _enrich_thesis_with_knowledge(thesis, activation, high_weights)

        # Adjustment must not exceed ±0.10
        delta = abs(thesis.confidence_score - original_conf)
        assert delta <= 0.10 + 1e-9, f"Confidence adjusted by {delta:.3f}, exceeds cap of 0.10"

    def test_probability_unchanged_after_enrichment(self):
        import json
        from oracle.thesis.generator import _enrich_thesis_with_knowledge
        from oracle.thesis.schema import BettingThesis
        from oracle.knowledge.resolver import resolve_knowledge_for_match

        thesis = BettingThesis(
            thesis_id="prob_test", match_id="test", generated_at="2026-06-21T00:00:00Z",
            model_version="v1", data_stage="stage_1",
            market_type="match_result", selection="home", line=None,
            model_probability=0.55, market_implied_probability=0.45,
            raw_edge=0.10, edge_pct=10.0, fair_odds=1.82,
            market_quality="sufficient", contrarian_classification="moderate_edge",
            contrarian_score=0.25, confidence_score=0.70, confidence_label="high",
            risk_level="low",
            supporting_factors=json.dumps([]),
            counter_factors=json.dumps([]),
            active_game_scripts=json.dumps([]),
            active_causal_chains=json.dumps([]),
            human_headline="Test",
            human_body="Test body.",
            key_risk_statement="Test risk.",
            opportunity_score=60, rank=1, display_tier="featured",
        )
        original_prob = thesis.model_probability
        activation = resolve_knowledge_for_match(
            "test", "argentina", "france", "2026-06-21T00:00:00Z"
        ).to_dict()
        _enrich_thesis_with_knowledge(thesis, activation, {})
        assert thesis.model_probability == original_prob
