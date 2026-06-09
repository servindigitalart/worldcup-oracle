"""
Market de-vigging: convert bookmaker decimal odds to fair probabilities.

All three methods are now implemented using penaltyblog.implied.calculate_implied,
which provides Shin (1993), power, multiplicative, and several other methods.

Method comparison (from penaltyblog and the literature):
  naive / multiplicative  — proportional normalization. Fast, biased toward
                            favourites (favourite-longshot bias uncorrected).
  power                   — finds exponent k s.t. (1/o_i)^(1/k) sums to 1.
                            Better than naive on FLB.
  shin                    — Shin (1993) insider-trading model. Gold standard
                            for favourite-longshot bias correction. Use this
                            for the CLV benchmark.

Blueprint (Part 3): "De-vig the closing line properly — Shin's method or the
power method, NOT naive normalization, because the favourite-longshot bias
matters. (penaltyblog has overround removal.)"

We keep naive_normalize as a local fallback (zero extra dependency) so the
harness still works if penaltyblog is unavailable.
"""
from __future__ import annotations

from penaltyblog.implied import calculate_implied, ImpliedMethod

Odds = dict[str, float]  # outcome -> decimal odds


# ------------------------------------------------------------------
# Raw helpers (no penaltyblog dependency)
# ------------------------------------------------------------------

def implied_probabilities(odds: Odds) -> dict[str, float]:
    """Convert decimal odds to raw (overround-inclusive) implied probabilities."""
    return {k: 1.0 / v for k, v in odds.items()}


def overround(odds: Odds) -> float:
    """Bookmaker margin: sum of implied probs. Should be > 1.0 for typical markets."""
    return sum(implied_probabilities(odds).values())


def naive_normalize(odds: Odds) -> dict[str, float]:
    """Proportional (multiplicative) normalization — fast but biased.

    Use as a fallback or sanity check only. Prefer `shin` or `power` in the
    actual pipeline.
    """
    impl = implied_probabilities(odds)
    total = sum(impl.values())
    return {k: v / total for k, v in impl.items()}


# ------------------------------------------------------------------
# penaltyblog-backed implementations
# ------------------------------------------------------------------

def _pb_devig(odds: Odds, method: ImpliedMethod) -> dict[str, float]:
    """Internal: call penaltyblog.calculate_implied and return a labelled dict."""
    keys = list(odds.keys())
    values = [odds[k] for k in keys]
    result = calculate_implied(values, method=method, market_names=keys)
    return dict(zip(keys, [float(p) for p in result.probabilities]))


def power_devig(odds: Odds) -> dict[str, float]:
    """Power method de-vig (Štrumbelj 2014).

    Finds exponent k such that (1/o_i)^(1/k) sums to 1.
    Better than naive normalization on favourite-longshot bias.
    """
    return _pb_devig(odds, ImpliedMethod.POWER)


def shin_devig(odds: Odds) -> dict[str, float]:
    """Shin (1993) de-vig — structurally models insider-trading proportion z.

    Gold standard for favourite-longshot bias correction.
    Use this as the default for CLV benchmark and market blend.
    """
    return _pb_devig(odds, ImpliedMethod.SHIN)


# ------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------

def devig(odds: Odds, method: str = "shin") -> dict[str, float]:
    """De-vig dispatcher.

    method: 'shin' (default) | 'power' | 'naive'

    Default changed from 'naive' (Week 1) to 'shin' (Week 2) now that
    penaltyblog is installed. Using 'naive' is now opt-in.
    """
    if method == "shin":
        return shin_devig(odds)
    if method == "power":
        return power_devig(odds)
    if method in ("naive", "multiplicative"):
        return naive_normalize(odds)
    raise ValueError(
        f"Unknown de-vig method: {method!r}. Choose 'shin', 'power', or 'naive'."
    )
