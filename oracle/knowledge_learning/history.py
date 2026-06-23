"""
Learning history audit trail — Week 27.

Builds the immutable LearningHistoryEntry log from WeightUpdate events.
The trail is append-only: earlier epochs first, later updates after.

Also produces a compact "effective weights" dict that the thesis generator
can use in place of the static knowledge_weights.json.
"""
from __future__ import annotations

import logging
from typing import Optional

from oracle.knowledge_learning.schema import LearningHistoryEntry, WeightUpdate

log = logging.getLogger(__name__)


def build_learning_history(
    bootstrap_updates: list[WeightUpdate],
    live_updates: list[WeightUpdate],
) -> list[LearningHistoryEntry]:
    """
    Concatenate bootstrap + live updates into an ordered audit trail.

    Bootstrap updates come first (earliest timestamps), live updates after.
    Cumulative evidence is tracked per (component_type, component_id).
    """
    all_updates: list[WeightUpdate] = sorted(
        bootstrap_updates + live_updates,
        key=lambda u: u.timestamp,
    )

    cumulative: dict[tuple[str, str], int] = {}
    entries: list[LearningHistoryEntry] = []

    for update in all_updates:
        key = (update.component_type, update.component_id)
        prior = cumulative.get(key, 0)
        cumulative[key] = prior + update.evidence_count

        entries.append(LearningHistoryEntry(
            component_id=update.component_id,
            component_type=update.component_type,
            timestamp=update.timestamp,
            weight=update.new_weight,
            evidence_count=update.evidence_count,
            cumulative_evidence=cumulative[key],
            stage=update.source,
            source=update.source,
            delta=update.delta,
        ))

    log.info("Built learning history: %d entries", len(entries))
    return entries


def extract_effective_weights(history: list[LearningHistoryEntry]) -> dict:
    """
    From the history, extract the most-recent weight for each component.

    Returns a dict in the same shape as knowledge_weights.json:
    {
      "chains":     {"C-03": 1.21, ...},
      "scripts":    {"favorite_dominance": 1.05, ...},
      "managers":   {"ancelotti:defensive_setup": 0.98, ...},
      "archetypes": {"possession_control": 1.12, ...},
    }
    """
    type_to_key = {
        "chain":     "chains",
        "script":    "scripts",
        "manager":   "managers",
        "archetype": "archetypes",
    }

    # Sort by timestamp so the last entry per component wins
    sorted_history = sorted(history, key=lambda e: e.timestamp)

    effective: dict[str, dict[str, float]] = {
        "chains": {}, "scripts": {}, "managers": {}, "archetypes": {}
    }

    for entry in sorted_history:
        bucket = type_to_key.get(entry.component_type, entry.component_type + "s")
        if bucket in effective:
            effective[bucket][entry.component_id] = entry.weight

    return effective


def summarize_history(history: list[LearningHistoryEntry]) -> dict:
    """Produce a concise summary of what changed and by how much."""
    if not history:
        return {
            "total_entries": 0,
            "components_tracked": 0,
            "largest_positive_delta": 0.0,
            "largest_negative_delta": 0.0,
            "avg_delta": 0.0,
            "bootstrap_entries": 0,
            "live_entries": 0,
        }

    bootstrap_entries = [e for e in history if e.stage.startswith("bootstrap")]
    live_entries      = [e for e in history if not e.stage.startswith("bootstrap")]
    deltas = [e.delta for e in history if e.delta != 0.0]

    components = {(e.component_type, e.component_id) for e in history}

    return {
        "total_entries":         len(history),
        "components_tracked":    len(components),
        "largest_positive_delta": max((d for d in deltas if d > 0), default=0.0),
        "largest_negative_delta": min((d for d in deltas if d < 0), default=0.0),
        "avg_delta":             round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
        "bootstrap_entries":     len(bootstrap_entries),
        "live_entries":          len(live_entries),
    }
