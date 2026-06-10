"""
Result provider types and interface — Week 17.

Defines the shared data model used by all result providers:
  RawResult         — as-ingested from any source, teams not yet canonicalised
  NormalizedResult  — validated, fixture-resolved, canonical team IDs
  MergeReport       — summary of the provider merge step
  ResultProviderError — exception raised on fetch/parse failures

Provider precedence (enforced in normalize.merge_results):
  1. manual seed (oracle.results.manual.ManualSeedProvider)
  2. local JSON file (oracle.results.external.LocalJsonResultProvider)

Manual seed always wins on conflict — it is the trusted correction mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

VALID_STATUSES: frozenset[str] = frozenset(
    {"scheduled", "live", "finished", "postponed", "cancelled", "unknown"}
)


class ResultProviderError(Exception):
    """Raised when a provider cannot fetch or parse results."""


@dataclass
class RawResult:
    """Result as returned by a provider — teams NOT yet canonicalised."""

    source:           str               # "manual" | "local_json" | …
    home_team:        str               # as-given by provider
    away_team:        str               # as-given by provider
    status:           str               # must be in VALID_STATUSES
    source_event_id:  str | None = None # provider's own event identifier
    match_id:         str | None = None # explicit WC2026 match_id if known
    home_goals:       int | None = None
    away_goals:       int | None = None
    kickoff_at:       str | None = None
    finished_at:      str | None = None
    captured_at:      str       = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_payload:      dict      = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source":          self.source,
            "source_event_id": self.source_event_id,
            "match_id":        self.match_id,
            "home_team":       self.home_team,
            "away_team":       self.away_team,
            "home_goals":      self.home_goals,
            "away_goals":      self.away_goals,
            "status":          self.status,
            "kickoff_at":      self.kickoff_at,
            "finished_at":     self.finished_at,
            "captured_at":     self.captured_at,
        }


@dataclass
class NormalizedResult:
    """Validated result with canonical team IDs and fixture match_id resolved."""

    source:          str
    match_id:        str               # resolved from fixture seed
    home_team:       str               # canonical ID from oracle/teams.py
    away_team:       str               # canonical ID from oracle/teams.py
    group:           str
    status:          str
    source_event_id: str | None = None
    home_goals:      int | None = None
    away_goals:      int | None = None
    kickoff_at:      str | None = None
    finished_at:     str | None = None
    captured_at:     str       = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "match_id":        self.match_id,
            "home_team":       self.home_team,
            "away_team":       self.away_team,
            "group":           self.group,
            "home_goals":      self.home_goals,
            "away_goals":      self.away_goals,
            "status":          self.status,
            "source":          self.source,
            "source_event_id": self.source_event_id,
            "kickoff_at":      self.kickoff_at,
            "finished_at":     self.finished_at,
            "captured_at":     self.captured_at,
        }


@dataclass
class MergeReport:
    """Summary of the provider merge step written to results_feed_report.json."""

    n_manual:    int
    n_external:  int
    n_merged:    int
    n_duplicates: int
    overrides:   list[dict]  = field(default_factory=list)
    unresolved:  list[dict]  = field(default_factory=list)
    warnings:    list[str]   = field(default_factory=list)
    generated_at: str        = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "generated_at":  self.generated_at,
            "n_manual":      self.n_manual,
            "n_external":    self.n_external,
            "n_merged":      self.n_merged,
            "n_duplicates":  self.n_duplicates,
            "overrides":     self.overrides,
            "unresolved":    self.unresolved,
            "warnings":      self.warnings,
        }
