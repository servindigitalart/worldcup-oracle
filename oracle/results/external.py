"""
External result provider(s) — Week 17.

LocalJsonResultProvider
  Reads from data/raw/results/provider_results.json when present.
  Returns an empty list if the file is absent — this is not an error.
  Never makes network calls.

External provider JSON schema:
  {
    "metadata": {
      "source": "local_json_result_provider",
      "captured_at": "2026-06-11T23:10:00Z"
    },
    "results": [
      {
        "source_event_id": "provider_001",   // provider's own event ID
        "match_id":        "wc2026_m001",    // optional — may not be present
        "home_team":       "Mexico",         // free-text, normalised via oracle/teams.py
        "away_team":       "South Africa",
        "home_goals":      2,
        "away_goals":      0,
        "status":          "finished",
        "finished_at":     "2026-06-11T23:00:00Z"
      }
    ]
  }

Important:
  - External data writes only to artifacts, NEVER to data/seed/.
  - Raw JSON files stay in data/raw/results/.
  - Manual seed has priority over external results in merge step.
  - If match_id is absent, the normaliser resolves via team-pair lookup.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from oracle.results.provider import VALID_STATUSES, RawResult, ResultProviderError

log = logging.getLogger(__name__)

_DEFAULT_PROVIDER_PATH = (
    Path(__file__).parent.parent.parent
    / "data" / "raw" / "results" / "provider_results.json"
)


class LocalJsonResultProvider:
    """Reads results from a local JSON file in data/raw/results/.

    Returns an empty list if the file is absent.
    Never makes network calls.
    """

    name = "local_json"

    def __init__(self, path: Path = _DEFAULT_PROVIDER_PATH) -> None:
        self._path = path

    def fetch_results(self, fixtures: list | None = None) -> list[RawResult]:
        """Load results from the local JSON file.

        Returns
        -------
        List of RawResult — empty if file is absent.

        Raises
        ------
        ResultProviderError
            If the file exists but is malformed.
        """
        if not self._path.exists():
            log.debug("LocalJsonResultProvider: %s not found — returning empty", self._path)
            return []

        try:
            data = json.loads(self._path.read_text())
        except json.JSONDecodeError as exc:
            raise ResultProviderError(
                f"LocalJsonResultProvider: {self._path} is not valid JSON: {exc}"
            )

        if not isinstance(data, dict):
            raise ResultProviderError(
                f"LocalJsonResultProvider: {self._path} must be a JSON object"
            )

        meta = data.get("metadata", {})
        captured_at = meta.get("captured_at") or datetime.now(timezone.utc).isoformat()
        raw_list = data.get("results", [])

        if not isinstance(raw_list, list):
            raise ResultProviderError(
                f"LocalJsonResultProvider: 'results' must be a JSON array"
            )

        results: list[RawResult] = []

        for i, r in enumerate(raw_list):
            if not isinstance(r, dict):
                raise ResultProviderError(
                    f"LocalJsonResultProvider: result at index {i} must be an object"
                )

            home_team = r.get("home_team")
            away_team = r.get("away_team")
            if not home_team or not away_team:
                raise ResultProviderError(
                    f"LocalJsonResultProvider: result at index {i} missing "
                    "home_team or away_team"
                )

            status = r.get("status", "unknown")
            if status not in VALID_STATUSES:
                raise ResultProviderError(
                    f"LocalJsonResultProvider: result at index {i} has invalid "
                    f"status {status!r}. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
                )

            home_goals = r.get("home_goals")
            away_goals = r.get("away_goals")

            if status == "finished":
                if home_goals is None or away_goals is None:
                    raise ResultProviderError(
                        f"LocalJsonResultProvider: result at index {i}: "
                        "status=finished requires home_goals and away_goals"
                    )
                if not isinstance(home_goals, int) or home_goals < 0:
                    raise ResultProviderError(
                        f"LocalJsonResultProvider: result at index {i}: "
                        "home_goals must be a non-negative integer"
                    )
                if not isinstance(away_goals, int) or away_goals < 0:
                    raise ResultProviderError(
                        f"LocalJsonResultProvider: result at index {i}: "
                        "away_goals must be a non-negative integer"
                    )

            results.append(RawResult(
                source="local_json",
                source_event_id=r.get("source_event_id"),
                match_id=r.get("match_id"),
                home_team=home_team,
                away_team=away_team,
                home_goals=home_goals,
                away_goals=away_goals,
                status=status,
                kickoff_at=r.get("kickoff_at"),
                finished_at=r.get("finished_at"),
                captured_at=captured_at,
                raw_payload=r,
            ))

        log.debug("LocalJsonResultProvider: %d results loaded from %s", len(results), self._path)
        return results
