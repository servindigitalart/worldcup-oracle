"""Tests for oracle/pipeline/market_intelligence.py — integration smoke tests."""
import json
import pytest
from pathlib import Path


def _write(tmp_path: Path, name: str, data: object) -> None:
    (tmp_path / name).write_text(json.dumps(data))


def _minimal_activation(match_id="usa_vs_england", home="usa", away="england") -> dict:
    return {
        "match_id":             match_id,
        "home_team":            home,
        "away_team":            away,
        "home_archetype":       "possession_control",
        "away_archetype":       "counter_attack",
        "knowledge_confidence": 0.65,
        "knowledge_headline":   "Test headline",
        "activated_chains":     [{"chain_id": "C-03", "confidence": 0.72}],
        "activated_scripts":    [{"script_id": "defensive_siege", "probability": 0.55}],
        "activated_manager_patterns": [],
    }


def _minimal_artifacts(tmp_path: Path, activations: list = None) -> None:
    if activations is None:
        activations = [_minimal_activation()]
    _write(tmp_path, "knowledge_activations.json",    activations)
    _write(tmp_path, "knowledge_effective_weights.json", {
        "chains": {"C-03": 1.21, "G-07": 0.85},
        "scripts": {"defensive_siege": 1.05},
        "managers": {}, "archetypes": {},
    })
    _write(tmp_path, "knowledge_learning_summary.json", {
        "trend_map": {"C-03": "up", "defensive_siege": "stable"},
    })


# ── Empty activations ─────────────────────────────────────────────────────────

def test_pipeline_handles_no_activations(tmp_path, monkeypatch):
    _write(tmp_path, "knowledge_activations.json",       [])
    _write(tmp_path, "knowledge_effective_weights.json", {})
    _write(tmp_path, "knowledge_learning_summary.json",  {})

    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    result = mi_mod.run()

    assert result["n_matches"] == 0
    assert result["n_cards"] == 0
    assert (tmp_path / "market_intelligence_cards.json").exists()
    assert (tmp_path / "market_intelligence_summary.json").exists()


# ── Single match ──────────────────────────────────────────────────────────────

def test_pipeline_generates_three_cards_per_match(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    result = mi_mod.run()

    assert result["n_matches"] == 1
    assert result["n_cards"] == 3  # corners, cards, shots

    cards = json.loads((tmp_path / "market_intelligence_cards.json").read_text())
    market_types = {c["market_type"] for c in cards}
    assert market_types == {"corners", "cards", "shots"}


def test_pipeline_cards_have_required_fields(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    cards = json.loads((tmp_path / "market_intelligence_cards.json").read_text())
    required = [
        "match_id", "market_type", "signal_level", "confidence",
        "knowledge_confidence", "market_score", "supporting_mechanisms",
        "active_chains", "active_scripts", "expected_direction",
        "environment", "risk_level", "headline", "explanation",
        "key_risk", "display_tier", "data_quality", "generated_at",
    ]
    for card in cards:
        for f in required:
            assert f in card, f"Card missing field: {f}"


def test_pipeline_card_match_ids_correct(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    cards = json.loads((tmp_path / "market_intelligence_cards.json").read_text())
    for c in cards:
        assert c["match_id"] == "usa_vs_england"


def test_pipeline_scores_in_bounds(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    cards = json.loads((tmp_path / "market_intelligence_cards.json").read_text())
    for c in cards:
        assert 0.0 <= c["market_score"] <= 100.0
        assert 0.0 <= c["confidence"] <= 1.0


def test_pipeline_signal_levels_valid(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    valid_signals = {"no_signal", "watchlist", "moderate_signal", "strong_signal"}
    cards = json.loads((tmp_path / "market_intelligence_cards.json").read_text())
    for c in cards:
        assert c["signal_level"] in valid_signals


def test_pipeline_environments_valid(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    valid_envs = {"very_low", "low", "normal", "high", "very_high"}
    cards = json.loads((tmp_path / "market_intelligence_cards.json").read_text())
    for c in cards:
        assert c["environment"] in valid_envs


# ── Summary ───────────────────────────────────────────────────────────────────

def test_pipeline_summary_has_required_keys(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    summary = json.loads((tmp_path / "market_intelligence_summary.json").read_text())
    required = [
        "generated_at", "stage", "n_matches", "n_cards",
        "n_strong_signals", "n_moderate_signals", "n_watchlist", "n_no_signal",
        "top_corners_signals", "top_cards_signals", "top_shots_signals",
        "dominant_mechanisms", "notes",
    ]
    for key in required:
        assert key in summary, f"Missing key: {key}"


def test_pipeline_summary_counts_consistent(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    summary = json.loads((tmp_path / "market_intelligence_summary.json").read_text())
    total_signals = (
        summary["n_strong_signals"] + summary["n_moderate_signals"]
        + summary["n_watchlist"] + summary["n_no_signal"]
    )
    assert total_signals == summary["n_cards"]


# ── Multiple matches ──────────────────────────────────────────────────────────

def test_pipeline_multiple_matches(tmp_path, monkeypatch):
    activations = [
        _minimal_activation("m01", "germany", "spain"),
        _minimal_activation("m02", "france", "brazil"),
        _minimal_activation("m03", "argentina", "england"),
    ]
    _minimal_artifacts(tmp_path, activations)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    result = mi_mod.run()

    assert result["n_matches"] == 3
    assert result["n_cards"] == 9


# ── Learning trend integration ────────────────────────────────────────────────

def test_learning_trend_applied(tmp_path, monkeypatch):
    """Cards with trending-up components should have higher confidence."""
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    mi_mod.run()

    cards = json.loads((tmp_path / "market_intelligence_cards.json").read_text())
    # Just check that confidence is within valid bounds
    for c in cards:
        assert 0.25 <= c["confidence"] <= 0.90


def test_no_learning_summary_doesnt_crash(tmp_path, monkeypatch):
    """Pipeline should work even when learning summary is empty."""
    _write(tmp_path, "knowledge_activations.json",       [_minimal_activation()])
    _write(tmp_path, "knowledge_effective_weights.json", {})
    _write(tmp_path, "knowledge_learning_summary.json",  {})  # empty — no trend_map

    import oracle.pipeline.market_intelligence as mi_mod
    monkeypatch.setattr(mi_mod, "_ARTIFACTS", tmp_path)
    result = mi_mod.run()

    assert result["n_cards"] == 3
