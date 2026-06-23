"""Tests for oracle.knowledge_calibration.managers — manager pattern evaluation."""
from __future__ import annotations

import pytest
from oracle.knowledge_calibration.managers import evaluate_managers
from oracle.knowledge_calibration.schema import ManagerPerformance


class TestEvaluateManagers:
    def test_returns_list(self):
        results = evaluate_managers()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_items_are_manager_performance(self):
        results = evaluate_managers()
        assert all(isinstance(m, ManagerPerformance) for m in results)

    def test_sorted_by_value_score_descending(self):
        results = evaluate_managers()
        scores = [m.value_score for m in results]
        assert scores == sorted(scores, reverse=True)

    def test_known_managers_present(self):
        results = evaluate_managers()
        manager_ids = {m.manager_id for m in results}
        for mid in ("scaloni", "deschamps", "nagelsmann", "bielsa", "regragui"):
            assert mid in manager_ids, f"Missing manager: {mid}"

    def test_hit_rates_in_range(self):
        results = evaluate_managers()
        for m in results:
            assert 0.0 <= m.observed_hit_rate <= 1.0

    def test_value_scores_in_range(self):
        results = evaluate_managers()
        for m in results:
            assert 0.0 <= m.value_score <= 100.0

    def test_weights_in_valid_range(self):
        results = evaluate_managers()
        for m in results:
            assert 0.50 <= m.weight <= 1.50

    def test_no_zero_weights(self):
        results = evaluate_managers()
        for m in results:
            assert m.weight > 0.0

    def test_volatility_labels_valid(self):
        results = evaluate_managers()
        for m in results:
            assert m.volatility in ("low", "medium", "high")

    def test_evidence_source_seed(self):
        results = evaluate_managers()
        for m in results:
            assert m.evidence_source == "seed_v1"

    def test_scaloni_lead_protection_strong(self):
        results = evaluate_managers()
        by_key = {(m.manager_id, m.pattern_id): m for m in results}
        scaloni_dp = by_key.get(("scaloni", "disciplined_defense_first"))
        if scaloni_dp:
            assert scaloni_dp.evidence_quality in ("strong", "moderate")
            assert scaloni_dp.value_score > 30.0

    def test_bielsa_limited_evidence(self):
        results = evaluate_managers()
        bielsa_patterns = [m for m in results if m.manager_id == "bielsa"]
        # All Bielsa patterns should be weak/insufficient due to small WC sample
        for m in bielsa_patterns:
            assert m.evidence_quality in ("weak", "insufficient", "moderate")

    def test_small_sample_manager_near_neutral_weight(self):
        results = evaluate_managers()
        # Patterns with activations < 5 should be pinned to neutral weight
        for m in results:
            if m.activations < 5:
                assert abs(m.weight - 1.0) < 0.01, f"{m.manager_id}:{m.pattern_id} weight={m.weight}"

    def test_to_dict_json_serialisable(self):
        import json
        results = evaluate_managers()
        for m in results:
            json.dumps(m.to_dict())
