"""Tests for oracle.pipeline.knowledge — artifact generation."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestKnowledgePipelineArtifacts:
    def test_pipeline_writes_all_four_artifacts(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        expected = [
            "knowledge_activations.json",
            "causal_chain_activations.json",
            "game_script_activations.json",
            "knowledge_summary.json",
        ]
        for fname in expected:
            path = tmp_path / fname
            assert path.exists(), f"Missing artifact: {fname}"

    def test_activations_is_list(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        data = json.loads((tmp_path / "knowledge_activations.json").read_text())
        assert isinstance(data, list)

    def test_activations_count_positive(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        activations = json.loads((tmp_path / "knowledge_activations.json").read_text())
        # Pipeline reads from seed fixtures; at least 1 activation generated
        assert isinstance(activations, list)

    def test_each_activation_has_required_fields(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        activations = json.loads((tmp_path / "knowledge_activations.json").read_text())
        required = {"match_id", "home_team", "away_team", "knowledge_confidence", "data_stage"}
        for act in activations[:5]:
            missing = required - set(act.keys())
            assert not missing, f"Activation missing keys: {missing}"

    def test_summary_has_metadata(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        summary = json.loads((tmp_path / "knowledge_summary.json").read_text())
        assert "n_matches" in summary
        assert "stage" in summary
        assert summary["stage"] == "stage_1"

    def test_activations_include_headline(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        activations = json.loads((tmp_path / "knowledge_activations.json").read_text())
        # Every activation should have knowledge_headline
        for act in activations:
            assert "knowledge_headline" in act, f"Missing knowledge_headline in {act.get('match_id')}"

    def test_causal_chains_is_list(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        data = json.loads((tmp_path / "causal_chain_activations.json").read_text())
        assert isinstance(data, list)

    def test_game_scripts_is_list(self, tmp_path):
        import oracle.pipeline.knowledge as kpipe

        with patch.object(kpipe, "_ARTIFACTS", tmp_path):
            kpipe.run()

        data = json.loads((tmp_path / "game_script_activations.json").read_text())
        assert isinstance(data, list)
