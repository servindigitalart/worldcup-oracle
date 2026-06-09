"""
Dixon-Coles goal model for international football.

Wraps penaltyblog.models.DixonColesGoalModel.  The model fits attack/defense
parameters per team from a history of match results, then generates a full
score matrix from which 1X2 probabilities are derived.

Design decisions (Week 3):
  - Training data: ALL matches with non-null scores, using canonical IDs for
    the 48 WC teams and raw team names for everyone else.  This maximises the
    data available to estimate each canonical team's attack/defense strength
    (a match between France and "Scotland" still informs France's parameters).
  - Time-decay: uses penaltyblog's dixon_coles_weights with xi=XI_DEFAULT
    (0.0018, half-life ~385 days).  This is the hyperparameter used in the
    original Dixon & Coles (1997) paper.  We make it configurable.
  - Neutral venue: passed as a per-match 0/1 array during fit, and as a
    flag on predict().  WC 2026 matches are all neutral (host cities, not
    home turf for any participant).
  - max_goals=10: capping the score matrix at 10 goals is standard; values
    beyond this have negligible probability and add compute cost.

Known limitation:
  - Teams with very few appearances in the training set get noisy parameter
    estimates.  For WC 2026 teams with thin martj42 history (e.g. Tanzania,
    Honduras), the Elo baseline may be more reliable.

TODO Week 4:
  - Add regularisation / shrinkage for thin-data teams.
  - Expose goal expectation ('home_goals', 'away_goals') in
    ratings_dataframe() for use in the simulator.
  - Persist fitted parameters to disk so the simulator can reload quickly.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import polars as pl
from penaltyblog.models import DixonColesGoalModel

from oracle.scoring.decay import XI_DEFAULT, match_weights
from oracle.teams import CANONICAL_TEAMS, try_resolve_team

log = logging.getLogger(__name__)

MODEL_VERSION = "dixon-coles-v0.3"


class DixonColesRatings:
    """Fit a Dixon-Coles goal model and predict 1X2 match probabilities.

    Usage::

        dc = DixonColesRatings(xi=0.0018)
        dc.fit(results_df)
        probs = dc.predict("france", "germany", neutral=True)
        # → {'home': 0.40, 'draw': 0.24, 'away': 0.36}
    """

    MAX_GOALS = 10

    def __init__(self, xi: float = XI_DEFAULT, max_date: Optional[date] = None) -> None:
        self.xi = xi
        self.max_date = max_date
        self._model: Optional[DixonColesGoalModel] = None
        self._n_train: int = 0
        self._fitted = False

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit(self, df: pl.DataFrame) -> "DixonColesRatings":
        """Train on a martj42-style DataFrame.

        Required columns: date, home_team, away_team, home_score, away_score.
        Optional columns: neutral, home_team_id, away_team_id.

        Non-null scores only.  Applies time-decay weights with self.xi.
        Uses canonical IDs for the 48 WC teams; raw team names for others.
        """
        required = {"date", "home_team", "away_team", "home_score", "away_score"}
        if missing := required - set(df.columns):
            raise ValueError(f"Results DataFrame missing columns: {missing}")

        df = df.sort("date")
        if self.max_date is not None:
            df = df.filter(pl.col("date") <= pl.lit(self.max_date))

        df = df.filter(
            pl.col("home_score").is_not_null() & pl.col("away_score").is_not_null()
        )

        if len(df) == 0:
            raise ValueError("No rows with non-null scores after filtering.")

        has_id_cols = {"home_team_id", "away_team_id"} <= set(df.columns)
        has_neutral  = "neutral" in df.columns

        home_teams: list[str] = []
        away_teams: list[str] = []
        g_home:     list[int] = []
        g_away:     list[int] = []
        dates:      list      = []
        neutral_vec: list[int] = []

        for row in df.iter_rows(named=True):
            if has_id_cols and row.get("home_team_id") and row.get("away_team_id"):
                hk = row["home_team_id"]
                ak = row["away_team_id"]
            else:
                hk = try_resolve_team(row["home_team"]) or row["home_team"]
                ak = try_resolve_team(row["away_team"]) or row["away_team"]

            home_teams.append(hk)
            away_teams.append(ak)
            g_home.append(int(row["home_score"]))
            g_away.append(int(row["away_score"]))

            match_date = row["date"]
            if isinstance(match_date, str):
                match_date = date.fromisoformat(match_date)
            dates.append(match_date)

            is_neutral = bool(row.get("neutral")) if has_neutral else False
            neutral_vec.append(1 if is_neutral else 0)

        weights = match_weights(dates, xi=self.xi)

        self._model = DixonColesGoalModel(
            g_home, g_away, home_teams, away_teams,
            weights=weights,
            neutral_venue=neutral_vec,
        )
        self._model.fit()
        self._n_train = len(home_teams)
        self._fitted = True

        log.info(
            "DixonColesRatings.fit: %d matches, xi=%.4f (half-life ~%.0f days)",
            self._n_train, self.xi, float(__import__("numpy").log(2) / self.xi),
        )
        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(
        self,
        home_team_id: str,
        away_team_id: str,
        neutral: bool = True,
    ) -> dict[str, float]:
        """Return 1X2 probability dict {'home', 'draw', 'away'}.

        neutral=True (default for WC 2026): no home advantage.
        """
        if not self._fitted or self._model is None:
            raise RuntimeError("Call .fit() before .predict().")

        grid = self._model.predict(
            home_team_id,
            away_team_id,
            max_goals=self.MAX_GOALS,
            normalize=True,
            neutral_venue=neutral,
        )
        h, d, a = grid.home_draw_away
        return {"home": float(h), "draw": float(d), "away": float(a)}

    def predict_grid(
        self,
        home_team_id: str,
        away_team_id: str,
        neutral: bool = True,
    ):
        """Return a FootballProbabilityGrid — the full (MAX_GOALS × MAX_GOALS) joint
        score probability matrix for the given matchup.

        Grid entry [h, a] = P(home scores h goals, away scores a goals).
        Rows are home goals; columns are away goals.  Probabilities are non-negative
        and sum to 1.0 (normalize=True).

        Intended use: scoreline sampling for the tournament group stage.  Call once
        per matchup pair before the Monte Carlo loop; reuse the result across sims.

        Assumptions:
          - neutral=True zeros the home-advantage parameter (correct for WC 2026).
          - Goals are capped at MAX_GOALS-1; tail probability is absorbed by the
            (MAX_GOALS-1, *) and (*, MAX_GOALS-1) cells.
          - Teams with thin training data produce noisy mu estimates; check
            home_goal_expectation / away_goal_expectation for sanity.
        """
        if not self._fitted or self._model is None:
            raise RuntimeError("Call .fit() before .predict_grid().")

        return self._model.predict(
            home_team_id,
            away_team_id,
            max_goals=self.MAX_GOALS,
            normalize=True,
            neutral_venue=neutral,
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def ratings_dataframe(self) -> pl.DataFrame:
        """Return a Polars DataFrame of attack/defense parameters for 48 WC teams.

        Only includes teams whose parameters were estimated during fit.
        Teams absent from training receive NaN parameters.
        """
        if not self._fitted or self._model is None:
            raise RuntimeError("Call .fit() before .ratings_dataframe().")

        params = self._model.get_params()
        rows = []
        for tid, (display_name, confederation) in CANONICAL_TEAMS.items():
            att_key  = f"attack_{tid}"
            def_key  = f"defence_{tid}"
            att = float(params[att_key])  if att_key  in params else float("nan")
            dfn = float(params[def_key])  if def_key  in params else float("nan")
            rows.append({
                "team_id":       tid,
                "display_name":  display_name,
                "confederation": confederation,
                "attack":        att,
                "defence":       dfn,
            })

        return pl.DataFrame(rows).sort("attack", descending=True, nulls_last=True)
