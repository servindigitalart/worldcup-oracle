"""
Result normalization and merge engine — Week 17.

Responsibilities:
  1. Canonicalise team names via oracle/teams.py
  2. Resolve fixture match_id from the fixture seed
  3. Validate result fields
  4. Merge results from multiple providers (manual > external)
  5. Report duplicates, overrides, and unresolved items

Fixture resolution order (for external results without a match_id):
  1. Exact match_id lookup (if provided by provider)
  2. Canonical (home_team, away_team) pair lookup — must be unique
  3. Reversed (away_team, home_team) pair — only if home/away roles can be inferred
     (not attempted here — ambiguity fails clearly)

Provider precedence:
  1. manual seed results override external results on the same match_id.
  2. External results that would override manual are rejected with a warning.

Only 'finished' results are ever forwarded to standings and simulation.
'live', 'scheduled', 'postponed', 'cancelled', 'unknown' are carried through
in the artifact but the simulation layer filters to status='finished'.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from oracle.results.provider import (
    VALID_STATUSES,
    MergeReport,
    NormalizedResult,
    RawResult,
    ResultProviderError,
)
from oracle.teams import try_resolve_team

log = logging.getLogger(__name__)

_FIXTURE_SEED = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_fixtures.json"


# ── Fixture index helpers ─────────────────────────────────────────────────────

def _load_fixture_index(fixture_path: Path = _FIXTURE_SEED) -> dict[str, dict]:
    """Return fixture_index keyed by match_id."""
    try:
        data = json.loads(fixture_path.read_text())
    except FileNotFoundError:
        raise ResultProviderError(f"Fixture seed not found: {fixture_path}")
    return {f["match_id"]: f for f in data.get("fixtures", [])}


def _build_pair_index(fixture_index: dict[str, dict]) -> dict[tuple[str, str], str]:
    """Return {(canonical_home, canonical_away): match_id} for fast team-pair lookup."""
    pair_index: dict[tuple[str, str], str] = {}
    for mid, f in fixture_index.items():
        pair_index[(f["home_team"], f["away_team"])] = mid
    return pair_index


# ── Normalization ─────────────────────────────────────────────────────────────

def normalize_raw(
    raw: RawResult,
    fixture_index: dict[str, dict],
    pair_index: dict[tuple[str, str], str],
) -> NormalizedResult:
    """Normalize a single RawResult → NormalizedResult.

    Raises
    ------
    ResultProviderError
        If team names cannot be resolved, fixture cannot be identified,
        or result fields are invalid.
    """
    # 1. Validate status
    if raw.status not in VALID_STATUSES:
        raise ResultProviderError(
            f"[{raw.source}] Invalid status {raw.status!r} for "
            f"{raw.home_team!r} vs {raw.away_team!r}"
        )

    # 2. Validate score fields
    if raw.status == "finished":
        if raw.home_goals is None or raw.away_goals is None:
            raise ResultProviderError(
                f"[{raw.source}] status=finished requires home_goals and away_goals "
                f"({raw.home_team!r} vs {raw.away_team!r})"
            )
        if not isinstance(raw.home_goals, int) or raw.home_goals < 0:
            raise ResultProviderError(
                f"[{raw.source}] home_goals must be a non-negative integer "
                f"({raw.home_team!r} vs {raw.away_team!r})"
            )
        if not isinstance(raw.away_goals, int) or raw.away_goals < 0:
            raise ResultProviderError(
                f"[{raw.source}] away_goals must be a non-negative integer "
                f"({raw.home_team!r} vs {raw.away_team!r})"
            )

    # 3. Resolve fixture via match_id (preferred path)
    fixture: dict | None = None

    if raw.match_id:
        fixture = fixture_index.get(raw.match_id)
        if fixture is None:
            raise ResultProviderError(
                f"[{raw.source}] match_id {raw.match_id!r} not found in fixture seed"
            )
        canonical_home = fixture["home_team"]
        canonical_away = fixture["away_team"]

    else:
        # 4. Resolve via team names
        canonical_home = try_resolve_team(raw.home_team)
        canonical_away = try_resolve_team(raw.away_team)

        if canonical_home is None:
            raise ResultProviderError(
                f"[{raw.source}] Cannot resolve home_team {raw.home_team!r} — "
                "add alias to oracle/teams.py"
            )
        if canonical_away is None:
            raise ResultProviderError(
                f"[{raw.source}] Cannot resolve away_team {raw.away_team!r} — "
                "add alias to oracle/teams.py"
            )

        mid = pair_index.get((canonical_home, canonical_away))
        if mid is None:
            # Try reversed pair — provider may have home/away swapped
            mid_rev = pair_index.get((canonical_away, canonical_home))
            if mid_rev is not None:
                raise ResultProviderError(
                    f"[{raw.source}] Teams {raw.home_team!r} vs {raw.away_team!r} "
                    f"found in fixture but with reversed home/away. "
                    f"Fixture has {canonical_away!r} as home. Provide match_id to disambiguate."
                )
            raise ResultProviderError(
                f"[{raw.source}] No fixture found for "
                f"{canonical_home!r} vs {canonical_away!r}"
            )

        fixture = fixture_index[mid]

    resolved_mid = fixture["match_id"]
    group = fixture.get("group", "")
    kickoff_at = raw.kickoff_at or fixture.get("kickoff_at")

    return NormalizedResult(
        source=raw.source,
        source_event_id=raw.source_event_id,
        match_id=resolved_mid,
        home_team=fixture["home_team"],
        away_team=fixture["away_team"],
        group=group,
        status=raw.status,
        home_goals=raw.home_goals,
        away_goals=raw.away_goals,
        kickoff_at=kickoff_at,
        finished_at=raw.finished_at,
        captured_at=raw.captured_at,
    )


# ── Merge engine ──────────────────────────────────────────────────────────────

def merge_results(
    manual_raw: list[RawResult],
    external_raw: list[RawResult],
    fixture_path: Path = _FIXTURE_SEED,
) -> tuple[list[NormalizedResult], MergeReport]:
    """Normalize and merge results from manual + external providers.

    Provider precedence: manual > external.
    Manual results always override external on the same match_id.

    Parameters
    ----------
    manual_raw:
        Results from ManualSeedProvider.
    external_raw:
        Results from LocalJsonResultProvider (or any external source).
    fixture_path:
        Path to the fixture seed for resolution.

    Returns
    -------
    (merged_list, MergeReport)
    """
    fixture_index = _load_fixture_index(fixture_path)
    pair_index    = _build_pair_index(fixture_index)

    ts = datetime.now(timezone.utc).isoformat()
    overrides:  list[dict] = []
    unresolved: list[dict] = []
    warnings:   list[str]  = []

    # Phase 1: normalise external results
    external_by_mid: dict[str, NormalizedResult] = {}
    for raw in external_raw:
        try:
            nr = normalize_raw(raw, fixture_index, pair_index)
            if nr.match_id in external_by_mid:
                warnings.append(
                    f"External: duplicate match_id {nr.match_id!r} — "
                    "keeping first occurrence"
                )
            else:
                external_by_mid[nr.match_id] = nr
        except ResultProviderError as exc:
            unresolved.append({
                "source":     raw.source,
                "home_team":  raw.home_team,
                "away_team":  raw.away_team,
                "match_id":   raw.match_id,
                "reason":     str(exc),
            })
            warnings.append(f"External result unresolved: {exc}")

    # Phase 2: normalise manual results (strict — all must resolve)
    manual_by_mid: dict[str, NormalizedResult] = {}
    for raw in manual_raw:
        try:
            nr = normalize_raw(raw, fixture_index, pair_index)
            manual_by_mid[nr.match_id] = nr
        except ResultProviderError as exc:
            # Manual seed failures propagate as hard errors
            raise ResultProviderError(f"Manual seed normalisation failed: {exc}") from exc

    # Phase 3: merge (manual wins)
    merged: dict[str, NormalizedResult] = {}

    # Start with external
    for mid, nr in external_by_mid.items():
        merged[mid] = nr

    # Apply manual, tracking overrides
    n_duplicates = 0
    for mid, nr in manual_by_mid.items():
        if mid in merged:
            n_duplicates += 1
            ext = merged[mid]
            overrides.append({
                "match_id": mid,
                "manual_status": nr.status,
                "external_status": ext.status,
                "manual_goals": f"{nr.home_goals}-{nr.away_goals}",
                "external_goals": f"{ext.home_goals}-{ext.away_goals}",
            })
            log.debug(
                "merge_results: manual overrides external for %s (%s vs %s)",
                mid, nr.home_team, nr.away_team,
            )
        merged[mid] = nr

    merged_list = list(merged.values())

    report = MergeReport(
        n_manual=len(manual_by_mid),
        n_external=len(external_by_mid),
        n_merged=len(merged_list),
        n_duplicates=n_duplicates,
        overrides=overrides,
        unresolved=unresolved,
        warnings=warnings,
        generated_at=ts,
    )

    return merged_list, report
