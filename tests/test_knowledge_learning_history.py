"""Tests for oracle/knowledge_learning/history.py"""
import pytest
from oracle.knowledge_learning.history import (
    build_learning_history,
    extract_effective_weights,
    summarize_history,
)
from oracle.knowledge_learning.schema import WeightUpdate, LearningHistoryEntry


# ── Helpers ───────────────────────────────────────────────────────────────────

def _update(cid, ctype, old, new, source, ts, n=10):
    return WeightUpdate(
        component_id=cid,
        component_type=ctype,
        old_weight=old,
        new_weight=new,
        delta=round(new - old, 4),
        evidence_count=n,
        evidence_strength="small",
        mean_contribution=0.30,
        reason="test",
        timestamp=ts,
        source=source,
    )


# ── build_learning_history ────────────────────────────────────────────────────

def test_build_history_empty_inputs():
    entries = build_learning_history([], [])
    assert entries == []


def test_build_history_returns_history_entries():
    boot = [_update("C-03", "chain", 1.00, 1.01, "bootstrap_2014", "2014-07-13T00:00:00+00:00")]
    live = [_update("C-03", "chain", 1.01, 1.02, "live_2026",      "2026-06-15T22:00:00+00:00")]
    history = build_learning_history(boot, live)
    assert len(history) == 2
    assert all(isinstance(e, LearningHistoryEntry) for e in history)


def test_build_history_ordered_by_timestamp():
    boot = [_update("C-03", "chain", 1.00, 1.01, "bootstrap_2022", "2022-12-18T00:00:00+00:00")]
    live = [_update("C-03", "chain", 1.01, 1.02, "live_2026",      "2026-06-15T00:00:00+00:00")]
    history = build_learning_history(boot, live)
    assert history[0].timestamp < history[1].timestamp


def test_build_history_cumulative_evidence_accumulates():
    boot = [
        _update("C-03", "chain", 1.00, 1.01, "bootstrap_2014", "2014-07-13T00:00:00+00:00", n=15),
        _update("C-03", "chain", 1.01, 1.02, "bootstrap_2018", "2018-07-15T00:00:00+00:00", n=15),
    ]
    history = build_learning_history(boot, [])
    assert history[0].cumulative_evidence == 15
    assert history[1].cumulative_evidence == 30


def test_build_history_tracks_multiple_components_independently():
    boot = [
        _update("C-03", "chain",  1.00, 1.01, "bootstrap_2014", "2014-07-13T00:00:00+00:00", n=10),
        _update("G-07", "chain",  1.00, 0.99, "bootstrap_2014", "2014-07-13T00:00:00+00:00", n=10),
    ]
    history = build_learning_history(boot, [])
    c03 = [e for e in history if e.component_id == "C-03"]
    g07 = [e for e in history if e.component_id == "G-07"]
    assert c03[0].cumulative_evidence == 10
    assert g07[0].cumulative_evidence == 10


# ── extract_effective_weights ─────────────────────────────────────────────────

def _hist_entry(cid, ctype, w, ts, stage="live"):
    return LearningHistoryEntry(
        component_id=cid,
        component_type=ctype,
        timestamp=ts,
        weight=w,
        evidence_count=10,
        cumulative_evidence=10,
        stage=stage,
        source=stage,
        delta=0.01,
    )


def test_extract_effective_weights_empty():
    w = extract_effective_weights([])
    assert w["chains"]     == {}
    assert w["scripts"]    == {}
    assert w["managers"]   == {}
    assert w["archetypes"] == {}


def test_extract_effective_weights_latest_wins():
    history = [
        _hist_entry("C-03", "chain", 1.05, "2022-12-18T00:00:00+00:00"),
        _hist_entry("C-03", "chain", 1.08, "2026-06-15T00:00:00+00:00"),
    ]
    w = extract_effective_weights(history)
    assert w["chains"]["C-03"] == pytest.approx(1.08)


def test_extract_effective_weights_correct_buckets():
    history = [
        _hist_entry("C-03",            "chain",     1.21, "2026-06-15T00:00:00+00:00"),
        _hist_entry("defensive_siege", "script",    1.05, "2026-06-15T00:00:00+00:00"),
        _hist_entry("southgate:x",     "manager",   0.98, "2026-06-15T00:00:00+00:00"),
        _hist_entry("possession_ctrl", "archetype", 1.12, "2026-06-15T00:00:00+00:00"),
    ]
    w = extract_effective_weights(history)
    assert "C-03"            in w["chains"]
    assert "defensive_siege" in w["scripts"]
    assert "southgate:x"     in w["managers"]
    assert "possession_ctrl" in w["archetypes"]


# ── summarize_history ─────────────────────────────────────────────────────────

def test_summarize_history_empty():
    s = summarize_history([])
    assert s["total_entries"] == 0
    assert s["components_tracked"] == 0


def test_summarize_history_counts():
    history = [
        _hist_entry("C-03", "chain", 1.21, "2022-01-01T00:00:00+00:00", "bootstrap_2022"),
        _hist_entry("C-03", "chain", 1.22, "2026-06-15T00:00:00+00:00", "live"),
        _hist_entry("G-07", "chain", 0.85, "2022-01-01T00:00:00+00:00", "bootstrap_2022"),
    ]
    # Manually set deltas
    history[0].delta = 0.01
    history[1].delta = 0.01
    history[2].delta = -0.01
    s = summarize_history(history)
    assert s["total_entries"] == 3
    assert s["components_tracked"] == 2
    assert s["bootstrap_entries"] == 2
    assert s["live_entries"] == 1
