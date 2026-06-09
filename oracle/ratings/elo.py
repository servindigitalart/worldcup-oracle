"""
Elo rating system for international football.

Wraps penaltyblog.ratings.Elo and fits it on the full martj42 history.

Design decisions (Week 2):
  - Teams not in the canonical table keep their raw name as the Elo key.
    This preserves their influence on 2026-team ratings (e.g. a 2022 qualifier
    that didn't make it to 2026 still shaped Argentina's rating via head-to-head).
  - Neutral venue: HFA is temporarily zeroed for neutral-venue matches, since
    the penaltyblog Elo doesn't expose a per-call neutral flag.
  - Friendly K-factor (10) < competitive K-factor (20), matching FIFA's
    own Elo methodology.
  - World Cup / continental championship matches use K=30 (higher signal).

TODO Week 3:
  - Replace with Dixon-Coles + time-decay weights (xi ≈ 0.002) for a
    proper attack/defense decomposition and full score matrix.
  - Add rating variance / uncertainty estimate (Glicko-style RD) so thin-data
    teams propagate wider distributions through the simulator.
  - Add Transfermarkt squad-value prior to regularize teams with < 20 matches.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import polars as pl
from penaltyblog.ratings import Elo

from oracle.teams import CANONICAL_TEAMS, try_resolve_team

log = logging.getLogger(__name__)

# Tournament-importance K-factors (FIFA Elo methodology)
_K_WC          = 30.0
_K_COMPETITIVE = 20.0
_K_FRIENDLY    = 10.0

_WC_KEYWORDS        = frozenset(["world cup", "fifa world cup"])
_FRIENDLY_KEYWORDS  = frozenset(["friendly"])


def _k_for_tournament(tournament: str | None) -> float:
    if not tournament:
        return _K_FRIENDLY
    t = tournament.lower()
    if any(kw in t for kw in _WC_KEYWORDS):
        return _K_WC
    if any(kw in t for kw in _FRIENDLY_KEYWORDS):
        return _K_FRIENDLY
    return _K_COMPETITIVE


class EloRatings:
    """Fit Elo ratings on a DataFrame of international match results.

    After fitting, `predict(home_id, away_id)` returns a 1X2 probability dict.
    `ratings_dataframe()` returns a ranked Polars DataFrame of the 48 WC teams.
    """

    DEFAULT_RATING = 1500.0

    def __init__(
        self,
        home_advantage: float = 75.0,
        min_date: Optional[date] = None,
        max_date: Optional[date] = None,
    ) -> None:
        self._elo = Elo(k=_K_COMPETITIVE, home_field_advantage=home_advantage)
        self.home_advantage = home_advantage
        self.min_date = min_date
        self.max_date = max_date
        self._n_matches: dict[str, int] = {}
        self._last_date: dict[str, str] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit(self, df: pl.DataFrame) -> "EloRatings":
        """Train on a martj42-style DataFrame (sorted chronologically).

        Required columns: date, home_team, away_team, home_score, away_score.
        Optional columns: tournament, neutral, home_team_id, away_team_id.
        """
        required = {"date", "home_team", "away_team", "home_score", "away_score"}
        if missing := required - set(df.columns):
            raise ValueError(f"Results DataFrame missing columns: {missing}")

        df = df.sort("date")
        has_id_cols = {"home_team_id", "away_team_id"} <= set(df.columns)
        has_neutral  = "neutral"    in df.columns
        has_tourney  = "tournament" in df.columns

        n_used = n_null = 0

        for row in df.iter_rows(named=True):
            if row["home_score"] is None or row["away_score"] is None:
                n_null += 1
                continue

            match_date = row["date"]
            if isinstance(match_date, str):
                match_date = date.fromisoformat(match_date)

            if self.min_date and match_date < self.min_date:
                continue
            if self.max_date and match_date > self.max_date:
                continue

            # Resolve team keys
            if has_id_cols and row["home_team_id"] and row["away_team_id"]:
                home_key = row["home_team_id"]
                away_key = row["away_team_id"]
            else:
                home_key = try_resolve_team(row["home_team"]) or row["home_team"]
                away_key = try_resolve_team(row["away_team"]) or row["away_team"]

            tournament = row.get("tournament") if has_tourney else None
            is_neutral = bool(row.get("neutral")) if has_neutral else False
            result = _result_code(int(row["home_score"]), int(row["away_score"]))

            # Apply tournament-importance K-factor
            self._elo.k = _k_for_tournament(tournament)

            # Apply neutral-venue adjustment
            if is_neutral:
                old_hfa, self._elo.hfa = self._elo.hfa, 0.0
                self._elo.update_ratings(home_key, away_key, result)
                self._elo.hfa = old_hfa
            else:
                self._elo.update_ratings(home_key, away_key, result)

            date_str = str(match_date)
            for key in (home_key, away_key):
                self._n_matches[key] = self._n_matches.get(key, 0) + 1
                self._last_date[key] = date_str

            n_used += 1

        # Restore defaults
        self._elo.k = _K_COMPETITIVE
        self._fitted = True
        log.info(
            "EloRatings.fit: %d matches used, %d skipped (null scores)",
            n_used, n_null,
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

        neutral=True (default for WC 2026): no home advantage applied.
        """
        if not self._fitted:
            raise RuntimeError("Call .fit() before .predict().")

        if neutral:
            old_hfa, self._elo.hfa = self._elo.hfa, 0.0
            raw = self._elo.calculate_match_probabilities(home_team_id, away_team_id)
            self._elo.hfa = old_hfa
        else:
            raw = self._elo.calculate_match_probabilities(home_team_id, away_team_id)

        return {
            "home": float(raw["home_win"]),
            "draw": float(raw["draw"]),
            "away": float(raw["away_win"]),
        }

    def get_rating(self, team_id: str) -> float:
        return float(self._elo.get_team_rating(team_id))

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def ratings_dataframe(self) -> pl.DataFrame:
        """Ranked Polars DataFrame for all 48 canonical WC teams."""
        rows = [
            {
                "team_id":          tid,
                "display_name":     info[0],
                "confederation":    info[1],
                "elo_rating":       self.get_rating(tid),
                "n_train_matches":  self._n_matches.get(tid, 0),
                "last_match_date":  self._last_date.get(tid),
            }
            for tid, info in CANONICAL_TEAMS.items()
        ]
        return pl.DataFrame(rows).sort("elo_rating", descending=True)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _result_code(home_score: int, away_score: int) -> int:
    """penaltyblog Elo encoding: 0 = home win, 1 = draw, 2 = away win."""
    if home_score > away_score:
        return 0
    if home_score == away_score:
        return 1
    return 2
