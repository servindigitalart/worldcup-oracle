"""Tests for oracle.knowledge_calibration.archetypes — archetype performance."""
from __future__ import annotations

import pytest
from oracle.knowledge_calibration.archetypes import evaluate_archetypes
from oracle.knowledge_calibration.schema import ArchetypePerformance


class TestEvaluateArchetypes:
    def test_returns_list(self):
        results = evaluate_archetypes()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_items_are_archetype_performance(self):
        results = evaluate_archetypes()
        assert all(isinstance(a, ArchetypePerformance) for a in results)

    def test_sorted_by_value_score_descending(self):
        results = evaluate_archetypes()
        scores = [a.value_score for a in results]
        assert scores == sorted(scores, reverse=True)

    def test_major_archetypes_present(self):
        results = evaluate_archetypes()
        ids = {a.archetype_id for a in results}
        for aid in ("possession_control", "counter_attack", "high_press", "low_block"):
            assert aid in ids

    def test_rates_sum_to_one(self):
        results = evaluate_archetypes()
        for a in results:
            total = a.win_rate + a.draw_rate + a.loss_rate
            assert abs(total - 1.0) < 0.01, f"{a.archetype_id}: rates sum {total}"

    def test_over_under_bounded(self):
        results = evaluate_archetypes()
        for a in results:
            assert 0.0 <= a.over_rate <= 1.0
            assert 0.0 <= a.under_rate <= 1.0

    def test_btts_rate_bounded(self):
        results = evaluate_archetypes()
        for a in results:
            assert 0.0 <= a.btts_rate <= 1.0

    def test_weights_in_range(self):
        results = evaluate_archetypes()
        for a in results:
            assert 0.50 <= a.weight <= 1.50

    def test_no_zero_weights(self):
        results = evaluate_archetypes()
        for a in results:
            assert a.weight > 0.0

    def test_value_scores_bounded(self):
        results = evaluate_archetypes()
        for a in results:
            assert 0.0 <= a.value_score <= 100.0

    def test_possession_control_higher_score_than_unknown(self):
        results = evaluate_archetypes()
        by_id = {a.archetype_id: a for a in results}
        if "possession_control" in by_id and "unknown" in by_id:
            assert by_id["possession_control"].value_score > by_id["unknown"].value_score

    def test_low_block_under_rate_high(self):
        results = evaluate_archetypes()
        by_id = {a.archetype_id: a for a in results}
        if "low_block" in by_id:
            lb = by_id["low_block"]
            # Low block teams should produce high under rate
            assert lb.under_rate > lb.over_rate

    def test_evidence_source_seed(self):
        results = evaluate_archetypes()
        for a in results:
            assert a.evidence_source == "seed_v1"

    def test_to_dict_json_serialisable(self):
        import json
        results = evaluate_archetypes()
        for a in results:
            json.dumps(a.to_dict())
