"""
Responsible Recommendation Engine — deterministic rules.

apply_rules(inp) → Recommendation

Gap thresholds (1X2 absolute probability difference):
  SMALL_GAP_THRESHOLD    = 0.04   (<  4pp → market_aligned)
  MODERATE_GAP_THRESHOLD = 0.08   (4–8pp  → watch)
  LARGE_GAP_THRESHOLD    = 0.08   (≥  8pp → model_gap_detected)

Conservative posture
--------------------
- Matches with no market data → no_recommendation (not actionable).
- Finished matches → no_recommendation (not actionable).
- is_actionable=True requires market data, pre_match status, official fixture,
  non-closing_locked or better capture status, AND model_gap_detected type.
- confidence="high" is never assigned by this engine.
- Thresholds are NOT tuned to maximise the number of interesting outputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from oracle.recommendations.schema import (
    STANDARD_WARNINGS,
    Recommendation,
    RecommendationInput,
)

# ── Gap thresholds ─────────────────────────────────────────────────────────────

SMALL_GAP_THRESHOLD    = 0.04   # below this → market_aligned
MODERATE_GAP_THRESHOLD = 0.08   # 0.04–0.08  → watch; ≥ 0.08 → model_gap_detected

# Edge confidence thresholds (absolute gap on largest-gap selection)
# 0-3pp = low, 3-6pp = medium, 6-10pp = high, 10pp+ = very_high, none = no gap
_EDGE_LOW_MAX    = 0.03
_EDGE_MEDIUM_MAX = 0.06
_EDGE_HIGH_MAX   = 0.10

_SELECTION_NAMES = {
    "home": "home_win",
    "draw": "draw",
    "away": "away_win",
}


def _edge_confidence_for_gap(abs_gap: float | None) -> str:
    """Classify edge confidence from the absolute model-market gap.

    0-3pp  → low
    3-6pp  → medium
    6-10pp → high
    10pp+  → very_high
    None   → none  (no market data)
    """
    if abs_gap is None:
        return "none"
    if abs_gap < _EDGE_LOW_MAX:
        return "low"
    if abs_gap < _EDGE_MEDIUM_MAX:
        return "medium"
    if abs_gap < _EDGE_HIGH_MAX:
        return "high"
    return "very_high"


def apply_rules(inp: RecommendationInput, generated_at: Optional[str] = None) -> Recommendation:
    """Apply deterministic recommendation rules to one RecommendationInput.

    Returns a Recommendation with conservative defaults.
    """
    ts  = generated_at or datetime.now(timezone.utc).isoformat()
    dq  = _data_quality(inp)
    st  = _match_status(inp)
    wrn = list(STANDARD_WARNINGS)

    # Shared identity kwargs — only fields that never vary between rules
    identity = dict(
        match_id=inp.match_id, home_team=inp.home_team, away_team=inp.away_team,
        group=inp.group, kickoff_at=inp.kickoff_at,
        market="1x2", warnings=wrn, generated_at=ts,
    )

    # ── Rule 1: Finished match ─────────────────────────────────────────────────
    if inp.result_status == "finished":
        return Recommendation(
            **identity,
            recommendation_type="no_recommendation",
            selection=None, model_probability=None, market_probability=None,
            blended_probability=None, model_market_gap=None,
            confidence="unknown", risk_label="unknown",
            data_quality=dq, status="finished", is_actionable=False,
            edge_confidence="none",
            reason="Match already finished.",
        )

    # ── Rule 2: No market data ─────────────────────────────────────────────────
    if not inp.has_market_data:
        return Recommendation(
            **identity,
            recommendation_type="no_recommendation",
            selection=None, model_probability=None, market_probability=None,
            blended_probability=None, model_market_gap=None,
            confidence="unknown", risk_label="unknown",
            data_quality="missing_market", status=st, is_actionable=False,
            edge_confidence="none",
            reason=(
                "Market benchmark unavailable. "
                "Probability signal is model-only — no market comparison possible."
            ),
        )

    # ── Market data available: compute gaps ────────────────────────────────────
    assert inp.market_home is not None
    assert inp.market_draw is not None
    assert inp.market_away is not None

    gaps = {
        "home": inp.model_home - inp.market_home,
        "draw": inp.model_draw - inp.market_draw,
        "away": inp.model_away - inp.market_away,
    }
    abs_gaps   = {sel: abs(g) for sel, g in gaps.items()}
    max_sel    = max(abs_gaps, key=abs_gaps.__getitem__)
    max_gap    = abs_gaps[max_sel]
    signed_gap = gaps[max_sel]

    model_prob = {"home": inp.model_home, "draw": inp.model_draw, "away": inp.model_away}[max_sel]
    market_prob = {"home": inp.market_home, "draw": inp.market_draw, "away": inp.market_away}[max_sel]
    blend_prob  = {"home": inp.blend_home,  "draw": inp.blend_draw,  "away": inp.blend_away}[max_sel]

    gap_pct    = round(abs(signed_gap) * 100)
    direction  = "higher" if signed_gap > 0 else "lower"
    sel_label  = _SELECTION_NAMES[max_sel]

    edge_conf = _edge_confidence_for_gap(max_gap)

    # ── Rule 3: Small gap → market_aligned ────────────────────────────────────
    if max_gap < SMALL_GAP_THRESHOLD:
        return Recommendation(
            **identity,
            recommendation_type="market_aligned",
            selection=sel_label,
            model_probability=round(model_prob, 4),
            market_probability=round(market_prob, 4),
            blended_probability=round(blend_prob, 4),
            model_market_gap=round(signed_gap, 4),
            confidence="low", risk_label="low",
            data_quality=dq, status=st, is_actionable=False,
            edge_confidence=edge_conf,
            reason=(
                "Model and market probabilities are broadly aligned "
                f"(gap < {int(SMALL_GAP_THRESHOLD * 100)}pp). "
                "No material difference detected."
            ),
        )

    # ── Rule 4: Moderate gap → watch ──────────────────────────────────────────
    if max_gap < MODERATE_GAP_THRESHOLD:
        return Recommendation(
            **identity,
            recommendation_type="watch",
            selection=sel_label,
            model_probability=round(model_prob, 4),
            market_probability=round(market_prob, 4),
            blended_probability=round(blend_prob, 4),
            model_market_gap=round(signed_gap, 4),
            confidence="low", risk_label="low",
            data_quality=dq, status=st, is_actionable=False,
            edge_confidence=edge_conf,
            reason=(
                f"Model probability is {gap_pct}pp {direction} than the market benchmark "
                f"on {sel_label}. Signal is present but not strong enough to flag."
            ),
        )

    # ── Rule 5: Large gap → model_gap_detected ────────────────────────────────
    return Recommendation(
        **identity,
        recommendation_type="model_gap_detected",
        selection=sel_label,
        model_probability=round(model_prob, 4),
        market_probability=round(market_prob, 4),
        blended_probability=round(blend_prob, 4),
        model_market_gap=round(signed_gap, 4),
        confidence=_gap_confidence(inp),
        risk_label=_gap_risk(max_gap),
        data_quality=dq, status=st, is_actionable=_is_actionable(inp),
        edge_confidence=edge_conf,
        reason=(
            f"Model probability is {gap_pct} percentage points {direction} "
            f"than the market benchmark on {sel_label}."
        ),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _match_status(inp: RecommendationInput) -> str:
    if inp.result_status == "finished":
        return "finished"
    if inp.result_status == "live":
        return "live"
    if inp.result_status in ("scheduled", None):
        return "pre_match"
    if inp.result_status in ("postponed", "cancelled"):
        return "unavailable"
    return "pre_match"


def _data_quality(inp: RecommendationInput) -> str:
    if not inp.has_market_data:
        return "missing_market"
    if inp.fixture_status != "official":
        return "placeholder"
    if inp.capture_status in ("no_market_data", "unknown"):
        return "missing_market"
    if inp.capture_status == "opening_only":
        return "partial"
    return "complete"


def _is_actionable(inp: RecommendationInput) -> bool:
    """True only when all safety conditions are met."""
    return (
        inp.has_market_data
        and _match_status(inp) == "pre_match"
        and inp.fixture_status == "official"
        and inp.capture_status not in ("no_market_data", "unknown")
        and inp.result_status != "finished"
    )


def _gap_confidence(inp: RecommendationInput) -> str:
    """Confidence level — never 'high' (conservative posture)."""
    if _data_quality(inp) in ("missing_market", "placeholder", "unknown"):
        return "low"
    if inp.capture_status in ("opening_only", "latest_available"):
        return "low"
    # closing_candidate or closing_locked → medium at most
    return "medium"


def _gap_risk(max_gap: float) -> str:
    if max_gap >= 0.12:
        return "high"
    if max_gap >= MODERATE_GAP_THRESHOLD:
        return "medium"
    return "low"
