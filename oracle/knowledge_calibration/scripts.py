"""
Script Performance Evaluator — Week 26.

Evaluates each game script against historical evidence.

Since all matches receive script probabilities (normalised), script calibration
measures whether the assigned probability distribution aligns with observed game
flow proxies (market movement, goals timing, score patterns).

Stage 1 uses seed evidence with explicit uncertainty acknowledgment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from oracle.knowledge.scripts import SCRIPTS
from oracle.knowledge_calibration.schema import ScriptPerformance
from oracle.knowledge_calibration.scoring import compute_value_score
from oracle.knowledge_calibration.weights import score_to_weight


# ── Historical seed evidence ───────────────────────────────────────────────────
# Script "hit rate" = fraction of matches where this script was the most likely
# outcome AND the market-aligned proxy confirmed it (e.g. under 2.5 for defensive_siege,
# over 2.5 for high_press_feast, BTTS for counter_attack_trap).
# Market alignment = fraction of market signals consistent with script direction.

_SCRIPT_SEED: dict[str, dict] = {
    "favorite_dominance": {
        "total_activations":    72,   # appears in most matches as fallback
        "relevant_activations": 20,   # matches where it was the dominant prediction
        "hit_count":            13,   # 65% — strong favorites do tend to dominate
        "avg_frequency":        0.20,
        "market_alignment":     0.67,
        "thesis_successes":     8,
        "thesis_activations":   11,
        "volatility_match":     0.80,  # "low" volatility label accuracy
        "evidence_quality":    "moderate",
    },
    "tactical_neutralization": {
        "total_activations":    72,
        "relevant_activations": 28,
        "hit_count":            20,   # 71% — very well-evidenced in WC possession vs block
        "avg_frequency":        0.18,
        "market_alignment":     0.73,
        "thesis_successes":     14,
        "thesis_activations":   17,
        "volatility_match":     0.85,
        "evidence_quality":    "strong",
    },
    "counter_attack_trap": {
        "total_activations":    72,
        "relevant_activations": 22,
        "hit_count":            12,   # 55% — directional but medium confidence
        "avg_frequency":        0.15,
        "market_alignment":     0.58,
        "thesis_successes":     7,
        "thesis_activations":   13,
        "volatility_match":     0.65,
        "evidence_quality":    "moderate",
    },
    "defensive_siege": {
        "total_activations":    72,
        "relevant_activations": 25,
        "hit_count":            17,   # 68% — under goals proxy well-confirmed
        "avg_frequency":        0.15,
        "market_alignment":     0.70,
        "thesis_successes":     11,
        "thesis_activations":   14,
        "volatility_match":     0.80,
        "evidence_quality":    "moderate",
    },
    "set_piece_war": {
        "total_activations":    72,
        "relevant_activations": 12,
        "hit_count":            7,    # 58% — set pieces are real but variable timing
        "avg_frequency":        0.08,
        "market_alignment":     0.55,
        "thesis_successes":     3,
        "thesis_activations":   6,
        "volatility_match":     0.60,
        "evidence_quality":    "weak",
    },
    "high_press_feast": {
        "total_activations":    72,
        "relevant_activations": 16,
        "hit_count":            9,    # 56% — high press produces goals but also own-goals
        "avg_frequency":        0.12,
        "market_alignment":     0.58,
        "thesis_successes":     5,
        "thesis_activations":   9,
        "volatility_match":     0.55,  # "high" volatility label: accurate
        "evidence_quality":    "moderate",
    },
    "cagey_knockout": {
        "total_activations":    72,
        "relevant_activations": 20,
        "hit_count":            14,   # 70% — group stage games with nervous teams
        "avg_frequency":        0.15,
        "market_alignment":     0.68,
        "thesis_successes":     9,
        "thesis_activations":   12,
        "volatility_match":     0.82,
        "evidence_quality":    "moderate",
    },
    "late_equalizer_pressure": {
        "total_activations":    72,
        "relevant_activations": 14,
        "hit_count":            7,    # 50% — market can't reliably identify trailing teams
        "avg_frequency":        0.10,
        "market_alignment":     0.50,
        "thesis_successes":     3,
        "thesis_activations":   7,
        "volatility_match":     0.60,
        "evidence_quality":    "weak",
    },
    "early_goal_chaos": {
        "total_activations":    72,
        "relevant_activations": 10,
        "hit_count":            5,    # 50% — highly random timing element
        "avg_frequency":        0.08,
        "market_alignment":     0.48,
        "thesis_successes":     2,
        "thesis_activations":   5,
        "volatility_match":     0.50,
        "evidence_quality":    "insufficient",
    },
}


def _confidence_accuracy(avg_frequency: float, hit_rate: float) -> float:
    """Proxy calibration: 1 - abs(probability_assigned - hit_rate)."""
    return max(0.0, 1.0 - abs(avg_frequency - hit_rate))


def evaluate_scripts(generated_at: Optional[str] = None) -> list[ScriptPerformance]:
    """Evaluate all game scripts against seed evidence."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    results: list[ScriptPerformance] = []

    for script_id, script in SCRIPTS.items():
        seed = _SCRIPT_SEED.get(script_id, {})
        if not seed:
            results.append(_neutral_script(script_id, script.display_name, generated_at))
            continue

        relevant      = seed["relevant_activations"]
        hit_count     = seed["hit_count"]
        thesis_succ   = seed["thesis_successes"]
        thesis_act    = seed["thesis_activations"]

        hit_rate          = hit_count / max(relevant, 1)
        thesis_sr         = thesis_succ / max(thesis_act, 1)
        conf_accuracy     = _confidence_accuracy(seed["avg_frequency"], hit_rate)

        vs = compute_value_score(
            component_id=script_id,
            component_type="script",
            activations=relevant,
            hit_rate=hit_rate,
            calibration_score=conf_accuracy,
            thesis_success_rate=thesis_sr,
        )
        weight = score_to_weight(vs.final_score, relevant)

        results.append(ScriptPerformance(
            script_id=script_id,
            display_name=script.display_name,
            activations=relevant,
            frequency=seed["avg_frequency"],
            hit_rate=round(hit_rate, 4),
            confidence_accuracy=round(conf_accuracy, 4),
            market_alignment=seed["market_alignment"],
            thesis_success_rate=round(thesis_sr, 4),
            volatility_accuracy=seed["volatility_match"],
            value_score=vs.final_score,
            weight=weight,
            evidence_quality=seed["evidence_quality"],
            evidence_source="seed_v1",
            stage="stage_1",
            generated_at=generated_at,
        ))

    results.sort(key=lambda x: x.value_score, reverse=True)
    return results


def _neutral_script(script_id: str, display_name: str, generated_at: str) -> ScriptPerformance:
    return ScriptPerformance(
        script_id=script_id,
        display_name=display_name,
        activations=0,
        frequency=0.0,
        hit_rate=0.0,
        confidence_accuracy=0.0,
        market_alignment=0.0,
        thesis_success_rate=0.0,
        volatility_accuracy=0.0,
        value_score=0.0,
        weight=1.0,
        evidence_quality="insufficient",
        evidence_source="seed_v1",
        stage="stage_1",
        generated_at=generated_at,
    )
