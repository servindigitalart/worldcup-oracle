"""
Calibration diagnostics for 1X2 match predictions.

Calibration measures whether stated probabilities match observed frequencies.
A model that says "40% home win" across many matches should see a home win
roughly 40% of the time in that group.

For a K=3 outcome market the standard diagnostic is a reliability diagram:
  1. Collect (predicted_prob, observed) pairs for one outcome (e.g. home_win).
  2. Sort by predicted_prob and bin into B equal-frequency groups.
  3. Within each bin, compare mean(predicted_prob) vs mean(observed==1).
  4. Perfect calibration: the two quantities should be equal (identity line).

Important caveats — be honest about these:
  - 36 matches is a very small holdout.  Calibration statistics at this scale
    have wide confidence intervals.  Report n_matches per bin to make this
    transparent.
  - Equal-frequency bins are used (not equal-width) to ensure each bin has
    enough samples to compute a meaningful rate.
  - We report calibration for the home_win outcome only.  For a 3-outcome
    market, calibrating all three simultaneously is a richer exercise but
    requires more data.

Reference: Niculescu-Mizil & Caruana, "Predicting Good Probabilities with
Supervised Learning", ICML 2005.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CalibrationBin:
    """Statistics for one calibration bin."""
    bin_index:         int
    n_matches:         int
    mean_predicted:    float     # average predicted probability in this bin
    observed_rate:     float     # fraction of matches where the outcome occurred
    # gap > 0 means model is over-confident in this bin
    calibration_gap:   float = field(init=False)

    def __post_init__(self) -> None:
        self.calibration_gap = self.mean_predicted - self.observed_rate


@dataclass
class CalibrationResult:
    """Full calibration output for one outcome."""
    outcome_label:   str
    n_matches:       int
    n_bins:          int
    bins:            list[CalibrationBin]
    mean_calibration_gap: float   # mean |gap| across bins (lower = better)
    # baseline: what would the gap be for a uniform (1/3) predictor?
    uniform_baseline_prob: float  # = 1/3 for 1X2


def calibration_bins(
    predicted_probs: list[float],
    observed:        list[int],      # 1 if outcome occurred, 0 otherwise
    outcome_label:   str = "home_win",
    n_bins:          int = 5,
) -> CalibrationResult:
    """Compute calibration bins for a single outcome.

    Parameters
    ----------
    predicted_probs:
        List of model's predicted probability for this outcome (one per match).
    observed:
        Binary list: 1 if the outcome occurred, 0 otherwise.
    outcome_label:
        Human-readable name for logging / JSON output.
    n_bins:
        Number of equal-frequency bins.  Use fewer bins with small samples.
        With 36 holdout matches, n_bins=5 gives ~7 matches/bin (borderline).
        With 36 matches, n_bins=10 gives ~3.6 matches/bin (too sparse).

    Returns
    -------
    CalibrationResult with per-bin statistics.
    """
    if len(predicted_probs) != len(observed):
        raise ValueError(
            f"predicted_probs ({len(predicted_probs)}) and observed ({len(observed)}) "
            "must have the same length."
        )
    if len(predicted_probs) == 0:
        raise ValueError("Empty inputs — no matches to calibrate.")
    if not (1 <= n_bins <= len(predicted_probs)):
        raise ValueError(f"n_bins must be in [1, {len(predicted_probs)}]; got {n_bins}.")

    n = len(predicted_probs)
    # Sort by predicted probability ascending
    pairs = sorted(zip(predicted_probs, observed), key=lambda x: x[0])

    # Build equal-frequency bins (last bin absorbs any remainder)
    bin_size = n // n_bins
    bins: list[CalibrationBin] = []

    for b in range(n_bins):
        start = b * bin_size
        end   = start + bin_size if b < n_bins - 1 else n
        chunk = pairs[start:end]
        if not chunk:
            continue

        preds = [p for p, _ in chunk]
        obs   = [o for _, o in chunk]

        bins.append(CalibrationBin(
            bin_index=b,
            n_matches=len(chunk),
            mean_predicted=sum(preds) / len(preds),
            observed_rate=sum(obs) / len(obs),
        ))

    mean_gap = (
        sum(abs(b.calibration_gap) for b in bins) / len(bins) if bins else float("nan")
    )

    return CalibrationResult(
        outcome_label=outcome_label,
        n_matches=n,
        n_bins=len(bins),
        bins=bins,
        mean_calibration_gap=mean_gap,
        uniform_baseline_prob=1.0 / 3.0,
    )


def calibration_to_dict(result: CalibrationResult) -> dict:
    """Serialise a CalibrationResult to a JSON-safe dict."""
    return {
        "outcome_label":         result.outcome_label,
        "n_matches":             result.n_matches,
        "n_bins":                result.n_bins,
        "mean_abs_calibration_gap": round(result.mean_calibration_gap, 4),
        "uniform_baseline_prob": round(result.uniform_baseline_prob, 4),
        "small_sample_warning": (
            result.n_matches < 100
        ),
        "bins": [
            {
                "bin_index":       b.bin_index,
                "n_matches":       b.n_matches,
                "mean_predicted":  round(b.mean_predicted, 4),
                "observed_rate":   round(b.observed_rate, 4),
                "calibration_gap": round(b.calibration_gap, 4),
            }
            for b in result.bins
        ],
    }
