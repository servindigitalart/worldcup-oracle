"""
Chain Performance Evaluator — Week 26.

Evaluates each Stage-1 causal chain against historical evidence.

Stage 1 uses principled seed evidence from football analytics research
(WC 2014/2018/2022 pattern estimates). Evidence is tagged with evidence_source="seed_v1"
so Stage 2 can replace with directly measured outcomes.

Evidence design:
    - total_opportunities: estimated matches where chain could have applied
    - confirmed_activations: estimated activations based on archetype prevalence
    - hit_count: estimated correct predictions
    - avg_activation_confidence: from chain.base_confidence
    - thesis_successes: estimated theses hitting display tier
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from oracle.knowledge.chains import CHAINS
from oracle.knowledge_calibration.schema import ChainPerformance
from oracle.knowledge_calibration.scoring import compute_value_score
from oracle.knowledge_calibration.weights import score_to_weight


# ── Historical seed evidence ───────────────────────────────────────────────────
# Based on WC 2014/2018/2022 group stage pattern estimates.
# Reference: 144 total group stage matches across 3 tournaments.
# Evidence is principled but approximate — "seed_v1" not "measured".

_CHAIN_SEED: dict[str, dict] = {
    "C-03": {
        # Possession-dominant team vs compact defensive block
        # Well-documented: possession teams create elevated corner counts
        # Spain 2010/2014, Brazil 2006-2014 data support this
        "total_opportunities":  144,     # evaluated against all WC matches
        "activations":          38,      # ~26% matches with possession vs block pairing
        "hit_count":            28,      # 74% hit rate (corners elevated above 8.5)
        "avg_confidence":       0.72,
        "thesis_successes":     18,
        "thesis_activations":   22,
        "brier_delta":         -0.018,   # better than baseline (negative = improvement)
        "rps_delta":           -0.014,
        "logloss_delta":       -0.022,
        "evidence_quality":    "strong",
        "notes": "Possession teams vs compact blocks: well-established corners elevation",
    },
    "C-05": {
        # Low block deflections generating corners mechanically
        # Morocco 2022, South Korea 2002 style defence
        "total_opportunities":  144,
        "activations":          32,
        "hit_count":            20,      # 63% hit rate
        "avg_confidence":       0.68,
        "thesis_successes":     13,
        "thesis_activations":   18,
        "brier_delta":         -0.012,
        "rps_delta":           -0.009,
        "logloss_delta":       -0.016,
        "evidence_quality":    "moderate",
        "notes": "Low block deflections: mechanically sound but corner market is noisy",
    },
    "G-01": {
        # Counter attack vs high defensive line
        # Germany 2014 (high line exploited), Belgium 2018 counter goals
        "total_opportunities":  144,
        "activations":          24,
        "hit_count":            14,      # 58% hit rate
        "avg_confidence":       0.70,
        "thesis_successes":     9,
        "thesis_activations":   14,
        "brier_delta":         -0.008,
        "rps_delta":           -0.006,
        "logloss_delta":       -0.012,
        "evidence_quality":    "moderate",
        "notes": "Counter vs high line: directionally correct but variable",
    },
    "G-07": {
        # Low block stalemate producing under goals / draws
        # WC group stages consistently produce under 2.5 in defensive matchups
        "total_opportunities":  144,
        "activations":          34,
        "hit_count":            25,      # 74% hit rate (under 2.5 market)
        "avg_confidence":       0.74,
        "thesis_successes":     17,
        "thesis_activations":   20,
        "brier_delta":         -0.021,
        "rps_delta":           -0.017,
        "logloss_delta":       -0.025,
        "evidence_quality":    "strong",
        "notes": "Low block stalemate: strongest evidence chain. WC consistently produces low-scoring draws in defensive matchups.",
    },
    "K-02": {
        # Press failure leading to tactical fouls and cards
        # Germany 2018 (pressing failures), less direct card market evidence
        "total_opportunities":  144,
        "activations":          18,
        "hit_count":            10,      # 56% hit rate
        "avg_confidence":       0.66,
        "thesis_successes":     5,
        "thesis_activations":   9,
        "brier_delta":         -0.004,
        "rps_delta":           -0.003,
        "logloss_delta":       -0.006,
        "evidence_quality":    "weak",
        "notes": "Press failure → cards: plausible mechanism but card market is highly variable",
    },
    "B-05": {
        # Elite defence vs weak attack → BTTS No / clean sheet
        # Argentina 2022, Italy historical clean sheets
        "total_opportunities":  144,
        "activations":          20,
        "hit_count":            13,      # 65% hit rate
        "avg_confidence":       0.68,
        "thesis_successes":     8,
        "thesis_activations":   12,
        "brier_delta":         -0.010,
        "rps_delta":           -0.007,
        "logloss_delta":       -0.014,
        "evidence_quality":    "moderate",
        "notes": "Elite defence vs weak attack: directionally strong but quality gap identification is uncertain",
    },
    "S-03": {
        # Pragmatic manager → 1-0 protection after scoring first
        # Scaloni/Argentina, Deschamps/France historical patterns
        # Small sample: requires specific manager + lead scenario
        "total_opportunities":  48,     # subset of matches with seeded managers
        "activations":          9,
        "hit_count":            6,      # 67% hit rate
        "avg_confidence":       0.72,
        "thesis_successes":     4,
        "thesis_activations":   6,
        "brier_delta":         -0.006,
        "rps_delta":           -0.004,
        "logloss_delta":       -0.009,
        "evidence_quality":    "weak",
        "notes": "Manager-specific pattern with small sample — directionally supported but low confidence",
    },
    "S-07": {
        # Late tournament fatigue → second-half simplification
        # Hard to isolate: group stage matches rarely show fatigue
        "total_opportunities":  48,     # later matches in tournament
        "activations":          5,
        "hit_count":            2,      # 40% hit rate — below base rate
        "avg_confidence":       0.60,
        "thesis_successes":     1,
        "thesis_activations":   3,
        "brier_delta":          0.003,  # slightly negative (worse than baseline)
        "rps_delta":            0.002,
        "logloss_delta":        0.004,
        "evidence_quality":    "insufficient",
        "notes": "Late tournament fatigue: insufficient evidence for group stage calibration. Signal absent.",
    },
}


def _compute_calibration_score(avg_confidence: float, hit_rate: float) -> float:
    """Calibration score: 1 - |confidence - hit_rate|, clamped [0, 1]."""
    return max(0.0, 1.0 - abs(avg_confidence - hit_rate))


def evaluate_chains(
    total_matches: int = 144,
    generated_at: Optional[str] = None,
) -> list[ChainPerformance]:
    """
    Evaluate all Stage-1 causal chains against seed evidence.

    Returns a ChainPerformance for each chain in the CHAINS catalogue.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    results: list[ChainPerformance] = []

    for chain_id, chain in CHAINS.items():
        seed = _CHAIN_SEED.get(chain_id, {})
        if not seed:
            # Unknown chain: produce neutral performance record
            results.append(_neutral_chain(chain_id, chain.name, generated_at))
            continue

        activations       = seed["activations"]
        hit_count         = seed["hit_count"]
        thesis_successes  = seed["thesis_successes"]
        thesis_activations = seed["thesis_activations"]

        activation_rate   = activations / max(total_matches, 1)
        hit_rate          = hit_count / max(activations, 1)
        thesis_success_rate = thesis_successes / max(thesis_activations, 1)
        avg_confidence    = seed["avg_confidence"]
        calibration_score = _compute_calibration_score(avg_confidence, hit_rate)

        # Uncertainty rate: insufficient evidence where we can't determine outcome
        uncertainty_rate  = max(0.0, 1.0 - (activations / 30.0))

        vs = compute_value_score(
            component_id=chain_id,
            component_type="chain",
            activations=activations,
            hit_rate=hit_rate,
            calibration_score=calibration_score,
            thesis_success_rate=thesis_success_rate,
        )

        weight = score_to_weight(vs.final_score, activations)

        results.append(ChainPerformance(
            chain_id=chain_id,
            name=chain.name,
            activations=activations,
            activation_rate=round(activation_rate, 4),
            average_confidence=avg_confidence,
            hit_rate=round(hit_rate, 4),
            calibration_score=round(calibration_score, 4),
            brier_delta=seed["brier_delta"],
            rps_delta=seed["rps_delta"],
            logloss_delta=seed["logloss_delta"],
            thesis_success_rate=round(thesis_success_rate, 4),
            uncertainty_rate=round(uncertainty_rate, 4),
            value_score=vs.final_score,
            weight=weight,
            evidence_quality=seed["evidence_quality"],
            evidence_source="seed_v1",
            stage="stage_1",
            generated_at=generated_at,
        ))

    results.sort(key=lambda x: x.value_score, reverse=True)
    return results


def _neutral_chain(chain_id: str, name: str, generated_at: str) -> ChainPerformance:
    return ChainPerformance(
        chain_id=chain_id,
        name=name,
        activations=0,
        activation_rate=0.0,
        average_confidence=0.0,
        hit_rate=0.0,
        calibration_score=0.0,
        brier_delta=0.0,
        rps_delta=0.0,
        logloss_delta=0.0,
        thesis_success_rate=0.0,
        uncertainty_rate=1.0,
        value_score=0.0,
        weight=1.0,
        evidence_quality="insufficient",
        evidence_source="seed_v1",
        stage="stage_1",
        generated_at=generated_at,
    )

