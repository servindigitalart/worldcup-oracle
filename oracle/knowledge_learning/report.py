"""
Learning summary report — Week 27.

Produces a plain-language summary artifact describing what the learning system
did this cycle: which components gained/lost weight, confidence in the updates,
and trend direction per component.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from oracle.knowledge_learning.schema import WeightUpdate, LearningHistoryEntry


def _trend(delta: float) -> str:
    if delta >= 0.005:
        return "up"
    if delta <= -0.005:
        return "down"
    return "stable"


def _format_update(u: WeightUpdate) -> dict:
    return {
        "component_id":   u.component_id,
        "component_type": u.component_type,
        "old_weight":     u.old_weight,
        "new_weight":     u.new_weight,
        "delta":          u.delta,
        "trend":          _trend(u.delta),
        "evidence_count": u.evidence_count,
        "reason":         u.reason,
    }


def build_learning_report(
    bootstrap_updates: list[WeightUpdate],
    live_updates: list[WeightUpdate],
    history_summary: dict,
    generated_at: Optional[str] = None,
) -> dict:
    """
    Build the knowledge_learning_summary artifact.

    Returns a dict ready to serialize to JSON.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    all_live = sorted(live_updates, key=lambda u: abs(u.delta), reverse=True)
    all_bootstrap = sorted(bootstrap_updates, key=lambda u: u.timestamp)

    # Split by direction
    gains  = [u for u in all_live if u.delta >= 0.005]
    losses = [u for u in all_live if u.delta <= -0.005]
    stable = [u for u in all_live if abs(u.delta) < 0.005]

    # By component type
    chains_updated     = [u for u in all_live if u.component_type == "chain"]
    scripts_updated    = [u for u in all_live if u.component_type == "script"]
    managers_updated   = [u for u in all_live if u.component_type == "manager"]
    archetypes_updated = [u for u in all_live if u.component_type == "archetype"]

    # Top movers
    top_gains  = [_format_update(u) for u in gains[:5]]
    top_losses = [_format_update(u) for u in losses[:5]]

    # Trend map per component (for frontend ↑/→/↓)
    trend_map: dict[str, str] = {}
    for u in all_live:
        trend_map[u.component_id] = _trend(u.delta)

    # Plain-language notes
    notes: list[str] = []
    if not all_live:
        notes.append("No live WC 2026 evidence yet — weights remain at calibration baseline.")
    else:
        notes.append(
            f"Processed {len(all_live)} component updates from live matches."
        )
        if gains:
            top = gains[0]
            notes.append(
                f"Largest gain: {top.component_id} (+{top.delta:.3f}, "
                f"{top.evidence_count} observations)."
            )
        if losses:
            bot = losses[0]
            notes.append(
                f"Largest reduction: {bot.component_id} ({bot.delta:.3f}, "
                f"{bot.evidence_count} observations)."
            )

    return {
        "generated_at":         generated_at,
        "stage":                "stage_1",
        "evidence_source":      "live_2026_and_bootstrap",
        "bootstrap_updates":    len(bootstrap_updates),
        "live_updates":         len(all_live),
        "components_gained":    len(gains),
        "components_lost":      len(losses),
        "components_stable":    len(stable),
        "chains_updated":       len(chains_updated),
        "scripts_updated":      len(scripts_updated),
        "managers_updated":     len(managers_updated),
        "archetypes_updated":   len(archetypes_updated),
        "top_gaining_components":  top_gains,
        "top_losing_components":   top_losses,
        "trend_map":            trend_map,
        "history_summary":      history_summary,
        "notes":                notes,
    }
