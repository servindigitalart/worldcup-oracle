"""
Knowledge Explanation Generator — Week 25E.

Generates deterministic headline, body, and key_risk strings from a
KnowledgeActivation. No LLM. No external calls.
"""
from __future__ import annotations

from oracle.knowledge.schema import KnowledgeActivation


def _archetype_label(archetype: str) -> str:
    labels: dict[str, str] = {
        "possession_control":    "possession-control",
        "counter_attack":        "counter-attacking",
        "high_press":            "high-press",
        "low_block":             "low-block",
        "tournament_survival":   "tournament-survival",
        "set_piece_heavy":       "set-piece-heavy",
        "direct_play":           "direct-play",
        "high_press_resistant":  "press-resistant",
        "unknown":               "uncharacterised",
    }
    return labels.get(archetype, archetype.replace("_", "-"))


def _script_label(script_id: str) -> str:
    labels: dict[str, str] = {
        "favorite_dominance":      "Favorite Dominance",
        "tactical_neutralization": "Tactical Neutralization",
        "counter_attack_trap":     "Counter Attack Trap",
        "defensive_siege":         "Defensive Siege",
        "set_piece_war":           "Set Piece War",
        "high_press_feast":        "High Press Feast",
        "cagey_knockout":          "Cagey Knockout",
        "late_equalizer_pressure": "Late Equalizer Pressure",
        "early_goal_chaos":        "Early Goal Chaos",
    }
    return labels.get(script_id, script_id.replace("_", " ").title())


# ── Headline builders ──────────────────────────────────────────────────────────

def _build_headline(activation: KnowledgeActivation) -> str:
    home  = activation.home_team.replace("_", " ").title()
    away  = activation.away_team.replace("_", " ").title()
    ha    = _archetype_label(activation.home_archetype)
    aa    = _archetype_label(activation.away_archetype)

    if activation.home_archetype == "unknown" or activation.away_archetype == "unknown":
        return f"{home} vs {away}: limited football context available."

    top_scripts = activation.activated_scripts[:2]
    if top_scripts:
        primary = _script_label(top_scripts[0].script_id)
        return f"{home}'s {ha} identity meets {away}'s {aa} approach — {primary} script likely."

    return f"{home} ({ha}) vs {away} ({aa}): knowledge layer activated."


# ── Body builder ───────────────────────────────────────────────────────────────

def _build_body(activation: KnowledgeActivation) -> str:
    home  = activation.home_team.replace("_", " ").title()
    away  = activation.away_team.replace("_", " ").title()
    ha    = _archetype_label(activation.home_archetype)
    aa    = _archetype_label(activation.away_archetype)

    if activation.home_archetype == "unknown" and activation.away_archetype == "unknown":
        return (
            f"Neither {home} nor {away} has a seeded knowledge profile. "
            "The knowledge layer cannot add football context to this matchup at Stage 1. "
            "Thesis signals are model-probability only."
        )

    parts: list[str] = []

    # Archetype framing
    parts.append(
        f"{home} are profiled as a {ha} side, while {away} operate as a "
        f"{aa} team."
    )

    # Top script explanation
    if activation.activated_scripts:
        s = activation.activated_scripts[0]
        parts.append(
            f"That interaction most commonly produces the {_script_label(s.script_id)} script "
            f"(estimated probability {s.probability:.0%})."
        )

    # Chain summaries (up to 2)
    if activation.activated_chains:
        chain_summaries = [c.explanation_snippet for c in activation.activated_chains[:2]]
        parts.extend(chain_summaries)

    # Manager patterns (up to 1)
    mgr_ctx = [
        p["description"] for p in activation.activated_manager_patterns
        if p.get("confidence", 0) >= 0.75
    ]
    if mgr_ctx:
        parts.append(mgr_ctx[0])

    # Supporting context (up to 1)
    if activation.supporting_context:
        parts.append(activation.supporting_context[0])

    body = " ".join(parts)

    # Confidence caveat
    conf = activation.knowledge_confidence
    if conf < 0.50:
        body += (
            " Note: knowledge confidence is limited for this matchup — "
            "treat football context as indicative only."
        )

    return body


# ── Key risk builder ───────────────────────────────────────────────────────────

def _build_key_risk(activation: KnowledgeActivation) -> str:
    if activation.counter_context:
        return activation.counter_context[0]
    top_scripts = activation.activated_scripts
    if top_scripts:
        s = top_scripts[0]
        return (
            f"If the {_script_label(s.script_id)} script does not materialise, "
            "the knowledge layer's market implications weaken."
        )
    return "Knowledge layer context is limited — model probability is the primary signal."


# ── Public function ────────────────────────────────────────────────────────────

def build_knowledge_explanation(
    activation: KnowledgeActivation,
) -> tuple[str, str, str]:
    """
    Build a deterministic knowledge explanation.

    Returns:
        (headline, body, key_risk)
    """
    headline = _build_headline(activation)
    body     = _build_body(activation)
    key_risk = _build_key_risk(activation)
    return headline, body, key_risk
