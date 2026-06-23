"""Tests for oracle/market_intelligence/corners.py"""
import pytest
from oracle.market_intelligence.corners import analyze_corners, CornersAnalysis


# ── Helpers ───────────────────────────────────────────────────────────────────

def _activation(**kwargs) -> dict:
    base = {
        "home_archetype": "possession_control",
        "away_archetype": "counter_attack",
        "knowledge_confidence": 0.65,
        "activated_chains": [],
        "activated_scripts": [],
        "activated_manager_patterns": [],
    }
    base.update(kwargs)
    return base


def _chain(cid, conf=0.70):
    return {"chain_id": cid, "confidence": conf}


def _script(sid, prob=0.55):
    return {"script_id": sid, "probability": prob}


# ── Basic structure ───────────────────────────────────────────────────────────

def test_returns_corners_analysis():
    result = analyze_corners(_activation())
    assert isinstance(result, CornersAnalysis)


def test_baseline_is_neutral():
    # Empty activation with neutral archetypes → roughly 50 + archetype delta
    act = _activation(home_archetype="unknown", away_archetype="unknown",
                      activated_chains=[], activated_scripts=[])
    result = analyze_corners(act)
    assert 40.0 <= result.score <= 65.0


def test_score_in_bounds():
    for _ in range(5):
        result = analyze_corners(_activation())
        assert 0.0 <= result.score <= 100.0


def test_none_activation_returns_neutral():
    result = analyze_corners(None)
    assert isinstance(result, CornersAnalysis)
    assert result.environment in ("very_low", "low", "normal", "high", "very_high")


# ── Chain mechanisms ──────────────────────────────────────────────────────────

def test_c03_chain_elevates_corners():
    base = _activation(activated_chains=[_chain("C-03", 0.80)])
    result = analyze_corners(base)
    baseline = analyze_corners(_activation(activated_chains=[]))
    assert result.score > baseline.score


def test_c05_chain_elevates_corners():
    base = _activation(activated_chains=[_chain("C-05", 0.75)])
    result = analyze_corners(base)
    baseline = analyze_corners(_activation(activated_chains=[]))
    assert result.score > baseline.score


def test_g01_chain_suppresses_corners():
    base = _activation(activated_chains=[_chain("G-01", 0.70)])
    result = analyze_corners(base)
    baseline = analyze_corners(_activation(activated_chains=[]))
    assert result.score <= baseline.score


def test_c03_appears_in_active_chains():
    act = _activation(activated_chains=[_chain("C-03")])
    result = analyze_corners(act)
    assert "C-03" in result.active_chains


# ── Script mechanisms ─────────────────────────────────────────────────────────

def test_defensive_siege_script_elevates_corners():
    base = _activation(activated_scripts=[_script("defensive_siege", 0.60)])
    result = analyze_corners(base)
    baseline = analyze_corners(_activation(activated_scripts=[]))
    assert result.score > baseline.score


def test_set_piece_war_script_elevates_corners():
    base = _activation(activated_scripts=[_script("set_piece_war", 0.50)])
    result = analyze_corners(base)
    baseline = analyze_corners(_activation(activated_scripts=[]))
    assert result.score > baseline.score


def test_counter_attack_trap_suppresses_corners():
    base = _activation(activated_scripts=[_script("counter_attack_trap", 0.60)])
    result = analyze_corners(base)
    baseline = analyze_corners(_activation(activated_scripts=[]))
    assert result.score < baseline.score


def test_defensive_siege_in_active_scripts():
    act = _activation(activated_scripts=[_script("defensive_siege")])
    result = analyze_corners(act)
    assert "defensive_siege" in result.active_scripts


# ── Archetype matchups ────────────────────────────────────────────────────────

def test_possession_vs_low_block_high_corners():
    act = _activation(home_archetype="possession_control", away_archetype="low_block",
                      activated_chains=[], activated_scripts=[])
    result = analyze_corners(act)
    assert result.score >= 62.0


def test_possession_vs_counter_elevated_corners():
    act = _activation(home_archetype="possession_control", away_archetype="counter_attack",
                      activated_chains=[], activated_scripts=[])
    result = analyze_corners(act)
    assert result.environment in ("high", "very_high", "normal")
    assert result.score >= 55.0


def test_counter_vs_counter_suppressed_corners():
    act = _activation(home_archetype="counter_attack", away_archetype="counter_attack",
                      activated_chains=[], activated_scripts=[])
    result = analyze_corners(act)
    # Should be notably below neutral
    assert result.score <= 50.0


def test_set_piece_heavy_elevated_corners():
    act = _activation(home_archetype="set_piece_heavy", away_archetype="counter_attack",
                      activated_chains=[], activated_scripts=[])
    result = analyze_corners(act)
    assert result.score >= 55.0


# ── Profile traits ────────────────────────────────────────────────────────────

def test_high_set_piece_reliance_elevates():
    home_profile = {"set_piece_reliance": "high", "aerial_reliance": "medium",
                    "defensive_block": "mid_block", "tempo": "medium", "pressing_intensity": "medium"}
    base  = analyze_corners(_activation())
    with_profile = analyze_corners(_activation(), home_profile=home_profile)
    assert with_profile.score >= base.score


def test_low_block_profile_elevates():
    profile = {"defensive_block": "low_block", "set_piece_reliance": "medium",
               "aerial_reliance": "medium", "tempo": "medium", "pressing_intensity": "medium"}
    base = analyze_corners(_activation())
    with_p = analyze_corners(_activation(), away_profile=profile)
    assert with_p.score >= base.score


# ── Environment classification ────────────────────────────────────────────────

def test_environment_is_valid():
    valid = {"very_low", "low", "normal", "high", "very_high"}
    result = analyze_corners(_activation())
    assert result.environment in valid


def test_direction_is_valid():
    valid = {"elevated", "neutral", "suppressed"}
    result = analyze_corners(_activation())
    assert result.direction in valid


def test_high_score_gives_elevated_direction():
    act = _activation(
        home_archetype="possession_control", away_archetype="low_block",
        activated_chains=[_chain("C-03", 0.90), _chain("C-05", 0.85)],
        activated_scripts=[_script("defensive_siege", 0.70)],
    )
    result = analyze_corners(act)
    assert result.direction == "elevated"


def test_supporting_mechanisms_populated():
    act = _activation(
        activated_chains=[_chain("C-03")],
        activated_scripts=[_script("defensive_siege")],
    )
    result = analyze_corners(act)
    assert len(result.supporting_mechanisms) >= 1


def test_weight_adjustments_respected():
    act = _activation(activated_chains=[_chain("C-03", 0.80)])
    weights_boosted  = {"chains": {"C-03": 1.40}, "scripts": {}}
    weights_reduced  = {"chains": {"C-03": 0.60}, "scripts": {}}
    r_boost  = analyze_corners(act, effective_weights=weights_boosted)
    r_reduce = analyze_corners(act, effective_weights=weights_reduced)
    assert r_boost.score > r_reduce.score
