"""Tests for oracle/market_intelligence/signals.py and scoring.py"""
import pytest
from oracle.market_intelligence.signals import classify_signal, classify_risk
from oracle.market_intelligence.scoring import (
    compute_knowledge_confidence,
    apply_learning_trend,
    score_to_confidence,
)


# ── classify_signal ───────────────────────────────────────────────────────────

def test_elevated_high_score_strong_signal():
    sig, tier = classify_signal(75.0, "elevated", 0.70)
    assert sig == "strong_signal"
    assert tier == "featured"


def test_elevated_moderate_score_moderate_signal():
    sig, tier = classify_signal(65.0, "elevated", 0.65)
    assert sig == "moderate_signal"
    assert tier == "secondary"


def test_elevated_watchlist_score():
    sig, tier = classify_signal(58.0, "elevated", 0.60)
    assert sig == "watchlist"
    assert tier == "watchlist"


def test_elevated_low_score_no_signal():
    sig, tier = classify_signal(52.0, "elevated", 0.60)
    assert sig == "no_signal"
    assert tier == "no_signal"


def test_neutral_always_no_signal():
    sig, tier = classify_signal(50.0, "neutral", 0.70)
    assert sig == "no_signal"


def test_suppressed_strong_score_moderate_signal():
    sig, tier = classify_signal(28.0, "suppressed", 0.65)
    assert sig == "moderate_signal"


def test_suppressed_watchlist():
    sig, tier = classify_signal(38.0, "suppressed", 0.60)
    assert sig == "watchlist"


def test_suppressed_normal_range_no_signal():
    sig, tier = classify_signal(48.0, "suppressed", 0.70)
    assert sig == "no_signal"


def test_insufficient_data_demotes_strong():
    sig, tier = classify_signal(80.0, "elevated", 0.70, data_quality="insufficient")
    assert sig == "watchlist"


def test_low_confidence_demotes_strong():
    sig, tier = classify_signal(76.0, "elevated", 0.30, data_quality="seed")
    assert sig != "strong_signal"


def test_signal_display_tier_mapping():
    _, t1 = classify_signal(80.0, "elevated", 0.70)
    _, t2 = classify_signal(65.0, "elevated", 0.65)
    _, t3 = classify_signal(57.0, "elevated", 0.60)
    _, t4 = classify_signal(50.0, "neutral", 0.70)
    assert t1 == "featured"
    assert t2 == "secondary"
    assert t3 == "watchlist"
    assert t4 == "no_signal"


# ── classify_risk ─────────────────────────────────────────────────────────────

def test_risk_low_when_confident_few_counters():
    assert classify_risk(70.0, 0.70, 0) == "low"


def test_risk_medium_with_moderate_confidence():
    assert classify_risk(65.0, 0.50, 1) == "medium"


def test_risk_high_with_low_confidence():
    assert classify_risk(65.0, 0.35, 1) == "high"


def test_risk_high_with_many_counter_mechanisms():
    assert classify_risk(70.0, 0.70, 3) == "high"


# ── compute_knowledge_confidence ──────────────────────────────────────────────

def test_neutral_weights_return_base_confidence():
    activation = {
        "activated_chains": [{"chain_id": "C-03", "confidence": 0.70}],
        "activated_scripts": [],
    }
    weights = {"chains": {"C-03": 1.0}, "scripts": {}}
    conf = compute_knowledge_confidence(activation, weights, base_confidence=0.55)
    assert pytest.approx(conf, abs=0.05) == 0.55


def test_boosted_weights_increase_confidence():
    activation = {
        "activated_chains": [{"chain_id": "C-03", "confidence": 0.70}],
        "activated_scripts": [],
    }
    neutral_w = {"chains": {"C-03": 1.0}, "scripts": {}}
    boosted_w = {"chains": {"C-03": 1.40}, "scripts": {}}
    base_conf = compute_knowledge_confidence(activation, neutral_w, 0.55)
    boost_conf = compute_knowledge_confidence(activation, boosted_w, 0.55)
    assert boost_conf > base_conf


def test_reduced_weights_decrease_confidence():
    activation = {
        "activated_chains": [{"chain_id": "C-03", "confidence": 0.70}],
        "activated_scripts": [],
    }
    neutral_w = {"chains": {"C-03": 1.0}, "scripts": {}}
    reduced_w = {"chains": {"C-03": 0.60}, "scripts": {}}
    base_conf    = compute_knowledge_confidence(activation, neutral_w, 0.55)
    reduced_conf = compute_knowledge_confidence(activation, reduced_w, 0.55)
    assert reduced_conf < base_conf


def test_confidence_in_bounds():
    activation = {
        "activated_chains": [{"chain_id": "X", "confidence": 0.80}] * 10,
        "activated_scripts": [{"script_id": "Y", "probability": 0.80}] * 10,
    }
    weights = {"chains": {"X": 1.50}, "scripts": {"Y": 1.50}}
    conf = compute_knowledge_confidence(activation, weights, 0.80)
    assert 0.25 <= conf <= 0.90


def test_no_activation_returns_base():
    conf = compute_knowledge_confidence({}, {}, base_confidence=0.50)
    assert conf == pytest.approx(0.50, abs=0.01)


# ── apply_learning_trend ──────────────────────────────────────────────────────

def test_trending_up_increases_confidence():
    trend_map = {"C-03": "up"}
    conf = apply_learning_trend(0.55, ["C-03"], [], trend_map)
    assert conf > 0.55


def test_trending_down_decreases_confidence():
    trend_map = {"C-03": "down"}
    conf = apply_learning_trend(0.55, ["C-03"], [], trend_map)
    assert conf < 0.55


def test_stable_trend_no_change():
    trend_map = {"C-03": "stable"}
    conf = apply_learning_trend(0.55, ["C-03"], [], trend_map)
    assert conf == pytest.approx(0.55, abs=0.001)


def test_learning_trend_capped_at_plus_0_05():
    trend_map = {"C-03": "up", "G-07": "up", "C-05": "up",
                 "B-05": "up", "S-07": "up", "defensive_siege": "up"}
    conf = apply_learning_trend(0.55, ["C-03", "G-07", "C-05", "B-05"], ["defensive_siege"], trend_map)
    assert conf <= 0.55 + 0.05 + 1e-9


def test_learning_trend_capped_at_minus_0_05():
    trend_map = {"C-03": "down", "G-07": "down", "C-05": "down",
                 "B-05": "down", "defensive_siege": "down"}
    conf = apply_learning_trend(0.60, ["C-03", "G-07", "C-05", "B-05"], ["defensive_siege"], trend_map)
    assert conf >= 0.60 - 0.05 - 1e-9


def test_empty_trend_map_unchanged():
    conf = apply_learning_trend(0.60, ["C-03"], ["defensive_siege"], {})
    assert conf == pytest.approx(0.60, abs=0.001)


# ── score_to_confidence ───────────────────────────────────────────────────────

def test_score_50_gives_low_confidence():
    conf = score_to_confidence(50.0, 0, "seed")
    assert conf < 0.50  # near neutral = low confidence


def test_score_80_gives_higher_confidence_than_60():
    c80 = score_to_confidence(80.0, 3, "seed")
    c60 = score_to_confidence(60.0, 3, "seed")
    assert c80 > c60


def test_more_mechanisms_increase_confidence():
    c0 = score_to_confidence(70.0, 0, "seed")
    c5 = score_to_confidence(70.0, 5, "seed")
    assert c5 > c0


def test_confidence_always_in_bounds():
    for score in (0, 25, 50, 75, 100):
        for n_mech in (0, 3, 8):
            conf = score_to_confidence(score, n_mech, "seed")
            assert 0.25 <= conf <= 0.90
