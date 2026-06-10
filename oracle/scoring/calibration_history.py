"""
Calibration history — transform calibration bin data into a frontend-friendly
bucket format with labelled probability ranges.

calibration_history_from_bins(bins, n_matches)  → list[dict]
generate_calibration_history(calibration_json, model_key)  → list[dict]

Output format per bucket:
  {
    "bucket":    "0.20-0.25",   # predicted-probability range label
    "predicted": 0.234,         # mean predicted probability in this bin
    "actual":    0.214,         # observed outcome rate
    "samples":   14,            # number of matches in this bin
    "gap":       0.020,         # signed gap = predicted − actual
  }
"""
from __future__ import annotations


def _bucket_label(mean_pred: float, bin_width: float = 0.05) -> str:
    """Return a 'lo-hi' label for the bin that mean_pred falls in."""
    lo = (mean_pred // bin_width) * bin_width
    hi = lo + bin_width
    return f"{lo:.2f}-{hi:.2f}"


def calibration_history_from_bins(
    bins: list[dict],
    total_matches: int | None = None,
) -> list[dict]:
    """Convert calibration bin dicts into calibration-history bucket dicts.

    Args:
        bins: List of bin dicts as produced by calibration_to_dict(). Each must
              have: n_matches, mean_predicted, observed_rate, calibration_gap.
        total_matches: Optional total for validation.  Not used for output.

    Returns:
        List of bucket dicts, sorted by mean_predicted ascending.
    """
    result = []
    for b in bins:
        n     = b["n_matches"]
        pred  = b["mean_predicted"]
        actual = b["observed_rate"]
        gap   = b.get("calibration_gap", round(pred - actual, 4))
        result.append({
            "bucket":    _bucket_label(pred),
            "predicted": round(pred, 4),
            "actual":    round(actual, 4),
            "samples":   n,
            "gap":       round(gap, 4),
        })
    result.sort(key=lambda x: x["predicted"])
    return result


def generate_calibration_history(
    calibration_json: dict,
    model_key: str = "elo-baseline-v0.2",
) -> list[dict]:
    """Extract calibration history from a calibration_worldcups.json structure.

    Args:
        calibration_json: Loaded content of calibration_worldcups.json (or _2022.json).
        model_key: Key in calibration_json["models"] to extract.

    Returns:
        List of bucket dicts (see calibration_history_from_bins).
        Empty list if model_key not found or calibration_json is malformed.
    """
    models = calibration_json.get("models", {})
    model_data = models.get(model_key)
    if not model_data:
        return []
    bins = model_data.get("bins", [])
    return calibration_history_from_bins(bins)
