"""
Methodology explainability — generate the methodology.json artifact.

generate() → dict   (JSON-serialisable)
"""
from __future__ import annotations

from oracle.forecast.baseline import MODEL_VERSION as ELO_VERSION
from oracle.market.blend import DEFAULT_MARKET_WEIGHT, DEFAULT_MODEL_WEIGHT
from oracle.methodology.inputs import INPUTS_NOT_USED, INPUTS_USED, LIMITATIONS
from oracle.ratings.dixon_coles import MODEL_VERSION as DC_VERSION

BLEND_VERSION = (
    f"market-{int(DEFAULT_MARKET_WEIGHT * 100)}-{int(DEFAULT_MODEL_WEIGHT * 100)}"
)

ELO_DESCRIPTION = {
    "name": "Elo Rating System",
    "version": ELO_VERSION,
    "what_it_is": (
        "A zero-sum rating system where every match transfers rating points "
        "from the loser to the winner, scaled by the K-factor and the "
        "probability of the result."
    ),
    "what_it_does": (
        "Converts per-team Elo ratings into 1X2 probabilities via the logistic "
        "function.  A 200-point Elo gap corresponds to roughly 75% win probability."
    ),
    "strengths": [
        "Robust to missing data — works even for teams with few appearances.",
        "Incorporates full match history back to 1872.",
        "Tournament-importance K-factors (WC=30, competitive=20, friendly=10) "
        "weight high-stakes results appropriately.",
        "Transparent, deterministic, and easy to audit.",
    ],
    "weaknesses": [
        "Ignores score margin — a 1-0 and 5-0 result update ratings identically.",
        "No squad-level or tactical information.",
        "Cannot capture within-tournament momentum or injury effects.",
        "Thin-data teams (debut nations) start at a default rating with high uncertainty.",
    ],
}

DIXON_COLES_DESCRIPTION = {
    "name": "Dixon-Coles Goal Model",
    "version": DC_VERSION,
    "what_it_is": (
        "A bivariate Poisson model with a low-score correlation correction "
        "(Dixon & Coles, 1997).  Fits per-team attack and defense parameters "
        "from historical scorelines."
    ),
    "what_it_does": (
        "Generates a full score-matrix (e.g., P(1-0), P(2-1), ...) from which "
        "1X2 probabilities, over/under, and exact-score odds can be derived.  "
        "Time-decay weights (xi=0.0018, half-life ≈385 days) down-weight older matches."
    ),
    "strengths": [
        "Uses scorelines — more information per match than Elo.",
        "Separates attack from defense strength.",
        "Time-decay naturally reduces the influence of results from distant tournaments.",
        "Generates a full distributional forecast, not just win probabilities.",
    ],
    "weaknesses": [
        "Requires more data per team to fit reliably than Elo.",
        "Score matrix computation is slower than a simple Elo lookup.",
        "Low-score correlation correction (rho) adds a fitted parameter that may over-fit on small samples.",
        "Neutral-venue is approximated as a binary flag, not modelled per-venue.",
    ],
}

MARKET_BLEND_DESCRIPTION = {
    "name": "Market Blend",
    "version": BLEND_VERSION,
    "market_weight": DEFAULT_MARKET_WEIGHT,
    "model_weight": DEFAULT_MODEL_WEIGHT,
    "why_it_exists": (
        "The closing line is empirically the most accurate pre-match probability "
        "estimate in liquid markets.  An 80/20 blend treats the market as the "
        "primary prior and the model as a corrective signal."
    ),
    "why_not_follow_market_blindly": (
        "Markets can be illiquid or slow-to-open for non-marquee matches.  "
        "The model provides a structural prior that is not subject to short-term "
        "line movement or bettor sentiment."
    ),
    "why_calibration_matters": (
        "A model that says 60% should be right 60% of the time across many "
        "similar predictions.  Without calibration, stated probabilities are "
        "uninterpretable and edges vs market cannot be assessed."
    ),
    "caveat": (
        "Blend weights have NOT been optimised for any financial objective.  "
        "They will be revisited once WC 2026 calibration data accumulates."
    ),
}


def generate() -> dict:
    """Return the full methodology descriptor dict."""
    return {
        "model_version":    ELO_VERSION,
        "goals_model":      DC_VERSION,
        "blend_version":    BLEND_VERSION,
        "inputs_used":      INPUTS_USED,
        "inputs_not_used":  INPUTS_NOT_USED,
        "limitations":      LIMITATIONS,
        "elo":              ELO_DESCRIPTION,
        "dixon_coles":      DIXON_COLES_DESCRIPTION,
        "market_blend":     MARKET_BLEND_DESCRIPTION,
    }
