"""
Model-market probability blend.

blend_probabilities()  — weighted average of model and market 1X2 probs.
blend_model_only()     — pass-through when market data is absent.
batch_blend()          — apply blend across a collection of matches.
backtest_blend()       — score blended vs pure-model on historical records.
                         Requires real historical market odds; without them
                         the results are illustrative only.

Default weights: 80% market / 20% model.

Rationale:
  The closing line is empirically the most accurate pre-match forecast.
  An 80/20 blend treats the market as the primary prior and the model as
  a corrective signal.  These weights have NOT been tuned for any financial
  objective and will be revisited once WC 2026 calibration data accumulates.
"""
from __future__ import annotations

from typing import Optional

from oracle.market.baseline import Probs1x2, validate_market_probs
from oracle.scoring.metrics import rps as _rps

DEFAULT_MARKET_WEIGHT = 0.80
DEFAULT_MODEL_WEIGHT  = 0.20

_OUTCOME_INDEX = {"home": 0, "draw": 1, "away": 2}
_SELECTIONS = ("home", "draw", "away")


def blend_probabilities(
    model_probs: Probs1x2,
    market_probs: Probs1x2,
    market_weight: float = DEFAULT_MARKET_WEIGHT,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
) -> dict:
    """Weighted blend of model and market 1X2 probabilities.

    Renormalises the result so it sums exactly to 1.0 (floating-point safety).

    Args:
        model_probs:   {"home": float, "draw": float, "away": float} summing to ~1.
        market_probs:  De-vigged market probabilities in the same format.
        market_weight: Weight on market.  Default: 0.80.
        model_weight:  Weight on model.   Default: 0.20.

    Returns dict with:
        home, draw, away          — blended, normalised probabilities
        market_weight, model_weight
        label = "blend"
        note                      — disclaimer (no "edge"/"profit"/"guaranteed" language)

    Raises ValueError if weights don't sum to 1.0 or inputs fail validation.
    """
    if abs(market_weight + model_weight - 1.0) > 1e-6:
        raise ValueError(
            f"Weights must sum to 1.0: market={market_weight} + model={model_weight} "
            f"= {market_weight + model_weight:.8f}"
        )
    for name, probs in [("model", model_probs), ("market", market_probs)]:
        if not validate_market_probs(probs):
            raise ValueError(f"{name} probabilities are invalid: {probs!r}")

    raw = {
        sel: market_weight * market_probs[sel] + model_weight * model_probs[sel]
        for sel in _SELECTIONS
    }
    total = sum(raw.values())
    normalised = {sel: v / total for sel, v in raw.items()}

    return {
        "home":          normalised["home"],
        "draw":          normalised["draw"],
        "away":          normalised["away"],
        "market_weight": market_weight,
        "model_weight":  model_weight,
        "label":         "blend",
        "note": (
            f"Blended probabilities (market {market_weight:.0%} / "
            f"model {model_weight:.0%}). "
            "For calibration benchmarking only. "
            "Weights reflect a prior on market information content "
            "and have not been calibrated to any specific objective. "
            "Not financial or betting advice."
        ),
    }


def blend_model_only(model_probs: Probs1x2) -> dict:
    """Pass-through for matches without market data.

    Returns model probabilities in the same schema as blend_probabilities()
    so downstream code handles both cases uniformly.
    """
    if not validate_market_probs(model_probs):
        raise ValueError(f"model probabilities are invalid: {model_probs!r}")
    return {
        "home":          model_probs["home"],
        "draw":          model_probs["draw"],
        "away":          model_probs["away"],
        "market_weight": 0.0,
        "model_weight":  1.0,
        "label":         "model_only",
        "note":          "No market data for this match — model probabilities used directly.",
    }


def batch_blend(
    model_probs_by_match: dict[str, Probs1x2],
    market_probs_by_match: dict[str, Optional[Probs1x2]],
    market_weight: float = DEFAULT_MARKET_WEIGHT,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
) -> dict[str, dict]:
    """Blend model and market probabilities for all matches.

    Matches without market data receive blend_model_only().
    Returns {match_id: blend_result_dict}.
    """
    results: dict[str, dict] = {}
    for match_id, model_p in model_probs_by_match.items():
        market_p = (market_probs_by_match or {}).get(match_id)
        if market_p is not None:
            results[match_id] = blend_probabilities(
                model_p, market_p,
                market_weight=market_weight,
                model_weight=model_weight,
            )
        else:
            results[match_id] = blend_model_only(model_p)
    return results


# ── Backtest infrastructure ───────────────────────────────────────────────────

def backtest_blend(
    records: list[dict],
    market_weight: float = DEFAULT_MARKET_WEIGHT,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
) -> dict:
    """Score blended vs pure-model predictions on a set of historical records.

    Each record must have:
        model_probs:  {"home": float, "draw": float, "away": float}
        market_probs: {"home": float, "draw": float, "away": float} or None
        outcome:      "home" | "draw" | "away"

    Returns:
        blend_mean_rps    — mean RPS of the blended predictions
        model_mean_rps    — mean RPS of the pure model predictions
        market_mean_rps   — mean RPS of market-only predictions (None if no market data)
        n_records         — total records evaluated
        n_with_market     — records where market data was used in the blend
        market_weight, model_weight
        has_real_data     — always False; real historical market odds not yet available
        note              — explicit limitation disclaimer

    ⚠️  Without real historical market odds, these results are illustrative only.
    """
    if not records:
        return {
            "blend_mean_rps":  None,
            "model_mean_rps":  None,
            "market_mean_rps": None,
            "n_records":       0,
            "n_with_market":   0,
            "market_weight":   market_weight,
            "model_weight":    model_weight,
            "has_real_data":   False,
            "note": (
                "No records provided. Real backtesting requires historical "
                "market odds captured before each match (not yet available)."
            ),
        }

    blend_rpss, model_rpss, market_rpss = [], [], []
    n_with_market = 0

    for rec in records:
        outcome = rec.get("outcome")
        if outcome not in _OUTCOME_INDEX:
            continue
        outcome_idx = _OUTCOME_INDEX[outcome]
        model_p = rec["model_probs"]

        model_rpss.append(_rps([model_p[s] for s in _SELECTIONS], outcome_idx))

        market_p = rec.get("market_probs")
        if market_p is not None and validate_market_probs(market_p):
            blended = blend_probabilities(model_p, market_p, market_weight, model_weight)
            blend_rpss.append(_rps([blended[s] for s in _SELECTIONS], outcome_idx))
            market_rpss.append(_rps([market_p[s] for s in _SELECTIONS], outcome_idx))
            n_with_market += 1
        else:
            blend_rpss.append(_rps([model_p[s] for s in _SELECTIONS], outcome_idx))

    n = len(blend_rpss)
    return {
        "blend_mean_rps":  sum(blend_rpss) / n if n else None,
        "model_mean_rps":  sum(model_rpss) / n if n else None,
        "market_mean_rps": sum(market_rpss) / n_with_market if n_with_market else None,
        "n_records":       n,
        "n_with_market":   n_with_market,
        "market_weight":   market_weight,
        "model_weight":    model_weight,
        "has_real_data":   False,
        "note": (
            "No real historical market odds available. "
            "Results are illustrative only. "
            "Real backtesting requires market odds captured before each match."
        ),
    }
