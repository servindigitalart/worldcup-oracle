"""Tests for oracle/pipeline/knowledge_learning.py — integration smoke tests."""
import json
import pytest
from pathlib import Path


def _write(tmp_path: Path, name: str, data: object) -> None:
    (tmp_path / name).write_text(json.dumps(data))


def _minimal_artifacts(tmp_path: Path) -> None:
    """Write the minimal artifact set needed by the learning pipeline."""
    # knowledge_weights.json (calibration output)
    _write(tmp_path, "knowledge_weights.json", {
        "chains":     {"C-03": 1.21, "G-07": 0.85},
        "scripts":    {"defensive_siege": 1.05, "favorite_dominance": 1.08},
        "managers":   {"southgate:defensive_setup": 0.98},
        "archetypes": {"possession_control": 1.12},
    })
    # No live results — pipeline should handle gracefully
    _write(tmp_path, "live_results.json",          [])
    _write(tmp_path, "knowledge_activations.json", [])
    _write(tmp_path, "betting_theses.json",        [])


# ── Pipeline integration smoke test ──────────────────────────────────────────

def test_pipeline_runs_with_no_live_data(tmp_path, monkeypatch):
    """Pipeline should complete without errors even with zero live matches."""
    _minimal_artifacts(tmp_path)

    # Redirect _ARTIFACTS to tmp_path
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)

    kl_mod.run()

    # All 7 artifacts should be written
    expected = [
        "knowledge_evidence_log.json",
        "knowledge_outcome_records.json",
        "knowledge_contribution_scores.json",
        "knowledge_weight_updates.json",
        "knowledge_learning_history.json",
        "knowledge_learning_summary.json",
        "knowledge_effective_weights.json",
    ]
    for name in expected:
        path = tmp_path / name
        assert path.exists(), f"Missing artifact: {name}"


def test_evidence_log_empty_when_no_live_results(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    data = json.loads((tmp_path / "knowledge_evidence_log.json").read_text())
    assert data == []


def test_outcome_records_empty_when_no_live_results(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    data = json.loads((tmp_path / "knowledge_outcome_records.json").read_text())
    assert data == []


def test_bootstrap_updates_written(tmp_path, monkeypatch):
    """Bootstrap updates should always be present regardless of live data."""
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    updates = json.loads((tmp_path / "knowledge_weight_updates.json").read_text())
    assert len(updates) > 0
    sources = {u["source"] for u in updates}
    assert any(s.startswith("bootstrap") for s in sources)


def test_effective_weights_has_correct_shape(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    weights = json.loads((tmp_path / "knowledge_effective_weights.json").read_text())
    assert "chains"     in weights
    assert "scripts"    in weights
    assert "managers"   in weights
    assert "archetypes" in weights
    assert "generated_at" in weights


def test_effective_weights_in_bounds(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    weights = json.loads((tmp_path / "knowledge_effective_weights.json").read_text())
    for bucket in ("chains", "scripts", "managers", "archetypes"):
        for cid, w in weights.get(bucket, {}).items():
            assert 0.50 <= w <= 1.50, f"{cid}: {w}"


def test_learning_history_has_bootstrap_entries(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    history = json.loads((tmp_path / "knowledge_learning_history.json").read_text())
    assert len(history) > 0
    stages = {e["stage"] for e in history}
    assert any(s.startswith("bootstrap") for s in stages)


def test_learning_summary_has_required_keys(tmp_path, monkeypatch):
    _minimal_artifacts(tmp_path)
    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    summary = json.loads((tmp_path / "knowledge_learning_summary.json").read_text())
    required = [
        "generated_at", "stage", "bootstrap_updates", "live_updates",
        "components_gained", "components_stable", "trend_map", "notes",
    ]
    for key in required:
        assert key in summary, f"Missing key: {key}"


def test_pipeline_with_finished_match(tmp_path, monkeypatch):
    """Smoke test with one finished match end-to-end."""
    _write(tmp_path, "knowledge_weights.json", {
        "chains": {"C-03": 1.21, "G-07": 0.85},
        "scripts": {"defensive_siege": 1.05},
        "managers": {}, "archetypes": {"possession_control": 1.12},
    })
    _write(tmp_path, "live_results.json", [{
        "match_id":  "m01",
        "status":    "finished",
        "date":      "2026-06-15",
        "home_team": "usa",
        "away_team": "england",
        "score":     "2-1",
    }])
    _write(tmp_path, "knowledge_activations.json", [{
        "match_id":             "m01",
        "knowledge_confidence": 0.65,
        "home_archetype":       "possession_control",
        "away_archetype":       "counter_attack",
        "activated_chains":     [{"chain_id": "C-03", "confidence": 0.72}],
        "activated_scripts":    [{"script_id": "defensive_siege", "probability": 0.55}],
        "activated_manager_patterns": [],
    }])
    _write(tmp_path, "betting_theses.json", [{
        "match_id":         "m01",
        "market_type":      "match_result",
        "selection":        "home",
        "opportunity_score": 75,
    }])

    import oracle.pipeline.knowledge_learning as kl_mod
    monkeypatch.setattr(kl_mod, "_ARTIFACTS", tmp_path)
    kl_mod.run()

    evidence = json.loads((tmp_path / "knowledge_evidence_log.json").read_text())
    outcomes  = json.loads((tmp_path / "knowledge_outcome_records.json").read_text())
    assert len(evidence) == 1
    assert len(outcomes)  == 1
    assert outcomes[0]["outcome_1x2"] == "home"
    assert outcomes[0]["total_goals"] == 3
