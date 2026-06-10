"""
Tests for oracle.results.normalize — Week 17.

Coverage:
  normalize_raw()
    - valid manual result normalizes correctly
    - valid external result resolves via team names
    - team alias resolves ("México" → "mexico")
    - exact match_id takes priority over team lookup
    - reversed home/away raises with clear message
    - unknown team raises ResultProviderError
    - invalid status raises ResultProviderError
    - negative goals raise ResultProviderError
    - finished without goals raises ResultProviderError
    - match_id not in fixture index raises
    - no fixture match for team pair raises

  merge_results()
    - manual-only returns all manual results
    - external-only returns all external results
    - manual overrides external on same match_id
    - n_duplicates counted correctly
    - unresolved external tracked (not raised)
    - external bad team → unresolved warning (not exception)
    - empty both providers → empty list
    - manual bad result → raises (strict)
    - merge report n_merged correct
    - merge report n_manual + n_external correct
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracle.results.normalize import (
    _build_pair_index,
    _load_fixture_index,
    merge_results,
    normalize_raw,
)
from oracle.results.provider import RawResult, ResultProviderError


# ── Shared test fixture seed ──────────────────────────────────────────────────

FIXTURE_ROWS = [
    {
        "match_id": "wc2026_m001", "stage": "group", "group": "A",
        "home_team": "mexico", "away_team": "south_africa",
        "kickoff_at": "2026-06-11T19:00:00+00:00",
        "venue": "Estadio Azteca", "city": "Mexico City",
        "host_country": "Mexico", "source": "test", "is_placeholder": False,
    },
    {
        "match_id": "wc2026_m002", "stage": "group", "group": "A",
        "home_team": "south_korea", "away_team": "czech_republic",
        "kickoff_at": "2026-06-12T02:00:00+00:00",
        "venue": "SoFi Stadium", "city": "Inglewood",
        "host_country": "USA", "source": "test", "is_placeholder": False,
    },
    {
        "match_id": "wc2026_m003", "stage": "group", "group": "B",
        "home_team": "canada", "away_team": "bosnia_herzegovina",
        "kickoff_at": "2026-06-12T19:00:00+00:00",
        "venue": "BC Place", "city": "Vancouver",
        "host_country": "Canada", "source": "test", "is_placeholder": False,
    },
]


def _fixture_seed_path(tmp_path: Path) -> Path:
    p = tmp_path / "fixtures.json"
    p.write_text(json.dumps({"metadata": {}, "fixtures": FIXTURE_ROWS}))
    return p


def _make_fixture_index(tmp_path: Path):
    fp = _fixture_seed_path(tmp_path)
    return _load_fixture_index(fp)


def _make_raw(
    *,
    source: str = "manual",
    home_team: str = "mexico",
    away_team: str = "south_africa",
    status: str = "finished",
    match_id: str | None = "wc2026_m001",
    home_goals: int | None = 2,
    away_goals: int | None = 0,
    **kwargs,
) -> RawResult:
    return RawResult(
        source=source,
        home_team=home_team,
        away_team=away_team,
        status=status,
        match_id=match_id,
        home_goals=home_goals,
        away_goals=away_goals,
        **kwargs,
    )


# ── normalize_raw ─────────────────────────────────────────────────────────────

class TestNormalizeRaw:
    def _indexes(self, tmp_path):
        idx = _make_fixture_index(tmp_path)
        pair_idx = _build_pair_index(idx)
        return idx, pair_idx

    def test_valid_manual_result(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001")
        nr = normalize_raw(raw, idx, pidx)
        assert nr.match_id == "wc2026_m001"
        assert nr.home_team == "mexico"
        assert nr.away_team == "south_africa"
        assert nr.group == "A"
        assert nr.home_goals == 2
        assert nr.away_goals == 0
        assert nr.status == "finished"
        assert nr.source == "manual"

    def test_kickoff_from_fixture_when_raw_none(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001", kickoff_at=None)
        nr = normalize_raw(raw, idx, pidx)
        assert nr.kickoff_at == "2026-06-11T19:00:00+00:00"

    def test_raw_kickoff_takes_precedence(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001", kickoff_at="2026-06-11T18:00:00+00:00")
        nr = normalize_raw(raw, idx, pidx)
        assert nr.kickoff_at == "2026-06-11T18:00:00+00:00"

    def test_resolve_via_canonical_team_names(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        # No match_id — resolve by team names (already canonical)
        raw = _make_raw(
            source="local_json",
            match_id=None,
            home_team="mexico",
            away_team="south_africa",
        )
        nr = normalize_raw(raw, idx, pidx)
        assert nr.match_id == "wc2026_m001"

    def test_team_alias_resolves(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        # "México" → "mexico" via teams.py alias map
        raw = _make_raw(
            source="local_json",
            match_id=None,
            home_team="México",     # alias
            away_team="south_africa",
        )
        nr = normalize_raw(raw, idx, pidx)
        assert nr.match_id == "wc2026_m001"
        assert nr.home_team == "mexico"

    def test_explicit_match_id_beats_team_lookup(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(
            source="local_json",
            match_id="wc2026_m002",
            home_team="mexico",    # wrong teams for this match_id — but match_id wins
            away_team="south_africa",
            home_goals=1,
            away_goals=0,
        )
        # match_id lookup uses fixture teams, ignoring raw teams
        nr = normalize_raw(raw, idx, pidx)
        assert nr.match_id == "wc2026_m002"
        assert nr.home_team == "south_korea"

    def test_reversed_home_away_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(
            source="local_json",
            match_id=None,
            home_team="south_africa",   # reversed
            away_team="mexico",
        )
        with pytest.raises(ResultProviderError, match="reversed home/away"):
            normalize_raw(raw, idx, pidx)

    def test_unknown_home_team_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(
            source="local_json",
            match_id=None,
            home_team="atlantis",
            away_team="south_africa",
        )
        with pytest.raises(ResultProviderError, match="Cannot resolve home_team"):
            normalize_raw(raw, idx, pidx)

    def test_unknown_away_team_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(
            source="local_json",
            match_id=None,
            home_team="mexico",
            away_team="atlantis",
        )
        with pytest.raises(ResultProviderError, match="Cannot resolve away_team"):
            normalize_raw(raw, idx, pidx)

    def test_no_fixture_for_pair_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(
            source="local_json",
            match_id=None,
            home_team="canada",
            away_team="south_africa",  # not a real fixture pair
            home_goals=1,
            away_goals=0,
        )
        with pytest.raises(ResultProviderError, match="No fixture found"):
            normalize_raw(raw, idx, pidx)

    def test_invalid_status_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001", status="abandoned", home_goals=None, away_goals=None)
        with pytest.raises(ResultProviderError, match="Invalid status"):
            normalize_raw(raw, idx, pidx)

    def test_finished_without_goals_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001", status="finished", home_goals=None, away_goals=None)
        with pytest.raises(ResultProviderError, match="requires home_goals"):
            normalize_raw(raw, idx, pidx)

    def test_negative_home_goals_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001", home_goals=-1, away_goals=0)
        with pytest.raises(ResultProviderError, match="non-negative integer"):
            normalize_raw(raw, idx, pidx)

    def test_negative_away_goals_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001", home_goals=0, away_goals=-2)
        with pytest.raises(ResultProviderError, match="non-negative integer"):
            normalize_raw(raw, idx, pidx)

    def test_match_id_not_in_index_raises(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m999")
        with pytest.raises(ResultProviderError, match="not found in fixture seed"):
            normalize_raw(raw, idx, pidx)

    def test_postponed_without_goals_accepted(self, tmp_path):
        idx, pidx = self._indexes(tmp_path)
        raw = _make_raw(match_id="wc2026_m001", status="postponed",
                        home_goals=None, away_goals=None)
        nr = normalize_raw(raw, idx, pidx)
        assert nr.status == "postponed"
        assert nr.home_goals is None


# ── merge_results ─────────────────────────────────────────────────────────────

class TestMergeResults:
    def _fp(self, tmp_path):
        return _fixture_seed_path(tmp_path)

    def test_manual_only(self, tmp_path):
        fp = self._fp(tmp_path)
        manual = [_make_raw(match_id="wc2026_m001")]
        merged, report = merge_results(manual, [], fixture_path=fp)
        assert len(merged) == 1
        assert merged[0].source == "manual"
        assert report.n_manual == 1
        assert report.n_external == 0
        assert report.n_merged == 1

    def test_external_only(self, tmp_path):
        fp = self._fp(tmp_path)
        external = [_make_raw(source="local_json", match_id="wc2026_m002",
                               home_team="south_korea", away_team="czech_republic",
                               home_goals=1, away_goals=1)]
        merged, report = merge_results([], external, fixture_path=fp)
        assert len(merged) == 1
        assert merged[0].source == "local_json"
        assert report.n_external == 1
        assert report.n_manual == 0

    def test_manual_overrides_external(self, tmp_path):
        fp = self._fp(tmp_path)
        manual   = [_make_raw(match_id="wc2026_m001", home_goals=2, away_goals=0)]
        external = [_make_raw(source="local_json", match_id="wc2026_m001",
                               home_team="mexico", away_team="south_africa",
                               home_goals=1, away_goals=1)]
        merged, report = merge_results(manual, external, fixture_path=fp)
        # manual wins
        assert len(merged) == 1
        assert merged[0].home_goals == 2
        assert merged[0].source == "manual"
        assert report.n_duplicates == 1
        assert len(report.overrides) == 1

    def test_override_details_recorded(self, tmp_path):
        fp = self._fp(tmp_path)
        manual   = [_make_raw(match_id="wc2026_m001", home_goals=2, away_goals=0)]
        external = [_make_raw(source="local_json", match_id="wc2026_m001",
                               home_team="mexico", away_team="south_africa",
                               home_goals=0, away_goals=0)]
        _, report = merge_results(manual, external, fixture_path=fp)
        assert report.overrides[0]["manual_goals"] == "2-0"
        assert report.overrides[0]["external_goals"] == "0-0"

    def test_no_conflict_both_kept(self, tmp_path):
        fp = self._fp(tmp_path)
        manual   = [_make_raw(match_id="wc2026_m001")]
        external = [_make_raw(source="local_json", match_id="wc2026_m002",
                               home_team="south_korea", away_team="czech_republic",
                               home_goals=1, away_goals=0)]
        merged, report = merge_results(manual, external, fixture_path=fp)
        assert len(merged) == 2
        assert report.n_duplicates == 0

    def test_external_unresolved_tracked_not_raised(self, tmp_path):
        fp = self._fp(tmp_path)
        external = [RawResult(
            source="local_json",
            home_team="atlantis",   # unknown
            away_team="south_africa",
            status="finished",
            home_goals=1,
            away_goals=0,
        )]
        merged, report = merge_results([], external, fixture_path=fp)
        assert len(merged) == 0
        assert len(report.unresolved) == 1
        assert len(report.warnings) >= 1

    def test_manual_bad_result_raises(self, tmp_path):
        fp = self._fp(tmp_path)
        manual = [_make_raw(match_id="wc2026_m999")]  # unknown match_id
        with pytest.raises(ResultProviderError, match="Manual seed normalisation failed"):
            merge_results(manual, [], fixture_path=fp)

    def test_empty_both_returns_empty(self, tmp_path):
        fp = self._fp(tmp_path)
        merged, report = merge_results([], [], fixture_path=fp)
        assert merged == []
        assert report.n_merged == 0
        assert report.n_manual == 0
        assert report.n_external == 0

    def test_report_has_generated_at(self, tmp_path):
        fp = self._fp(tmp_path)
        _, report = merge_results([], [], fixture_path=fp)
        assert report.generated_at

    def test_report_to_dict_serialisable(self, tmp_path):
        fp = self._fp(tmp_path)
        _, report = merge_results([], [], fixture_path=fp)
        import json
        d = json.dumps(report.to_dict())
        parsed = json.loads(d)
        assert "n_merged" in parsed

    def test_external_duplicate_warns_not_raises(self, tmp_path):
        fp = self._fp(tmp_path)
        # Two external results for the same match_id
        ext = [
            _make_raw(source="local_json", match_id="wc2026_m001",
                       home_team="mexico", away_team="south_africa",
                       home_goals=1, away_goals=0),
            _make_raw(source="local_json", match_id="wc2026_m001",
                       home_team="mexico", away_team="south_africa",
                       home_goals=2, away_goals=1),
        ]
        merged, report = merge_results([], ext, fixture_path=fp)
        # Should keep only the first and warn
        assert len(merged) == 1
        assert any("duplicate" in w.lower() for w in report.warnings)
