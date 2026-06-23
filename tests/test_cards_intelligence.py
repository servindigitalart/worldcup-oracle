"""Tests for oracle/market_intelligence/cards.py"""
import pytest
from oracle.market_intelligence.cards import analyze_cards, CardsAnalysis


def _activation(**kwargs) -> dict:
    base = {
        "home_archetype": "high_press",
        "away_archetype": "counter_attack",
        "knowledge_confidence": 0.60,
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

def test_returns_cards_analysis():
    result = analyze_cards(_activation())
    assert isinstance(result, CardsAnalysis)


def test_score_in_bounds():
    result = analyze_cards(_activation())
    assert 0.0 <= result.score <= 100.0


def test_none_activation_returns_analysis():
    result = analyze_cards(None)
    assert isinstance(result, CardsAnalysis)


def test_baseline_neutral():
    act = _activation(home_archetype="unknown", away_archetype="unknown",
                      activated_chains=[], activated_scripts=[])
    result = analyze_cards(act)
    assert 40.0 <= result.score <= 65.0


# ── Chain mechanisms ──────────────────────────────────────────────────────────

def test_t01_chain_elevates_cards():
    act = _activation(activated_chains=[_chain("T-01", 0.80)])
    r   = analyze_cards(act)
    baseline = analyze_cards(_activation(activated_chains=[]))
    assert r.score > baseline.score


def test_b05_chain_elevates_cards():
    act = _activation(activated_chains=[_chain("B-05", 0.75)])
    r   = analyze_cards(act)
    baseline = analyze_cards(_activation(activated_chains=[]))
    assert r.score > baseline.score


def test_k02_chain_elevates_cards():
    act = _activation(activated_chains=[_chain("K-02", 0.70)])
    r   = analyze_cards(act)
    baseline = analyze_cards(_activation(activated_chains=[]))
    assert r.score > baseline.score


def test_c03_suppresses_cards():
    act = _activation(activated_chains=[_chain("C-03", 0.80)])
    r   = analyze_cards(act)
    baseline = analyze_cards(_activation(activated_chains=[]))
    assert r.score < baseline.score


def test_t01_appears_in_active_chains():
    act = _activation(activated_chains=[_chain("T-01")])
    r   = analyze_cards(act)
    assert "T-01" in r.active_chains


# ── Script mechanisms ─────────────────────────────────────────────────────────

def test_high_press_feast_elevates_cards():
    act = _activation(activated_scripts=[_script("high_press_feast", 0.65)])
    r   = analyze_cards(act)
    baseline = analyze_cards(_activation(activated_scripts=[]))
    assert r.score > baseline.score


def test_late_equalizer_pressure_elevates_cards():
    act = _activation(activated_scripts=[_script("late_equalizer_pressure", 0.55)])
    r   = analyze_cards(act)
    baseline = analyze_cards(_activation(activated_scripts=[]))
    assert r.score > baseline.score


def test_favorite_dominance_suppresses_cards():
    act = _activation(activated_scripts=[_script("favorite_dominance", 0.70)])
    r   = analyze_cards(act)
    baseline = analyze_cards(_activation(activated_scripts=[]))
    assert r.score < baseline.score


def test_script_appears_in_active_scripts():
    act = _activation(activated_scripts=[_script("high_press_feast")])
    r   = analyze_cards(act)
    assert "high_press_feast" in r.active_scripts


# ── Archetype matchups ────────────────────────────────────────────────────────

def test_high_press_vs_counter_elevated_cards():
    act = _activation(home_archetype="high_press", away_archetype="counter_attack",
                      activated_chains=[], activated_scripts=[])
    r   = analyze_cards(act)
    assert r.score >= 58.0


def test_possession_vs_possession_suppresses_cards():
    act = _activation(home_archetype="possession_control", away_archetype="possession_control",
                      activated_chains=[], activated_scripts=[])
    r   = analyze_cards(act)
    assert r.score <= 50.0


def test_tournament_survival_vs_high_press_elevated():
    act = _activation(home_archetype="tournament_survival", away_archetype="high_press",
                      activated_chains=[], activated_scripts=[])
    r   = analyze_cards(act)
    assert r.score >= 58.0


# ── Profile traits ────────────────────────────────────────────────────────────

def test_high_pressing_profile_elevates():
    profile = {"pressing_intensity": "high", "defensive_block": "mid_block",
               "tempo": "medium", "risk_profile": "medium"}
    base   = analyze_cards(_activation(activated_chains=[], activated_scripts=[]))
    with_p = analyze_cards(_activation(activated_chains=[], activated_scripts=[]),
                           home_profile=profile)
    assert with_p.score >= base.score


def test_low_press_profile_reduces():
    profile = {"pressing_intensity": "low", "defensive_block": "mid_block",
               "tempo": "slow", "risk_profile": "low"}
    base   = analyze_cards(_activation(home_archetype="unknown", away_archetype="unknown",
                                       activated_chains=[], activated_scripts=[]))
    with_p = analyze_cards(_activation(home_archetype="unknown", away_archetype="unknown",
                                       activated_chains=[], activated_scripts=[]),
                           home_profile=profile)
    assert with_p.score <= base.score


# ── Environment + direction ───────────────────────────────────────────────────

def test_environment_is_valid():
    valid = {"very_low", "low", "normal", "high", "very_high"}
    r = analyze_cards(_activation())
    assert r.environment in valid


def test_direction_is_valid():
    valid = {"elevated", "neutral", "suppressed"}
    r = analyze_cards(_activation())
    assert r.direction in valid


def test_high_press_feast_combined_elevates_direction():
    act = _activation(
        home_archetype="high_press", away_archetype="high_press",
        activated_chains=[_chain("B-05", 0.75)],
        activated_scripts=[_script("high_press_feast", 0.65)],
    )
    r = analyze_cards(act)
    assert r.direction == "elevated"


def test_weight_adjustment_respected():
    act = _activation(activated_chains=[_chain("T-01", 0.80)])
    r_boost  = analyze_cards(act, effective_weights={"chains": {"T-01": 1.40}, "scripts": {}})
    r_reduce = analyze_cards(act, effective_weights={"chains": {"T-01": 0.60}, "scripts": {}})
    assert r_boost.score > r_reduce.score
