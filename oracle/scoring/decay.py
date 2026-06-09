"""
Time-decay weights for match history.

The intuition: a match played five years ago is less informative about a team's
current strength than a match played last month. Exponential decay captures this
with one tunable parameter (xi).

The formula is: weight = exp(-xi * days_before_base_date)

Half-life reference values (useful for communicating the decay speed to humans):
  xi = 0.0005  →  half-life ≈ 1386 days (~3.8 years)  [very mild]
  xi = 0.0010  →  half-life ≈  693 days (~1.9 years)   [mild]
  xi = 0.0018  →  half-life ≈  385 days (~12.8 months) [Dixon-Coles 1997 default]
  xi = 0.0030  →  half-life ≈  231 days (~7.7 months)  [steep]
  xi = 0.0050  →  half-life ≈  139 days (~4.6 months)  [very steep]

Dixon and Coles (1997) used xi ≈ 0.0018 on English football data.  For
international football (fewer matches per year per team), a slightly milder
decay may be appropriate.  We expose XI_DEFAULT as the recommended starting
point and let callers override.

Delegate to penaltyblog.models.dixon_coles_weights rather than re-implementing
the formula.
"""
from __future__ import annotations

from datetime import date

import numpy as np
from penaltyblog.models import dixon_coles_weights

# Half-life ≈ 385 days — matches Dixon & Coles (1997)
XI_DEFAULT: float = 0.0018
# Half-life ≈ 693 days — gentler decay for sparse international schedules
XI_MILD: float = 0.0010
# Half-life ≈ 231 days — faster forgetting, emphasises recent form
XI_STEEP: float = 0.0030


def match_weights(
    dates: list,
    xi: float = XI_DEFAULT,
    base_date: date | None = None,
) -> np.ndarray:
    """Return exponential time-decay weights for a list of match dates.

    The weight for a match d days before base_date is exp(-xi * d).
    The most-recent match (d=0) always gets weight 1.0.

    Parameters
    ----------
    dates:
        Ordered or unordered list of `datetime.date` objects.
    xi:
        Decay rate. Larger xi → faster forgetting. See module docstring for
        half-life reference values.  Default is XI_DEFAULT (0.0018).
    base_date:
        The reference "today" from which decay is measured.  Defaults to
        max(dates).  Explicitly pass the train cutoff when computing weights
        for a train set so the weighting is reproducible regardless of when
        the pipeline is run.

    Returns
    -------
    np.ndarray of shape (len(dates),) with values in (0, 1].
    """
    return dixon_coles_weights(dates, xi=xi, base_date=base_date)


def half_life_days(xi: float) -> float:
    """Return the half-life in days for a given decay rate xi.

    weight(t) = exp(-xi * t) = 0.5  →  t = ln(2) / xi
    """
    return float(np.log(2) / xi)
