"""Tests for oracle.pipeline.thesis."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestThesisPipelineRun:
    """Integration-style tests for the thesis pipeline."""

    def _minimal_card(self, match_id: str = "test_vs_test") -> dict:
        return {
            "match_id": match_id,
            "group": "A",
            "kickoff_at": "2026-07-01T18:00:00+00:00",
            "venue": "Test Arena",
            "city": "Test City",
            "home_team": "home_team",
            "away_team": "away_team",
            "n_markets": 3,
            "n_signals": 0,
            "markets": [
                {
                    "match_id": match_id,
                    "market_type": "1x2",
                    "selection": "home_win",
                    "probability": 0.65,
                    "fair_decimal_odds": 1.54,
                    "model_source": "elo_blend",
                    "confidence": "medium",
                    "risk_label": "medium",
                    "data_quality": "model_only",
                    "signal_level": "model_probability_only",
                    "market_probability": None,
                    "market_gap": None,
                    "reason": "Home Win: model 65.0%",
                    "warnings": [],
                    "generated_at": "2026-06-20T10:00:00+00:00",
                },
                {
                    "match_id": match_id,
                    "market_type": "over_under_2_5",
                    "selection": "over",
                    "probability": 0.55,
                    "fair_decimal_odds": 1.82,
                    "model_source": "dixon_coles",
                    "confidence": "medium",
                    "risk_label": "medium",
                    "data_quality": "model_only",
                    "signal_level": "model_probability_only",
                    "market_probability": None,
                    "market_gap": None,
                    "reason": "Over 2.5: model 55.0%",
                    "warnings": [],
                    "generated_at": "2026-06-20T10:00:00+00:00",
                },
                {
                    "match_id": match_id,
                    "market_type": "btts",
                    "selection": "yes",
                    "probability": 0.48,
                    "fair_decimal_odds": 2.08,
                    "model_source": "dixon_coles",
                    "confidence": "medium",
                    "risk_label": "medium",
                    "data_quality": "model_only",
                    "signal_level": "model_probability_only",
                    "market_probability": None,
                    "market_gap": None,
                    "reason": "BTTS Yes: model 48.0%",
                    "warnings": [],
                    "generated_at": "2026-06-20T10:00:00+00:00",
                },
            ],
            "top_signals": [],
            "no_signal_reason": "No market data.",
            "generated_at": "2026-06-20T10:00:00+00:00",
        }

    def test_pipeline_run_with_mocked_cards(self, tmp_path):
        """Pipeline run should write all artifacts without error."""
        cards = [self._minimal_card("a_vs_b"), self._minimal_card("c_vs_d")]

        artifacts_dir = tmp_path / "data" / "artifacts"
        frontend_dir  = tmp_path / "frontend" / "src" / "data"
        artifacts_dir.mkdir(parents=True)
        frontend_dir.mkdir(parents=True)

        # Write a fake match_betting_cards.json
        (artifacts_dir / "match_betting_cards.json").write_text(json.dumps(cards))

        import oracle.pipeline.thesis as thesis_pipe
        import oracle.thesis.generator as gen_mod

        with (
            patch.object(gen_mod, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_FRONTEND", frontend_dir),
        ):
            summary = thesis_pipe.run()

        assert summary["n_matches"] == 2
        assert summary["n_theses"] > 0
        assert (artifacts_dir / "betting_theses.json").exists()
        assert (artifacts_dir / "thesis_summary.json").exists()
        assert (artifacts_dir / "betting_theses.parquet").exists()
        assert (frontend_dir / "betting_theses.json").exists()
        assert (frontend_dir / "thesis_summary.json").exists()

    def test_summary_has_required_keys(self, tmp_path):
        cards = [self._minimal_card("a_vs_b")]
        artifacts_dir = tmp_path / "data" / "artifacts"
        frontend_dir  = tmp_path / "frontend" / "src" / "data"
        artifacts_dir.mkdir(parents=True)
        frontend_dir.mkdir(parents=True)
        (artifacts_dir / "match_betting_cards.json").write_text(json.dumps(cards))

        import oracle.pipeline.thesis as thesis_pipe
        import oracle.thesis.generator as gen_mod
        with (
            patch.object(gen_mod, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_FRONTEND", frontend_dir),
        ):
            summary = thesis_pipe.run()

        for key in [
            "generated_at", "data_stage", "n_matches", "n_theses",
            "n_featured", "n_secondary", "n_watchlist", "n_hidden",
            "n_model_only", "n_market_edge", "markets_supported",
            "markets_unavailable", "disclaimer", "language_policy",
            "match_summaries",
        ]:
            assert key in summary, f"Missing key: {key}"

    def test_json_output_valid(self, tmp_path):
        cards = [self._minimal_card("a_vs_b")]
        artifacts_dir = tmp_path / "data" / "artifacts"
        frontend_dir  = tmp_path / "frontend" / "src" / "data"
        artifacts_dir.mkdir(parents=True)
        frontend_dir.mkdir(parents=True)
        (artifacts_dir / "match_betting_cards.json").write_text(json.dumps(cards))

        import oracle.pipeline.thesis as thesis_pipe
        import oracle.thesis.generator as gen_mod
        with (
            patch.object(gen_mod, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_FRONTEND", frontend_dir),
        ):
            thesis_pipe.run()

        theses = json.loads((artifacts_dir / "betting_theses.json").read_text())
        assert isinstance(theses, list)
        if theses:
            t = theses[0]
            assert "thesis_id" in t
            assert "opportunity_score" in t
            assert "display_tier" in t
            assert "human_headline" in t

    def test_no_forbidden_language_in_outputs(self, tmp_path):
        cards = [self._minimal_card("a_vs_b")]
        artifacts_dir = tmp_path / "data" / "artifacts"
        frontend_dir  = tmp_path / "frontend" / "src" / "data"
        artifacts_dir.mkdir(parents=True)
        frontend_dir.mkdir(parents=True)
        (artifacts_dir / "match_betting_cards.json").write_text(json.dumps(cards))

        import oracle.pipeline.thesis as thesis_pipe
        import oracle.thesis.generator as gen_mod
        from oracle.thesis.schema import FORBIDDEN_TERMS

        with (
            patch.object(gen_mod, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_FRONTEND", frontend_dir),
        ):
            thesis_pipe.run()

        theses = json.loads((artifacts_dir / "betting_theses.json").read_text())
        for t in theses:
            for field in ["human_headline", "human_body", "key_risk_statement"]:
                text = t.get(field, "").lower()
                for term in FORBIDDEN_TERMS:
                    assert term not in text, f"Forbidden term '{term}' in {field}: {text}"

    def test_parquet_readable(self, tmp_path):
        cards = [self._minimal_card("a_vs_b")]
        artifacts_dir = tmp_path / "data" / "artifacts"
        frontend_dir  = tmp_path / "frontend" / "src" / "data"
        artifacts_dir.mkdir(parents=True)
        frontend_dir.mkdir(parents=True)
        (artifacts_dir / "match_betting_cards.json").write_text(json.dumps(cards))

        import oracle.pipeline.thesis as thesis_pipe
        import oracle.thesis.generator as gen_mod
        with (
            patch.object(gen_mod, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_FRONTEND", frontend_dir),
        ):
            thesis_pipe.run()

        import polars as pl
        df = pl.read_parquet(artifacts_dir / "betting_theses.parquet")
        assert "thesis_id" in df.columns
        assert "opportunity_score" in df.columns

    def test_missing_betting_cards_does_not_crash(self, tmp_path):
        artifacts_dir = tmp_path / "data" / "artifacts"
        frontend_dir  = tmp_path / "frontend" / "src" / "data"
        artifacts_dir.mkdir(parents=True)
        frontend_dir.mkdir(parents=True)
        # No match_betting_cards.json file written

        import oracle.pipeline.thesis as thesis_pipe
        import oracle.thesis.generator as gen_mod
        with (
            patch.object(gen_mod, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_FRONTEND", frontend_dir),
        ):
            summary = thesis_pipe.run()

        assert summary["n_theses"] == 0
        assert summary["n_matches"] == 0

    def test_stage_2_markets_in_unavailable_list(self, tmp_path):
        cards = [self._minimal_card("a_vs_b")]
        artifacts_dir = tmp_path / "data" / "artifacts"
        frontend_dir  = tmp_path / "frontend" / "src" / "data"
        artifacts_dir.mkdir(parents=True)
        frontend_dir.mkdir(parents=True)
        (artifacts_dir / "match_betting_cards.json").write_text(json.dumps(cards))

        import oracle.pipeline.thesis as thesis_pipe
        import oracle.thesis.generator as gen_mod
        with (
            patch.object(gen_mod, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_ARTIFACTS", artifacts_dir),
            patch.object(thesis_pipe, "_FRONTEND", frontend_dir),
        ):
            summary = thesis_pipe.run()

        assert "corners" in summary["markets_unavailable"]
        assert "player_props" in summary["markets_unavailable"]
        assert "cards" in summary["markets_unavailable"]
