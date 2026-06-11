"""
Tests for oracle.pipeline.bracket — Week 21.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracle.pipeline.bracket import run as bracket_run


# ── Helpers ───────────────────────────────────────────────────────────────────

_GROUPS = list("ABCDEFGHIJKL")

_TEAMS_BY_GROUP = {
    "A": ["mexico",       "south_africa",       "south_korea",  "czech_republic"],
    "B": ["canada",       "bosnia_herzegovina", "qatar",        "switzerland"],
    "C": ["brazil",       "morocco",            "haiti",        "scotland"],
    "D": ["united_states","paraguay",           "australia",    "turkey"],
    "E": ["germany",      "curacao",            "cote_divoire", "ecuador"],
    "F": ["netherlands",  "japan",              "sweden",       "tunisia"],
    "G": ["belgium",      "egypt",              "iran",         "new_zealand"],
    "H": ["spain",        "cape_verde",         "saudi_arabia", "uruguay"],
    "I": ["france",       "senegal",            "iraq",         "norway"],
    "J": ["argentina",    "algeria",            "austria",      "jordan"],
    "K": ["portugal",     "dr_congo",           "uzbekistan",   "colombia"],
    "L": ["england",      "croatia",            "ghana",        "panama"],
}


def _write_standings(artifacts: Path) -> None:
    """Write a minimal group_standings.json with 12 groups."""
    rows = []
    for g, teams in _TEAMS_BY_GROUP.items():
        base_pts = [9, 6, 3, 0]
        for i, team in enumerate(teams):
            rows.append({
                "group": g,
                "team":  team,
                "rank":  i + 1,
                "points": base_pts[i],
                "gd":     3 - i,
                "gf":     5 - i,
                "ga":     2 + i,
                "played": 3, "won": 3 - i, "drawn": 0, "lost": i,
                "status_label": "alive",
            })
    (artifacts / "group_standings.json").write_text(json.dumps(rows))


# ── Artifacts written ─────────────────────────────────────────────────────────

class TestBracketPipelineArtifacts:
    def test_writes_best_thirds_json(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        bracket_run(artifacts_dir=artifacts)
        assert (artifacts / "best_thirds.json").exists()

    def test_writes_bracket_structure_json(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        bracket_run(artifacts_dir=artifacts)
        assert (artifacts / "bracket_structure.json").exists()

    def test_writes_bracket_paths_json(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        bracket_run(artifacts_dir=artifacts)
        assert (artifacts / "bracket_paths.json").exists()

    def test_writes_knockout_projection_json(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        bracket_run(artifacts_dir=artifacts)
        assert (artifacts / "knockout_projection.json").exists()

    def test_no_standings_writes_empty_bracket(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        # No group_standings.json written
        bracket_run(artifacts_dir=artifacts)
        assert (artifacts / "bracket_structure.json").exists()


# ── best_thirds.json structure ────────────────────────────────────────────────

class TestBestThirdsArtifact:
    def _run(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        bracket_run(artifacts_dir=artifacts)
        return json.loads((artifacts / "best_thirds.json").read_text())

    def test_n_qualifying_is_8(self, tmp_path):
        data = self._run(tmp_path)
        assert data["n_qualifying"] == 8

    def test_all_thirds_has_12_entries(self, tmp_path):
        data = self._run(tmp_path)
        assert data["n_thirds_ranked"] == 12
        assert len(data["all_thirds"]) == 12

    def test_each_third_has_required_keys(self, tmp_path):
        data = self._run(tmp_path)
        for row in data["all_thirds"]:
            for key in ("rank", "team", "group", "points", "gd", "gf", "qualifies"):
                assert key in row, f"Missing key {key}"

    def test_top_8_qualify(self, tmp_path):
        data = self._run(tmp_path)
        for row in data["all_thirds"][:8]:
            assert row["qualifies"] is True
        for row in data["all_thirds"][8:]:
            assert row["qualifies"] is False

    def test_note_present(self, tmp_path):
        data = self._run(tmp_path)
        assert len(data["note"]) > 0


# ── bracket_structure.json structure ──────────────────────────────────────────

class TestBracketStructureArtifact:
    def _run(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        bracket_run(artifacts_dir=artifacts)
        return json.loads((artifacts / "bracket_structure.json").read_text())

    def test_has_5_rounds(self, tmp_path):
        data = self._run(tmp_path)
        assert len(data["rounds"]) == 5

    def test_r32_has_16_matches(self, tmp_path):
        data = self._run(tmp_path)
        r32 = next(r for r in data["rounds"] if r["round_name"] == "R32")
        assert r32["n_matches"] == 16

    def test_bracket_note_present(self, tmp_path):
        data = self._run(tmp_path)
        assert len(data["bracket_note"]) > 10

    def test_r32_teams_populated(self, tmp_path):
        data = self._run(tmp_path)
        r32 = next(r for r in data["rounds"] if r["round_name"] == "R32")
        for m in r32["matches"]:
            assert m["team_a"] is not None, f"{m['match_id']} missing team_a"
            assert m["team_b"] is not None, f"{m['match_id']} missing team_b"


# ── knockout_projection.json structure ────────────────────────────────────────

class TestKnockoutProjectionArtifact:
    def _run(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        bracket_run(artifacts_dir=artifacts)
        return json.loads((artifacts / "knockout_projection.json").read_text())

    def test_has_16_r32_matches(self, tmp_path):
        data = self._run(tmp_path)
        assert data["n_r32_matches"] == 16
        assert len(data["r32_matches"]) == 16

    def test_probabilities_sum_to_one(self, tmp_path):
        data = self._run(tmp_path)
        for m in data["r32_matches"]:
            if m["p_a_wins"] is not None and m["p_b_wins"] is not None:
                total = m["p_a_wins"] + m["p_b_wins"]
                assert abs(total - 1.0) < 1e-5, f"{m['match_id']} probs don't sum to 1: {total}"

    def test_projected_winner_set(self, tmp_path):
        data = self._run(tmp_path)
        for m in data["r32_matches"]:
            if m["team_a"] and m["team_b"]:
                assert m["projected_winner"] is not None

    def test_disclaimer_present(self, tmp_path):
        data = self._run(tmp_path)
        assert len(data["disclaimer"]) > 0

    def test_summary_returned_from_run(self, tmp_path):
        artifacts = tmp_path / "data" / "artifacts"
        artifacts.mkdir(parents=True)
        _write_standings(artifacts)
        summary = bracket_run(artifacts_dir=artifacts)
        assert "n_groups" in summary
        assert "n_qualifying_thirds" in summary
        assert summary["n_qualifying_thirds"] == 8
