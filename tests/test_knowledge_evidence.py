"""Tests for oracle/knowledge_learning/evidence.py"""
import json
import pytest
from pathlib import Path
from oracle.knowledge_learning.evidence import build_evidence_log, _entry_id, _top_thesis_for_match


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write(tmp_path: Path, name: str, data: object) -> None:
    (tmp_path / name).write_text(json.dumps(data))


def _finished_result(match_id="m01", home="usa", away="england"):
    return {
        "match_id": match_id,
        "status":   "finished",
        "date":     "2026-06-15",
        "home_team": home,
        "away_team": away,
        "score": "2-1",
    }


def _activation(match_id="m01"):
    return {
        "match_id":            match_id,
        "knowledge_confidence": 0.65,
        "knowledge_headline":  "Test headline",
        "home_archetype":      "possession_control",
        "away_archetype":      "counter_attack",
        "activated_chains":    [{"chain_id": "C-03", "confidence": 0.72}],
        "activated_scripts":   [{"script_id": "defensive_siege", "probability": 0.55}],
        "activated_manager_patterns": [
            {"manager_id": "southgate", "pattern_id": "defensive_setup", "confidence": 0.60}
        ],
    }


def _thesis(match_id="m01", opp=80):
    return {
        "match_id":         match_id,
        "market_type":      "match_result",
        "opportunity_score": opp,
        "selection":        "home",
    }


# ── _entry_id ─────────────────────────────────────────────────────────────────

def test_entry_id_is_deterministic():
    a = _entry_id("m01", "live_2026")
    b = _entry_id("m01", "live_2026")
    assert a == b


def test_entry_id_length():
    assert len(_entry_id("m01", "live_2026")) == 16


def test_entry_id_differs_by_source():
    a = _entry_id("m01", "live_2026")
    b = _entry_id("m01", "bootstrap_2014")
    assert a != b


# ── _top_thesis_for_match ─────────────────────────────────────────────────────

def test_top_thesis_selects_highest_opportunity():
    theses = [
        _thesis("m01", opp=60),
        _thesis("m01", opp=80),
        _thesis("m01", opp=40),
    ]
    top = _top_thesis_for_match(theses, "m01")
    assert top is not None
    assert top["opportunity_score"] == 80


def test_top_thesis_returns_none_for_missing_match():
    assert _top_thesis_for_match([_thesis("m01")], "m99") is None


def test_top_thesis_returns_none_for_empty_list():
    assert _top_thesis_for_match([], "m01") is None


# ── build_evidence_log ────────────────────────────────────────────────────────

def test_returns_empty_when_no_live_results(tmp_path):
    _write(tmp_path, "live_results.json", [])
    result = build_evidence_log(tmp_path)
    assert result == []


def test_returns_empty_when_file_missing(tmp_path):
    result = build_evidence_log(tmp_path)
    assert result == []


def test_skips_unfinished_matches(tmp_path):
    results = [
        {"match_id": "m01", "status": "scheduled", "date": "2026-06-15",
         "home_team": "usa", "away_team": "england", "score": ""},
    ]
    _write(tmp_path, "live_results.json", results)
    result = build_evidence_log(tmp_path)
    assert result == []


def test_builds_entry_from_finished_match(tmp_path):
    _write(tmp_path, "live_results.json",       [_finished_result()])
    _write(tmp_path, "knowledge_activations.json", [_activation()])
    _write(tmp_path, "betting_theses.json",     [_thesis()])

    entries = build_evidence_log(tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert e.match_id == "m01"
    assert "C-03" in e.activated_chain_ids
    assert "defensive_siege" in e.activated_script_ids
    assert "possession_control" in e.activated_archetype_ids
    assert e.data_source == "live_2026"


def test_unknown_archetype_excluded(tmp_path):
    act = _activation()
    act["home_archetype"] = "unknown"
    act["away_archetype"] = "possession_control"
    _write(tmp_path, "live_results.json",          [_finished_result()])
    _write(tmp_path, "knowledge_activations.json", [act])
    _write(tmp_path, "betting_theses.json",        [])

    entries = build_evidence_log(tmp_path)
    assert "unknown" not in entries[0].activated_archetype_ids
    assert "possession_control" in entries[0].activated_archetype_ids


def test_entry_id_is_deterministic_across_calls(tmp_path):
    _write(tmp_path, "live_results.json",          [_finished_result()])
    _write(tmp_path, "knowledge_activations.json", [_activation()])
    _write(tmp_path, "betting_theses.json",        [])

    e1 = build_evidence_log(tmp_path)[0]
    e2 = build_evidence_log(tmp_path)[0]
    assert e1.entry_id == e2.entry_id


def test_multiple_matches(tmp_path):
    results = [_finished_result("m01"), _finished_result("m02", "germany", "spain")]
    _write(tmp_path, "live_results.json",          results)
    _write(tmp_path, "knowledge_activations.json", [_activation("m01"), _activation("m02")])
    _write(tmp_path, "betting_theses.json",        [])

    entries = build_evidence_log(tmp_path)
    assert len(entries) == 2
    ids = {e.match_id for e in entries}
    assert ids == {"m01", "m02"}


def test_no_crash_when_activation_missing(tmp_path):
    _write(tmp_path, "live_results.json",          [_finished_result()])
    _write(tmp_path, "knowledge_activations.json", [])
    _write(tmp_path, "betting_theses.json",        [])

    entries = build_evidence_log(tmp_path)
    assert len(entries) == 1
    assert entries[0].activated_chain_ids == []
