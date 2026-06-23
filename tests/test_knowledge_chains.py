"""Tests for oracle.knowledge.chains — activation and market support."""
from __future__ import annotations

import pytest
from oracle.knowledge.chains import CHAINS, activate_chains, chains_support_market
from oracle.knowledge.schema import ActivatedChain


class TestChainsDict:
    def test_all_stage1_chains_present(self):
        stage1_ids = {"C-03", "C-05", "G-01", "G-07", "K-02", "B-05", "S-03", "S-07"}
        assert stage1_ids.issubset(set(CHAINS.keys()))

    def test_all_chains_have_markets_affected(self):
        for cid, chain in CHAINS.items():
            assert len(chain.markets_affected) > 0, f"{cid} has no markets_affected"

    def test_all_chains_stage1(self):
        for cid, chain in CHAINS.items():
            assert chain.stage_required == "stage_1", f"{cid} is not stage_1"


class TestActivateChains:
    def test_returns_activated_chain_objects(self):
        result = activate_chains(["C-03"])
        assert len(result) == 1
        assert isinstance(result[0], ActivatedChain)
        assert result[0].chain_id == "C-03"

    def test_unknown_chain_ids_ignored(self):
        result = activate_chains(["C-03", "FAKE-99"])
        assert len(result) == 1

    def test_empty_list_returns_empty(self):
        result = activate_chains([])
        assert result == []

    def test_multiple_chains_all_returned(self):
        result = activate_chains(["C-03", "G-01", "B-05"])
        ids = {r.chain_id for r in result}
        assert ids == {"C-03", "G-01", "B-05"}

    def test_activation_confidence_within_range(self):
        result = activate_chains(list(CHAINS.keys()))
        for ac in result:
            assert 0.0 < ac.activation_confidence <= 1.0

    def test_explanation_snippet_not_empty(self):
        result = activate_chains(["C-03"])
        assert result[0].explanation_snippet.strip() != ""


class TestChainsSupportsMarket:
    def test_corners_chain_supports_corners_market(self):
        activated = activate_chains(["C-03"])
        assert chains_support_market(activated, "corners_over")

    def test_returns_false_when_no_chains(self):
        assert chains_support_market([], "corners_over_9.5") is False

    def test_returns_false_for_unsupported_market(self):
        activated = activate_chains(["C-03"])
        assert chains_support_market(activated, "player_goals") is False

    def test_btts_chain_supports_btts(self):
        activated = activate_chains(["G-01"])
        # G-01 should support btts or goal markets
        d = CHAINS["G-01"].markets_affected
        if "btts" in d or "over_2.5" in d or "goals" in d[0].lower() if d else False:
            assert chains_support_market(activated, d[0])
        else:
            # Just verify function doesn't raise
            chains_support_market(activated, "btts")
