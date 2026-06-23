"""Tests for oracle/market_intelligence/shots.py"""
import pytest
from oracle.market_intelligence.shots import analyze_shots, ShotsAnalysis


def _activation(**kwargs) -> dict:
    base = {
        "home_archetype": "high_press",
        "away_archetype": "possession_control",
        "knowledge_confidence": 0.60,
        "activated_chains": [],
        "activated_scripts": [],
    }
    base.update(kwargs)
    return base


def _chain(cid, conf=0.70):
    return {"chain_id": cid, "confidence": conf}


def _script(sid, prob=0.55):
    return {"script_id": sid, "probability": prob}


# ── Basic structure ───────────────────────────────────────────────────────────

def test_returns_shots_analysis():
    r = analyze_shots(_activation())
    assert isinstance(r, ShotsAnalysis)


def test_score_in_bounds():
    r = analyze_shots(_activation())
    assert 0.0 <= r.score <= 100.0


def test_none_activation_returns_analysis():
    r = analyze_shots(None)
    assert isinstance(r, ShotsAnalysis)
    assert r.environment in ("very_low", "low", "normal", "high", "very_high")


def test_baseline_neutral():
    act = _activation(home_archetype="unknown", away_archetype="unknown",
                      activated_chains=[], activated_scripts=[])
    r = analyze_shots(act)
    assert 35.0 <= r.score <= 65.0


# ── Chain mechanisms ──────────────────────────────────────────────────────────

def test_g01_chain_elevates_shots():
    act = _activation(activated_chains=[_chain("G-01", 0.80)])
    r   = analyze_shots(act)
    baseline = analyze_shots(_activation(activated_chains=[]))
    assert r.score > baseline.score


def test_g07_chain_suppresses_shots():
    act = _activation(activated_chains=[_chain("G-07", 0.75)])
    r   = analyze_shots(act)
    baseline = analyze_shots(_activation(activated_chains=[]))
    assert r.score < baseline.score


def test_b05_chain_elevates_shots():
    act = _activation(activated_chains=[_chain("B-05", 0.70)])
    r   = analyze_shots(act)
    baseline = analyze_shots(_activation(activated_chains=[]))
    assert r.score > baseline.score


def test_active_chains_populated():
    act = _activation(activated_chains=[_chain("G-01"), _chain("B-05")])
    r   = analyze_shots(act)
    assert len(r.active_chains) >= 1


# ── Script mechanisms ─────────────────────────────────────────────────────────

def test_favorite_dominance_elevates_shots():
    act = _activation(activated_scripts=[_script("favorite_dominance", 0.70)])
    r   = analyze_shots(act)
    baseline = analyze_shots(_activation(activated_scripts=[]))
    assert r.score > baseline.score


def test_high_press_feast_elevates_shots():
    act = _activation(activated_scripts=[_script("high_press_feast", 0.65)])
    r   = analyze_shots(act)
    baseline = analyze_shots(_activation(activated_scripts=[]))
    assert r.score > baseline.score


def test_tactical_neutralization_suppresses_shots():
    act = _activation(activated_scripts=[_script("tactical_neutralization", 0.65)])
    r   = analyze_shots(act)
    baseline = analyze_shots(_activation(activated_scripts=[]))
    assert r.score < baseline.score


def test_defensive_siege_suppresses_shots():
    act = _activation(activated_scripts=[_script("defensive_siege", 0.60)])
    r   = analyze_shots(act)
    baseline = analyze_shots(_activation(activated_scripts=[]))
    assert r.score < baseline.score


def test_active_scripts_populated():
    act = _activation(activated_scripts=[_script("favorite_dominance")])
    r   = analyze_shots(act)
    assert "favorite_dominance" in r.active_scripts


# ── Archetype matchups ────────────────────────────────────────────────────────

def test_high_press_vs_high_press_elevated_shots():
    act = _activation(home_archetype="high_press", away_archetype="high_press",
                      activated_chains=[], activated_scripts=[])
    r = analyze_shots(act)
    assert r.score >= 60.0


def test_counter_vs_counter_suppressed_shots():
    act = _activation(home_archetype="counter_attack", away_archetype="counter_attack",
                      activated_chains=[], activated_scripts=[])
    r = analyze_shots(act)
    # Counter vs counter → fewer structured attacks
    baseline = analyze_shots(_activation(home_archetype="high_press", away_archetype="high_press",
                                          activated_chains=[], activated_scripts=[]))
    assert r.score < baseline.score


def test_tournament_survival_suppresses_shots():
    act = _activation(home_archetype="tournament_survival", away_archetype="counter_attack",
                      activated_chains=[], activated_scripts=[])
    r = analyze_shots(act)
    # survival + counter → low shot environment
    assert r.score <= 52.0


# ── Profile traits ────────────────────────────────────────────────────────────

def test_high_pressing_profile_elevates_shots():
    profile = {"pressing_intensity": "high", "tempo": "high",
               "risk_profile": "high", "defensive_block": "high_line"}
    base   = analyze_shots(_activation(home_archetype="unknown", away_archetype="unknown",
                                        activated_chains=[], activated_scripts=[]))
    with_p = analyze_shots(_activation(home_archetype="unknown", away_archetype="unknown",
                                        activated_chains=[], activated_scripts=[]),
                           home_profile=profile)
    assert with_p.score >= base.score


def test_risk_profile_low_reduces_shots():
    profile = {"pressing_intensity": "low", "tempo": "slow",
               "risk_profile": "low", "defensive_block": "mid_block"}
    base   = analyze_shots(_activation(home_archetype="unknown", away_archetype="unknown",
                                        activated_chains=[], activated_scripts=[]))
    with_p = analyze_shots(_activation(home_archetype="unknown", away_archetype="unknown",
                                        activated_chains=[], activated_scripts=[]),
                           home_profile=profile)
    assert with_p.score <= base.score


# ── Classification ────────────────────────────────────────────────────────────

def test_environment_valid():
    valid = {"very_low", "low", "normal", "high", "very_high"}
    r = analyze_shots(_activation())
    assert r.environment in valid


def test_direction_valid():
    valid = {"elevated", "neutral", "suppressed"}
    r = analyze_shots(_activation())
    assert r.direction in valid


def test_high_shot_environment():
    act = _activation(
        home_archetype="high_press", away_archetype="high_press",
        activated_chains=[_chain("G-01", 0.85), _chain("B-05", 0.75)],
        activated_scripts=[_script("favorite_dominance", 0.70), _script("high_press_feast", 0.65)],
    )
    r = analyze_shots(act)
    assert r.direction == "elevated"
    assert r.environment in ("high", "very_high")


def test_weight_adjustment_respected():
    act = _activation(activated_scripts=[_script("favorite_dominance", 0.70)])
    r_boost  = analyze_shots(act, effective_weights={"chains": {}, "scripts": {"favorite_dominance": 1.40}})
    r_reduce = analyze_shots(act, effective_weights={"chains": {}, "scripts": {"favorite_dominance": 0.60}})
    assert r_boost.score > r_reduce.score
