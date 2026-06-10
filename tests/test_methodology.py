"""
Tests for oracle.methodology — Week 15.

Coverage:
  - inputs.py: INPUTS_USED / INPUTS_NOT_USED / LIMITATIONS are non-empty lists
  - explain.py: generate() returns a complete, well-structured dict
  - pipeline: run() writes methodology.json with correct content
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracle.methodology.explain import BLEND_VERSION, generate
from oracle.methodology.inputs import INPUTS_NOT_USED, INPUTS_USED, LIMITATIONS
from oracle.pipeline.methodology import run


# ── inputs.py ─────────────────────────────────────────────────────────────────

class TestInputsModule:
    def test_inputs_used_is_list(self):
        assert isinstance(INPUTS_USED, list)

    def test_inputs_used_non_empty(self):
        assert len(INPUTS_USED) > 0

    def test_inputs_not_used_is_list(self):
        assert isinstance(INPUTS_NOT_USED, list)

    def test_inputs_not_used_non_empty(self):
        assert len(INPUTS_NOT_USED) > 0

    def test_limitations_is_list(self):
        assert isinstance(LIMITATIONS, list)

    def test_limitations_non_empty(self):
        assert len(LIMITATIONS) > 0

    def test_inputs_are_strings(self):
        assert all(isinstance(s, str) for s in INPUTS_USED)
        assert all(isinstance(s, str) for s in INPUTS_NOT_USED)
        assert all(isinstance(s, str) for s in LIMITATIONS)

    def test_no_overlap_between_used_and_not_used(self):
        assert set(INPUTS_USED).isdisjoint(set(INPUTS_NOT_USED))

    def test_historical_results_in_used(self):
        assert "historical_results" in INPUTS_USED

    def test_injuries_in_not_used(self):
        assert "injuries" in INPUTS_NOT_USED

    def test_market_odds_in_used(self):
        assert "market_odds" in INPUTS_USED


# ── explain.py ────────────────────────────────────────────────────────────────

class TestGenerate:
    def test_returns_dict(self):
        result = generate()
        assert isinstance(result, dict)

    def test_required_top_level_keys(self):
        result = generate()
        for key in ("model_version", "goals_model", "blend_version",
                    "inputs_used", "inputs_not_used", "limitations",
                    "elo", "dixon_coles", "market_blend"):
            assert key in result, f"Missing key: {key!r}"

    def test_model_version_is_string(self):
        assert isinstance(generate()["model_version"], str)

    def test_blend_version_format(self):
        bv = generate()["blend_version"]
        assert bv.startswith("market-")
        assert "80" in bv or "20" in bv

    def test_inputs_used_matches_module(self):
        assert generate()["inputs_used"] == INPUTS_USED

    def test_inputs_not_used_matches_module(self):
        assert generate()["inputs_not_used"] == INPUTS_NOT_USED

    def test_limitations_matches_module(self):
        assert generate()["limitations"] == LIMITATIONS

    def test_elo_section_has_required_fields(self):
        elo = generate()["elo"]
        for field in ("name", "version", "strengths", "weaknesses"):
            assert field in elo

    def test_dixon_coles_section_has_required_fields(self):
        dc = generate()["dixon_coles"]
        for field in ("name", "version", "strengths", "weaknesses"):
            assert field in dc

    def test_market_blend_section_has_required_fields(self):
        mb = generate()["market_blend"]
        for field in ("name", "market_weight", "model_weight"):
            assert field in mb

    def test_weights_sum_to_one(self):
        mb = generate()["market_blend"]
        assert pytest.approx(mb["market_weight"] + mb["model_weight"]) == 1.0


# ── pipeline ──────────────────────────────────────────────────────────────────

class TestMethodologyPipeline:
    def test_writes_methodology_json(self, tmp_path):
        run(artifacts_dir=tmp_path)
        assert (tmp_path / "methodology.json").exists()

    def test_json_is_valid(self, tmp_path):
        run(artifacts_dir=tmp_path)
        data = json.loads((tmp_path / "methodology.json").read_text())
        assert isinstance(data, dict)

    def test_generated_at_present(self, tmp_path):
        run(artifacts_dir=tmp_path)
        data = json.loads((tmp_path / "methodology.json").read_text())
        assert "generated_at" in data

    def test_returns_dict(self, tmp_path):
        result = run(artifacts_dir=tmp_path)
        assert isinstance(result, dict)

    def test_artifact_has_all_sections(self, tmp_path):
        run(artifacts_dir=tmp_path)
        data = json.loads((tmp_path / "methodology.json").read_text())
        for key in ("inputs_used", "inputs_not_used", "limitations",
                    "elo", "dixon_coles", "market_blend"):
            assert key in data
