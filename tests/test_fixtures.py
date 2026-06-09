"""
Tests for Week 11–12 fixture seed infrastructure.

Covers:
  - fixture schema validation (all required fields present)
  - 48 unique teams across the complete group-stage set
  - 12 groups
  - 4 teams per group
  - 72 group-stage fixtures
  - no duplicate match_id values
  - all teams resolve to canonical IDs
  - official flag present and correct (Week 12: is_official=True, is_placeholder=False)
  - all 72 kickoff_at values are non-null (official data)
  - derive_groups_from_fixtures reconstructs correct group membership
  - load_groups() uses seed file when available; falls back to hardcoded
  - closing-line kickoff wiring: load_kickoff_times() returns 72 kickoffs
  - simulator accepts a groups= parameter without error
  - frontend export script produces fixture_source.json and fixture_schedule.json
"""
from __future__ import annotations

import json
import tempfile
from itertools import combinations
from pathlib import Path

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

SEED_PATH = Path(__file__).parent.parent / "data" / "seed" / "wc2026_fixtures.json"


def _load_seed() -> dict:
    return json.loads(SEED_PATH.read_text())


def _group_stage(data: dict) -> list[dict]:
    return [f for f in data["fixtures"] if f["stage"] == "group"]


# ── 1. Schema validation ──────────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "match_id", "stage", "group", "home_team", "away_team",
    "kickoff_at", "venue", "city", "host_country", "source", "is_placeholder",
}


def test_all_required_fields_present():
    data = _load_seed()
    for fix in data["fixtures"]:
        missing = REQUIRED_FIELDS - fix.keys()
        assert not missing, f"match_id={fix.get('match_id')!r} missing fields: {missing}"


def test_metadata_present():
    data = _load_seed()
    meta = data.get("metadata", {})
    for key in ("source", "is_official", "description", "total_fixtures"):
        assert key in meta, f"metadata missing key: {key!r}"


# ── 2. 48 unique teams ────────────────────────────────────────────────────────

def test_48_unique_teams():
    data = _load_seed()
    gs = _group_stage(data)
    teams = {t for f in gs for t in (f["home_team"], f["away_team"])}
    assert len(teams) == 48, f"Expected 48 unique teams, got {len(teams)}"


# ── 3. 12 groups ──────────────────────────────────────────────────────────────

def test_12_groups():
    data = _load_seed()
    gs = _group_stage(data)
    groups = {f["group"] for f in gs}
    assert len(groups) == 12, f"Expected 12 groups, got {len(groups)}: {sorted(groups)}"
    assert groups == set("ABCDEFGHIJKL"), f"Unexpected group letters: {sorted(groups)}"


# ── 4. 4 teams per group ──────────────────────────────────────────────────────

def test_4_teams_per_group():
    data = _load_seed()
    gs = _group_stage(data)
    teams_by_group: dict[str, set[str]] = {}
    for f in gs:
        teams_by_group.setdefault(f["group"], set()).update(
            [f["home_team"], f["away_team"]]
        )
    for g, teams in teams_by_group.items():
        assert len(teams) == 4, f"Group {g} has {len(teams)} teams (expected 4): {teams}"


# ── 5. 72 group-stage fixtures ────────────────────────────────────────────────

def test_72_group_stage_fixtures():
    data = _load_seed()
    gs = _group_stage(data)
    assert len(gs) == 72, f"Expected 72 group-stage fixtures, got {len(gs)}"


def test_6_fixtures_per_group():
    data = _load_seed()
    gs = _group_stage(data)
    by_group: dict[str, list] = {}
    for f in gs:
        by_group.setdefault(f["group"], []).append(f)
    for g, fixtures in by_group.items():
        assert len(fixtures) == 6, f"Group {g} has {len(fixtures)} fixtures (expected 6)"


# ── 6. No duplicate match_id ──────────────────────────────────────────────────

def test_no_duplicate_match_ids():
    data = _load_seed()
    ids = [f["match_id"] for f in data["fixtures"]]
    duplicates = {mid for mid in ids if ids.count(mid) > 1}
    assert not duplicates, f"Duplicate match_id values: {duplicates}"


# ── 7. All teams resolve to canonical IDs ────────────────────────────────────

def test_all_teams_are_canonical():
    from oracle.teams import resolve_team

    data = _load_seed()
    gs = _group_stage(data)
    unresolved = []
    for fix in gs:
        for field in ("home_team", "away_team"):
            raw = fix[field]
            try:
                resolved = resolve_team(raw)
                assert resolved == raw, (
                    f"match_id={fix['match_id']!r}: {field}={raw!r} resolves "
                    f"to {resolved!r} — seed file should store canonical IDs directly"
                )
            except KeyError:
                unresolved.append((fix["match_id"], field, raw))
    assert not unresolved, f"Unresolved teams: {unresolved}"


# ── 8. Official flag is set correctly (Week 12: real data) ────────────────────

def test_official_flag_is_set():
    data = _load_seed()
    meta = data.get("metadata", {})
    assert meta.get("is_official") is True, "metadata.is_official should be True"
    assert meta.get("is_placeholder") is False, "metadata.is_placeholder should be False"
    for fix in data["fixtures"]:
        assert fix["is_placeholder"] is False, (
            f"match_id={fix['match_id']!r}: expected is_placeholder=false"
        )


def test_all_kickoff_times_non_null():
    data = _load_seed()
    gs = _group_stage(data)
    null_kickoffs = [f["match_id"] for f in gs if f.get("kickoff_at") is None]
    assert not null_kickoffs, (
        f"Official fixtures must have kickoff_at set; missing: {null_kickoffs}"
    )


def test_source_field_is_consistent():
    data = _load_seed()
    meta = data.get("metadata", {})
    meta_source = meta.get("source")
    for fix in data["fixtures"]:
        assert fix["source"] == meta_source, (
            f"match_id={fix['match_id']!r}: source {fix['source']!r} != "
            f"metadata source {meta_source!r}"
        )


# ── 9. derive_groups_from_fixtures ───────────────────────────────────────────

def test_derive_groups_matches_seed_teams():
    from oracle.sim.groups import WC2026_GROUPS, derive_groups_from_fixtures

    data = _load_seed()
    gs = _group_stage(data)
    derived = derive_groups_from_fixtures(gs)

    assert set(derived.keys()) == set(WC2026_GROUPS.keys()), (
        f"Group keys mismatch: derived={sorted(derived)}, expected={sorted(WC2026_GROUPS)}"
    )
    for g in WC2026_GROUPS:
        assert set(derived[g]) == set(WC2026_GROUPS[g]), (
            f"Group {g}: derived teams {set(derived[g])} != expected {set(WC2026_GROUPS[g])}"
        )
        assert len(derived[g]) == 4


def test_load_groups_uses_seed_file():
    from oracle.sim.groups import WC2026_GROUPS, load_groups

    groups, meta = load_groups(seed_path=SEED_PATH)
    assert len(groups) == 12
    for g, teams in groups.items():
        assert len(teams) == 4
        assert set(teams) == set(WC2026_GROUPS[g])
    assert meta.get("is_official") is True
    assert meta.get("is_placeholder") is False
    assert meta.get("n_fixtures_loaded") == 72


def test_load_groups_falls_back_to_hardcoded(tmp_path):
    from oracle.sim.groups import WC2026_GROUPS, load_groups

    missing = tmp_path / "nonexistent.json"
    groups, meta = load_groups(seed_path=missing)
    assert groups is WC2026_GROUPS
    assert meta.get("is_placeholder") is False
    assert meta.get("source") == "official_fifa_2026_hardcoded"


# ── 10. Closing-line kickoff wiring ───────────────────────────────────────────

def test_load_kickoff_times_returns_all_kickoffs():
    from oracle.ingest.fixtures import load_kickoff_times

    kickoffs = load_kickoff_times(SEED_PATH)
    assert len(kickoffs) == 72, (
        f"Official seed has 72 fixtures with non-null kickoffs — "
        f"expected 72 entries, got {len(kickoffs)}"
    )
    for pair, dt in kickoffs.items():
        assert dt.tzinfo is not None, f"kickoff for {pair} must be timezone-aware"


def test_load_kickoff_times_returns_populated_dict(tmp_path):
    from oracle.ingest.fixtures import load_kickoff_times

    seed = {
        "metadata": {"source": "test"},
        "fixtures": [
            {
                "match_id": "test_001",
                "stage": "group",
                "group": "A",
                "home_team": "united_states",
                "away_team": "england",
                "kickoff_at": "2026-06-12T20:00:00+00:00",
                "venue": None,
                "city": None,
                "host_country": None,
                "source": "test",
                "is_placeholder": False,
            },
            {
                "match_id": "test_002",
                "stage": "group",
                "group": "A",
                "home_team": "romania",
                "away_team": "senegal",
                "kickoff_at": None,
                "venue": None,
                "city": None,
                "host_country": None,
                "source": "test",
                "is_placeholder": True,
            },
        ],
    }
    p = tmp_path / "fixtures.json"
    p.write_text(json.dumps(seed))

    kickoffs = load_kickoff_times(p)
    assert len(kickoffs) == 1
    assert ("united_states", "england") in kickoffs
    from datetime import timezone
    assert kickoffs[("united_states", "england")].tzinfo is not None


def test_load_kickoff_times_missing_file(tmp_path):
    from oracle.ingest.fixtures import load_kickoff_times

    kickoffs = load_kickoff_times(tmp_path / "missing.json")
    assert kickoffs == {}


# ── 11. Simulator accepts groups parameter ────────────────────────────────────

def test_simulator_accepts_groups_param():
    from oracle.ingest.results import load_results
    from oracle.ratings.elo import EloRatings
    from oracle.sim.groups import load_groups
    from oracle.sim.tournament import monte_carlo

    df = load_results()
    elo = EloRatings()
    elo.fit(df)

    groups, _ = load_groups(seed_path=SEED_PATH)
    mc = monte_carlo(elo, n_sims=10, seed=0, groups=groups)

    assert set(mc["team_probs"].keys()) == {
        t for g in groups.values() for t in g
    }
    assert mc["n_sims"] == 10


def test_simulator_groups_match_seed():
    from oracle.ingest.results import load_results
    from oracle.ratings.elo import EloRatings
    from oracle.sim.groups import WC2026_GROUPS, load_groups
    from oracle.sim.tournament import monte_carlo

    df = load_results()
    elo = EloRatings()
    elo.fit(df)

    groups, meta = load_groups(seed_path=SEED_PATH)
    mc = monte_carlo(elo, n_sims=5, seed=1, groups=groups)

    # Every team in the seed should appear in team_probs
    all_seed_teams = {t for g in WC2026_GROUPS.values() for t in g}
    assert set(mc["team_probs"].keys()) == all_seed_teams


# ── 12. ingest_fixtures validation ────────────────────────────────────────────

def test_ingest_fixtures_validates_schema():
    from oracle.ingest.fixtures import FixtureValidationError, load_fixtures

    bad_fixture = {
        "metadata": {"source": "test"},
        "fixtures": [
            {"match_id": "x", "stage": "group"}  # missing many required fields
        ],
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(bad_fixture, f)
        p = Path(f.name)

    with pytest.raises(FixtureValidationError, match="missing required fields"):
        load_fixtures(p)
    p.unlink()


def test_ingest_fixtures_rejects_duplicate_match_id():
    from oracle.ingest.fixtures import FixtureValidationError, load_fixtures

    fix = {
        "match_id": "dup", "stage": "group", "group": "A",
        "home_team": "united_states", "away_team": "england",
        "kickoff_at": None, "venue": None, "city": None,
        "host_country": None, "source": "test", "is_placeholder": True,
    }
    data = {"metadata": {"source": "test"}, "fixtures": [fix, fix]}
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(data, f)
        p = Path(f.name)

    with pytest.raises(FixtureValidationError, match="Duplicate match_id"):
        load_fixtures(p)
    p.unlink()


def test_ingest_fixtures_rejects_unknown_team():
    from oracle.ingest.fixtures import load_fixtures

    fix = {
        "match_id": "x1", "stage": "group", "group": "A",
        "home_team": "this_team_does_not_exist",
        "away_team": "england",
        "kickoff_at": None, "venue": None, "city": None,
        "host_country": None, "source": "test", "is_placeholder": True,
    }
    data = {"metadata": {"source": "test"}, "fixtures": [fix]}
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(data, f)
        p = Path(f.name)

    with pytest.raises(KeyError, match="unresolved team"):
        load_fixtures(p)
    p.unlink()


def test_load_fixtures_from_real_seed():
    from oracle.ingest.fixtures import load_fixtures

    df = load_fixtures(SEED_PATH)
    assert len(df) == 72
    assert "match_id" in df.columns
    assert "kickoff_at" in df.columns
    assert "is_placeholder" in df.columns
    assert "source" in df.columns
    assert df["is_placeholder"].to_list().count(True) == 0
    assert df["is_placeholder"].to_list().count(False) == 72


# ── 13. Placeholder flag propagates into blend artifact ───────────────────────

def test_fixture_source_in_blend_artifact():
    """market_blend_summary.json must contain fixture_source with is_placeholder."""
    artifact = Path(__file__).parent.parent / "data" / "artifacts" / "market_blend_summary.json"
    if not artifact.exists():
        pytest.skip("market_blend_summary.json not generated yet — run make blend")
    data = json.loads(artifact.read_text())
    assert "fixture_source" in data, "fixture_source key missing from market_blend_summary.json"
    fs = data["fixture_source"]
    assert "is_placeholder" in fs
    assert "is_official" in fs
    assert "source" in fs


def test_fixture_source_in_sim_artifact():
    """sim_2026_summary.json must contain fixture_source with is_placeholder."""
    artifact = Path(__file__).parent.parent / "data" / "artifacts" / "sim_2026_summary.json"
    if not artifact.exists():
        pytest.skip("sim_2026_summary.json not generated yet — run make simulate")
    data = json.loads(artifact.read_text())
    assert "fixture_source" in data, "fixture_source key missing from sim_2026_summary.json"
    fs = data["fixture_source"]
    assert "is_placeholder" in fs
    assert "is_official" in fs


# ── 14. Frontend export produces fixture_source.json ─────────────────────────

def test_export_produces_fixture_source(tmp_path):
    """export_artifacts.py _build_fixture_source() returns expected keys."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_artifacts import _build_fixture_source  # type: ignore

    result = _build_fixture_source()
    assert "is_official" in result
    assert "is_placeholder" in result
    assert "source" in result
    assert "groups" in result
    assert len(result["groups"]) == 12
    assert result["is_official"] is True
    assert result["is_placeholder"] is False


def test_export_produces_fixture_schedule():
    """export_artifacts.py _build_fixture_schedule() returns 144 entries (72 × bidirectional)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_artifacts import _build_fixture_schedule  # type: ignore

    result = _build_fixture_schedule()
    assert len(result) == 144, f"Expected 144 bidirectional keys, got {len(result)}"
    first = next(iter(result.values()))
    assert "kickoff_at" in first
    assert "venue" in first
    assert "city" in first
    assert "host_country" in first
    # All kickoffs should be non-null in official data
    null_ko = [k for k, v in result.items() if v.get("kickoff_at") is None]
    assert not null_ko, f"Official schedule should have no null kickoffs: {null_ko[:3]}"
