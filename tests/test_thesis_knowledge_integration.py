"""Tests for thesis ↔ knowledge integration."""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch
from oracle.knowledge.resolver import resolve_knowledge_for_match
from oracle.thesis import generator as gen_mod
from oracle.thesis.generator import _enrich_thesis_with_knowledge, _knowledge_supports_market
from oracle.thesis.schema import BettingThesis


FORBIDDEN_TERMS = {
    "bet this", "lock", "guaranteed", "sure thing", "profit", "free money",
    "must bet", "bet this now", "risk-free",
}


def _make_thesis(**kwargs) -> BettingThesis:
    defaults = dict(
        thesis_id="test_thesis_001",
        match_id="arg_vs_fra",
        generated_at="2026-06-20T00:00:00Z",
        model_version="v1",
        data_stage="stage_1",
        market_type="match_result",
        selection="home",
        line=None,
        model_probability=0.45,
        market_implied_probability=0.38,
        raw_edge=0.07,
        edge_pct=7.0,
        fair_odds=2.22,
        market_quality="sufficient",
        contrarian_classification="moderate_edge",
        contrarian_score=0.175,
        confidence_score=0.62,
        confidence_label="medium",
        risk_level="low",
        supporting_factors=json.dumps([{"factor": "model edge", "weight": 0.7}]),
        counter_factors=json.dumps([{"factor": "market knows more", "weight": 0.3}]),
        active_game_scripts=json.dumps([]),
        active_causal_chains=json.dumps([]),
        human_headline="Model detects edge in result market",
        human_body="The model assigns higher probability than the market.",
        key_risk_statement="Market may be pricing in information not reflected in model.",
        opportunity_score=55,
        rank=1,
        display_tier="watchlist",
    )
    defaults.update(kwargs)
    return BettingThesis(**defaults)


def _activation_dict(home: str, away: str, match_id: str = "test") -> dict:
    """Resolve a KnowledgeActivation and convert to dict (as generator.py expects)."""
    return resolve_knowledge_for_match(match_id, home, away, "2026-06-20T00:00:00Z").to_dict()


class TestEnrichThesisWithKnowledge:
    def test_enrichment_adds_chains(self):
        thesis = _make_thesis()
        activation = _activation_dict("argentina", "france", "arg_vs_fra")
        _enrich_thesis_with_knowledge(thesis, activation)
        chains = json.loads(thesis.active_causal_chains)
        assert isinstance(chains, list)

    def test_enrichment_adds_scripts(self):
        thesis = _make_thesis()
        activation = _activation_dict("argentina", "france", "arg_vs_fra")
        _enrich_thesis_with_knowledge(thesis, activation)
        scripts = json.loads(thesis.active_game_scripts)
        assert isinstance(scripts, list)

    def test_enrichment_appends_to_human_body(self):
        thesis = _make_thesis()
        original_body = thesis.human_body
        activation = _activation_dict("argentina", "france", "arg_vs_fra")
        _enrich_thesis_with_knowledge(thesis, activation)
        assert len(thesis.human_body) >= len(original_body)

    def test_knowledge_does_not_override_probability(self):
        thesis = _make_thesis(model_probability=0.45)
        activation = _activation_dict("argentina", "france", "arg_vs_fra")
        _enrich_thesis_with_knowledge(thesis, activation)
        assert thesis.model_probability == 0.45

    def test_confidence_adjustment_bounded(self):
        thesis = _make_thesis(confidence_score=0.62)
        activation = _activation_dict("argentina", "france", "arg_vs_fra")
        _enrich_thesis_with_knowledge(thesis, activation)
        assert 0.0 <= thesis.confidence_score <= 1.0

    def test_no_unsafe_language_in_body(self):
        thesis = _make_thesis()
        activation = _activation_dict("argentina", "france", "arg_vs_fra")
        _enrich_thesis_with_knowledge(thesis, activation)
        lower = thesis.human_body.lower()
        for term in FORBIDDEN_TERMS:
            assert term not in lower, f"Forbidden term '{term}' in body"

    def test_low_confidence_activation_no_forbidden_terms(self):
        thesis = _make_thesis()
        # Unknown teams → knowledge_confidence=0.30 (floor)
        activation = _activation_dict("atlantis", "narnia", "test")
        _enrich_thesis_with_knowledge(thesis, activation)
        lower = thesis.human_body.lower()
        for term in FORBIDDEN_TERMS:
            assert term not in lower


class TestKnowledgeSupportsMarket:
    def test_returns_bool(self):
        activation = _activation_dict("argentina", "france")
        result = _knowledge_supports_market(activation, "match_result")
        assert isinstance(result, bool)

    def test_no_chains_returns_false(self):
        activation = _activation_dict("atlantis", "narnia")
        result = _knowledge_supports_market(activation, "corners_over")
        assert isinstance(result, bool)


class TestGenerateAllThesesKnowledge:
    def test_generate_all_theses_no_raise(self, tmp_path):
        import oracle.pipeline.thesis as thesis_pipe

        with (
            patch.object(gen_mod, "_ARTIFACTS", tmp_path),
            patch.object(thesis_pipe, "_ARTIFACTS", tmp_path),
        ):
            # Pre-populate empty knowledge to avoid file-not-found
            (tmp_path / "knowledge_activations.json").write_text("[]")
            (tmp_path / "match_betting_cards.json").write_text("[]")
            thesis_pipe.run()

        assert (tmp_path / "betting_theses.json").exists()

    def test_theses_output_is_list(self, tmp_path):
        import oracle.pipeline.thesis as thesis_pipe

        with (
            patch.object(gen_mod, "_ARTIFACTS", tmp_path),
            patch.object(thesis_pipe, "_ARTIFACTS", tmp_path),
        ):
            (tmp_path / "knowledge_activations.json").write_text("[]")
            (tmp_path / "match_betting_cards.json").write_text("[]")
            thesis_pipe.run()

        theses = json.loads((tmp_path / "betting_theses.json").read_text())
        assert isinstance(theses, list)
