"""
Odds provider interface and implementations.

OddsProvider      — abstract base class; all providers implement fetch_upcoming_1x2().
DummyOddsProvider — hard-coded snapshots for tests and dry-runs; zero network calls.
TheOddsAPIProvider — The Odds API v4; requires ODDS_API_KEY env var.

The Odds API integration:
  - Fetches the 'h2h' (1X2) market for soccer_fifa_world_cup events.
  - API key read from ODDS_API_KEY env var; raise OddsAPIKeyMissing if absent.
  - Maps outcome names ("France", "Draw", "Germany") to ("home", "draw", "away").
  - Accepts _http_get callable injection for tests (no monkeypatching needed).
  - Applies Shin de-vig on ingest via build_1x2_snapshots().
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable, Optional

from oracle.market.schema import OddsSnapshot, build_1x2_snapshots

log = logging.getLogger(__name__)


class OddsAPIKeyMissing(Exception):
    """Raised when TheOddsAPIProvider is instantiated without an API key."""


class OddsProvider(ABC):
    """Abstract source of market odds snapshots."""

    @abstractmethod
    def fetch_upcoming_1x2(
        self,
        bookmakers: Optional[list[str]] = None,
    ) -> list[OddsSnapshot]:
        """Fetch current 1X2 odds for all upcoming events.

        Returns one OddsSnapshot per (event × bookmaker × selection).
        """


class DummyOddsProvider(OddsProvider):
    """Hard-coded snapshots for tests and pipeline dry-runs. No network calls."""

    _SOURCE = "dummy"
    _BOOKMAKER = "dummy_book"

    # Two valid group-stage matchups with time-separated captures.
    # Group B: mexico, france, south_korea, morocco
    # Group C: canada, germany, japan, nigeria
    # Using canonical team IDs so the blend pipeline can match them.
    _FIXTURES: list[dict] = [
        {
            "match_id": "wc2026_B_01",
            "home_team": "mexico",
            "away_team": "france",
            "captures": [
                {
                    "odds": {"home": 2.40, "draw": 3.60, "away": 3.00},
                    "captured_at": "2026-06-11T08:00:00Z",
                },
                {
                    "odds": {"home": 2.25, "draw": 3.50, "away": 3.20},
                    "captured_at": "2026-06-11T15:00:00Z",
                },
            ],
        },
        {
            "match_id": "wc2026_C_01",
            "home_team": "canada",
            "away_team": "germany",
            "captures": [
                {
                    "odds": {"home": 3.80, "draw": 3.50, "away": 2.00},
                    "captured_at": "2026-06-12T10:00:00Z",
                },
            ],
        },
    ]

    def fetch_upcoming_1x2(
        self,
        bookmakers: Optional[list[str]] = None,
    ) -> list[OddsSnapshot]:
        snapshots: list[OddsSnapshot] = []
        for fixture in self._FIXTURES:
            for capture in fixture["captures"]:
                snapshots.extend(
                    build_1x2_snapshots(
                        match_id=fixture["match_id"],
                        home_team=fixture["home_team"],
                        away_team=fixture["away_team"],
                        bookmaker=self._BOOKMAKER,
                        odds_1x2=capture["odds"],
                        captured_at=capture["captured_at"],
                        source=self._SOURCE,
                    )
                )
        return snapshots


class TheOddsAPIProvider(OddsProvider):
    """The Odds API v4 integration for WC 2026 1X2 markets.

    Requires ODDS_API_KEY environment variable (free-tier key sufficient).

    Args:
        api_key:   Explicit key; overrides ODDS_API_KEY env var if provided.
        _http_get: Injectable HTTP GET callable (default: requests.get).
                   Signature: (url, *, params, timeout) -> response.
                   Used in tests to inject a fake response without any
                   network I/O; no monkeypatching required.
    """

    _BASE_URL = "https://api.the-odds-api.com/v4"
    _SPORT = "soccer_fifa_world_cup"
    _MARKET = "h2h"
    _SOURCE = "the-odds-api"

    def __init__(
        self,
        api_key: Optional[str] = None,
        _http_get: Optional[Callable] = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("ODDS_API_KEY")
        if not self._api_key:
            raise OddsAPIKeyMissing(
                "ODDS_API_KEY environment variable not set. "
                "Set it before using TheOddsAPIProvider. "
                "Use DummyOddsProvider for tests and dry-runs."
            )
        self._http_get = _http_get

    def fetch_upcoming_1x2(
        self,
        bookmakers: Optional[list[str]] = None,
    ) -> list[OddsSnapshot]:
        """Fetch all upcoming WC 2026 h2h odds from The Odds API."""
        url = f"{self._BASE_URL}/sports/{self._SPORT}/odds/"
        params: dict = {
            "apiKey": self._api_key,
            "regions": "eu",
            "markets": self._MARKET,
            "oddsFormat": "decimal",
        }
        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)

        captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        events = self._get(url, params)

        snapshots: list[OddsSnapshot] = []
        for event in events:
            snapshots.extend(self._parse_event(event, captured_at))

        log.info("Fetched %d 1X2 snapshot rows from The Odds API.", len(snapshots))
        return snapshots

    def _get(self, url: str, params: dict) -> list[dict]:
        if self._http_get is not None:
            resp = self._http_get(url, params=params, timeout=30)
        else:
            try:
                import requests
            except ImportError as exc:
                raise RuntimeError(
                    "requests package required. Install with: pip install requests"
                ) from exc
            resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _parse_event(self, event: dict, captured_at: str) -> list[OddsSnapshot]:
        source_event_id = event.get("id")
        home_raw = event.get("home_team", "")
        away_raw = event.get("away_team", "")
        match_id = source_event_id or f"odds_api_{home_raw}_{away_raw}"

        snapshots: list[OddsSnapshot] = []
        for bm in event.get("bookmakers", []):
            bookmaker = bm.get("key", "unknown")
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "h2h":
                    continue
                odds_map = _map_h2h_outcomes(mkt.get("outcomes", []), home_raw, away_raw)
                if set(odds_map.keys()) != {"home", "draw", "away"}:
                    log.debug(
                        "Skipping incomplete h2h market: event=%s bm=%s got=%s",
                        source_event_id, bookmaker, list(odds_map.keys()),
                    )
                    continue
                snapshots.extend(
                    build_1x2_snapshots(
                        match_id=match_id,
                        home_team=home_raw.lower(),
                        away_team=away_raw.lower(),
                        bookmaker=bookmaker,
                        odds_1x2=odds_map,
                        captured_at=captured_at,
                        source=self._SOURCE,
                        source_event_id=source_event_id,
                    )
                )
        return snapshots


def _map_h2h_outcomes(
    outcomes: list[dict],
    home_team: str,
    away_team: str,
) -> dict[str, float]:
    """Map Odds API outcome names to {home, draw, away} decimal odds.

    The Odds API uses team full names as outcome labels ("France") not
    positional labels ("home"). "Draw" is the only standardised label.
    Unrecognised names are skipped with a debug log.
    """
    result: dict[str, float] = {}
    for o in outcomes:
        name = o.get("name", "")
        price = float(o.get("price", 0.0))
        if name == "Draw":
            result["draw"] = price
        elif name.lower() == home_team.lower():
            result["home"] = price
        elif name.lower() == away_team.lower():
            result["away"] = price
        else:
            log.debug("Unrecognised outcome name %r — skipping.", name)
    return result
