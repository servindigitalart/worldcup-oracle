"""
Manual seed result provider — Week 17.

Reads data/seed/wc2026_results.json and returns RawResult objects.

The manual seed is the trusted correction mechanism:
  - manual seed always overrides external providers on conflict.
  - the seed file is NEVER mutated by provider code.
  - an empty seed is valid (returns an empty list).

Validation matches oracle.ingest.results_2026.load_results_2026:
  - match_id must exist in the fixture seed.
  - home_team / away_team must match the fixture record.
  - status must be in VALID_STATUSES.
  - status=finished requires non-negative integer goals.
  - no duplicate match_id entries.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oracle.results.provider import VALID_STATUSES, RawResult, ResultProviderError

log = logging.getLogger(__name__)

_RESULTS_SEED = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_results.json"
_FIXTURE_SEED = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_fixtures.json"


class ManualSeedProvider:
    """Reads results from data/seed/wc2026_results.json."""

    name = "manual"

    def __init__(
        self,
        results_path: Path = _RESULTS_SEED,
        fixture_path: Path = _FIXTURE_SEED,
    ) -> None:
        self._results_path = results_path
        self._fixture_path = fixture_path

    def fetch_results(self, fixtures: list | None = None) -> list[RawResult]:
        """Load, validate, and return results from the manual seed.

        Parameters
        ----------
        fixtures:
            Ignored — the manual seed already contains match_id references to
            the fixture seed directly.

        Returns
        -------
        List of RawResult (may be empty if seed has no results).

        Raises
        ------
        ResultProviderError
            If the seed file is missing, malformed JSON, or fails validation.
        """
        try:
            data = json.loads(self._results_path.read_text())
        except FileNotFoundError:
            raise ResultProviderError(
                f"Manual seed not found: {self._results_path}"
            )
        except json.JSONDecodeError as exc:
            raise ResultProviderError(
                f"Manual seed is not valid JSON: {exc}"
            )

        if not isinstance(data, dict):
            raise ResultProviderError(
                "Manual seed must be a JSON object with a 'results' key."
            )

        raw_results: list[dict[str, Any]] = data.get("results", [])

        if not raw_results:
            return []

        # Load fixture index for cross-validation
        try:
            fixture_data = json.loads(self._fixture_path.read_text())
        except FileNotFoundError:
            raise ResultProviderError(
                f"Fixture seed not found: {self._fixture_path}"
            )
        except json.JSONDecodeError as exc:
            raise ResultProviderError(
                f"Fixture seed is not valid JSON: {exc}"
            )

        fixture_index: dict[str, dict] = {
            f["match_id"]: f
            for f in fixture_data.get("fixtures", [])
        }

        captured_at = datetime.now(timezone.utc).isoformat()
        seen_ids: set[str] = set()
        results: list[RawResult] = []

        for i, r in enumerate(raw_results):
            mid = r.get("match_id")
            if not mid:
                raise ResultProviderError(
                    f"Manual seed: result at index {i} missing 'match_id'"
                )

            if mid in seen_ids:
                raise ResultProviderError(
                    f"Manual seed: duplicate match_id {mid!r}"
                )
            seen_ids.add(mid)

            if mid not in fixture_index:
                raise ResultProviderError(
                    f"Manual seed: match_id {mid!r} not found in fixture seed"
                )

            fixture = fixture_index[mid]
            status  = r.get("status", "finished")

            if status not in VALID_STATUSES:
                raise ResultProviderError(
                    f"Manual seed: match_id {mid!r} has invalid status {status!r}. "
                    f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
                )

            home_team = r.get("home_team", fixture["home_team"])
            away_team = r.get("away_team", fixture["away_team"])

            if home_team != fixture["home_team"] or away_team != fixture["away_team"]:
                raise ResultProviderError(
                    f"Manual seed: match_id {mid!r}: teams {home_team!r} vs {away_team!r} "
                    f"don't match fixture ({fixture['home_team']!r} vs {fixture['away_team']!r})"
                )

            home_goals: int | None = r.get("home_goals")
            away_goals: int | None = r.get("away_goals")

            if status == "finished":
                if home_goals is None or away_goals is None:
                    raise ResultProviderError(
                        f"Manual seed: match_id {mid!r}: status=finished requires "
                        "home_goals and away_goals"
                    )
                if not isinstance(home_goals, int) or home_goals < 0:
                    raise ResultProviderError(
                        f"Manual seed: match_id {mid!r}: home_goals must be a "
                        "non-negative integer"
                    )
                if not isinstance(away_goals, int) or away_goals < 0:
                    raise ResultProviderError(
                        f"Manual seed: match_id {mid!r}: away_goals must be a "
                        "non-negative integer"
                    )

            results.append(RawResult(
                source="manual",
                source_event_id=None,
                match_id=mid,
                home_team=home_team,
                away_team=away_team,
                home_goals=home_goals,
                away_goals=away_goals,
                status=status,
                kickoff_at=fixture.get("kickoff_at"),
                finished_at=r.get("finished_at"),
                captured_at=captured_at,
                raw_payload=r,
            ))

        log.debug("ManualSeedProvider: %d results loaded", len(results))
        return results
