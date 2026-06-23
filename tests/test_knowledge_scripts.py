"""Tests for oracle.knowledge.scripts — script estimation and normalisation."""
from __future__ import annotations

import pytest
from oracle.knowledge.scripts import estimate_scripts, SCRIPTS
from oracle.knowledge.schema import ActivatedScript


class TestEstimateScripts:
    def test_returns_activated_script_list(self):
        result = estimate_scripts("possession_control", "low_block")
        assert len(result) > 0
        assert all(isinstance(s, ActivatedScript) for s in result)

    def test_probabilities_sum_to_one(self):
        for home in ["possession_control", "counter_attack", "high_press", "unknown"]:
            for away in ["tournament_survival", "low_block", "counter_attack", "unknown"]:
                result = estimate_scripts(home, away)
                total = sum(s.probability for s in result)
                assert abs(total - 1.0) < 1e-6, f"{home} vs {away}: sum={total}"

    def test_sorted_descending(self):
        result = estimate_scripts("possession_control", "tournament_survival")
        probs = [s.probability for s in result]
        assert probs == sorted(probs, reverse=True)

    def test_possession_vs_low_block_includes_tactical_neutralization(self):
        result = estimate_scripts("possession_control", "low_block")
        ids = {s.script_id for s in result}
        assert "tactical_neutralization" in ids

    def test_possession_vs_tournament_survival_includes_defensive(self):
        result = estimate_scripts("possession_control", "tournament_survival")
        ids = {s.script_id for s in result}
        assert "tactical_neutralization" in ids or "defensive_siege" in ids

    def test_counter_vs_high_press_includes_counter_attack_trap(self):
        result = estimate_scripts("counter_attack", "high_press")
        ids = {s.script_id for s in result}
        assert "counter_attack_trap" in ids

    def test_unknown_vs_unknown_returns_default_distribution(self):
        result = estimate_scripts("unknown", "unknown")
        assert len(result) > 0
        total = sum(s.probability for s in result)
        assert abs(total - 1.0) < 1e-6

    def test_probabilities_nonnegative(self):
        result = estimate_scripts("high_press", "possession_control")
        for s in result:
            assert s.probability >= 0.0

    def test_all_script_ids_valid(self):
        valid_ids = set(SCRIPTS.keys())
        result = estimate_scripts("possession_control", "counter_attack")
        for s in result:
            assert s.script_id in valid_ids, f"Unknown script_id: {s.script_id}"


class TestScriptsDict:
    def test_all_scripts_have_volatility(self):
        for sid, script in SCRIPTS.items():
            assert script.volatility in {"low", "medium", "high"}, f"{sid}: {script.volatility}"

    def test_all_scripts_have_markets_impacted(self):
        for sid, script in SCRIPTS.items():
            assert isinstance(script.markets_impacted, dict)
