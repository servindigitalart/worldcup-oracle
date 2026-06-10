"""
Tests for oracle.results.manual and oracle.results.external — Week 17.

Coverage:
  ManualSeedProvider
    - empty seed returns empty list
    - valid seed with finished result returns RawResult list
    - missing seed file raises ResultProviderError
    - malformed JSON raises ResultProviderError
    - duplicate match_id raises ResultProviderError
    - unknown match_id raises ResultProviderError
    - team mismatch raises ResultProviderError
    - invalid status raises ResultProviderError
    - finished without goals raises ResultProviderError
    - negative goals raise ResultProviderError

  LocalJsonResultProvider
    - absent file returns empty list (never fails)
    - valid file returns RawResult list
    - invalid JSON raises ResultProviderError
    - not-an-object raises ResultProviderError
    - results not a list raises ResultProviderError
    - missing home_team raises ResultProviderError
    - invalid status raises ResultProviderError
    - finished without goals raises ResultProviderError
    - never makes network calls (no socket calls)
    - result with match_id field is accepted
    - result without match_id is accepted (resolved later)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracle.results.manual import ManualSeedProvider
from oracle.results.external import LocalJsonResultProvider
from oracle.results.provider import ResultProviderError, RawResult


# ── Fixture helpers ────────────────────────────────────────────────────────────

def _minimal_fixture_seed(tmp_path: Path) -> Path:
    """Write a minimal fixture seed with 3 matches and return its path."""
    data = {
        "metadata": {"source": "test", "is_official": True},
        "fixtures": [
            {
                "match_id": "wc2026_m001",
                "stage": "group",
                "group": "A",
                "home_team": "mexico",
                "away_team": "south_africa",
                "kickoff_at": "2026-06-11T19:00:00+00:00",
                "venue": "Estadio Azteca",
                "city": "Mexico City",
                "host_country": "Mexico",
                "source": "test",
                "is_placeholder": False,
            },
            {
                "match_id": "wc2026_m002",
                "stage": "group",
                "group": "A",
                "home_team": "south_korea",
                "away_team": "czech_republic",
                "kickoff_at": "2026-06-12T02:00:00+00:00",
                "venue": "SoFi Stadium",
                "city": "Inglewood",
                "host_country": "USA",
                "source": "test",
                "is_placeholder": False,
            },
            {
                "match_id": "wc2026_m003",
                "stage": "group",
                "group": "B",
                "home_team": "canada",
                "away_team": "bosnia_herzegovina",
                "kickoff_at": "2026-06-12T19:00:00+00:00",
                "venue": "BC Place",
                "city": "Vancouver",
                "host_country": "Canada",
                "source": "test",
                "is_placeholder": False,
            },
        ],
    }
    path = tmp_path / "wc2026_fixtures.json"
    path.write_text(json.dumps(data))
    return path


def _empty_results_seed(tmp_path: Path) -> Path:
    data = {
        "metadata": {"source": "manual"},
        "results": [],
    }
    path = tmp_path / "wc2026_results.json"
    path.write_text(json.dumps(data))
    return path


def _results_seed_with_one(tmp_path: Path) -> Path:
    data = {
        "metadata": {"source": "manual"},
        "results": [
            {
                "match_id":   "wc2026_m001",
                "home_team":  "mexico",
                "away_team":  "south_africa",
                "home_goals": 2,
                "away_goals": 0,
                "status":     "finished",
                "finished_at": "2026-06-11T23:00:00Z",
                "source":     "manual",
                "notes":      None,
            }
        ],
    }
    path = tmp_path / "wc2026_results.json"
    path.write_text(json.dumps(data))
    return path


# ── ManualSeedProvider ────────────────────────────────────────────────────────

class TestManualSeedProvider:
    def test_empty_seed_returns_empty_list(self, tmp_path):
        rp = _empty_results_seed(tmp_path)
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        results = provider.fetch_results()
        assert results == []

    def test_valid_result_parsed(self, tmp_path):
        rp = _results_seed_with_one(tmp_path)
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        results = provider.fetch_results()
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, RawResult)
        assert r.match_id == "wc2026_m001"
        assert r.home_team == "mexico"
        assert r.away_team == "south_africa"
        assert r.home_goals == 2
        assert r.away_goals == 0
        assert r.status == "finished"
        assert r.source == "manual"

    def test_result_has_kickoff_from_fixture(self, tmp_path):
        rp = _results_seed_with_one(tmp_path)
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        results = provider.fetch_results()
        assert results[0].kickoff_at == "2026-06-11T19:00:00+00:00"

    def test_missing_seed_raises(self, tmp_path):
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(
            results_path=tmp_path / "nonexistent.json",
            fixture_path=fp,
        )
        with pytest.raises(ResultProviderError, match="not found"):
            provider.fetch_results()

    def test_malformed_json_raises(self, tmp_path):
        rp = tmp_path / "bad.json"
        rp.write_text("this is not json")
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError):
            provider.fetch_results()

    def test_duplicate_match_id_raises(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [
                {"match_id": "wc2026_m001", "home_team": "mexico",
                 "away_team": "south_africa", "home_goals": 2, "away_goals": 0, "status": "finished"},
                {"match_id": "wc2026_m001", "home_team": "mexico",
                 "away_team": "south_africa", "home_goals": 1, "away_goals": 1, "status": "finished"},
            ],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError, match="duplicate"):
            provider.fetch_results()

    def test_unknown_match_id_raises(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [
                {"match_id": "wc2026_m999", "home_team": "x", "away_team": "y",
                 "home_goals": 1, "away_goals": 0, "status": "finished"},
            ],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError, match="not found in fixture seed"):
            provider.fetch_results()

    def test_team_mismatch_raises(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [
                {"match_id": "wc2026_m001", "home_team": "brazil",
                 "away_team": "south_africa", "home_goals": 2, "away_goals": 0, "status": "finished"},
            ],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError, match="don't match fixture"):
            provider.fetch_results()

    def test_invalid_status_raises(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [
                {"match_id": "wc2026_m001", "home_team": "mexico",
                 "away_team": "south_africa", "status": "abandoned"},
            ],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError, match="invalid status"):
            provider.fetch_results()

    def test_finished_without_goals_raises(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [
                {"match_id": "wc2026_m001", "home_team": "mexico",
                 "away_team": "south_africa", "status": "finished"},
            ],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError, match="requires home_goals"):
            provider.fetch_results()

    def test_negative_home_goals_raises(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [
                {"match_id": "wc2026_m001", "home_team": "mexico",
                 "away_team": "south_africa", "home_goals": -1, "away_goals": 0, "status": "finished"},
            ],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError, match="non-negative integer"):
            provider.fetch_results()

    def test_missing_match_id_raises(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [{"home_team": "mexico", "away_team": "south_africa", "status": "finished"}],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        with pytest.raises(ResultProviderError, match="missing 'match_id'"):
            provider.fetch_results()

    def test_postponed_status_accepted(self, tmp_path):
        data = {
            "metadata": {"source": "manual"},
            "results": [
                {"match_id": "wc2026_m002", "home_team": "south_korea",
                 "away_team": "czech_republic", "status": "postponed"},
            ],
        }
        rp = tmp_path / "results.json"
        rp.write_text(json.dumps(data))
        fp = _minimal_fixture_seed(tmp_path)
        provider = ManualSeedProvider(results_path=rp, fixture_path=fp)
        results = provider.fetch_results()
        assert len(results) == 1
        assert results[0].status == "postponed"


# ── LocalJsonResultProvider ───────────────────────────────────────────────────

class TestLocalJsonResultProvider:
    def _valid_payload(self) -> dict:
        return {
            "metadata": {
                "source": "local_json_result_provider",
                "captured_at": "2026-06-11T23:10:00Z",
            },
            "results": [
                {
                    "source_event_id": "abc123",
                    "home_team":  "Mexico",
                    "away_team":  "South Africa",
                    "home_goals": 2,
                    "away_goals": 0,
                    "status":     "finished",
                    "finished_at": "2026-06-11T23:00:00Z",
                }
            ],
        }

    def test_absent_file_returns_empty(self, tmp_path):
        provider = LocalJsonResultProvider(path=tmp_path / "nonexistent.json")
        results = provider.fetch_results()
        assert results == []

    def test_valid_file_parsed(self, tmp_path):
        p = tmp_path / "provider.json"
        p.write_text(json.dumps(self._valid_payload()))
        provider = LocalJsonResultProvider(path=p)
        results = provider.fetch_results()
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, RawResult)
        assert r.source == "local_json"
        assert r.home_team == "Mexico"
        assert r.away_team == "South Africa"
        assert r.home_goals == 2
        assert r.away_goals == 0
        assert r.status == "finished"
        assert r.source_event_id == "abc123"

    def test_captured_at_from_metadata(self, tmp_path):
        p = tmp_path / "provider.json"
        p.write_text(json.dumps(self._valid_payload()))
        provider = LocalJsonResultProvider(path=p)
        results = provider.fetch_results()
        assert results[0].captured_at == "2026-06-11T23:10:00Z"

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not valid json!!")
        provider = LocalJsonResultProvider(path=p)
        with pytest.raises(ResultProviderError):
            provider.fetch_results()

    def test_not_an_object_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps([1, 2, 3]))
        provider = LocalJsonResultProvider(path=p)
        with pytest.raises(ResultProviderError, match="must be a JSON object"):
            provider.fetch_results()

    def test_results_not_list_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"metadata": {}, "results": "not a list"}))
        provider = LocalJsonResultProvider(path=p)
        with pytest.raises(ResultProviderError, match="must be a JSON array"):
            provider.fetch_results()

    def test_missing_home_team_raises(self, tmp_path):
        data = {
            "metadata": {},
            "results": [{"away_team": "Mexico", "status": "finished", "home_goals": 1, "away_goals": 0}],
        }
        p = tmp_path / "p.json"
        p.write_text(json.dumps(data))
        provider = LocalJsonResultProvider(path=p)
        with pytest.raises(ResultProviderError, match="home_team or away_team"):
            provider.fetch_results()

    def test_invalid_status_raises(self, tmp_path):
        data = {
            "metadata": {},
            "results": [{"home_team": "Mexico", "away_team": "USA", "status": "ended"}],
        }
        p = tmp_path / "p.json"
        p.write_text(json.dumps(data))
        provider = LocalJsonResultProvider(path=p)
        with pytest.raises(ResultProviderError, match="invalid status"):
            provider.fetch_results()

    def test_finished_without_goals_raises(self, tmp_path):
        data = {
            "metadata": {},
            "results": [{"home_team": "Mexico", "away_team": "USA", "status": "finished"}],
        }
        p = tmp_path / "p.json"
        p.write_text(json.dumps(data))
        provider = LocalJsonResultProvider(path=p)
        with pytest.raises(ResultProviderError, match="requires home_goals"):
            provider.fetch_results()

    def test_negative_goals_raises(self, tmp_path):
        data = {
            "metadata": {},
            "results": [{"home_team": "Mexico", "away_team": "USA",
                         "status": "finished", "home_goals": -1, "away_goals": 0}],
        }
        p = tmp_path / "p.json"
        p.write_text(json.dumps(data))
        provider = LocalJsonResultProvider(path=p)
        with pytest.raises(ResultProviderError, match="non-negative integer"):
            provider.fetch_results()

    def test_result_with_explicit_match_id_accepted(self, tmp_path):
        data = {
            "metadata": {"captured_at": "2026-06-11T23:00:00Z"},
            "results": [{
                "match_id":   "wc2026_m001",
                "home_team":  "Mexico",
                "away_team":  "South Africa",
                "status":     "finished",
                "home_goals": 1,
                "away_goals": 0,
            }],
        }
        p = tmp_path / "p.json"
        p.write_text(json.dumps(data))
        provider = LocalJsonResultProvider(path=p)
        results = provider.fetch_results()
        assert results[0].match_id == "wc2026_m001"

    def test_result_without_match_id_accepted(self, tmp_path):
        data = {
            "metadata": {"captured_at": "2026-06-11T23:00:00Z"},
            "results": [{
                "home_team":  "Mexico",
                "away_team":  "South Africa",
                "status":     "finished",
                "home_goals": 2,
                "away_goals": 1,
            }],
        }
        p = tmp_path / "p.json"
        p.write_text(json.dumps(data))
        provider = LocalJsonResultProvider(path=p)
        results = provider.fetch_results()
        assert results[0].match_id is None

    def test_no_network_calls(self, tmp_path, monkeypatch):
        """Provider must never make network calls."""
        import socket
        original_connect = socket.socket.connect

        def _no_connect(self, *args, **kwargs):
            raise AssertionError("Network call detected in LocalJsonResultProvider!")

        monkeypatch.setattr(socket.socket, "connect", _no_connect)

        provider = LocalJsonResultProvider(path=tmp_path / "nonexistent.json")
        results = provider.fetch_results()
        assert results == []

    def test_empty_results_array(self, tmp_path):
        data = {"metadata": {"captured_at": "2026-06-11T23:00:00Z"}, "results": []}
        p = tmp_path / "p.json"
        p.write_text(json.dumps(data))
        provider = LocalJsonResultProvider(path=p)
        results = provider.fetch_results()
        assert results == []

    def test_provider_name(self):
        provider = LocalJsonResultProvider()
        assert provider.name == "local_json"

    def test_manual_provider_name(self):
        provider = ManualSeedProvider()
        assert provider.name == "manual"
