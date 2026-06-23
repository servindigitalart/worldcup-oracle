"""Tests for oracle/knowledge_learning/outcomes.py"""
from oracle.knowledge_learning.outcomes import (
    evaluate_outcomes,
    _determine_1x2,
    _parse_score,
    _thesis_hit,
    _market_aligned,
    _knowledge_aligned,
)


# ── _determine_1x2 ────────────────────────────────────────────────────────────

def test_home_win():
    assert _determine_1x2(2, 1) == "home"


def test_away_win():
    assert _determine_1x2(0, 1) == "away"


def test_draw():
    assert _determine_1x2(1, 1) == "draw"


def test_zero_zero_draw():
    assert _determine_1x2(0, 0) == "draw"


# ── _parse_score ──────────────────────────────────────────────────────────────

def test_parse_dash_format():
    assert _parse_score("2-1") == (2, 1)


def test_parse_colon_format():
    assert _parse_score("3:0") == (3, 0)


def test_parse_with_spaces():
    assert _parse_score(" 1 - 1 ") == (1, 1)


def test_parse_invalid_returns_negative():
    assert _parse_score("invalid") == (-1, -1)


def test_parse_empty_returns_negative():
    assert _parse_score("") == (-1, -1)


# ── _thesis_hit ───────────────────────────────────────────────────────────────

def test_thesis_hit_match_result_correct():
    thesis = {"market_type": "match_result", "selection": "home"}
    assert _thesis_hit(thesis, "home", 2, False) is True


def test_thesis_hit_match_result_wrong():
    thesis = {"market_type": "match_result", "selection": "away"}
    assert _thesis_hit(thesis, "home", 2, False) is False


def test_thesis_hit_over_2_5_over():
    thesis = {"market_type": "over_under_2_5", "selection": "over"}
    assert _thesis_hit(thesis, "home", 3, True) is True


def test_thesis_hit_over_2_5_under():
    thesis = {"market_type": "over_under_2_5", "selection": "under"}
    assert _thesis_hit(thesis, "draw", 1, False) is True


def test_thesis_hit_btts_yes():
    thesis = {"market_type": "btts", "selection": "yes"}
    assert _thesis_hit(thesis, "home", 3, True) is True


def test_thesis_hit_btts_no():
    thesis = {"market_type": "btts", "selection": "no"}
    assert _thesis_hit(thesis, "home", 3, False) is True


def test_thesis_hit_none_when_no_thesis():
    assert _thesis_hit(None, "home", 2, False) is None


def test_thesis_hit_unknown_market_returns_none():
    thesis = {"market_type": "corners", "selection": "over"}
    assert _thesis_hit(thesis, "home", 2, False) is None


# ── _market_aligned ───────────────────────────────────────────────────────────

def test_market_aligned_none_when_no_thesis():
    assert _market_aligned(None, "home") is None


def test_market_aligned_none_when_missing_probs():
    thesis = {"market_type": "match_result", "selection": "home"}
    assert _market_aligned(thesis, "home") is None


def test_market_aligned_true_when_market_correct():
    thesis = {
        "market_type": "match_result",
        "selection": "home",
        "market_implied_probability": 0.60,
        "model_probability": 0.55,
    }
    assert _market_aligned(thesis, "home") is True


def test_market_aligned_false_when_market_wrong():
    thesis = {
        "market_type": "match_result",
        "selection": "home",
        "market_implied_probability": 0.60,
        "model_probability": 0.55,
    }
    assert _market_aligned(thesis, "away") is False


# ── _knowledge_aligned ────────────────────────────────────────────────────────

def test_knowledge_aligned_none_when_no_activation():
    assert _knowledge_aligned({}, "home", 2) is None


def test_knowledge_aligned_none_when_empty_chains_and_scripts():
    act = {"activated_chains": [], "activated_scripts": []}
    assert _knowledge_aligned(act, "home", 2) is None


def test_knowledge_aligned_g07_low_scoring():
    act = {"activated_chains": [{"chain_id": "G-07"}], "activated_scripts": []}
    assert _knowledge_aligned(act, "draw", 1) is True


def test_knowledge_aligned_g07_high_scoring():
    act = {"activated_chains": [{"chain_id": "G-07"}], "activated_scripts": []}
    assert _knowledge_aligned(act, "home", 3) is False


def test_knowledge_aligned_script_defensive_siege():
    act = {
        "activated_chains": [],
        "activated_scripts": [{"script_id": "defensive_siege", "probability": 0.60}],
    }
    assert _knowledge_aligned(act, "draw", 1) is True


def test_knowledge_aligned_script_high_press_feast():
    act = {
        "activated_chains": [],
        "activated_scripts": [{"script_id": "high_press_feast", "probability": 0.60}],
    }
    assert _knowledge_aligned(act, "home", 3) is True


# ── evaluate_outcomes ─────────────────────────────────────────────────────────

def _live_result(match_id="m01", score="2-1", status="finished"):
    return {
        "match_id":  match_id,
        "status":    status,
        "score":     score,
        "home_team": "usa",
        "away_team": "england",
    }


def test_evaluate_outcomes_returns_records():
    results = [_live_result()]
    records = evaluate_outcomes(results, {}, {})
    assert len(records) == 1
    assert records[0].outcome_1x2 == "home"
    assert records[0].total_goals == 3


def test_evaluate_outcomes_skips_unfinished():
    results = [_live_result(status="scheduled")]
    records = evaluate_outcomes(results, {}, {})
    assert records == []


def test_evaluate_outcomes_skips_bad_score():
    results = [_live_result(score="tbd")]
    records = evaluate_outcomes(results, {}, {})
    assert records == []


def test_evaluate_outcomes_btts_true():
    records = evaluate_outcomes([_live_result(score="1-1")], {}, {})
    assert records[0].btts is True


def test_evaluate_outcomes_btts_false():
    records = evaluate_outcomes([_live_result(score="2-0")], {}, {})
    assert records[0].btts is False


def test_evaluate_outcomes_over_flags():
    records = evaluate_outcomes([_live_result(score="3-1")], {}, {})
    r = records[0]
    assert r.over_1_5 is True
    assert r.over_2_5 is True
    assert r.over_3_5 is True


def test_evaluate_outcomes_correct_score():
    records = evaluate_outcomes([_live_result(score="2-1")], {}, {})
    assert records[0].correct_score == "2-1"


def test_evaluate_outcomes_multiple():
    results = [_live_result("m01", "2-1"), _live_result("m02", "0-0")]
    records = evaluate_outcomes(results, {}, {})
    assert len(records) == 2
    ids = {r.match_id for r in records}
    assert ids == {"m01", "m02"}
