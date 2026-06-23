"""Tests for oracle/knowledge_learning/updater.py"""
import pytest
from oracle.knowledge_learning.updater import (
    compute_single_update,
    compute_weight_updates,
    bootstrap_from_calibration,
    evidence_influence,
    _evidence_strength,
)
from oracle.knowledge_learning.schema import ContributionScore


# ── evidence_influence ────────────────────────────────────────────────────────

def test_alpha_minimal_sample():
    assert evidence_influence(0) == pytest.approx(0.02)
    assert evidence_influence(4) == pytest.approx(0.02)


def test_alpha_small_sample():
    assert evidence_influence(5)  == pytest.approx(0.05)
    assert evidence_influence(19) == pytest.approx(0.05)


def test_alpha_moderate_sample():
    assert evidence_influence(20) == pytest.approx(0.10)
    assert evidence_influence(49) == pytest.approx(0.10)


def test_alpha_full_sample():
    assert evidence_influence(50)  == pytest.approx(0.20)
    assert evidence_influence(200) == pytest.approx(0.20)


# ── _evidence_strength ────────────────────────────────────────────────────────

def test_evidence_strength_minimal():
    assert _evidence_strength(0) == "minimal"


def test_evidence_strength_small():
    assert _evidence_strength(10) == "small"


def test_evidence_strength_moderate():
    assert _evidence_strength(30) == "moderate"


def test_evidence_strength_full():
    assert _evidence_strength(100) == "full"


# ── compute_single_update ─────────────────────────────────────────────────────

def _contrib(score, cid="C-03", ctype="chain", mid="m01"):
    return ContributionScore(
        component_id=cid,
        component_type=ctype,
        match_id=mid,
        raw_score=score,
        confidence=0.70,
        direction="supported" if score > 0 else "contradicted",
        market_type="match_result",
        explanation="test",
    )


def test_single_update_no_evidence():
    u = compute_single_update("C-03", "chain", 1.21, 1.21, [])
    assert u.delta == 0.0
    assert u.new_weight == u.old_weight
    assert u.evidence_count == 0


def test_single_update_positive_contribution_increases_weight():
    contributions = [_contrib(0.5)] * 10
    u = compute_single_update("C-03", "chain", 1.00, 1.10, contributions)
    assert u.delta > 0
    assert u.new_weight > u.old_weight


def test_single_update_negative_contribution_decreases_weight():
    contributions = [_contrib(-0.5)] * 10
    u = compute_single_update("C-03", "chain", 1.00, 0.90, contributions)
    assert u.delta <= 0
    assert u.new_weight <= u.old_weight


def test_single_update_delta_capped_at_0_03():
    # Even very strong contribution, delta should be ≤ 0.03
    contributions = [_contrib(1.0)] * 100
    u = compute_single_update("C-03", "chain", 0.50, 1.50, contributions)
    assert abs(u.delta) <= 0.03


def test_single_update_weight_clamped_to_min():
    contributions = [_contrib(-1.0)] * 100
    u = compute_single_update("C-03", "chain", 0.51, 0.50, contributions)
    assert u.new_weight >= 0.50


def test_single_update_weight_clamped_to_max():
    contributions = [_contrib(1.0)] * 100
    u = compute_single_update("C-03", "chain", 1.49, 1.50, contributions)
    assert u.new_weight <= 1.50


def test_single_update_fields_populated():
    contributions = [_contrib(0.3)] * 5
    u = compute_single_update("C-03", "chain", 1.10, 1.15, contributions)
    assert u.component_id == "C-03"
    assert u.component_type == "chain"
    assert u.evidence_count == 5
    assert u.evidence_strength == "small"
    assert u.source == "live"
    assert u.reason != ""


# ── compute_weight_updates ────────────────────────────────────────────────────

def test_compute_weight_updates_groups_by_component():
    contributions = [
        _contrib(0.5, "C-03", "chain"),
        _contrib(0.3, "G-07", "chain"),
        _contrib(0.4, "defensive_siege", "script"),
    ]
    cal_w = {"chains": {"C-03": 1.21, "G-07": 1.15}, "scripts": {"defensive_siege": 1.05}}
    updates = compute_weight_updates(contributions, cal_w)
    assert len(updates) == 3
    ids = {u.component_id for u in updates}
    assert "C-03" in ids
    assert "G-07" in ids
    assert "defensive_siege" in ids


def test_compute_weight_updates_empty_contributions():
    updates = compute_weight_updates([], {"chains": {"C-03": 1.21}})
    assert updates == []


def test_compute_weight_updates_uses_calibration_weight_as_baseline():
    contributions = [_contrib(0.0, "C-03", "chain")]  # neutral
    cal_w = {"chains": {"C-03": 1.21}}
    updates = compute_weight_updates(contributions, cal_w)
    # With zero contribution, new weight should equal old weight (neutral)
    u = updates[0]
    assert abs(u.delta) < 0.005


# ── bootstrap_from_calibration ────────────────────────────────────────────────

def test_bootstrap_generates_updates():
    cal_w = {"chains": {"C-03": 1.21}, "scripts": {"defensive_siege": 1.05}}
    updates = bootstrap_from_calibration(cal_w)
    assert len(updates) > 0


def test_bootstrap_creates_three_epochs():
    cal_w = {"chains": {"C-03": 1.21}}
    updates = bootstrap_from_calibration(cal_w)
    sources = {u.source for u in updates}
    assert "bootstrap_2014" in sources
    assert "bootstrap_2018" in sources
    assert "bootstrap_2022" in sources


def test_bootstrap_final_weight_approaches_calibration():
    cal_w = {"chains": {"C-03": 1.30}}
    updates = bootstrap_from_calibration(cal_w, epochs=("bootstrap_2014", "bootstrap_2018", "bootstrap_2022"))
    chain_updates = [u for u in updates if u.component_id == "C-03"]
    assert len(chain_updates) == 3
    # Final weight should be between 1.0 and 1.30 but approaching 1.30
    final = chain_updates[-1].new_weight
    assert 1.0 <= final <= 1.30


def test_bootstrap_all_weights_in_bounds():
    cal_w = {
        "chains":     {"C-03": 1.21, "G-07": 0.85},
        "scripts":    {"defensive_siege": 1.05},
        "managers":   {"southgate:defensive_setup": 0.95},
        "archetypes": {"possession_control": 1.12},
    }
    updates = bootstrap_from_calibration(cal_w)
    for u in updates:
        assert 0.50 <= u.new_weight <= 1.50, f"{u.component_id}: {u.new_weight}"
        assert abs(u.delta) <= 0.03, f"{u.component_id}: delta={u.delta}"
