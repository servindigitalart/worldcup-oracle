"""Tests for oracle/knowledge_learning/scoring.py"""
import pytest
from oracle.knowledge_learning.scoring import (
    compute_contributions,
    score_chain_contributions,
    score_script_contributions,
    score_archetype_contributions,
    _raw_score,
    _direction,
)
from oracle.knowledge_learning.schema import OutcomeRecord


# ── Helpers ───────────────────────────────────────────────────────────────────

def _outcome(match_id="m01", outcome="home", total=2, btts=True,
             thesis_hit=True, knowledge_aligned=True):
    return OutcomeRecord(
        entry_id=match_id,
        match_id=match_id,
        outcome_1x2=outcome,
        home_goals=1, away_goals=1,
        total_goals=total,
        btts=btts,
        over_1_5=True, over_2_5=False, over_3_5=False,
        correct_score="1-1",
        thesis_hit=thesis_hit,
        market_aligned=None,
        knowledge_aligned=knowledge_aligned,
        recorded_at="2026-06-15T22:00:00+00:00",
    )


def _entry(match_id="m01", market="match_result"):
    return {"match_id": match_id, "top_thesis_market": market}


def _activation(**kwargs):
    base = {
        "activated_chains": [{"chain_id": "C-03", "confidence": 0.70}],
        "activated_scripts": [{"script_id": "defensive_siege", "probability": 0.55}],
        "activated_manager_patterns": [
            {"manager_id": "southgate", "pattern_id": "defensive_setup", "confidence": 0.60}
        ],
        "home_archetype": "possession_control",
        "away_archetype": "counter_attack",
        "knowledge_confidence": 0.65,
    }
    base.update(kwargs)
    return base


# ── _raw_score ────────────────────────────────────────────────────────────────

def test_raw_score_positive_when_aligned():
    s = _raw_score(True, 0.70)
    assert s > 0


def test_raw_score_negative_when_not_aligned():
    s = _raw_score(False, 0.70)
    assert s < 0


def test_raw_score_zero_when_none():
    assert _raw_score(None, 0.70) == 0.0


def test_raw_score_clamped_to_minimum_confidence():
    # Even very low confidence returns minimum 0.30 base
    s = _raw_score(True, 0.01)
    assert s == pytest.approx(0.30, abs=0.001)


def test_raw_score_max_at_full_confidence():
    s = _raw_score(True, 1.0)
    assert s == pytest.approx(1.0, abs=0.001)


# ── _direction ────────────────────────────────────────────────────────────────

def test_direction_supported():
    assert _direction(0.30) == "supported"


def test_direction_contradicted():
    assert _direction(-0.30) == "contradicted"


def test_direction_neutral_near_zero():
    assert _direction(0.0) == "neutral"
    assert _direction(0.04) == "neutral"
    assert _direction(-0.04) == "neutral"


# ── score_chain_contributions ─────────────────────────────────────────────────

def test_chain_contributions_creates_score():
    act = _activation()
    o   = _outcome(knowledge_aligned=True)
    scores = score_chain_contributions(_entry(), o, act)
    assert len(scores) == 1
    assert scores[0].component_id == "C-03"
    assert scores[0].component_type == "chain"
    assert scores[0].direction == "supported"


def test_chain_contributions_empty_when_no_chains():
    act = _activation(activated_chains=[])
    scores = score_chain_contributions(_entry(), _outcome(), act)
    assert scores == []


def test_chain_contributions_negative_when_not_aligned():
    act = _activation()
    o   = _outcome(knowledge_aligned=False)
    scores = score_chain_contributions(_entry(), o, act)
    assert scores[0].raw_score < 0


# ── score_script_contributions ────────────────────────────────────────────────

def test_script_contributions_creates_score():
    act = _activation()
    o   = _outcome(knowledge_aligned=True)
    scores = score_script_contributions(_entry(), o, act)
    assert len(scores) == 1
    assert scores[0].component_id == "defensive_siege"
    assert scores[0].component_type == "script"


def test_script_contributions_empty_when_no_scripts():
    act = _activation(activated_scripts=[])
    scores = score_script_contributions(_entry(), _outcome(), act)
    assert scores == []


# ── score_archetype_contributions ─────────────────────────────────────────────

def test_archetype_contributions_creates_two_scores():
    act = _activation()
    o   = _outcome(knowledge_aligned=True)
    scores = score_archetype_contributions(_entry(), o, act)
    assert len(scores) == 2
    component_ids = {s.component_id for s in scores}
    assert "possession_control" in component_ids
    assert "counter_attack" in component_ids


def test_archetype_contributions_skips_unknown():
    act = _activation(home_archetype="unknown", away_archetype="possession_control")
    scores = score_archetype_contributions(_entry(), _outcome(), act)
    assert len(scores) == 1
    assert scores[0].component_id == "possession_control"


# ── compute_contributions ─────────────────────────────────────────────────────

def test_compute_contributions_returns_flat_list():
    entries = [_entry("m01"), _entry("m02")]
    outcomes = [_outcome("m01"), _outcome("m02")]
    activations = {"m01": _activation(), "m02": _activation()}
    scores = compute_contributions(entries, outcomes, activations)
    assert len(scores) > 0
    types = {s.component_type for s in scores}
    assert "chain" in types
    assert "script" in types


def test_compute_contributions_skips_missing_outcome():
    entries = [_entry("m01")]
    outcomes = []   # no outcomes
    scores = compute_contributions(entries, outcomes, {"m01": _activation()})
    assert scores == []


def test_compute_contributions_match_ids_in_scores():
    entries = [_entry("m01")]
    outcomes = [_outcome("m01")]
    scores = compute_contributions(entries, outcomes, {"m01": _activation()})
    for s in scores:
        assert s.match_id == "m01"
