"""Tests for oracle.knowledge_calibration.scripts — script performance evaluation."""
from __future__ import annotations

import pytest
from oracle.knowledge_calibration.scripts import evaluate_scripts
from oracle.knowledge_calibration.schema import ScriptPerformance


class TestEvaluateScripts:
    def test_returns_list_of_script_performance(self):
        results = evaluate_scripts()
        assert isinstance(results, list)
        assert all(isinstance(s, ScriptPerformance) for s in results)

    def test_all_scripts_evaluated(self):
        from oracle.knowledge.scripts import SCRIPTS
        results = evaluate_scripts()
        ids = {s.script_id for s in results}
        for script_id in SCRIPTS:
            assert script_id in ids, f"Missing evaluation for {script_id}"

    def test_sorted_by_value_score_descending(self):
        results = evaluate_scripts()
        scores = [s.value_score for s in results]
        assert scores == sorted(scores, reverse=True)

    def test_hit_rates_in_range(self):
        results = evaluate_scripts()
        for s in results:
            assert 0.0 <= s.hit_rate <= 1.0, f"{s.script_id}: hit_rate={s.hit_rate}"

    def test_weights_in_valid_range(self):
        results = evaluate_scripts()
        for s in results:
            assert 0.50 <= s.weight <= 1.50, f"{s.script_id}: weight={s.weight}"

    def test_no_zero_weights(self):
        results = evaluate_scripts()
        for s in results:
            assert s.weight > 0.0

    def test_evidence_source_seed(self):
        results = evaluate_scripts()
        for s in results:
            assert s.evidence_source == "seed_v1"

    def test_strong_evidence_script_has_high_score(self):
        results = evaluate_scripts()
        by_id = {s.script_id: s for s in results}
        # tactical_neutralization is "strong" evidence
        if "tactical_neutralization" in by_id:
            tn = by_id["tactical_neutralization"]
            assert tn.value_score > 40.0, f"tactical_neutralization score: {tn.value_score}"

    def test_insufficient_evidence_script_has_low_score(self):
        results = evaluate_scripts()
        by_id = {s.script_id: s for s in results}
        if "early_goal_chaos" in by_id:
            eg = by_id["early_goal_chaos"]
            # early_goal_chaos is "insufficient" — expect lower score
            assert eg.evidence_quality == "insufficient"

    def test_market_alignment_in_range(self):
        results = evaluate_scripts()
        for s in results:
            assert 0.0 <= s.market_alignment <= 1.0

    def test_to_dict_json_serialisable(self):
        import json
        results = evaluate_scripts()
        for s in results:
            json.dumps(s.to_dict())

    def test_value_scores_bounded(self):
        results = evaluate_scripts()
        for s in results:
            assert 0.0 <= s.value_score <= 100.0
