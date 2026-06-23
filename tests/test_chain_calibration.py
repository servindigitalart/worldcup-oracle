"""Tests for oracle.knowledge_calibration.chains — chain performance evaluation."""
from __future__ import annotations

import pytest
from oracle.knowledge_calibration.chains import evaluate_chains
from oracle.knowledge_calibration.schema import ChainPerformance


class TestEvaluateChains:
    def test_returns_list_of_chain_performance(self):
        results = evaluate_chains()
        assert isinstance(results, list)
        assert all(isinstance(c, ChainPerformance) for c in results)

    def test_all_stage1_chains_evaluated(self):
        from oracle.knowledge.chains import CHAINS
        results = evaluate_chains()
        ids = {c.chain_id for c in results}
        for chain_id in CHAINS:
            assert chain_id in ids, f"Missing evaluation for {chain_id}"

    def test_sorted_by_value_score_descending(self):
        results = evaluate_chains()
        scores = [c.value_score for c in results]
        assert scores == sorted(scores, reverse=True)

    def test_hit_rates_in_range(self):
        results = evaluate_chains()
        for c in results:
            assert 0.0 <= c.hit_rate <= 1.0, f"{c.chain_id}: hit_rate={c.hit_rate}"

    def test_value_scores_in_range(self):
        results = evaluate_chains()
        for c in results:
            assert 0.0 <= c.value_score <= 100.0, f"{c.chain_id}: score={c.value_score}"

    def test_weights_in_range(self):
        results = evaluate_chains()
        for c in results:
            assert 0.50 <= c.weight <= 1.50, f"{c.chain_id}: weight={c.weight}"

    def test_no_zero_weights(self):
        results = evaluate_chains()
        for c in results:
            assert c.weight > 0.0, f"{c.chain_id} has zero weight"

    def test_evidence_source_is_seed(self):
        results = evaluate_chains()
        for c in results:
            assert c.evidence_source == "seed_v1"

    def test_stage_is_stage1(self):
        results = evaluate_chains()
        for c in results:
            assert c.stage == "stage_1"

    def test_calibration_scores_in_range(self):
        results = evaluate_chains()
        for c in results:
            assert 0.0 <= c.calibration_score <= 1.0, f"{c.chain_id}: cal={c.calibration_score}"

    def test_strong_evidence_chains_have_higher_scores(self):
        results = evaluate_chains()
        by_quality = {c.chain_id: c for c in results}
        # G-07 (Low Block Stalemate) and C-03 (Possession → Corners) are strong evidence
        if "G-07" in by_quality and "S-07" in by_quality:
            assert by_quality["G-07"].value_score > by_quality["S-07"].value_score

    def test_insufficient_evidence_chain_has_low_score(self):
        results = evaluate_chains()
        s07 = next((c for c in results if c.chain_id == "S-07"), None)
        if s07:
            assert s07.value_score < 40.0, f"S-07 should have low score, got {s07.value_score}"

    def test_insufficient_evidence_weight_near_neutral(self):
        results = evaluate_chains()
        s07 = next((c for c in results if c.chain_id == "S-07"), None)
        if s07:
            # Insufficient evidence: weight should be close to neutral (1.0)
            assert 0.60 <= s07.weight <= 1.10, f"S-07 weight should be near-neutral: {s07.weight}"

    def test_to_dict_is_serialisable(self):
        import json
        results = evaluate_chains()
        for c in results:
            json.dumps(c.to_dict())  # should not raise

    def test_uncertainty_rate_in_range(self):
        results = evaluate_chains()
        for c in results:
            assert 0.0 <= c.uncertainty_rate <= 1.0


class TestSmallSampleHandling:
    def test_small_sample_reduces_value_score(self):
        from oracle.knowledge_calibration.scoring import compute_value_score
        # Same hit rate but different samples: small sample gets lower score
        high_sample = compute_value_score("x", "chain", 40, 0.72, 0.98, 0.82)
        low_sample  = compute_value_score("x", "chain",  3, 0.72, 0.98, 0.82)
        assert low_sample.final_score < high_sample.final_score

    def test_very_small_sample_gets_sample_penalty(self):
        from oracle.knowledge_calibration.scoring import compute_value_score
        vs = compute_value_score("x", "chain", 3, 0.72, 0.98, 0.82)
        assert vs.sample_penalty > 0.0

    def test_sufficient_sample_no_penalty(self):
        from oracle.knowledge_calibration.scoring import compute_value_score
        vs = compute_value_score("x", "chain", 15, 0.72, 0.98, 0.82)
        assert vs.sample_penalty == 0.0
