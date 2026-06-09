"""Tests: Elo rating system — fit, predict, output validity."""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from oracle.ratings.elo import EloRatings, _result_code


# ---------------------------------------------------------------------------
# Synthetic training data (no network required)
# ---------------------------------------------------------------------------

def _make_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows)


SMALL_HISTORY = _make_df([
    {"date": date(2020, 1, 1), "home_team": "argentina", "away_team": "brazil",
     "home_score": 2, "away_score": 0, "tournament": "Friendly", "neutral": False},
    {"date": date(2020, 3, 1), "home_team": "france",    "away_team": "germany",
     "home_score": 1, "away_score": 1, "tournament": "Friendly", "neutral": False},
    {"date": date(2020, 6, 1), "home_team": "brazil",    "away_team": "france",
     "home_score": 0, "away_score": 2, "tournament": "FIFA World Cup", "neutral": True},
    {"date": date(2021, 1, 1), "home_team": "spain",     "away_team": "england",
     "home_score": 0, "away_score": 1, "tournament": "Friendly", "neutral": False},
    {"date": date(2021, 6, 1), "home_team": "argentina", "away_team": "france",
     "home_score": 3, "away_score": 3, "tournament": "FIFA World Cup", "neutral": True},
])


class TestResultCode:
    # penaltyblog Elo encoding: 0=home win, 1=draw, 2=away win
    def test_home_win(self) -> None:
        assert _result_code(3, 1) == 0

    def test_draw(self) -> None:
        assert _result_code(1, 1) == 1

    def test_away_win(self) -> None:
        assert _result_code(0, 2) == 2


class TestEloFit:
    def test_fits_without_error(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        assert elo._fitted

    def test_ratings_updated_after_fit(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        # Argentina won 2 matches → should be above 1500
        assert elo.get_rating("argentina") > 1500.0

    def test_loser_rating_drops(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        # Brazil lost to Argentina early; check rating < winner
        assert elo.get_rating("argentina") > elo.get_rating("brazil")

    def test_raises_on_missing_columns(self) -> None:
        bad_df = pl.DataFrame({"date": [date(2020, 1, 1)], "home_team": ["a"]})
        with pytest.raises(ValueError, match="missing columns"):
            EloRatings().fit(bad_df)

    def test_date_filtering_min(self) -> None:
        elo_all  = EloRatings()
        elo_late = EloRatings(min_date=date(2021, 1, 1))
        elo_all.fit(SMALL_HISTORY)
        elo_late.fit(SMALL_HISTORY)
        # With fewer matches, late-only ratings stay closer to default
        assert elo_late._n_matches.get("argentina", 0) < elo_all._n_matches.get("argentina", 0)

    def test_date_filtering_max(self) -> None:
        elo = EloRatings(max_date=date(2020, 12, 31))
        elo.fit(SMALL_HISTORY)
        assert elo._n_matches.get("spain", 0) == 0  # spain only played in 2021

    def test_null_scores_skipped(self) -> None:
        df = _make_df([
            {"date": date(2020, 1, 1), "home_team": "argentina", "away_team": "brazil",
             "home_score": None, "away_score": None, "tournament": "Friendly", "neutral": False},
            {"date": date(2020, 2, 1), "home_team": "france",    "away_team": "germany",
             "home_score": 1, "away_score": 0, "tournament": "Friendly", "neutral": False},
        ])
        elo = EloRatings()
        elo.fit(df)
        # Only the france/germany match should be counted
        assert elo._n_matches.get("argentina", 0) == 0
        assert elo._n_matches.get("france", 0) == 1

    def test_n_train_matches_tracked(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        # argentina played in rows 0 and 4
        assert elo._n_matches.get("argentina", 0) == 2

    def test_wc_k_higher_than_friendly_k(self) -> None:
        # WC wins should move ratings more than friendly wins
        friendly_df = _make_df([
            {"date": date(2020, 1, 1), "home_team": "alpha", "away_team": "beta",
             "home_score": 3, "away_score": 0, "tournament": "Friendly", "neutral": False},
        ])
        wc_df = _make_df([
            {"date": date(2020, 1, 1), "home_team": "alpha", "away_team": "beta",
             "home_score": 3, "away_score": 0, "tournament": "FIFA World Cup", "neutral": False},
        ])
        elo_f = EloRatings()
        elo_w = EloRatings()
        elo_f.fit(friendly_df)
        elo_w.fit(wc_df)
        assert elo_w.get_rating("alpha") > elo_f.get_rating("alpha")


class TestEloPredict:
    def test_probs_sum_to_one(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        probs = elo.predict("argentina", "france")
        assert abs(sum(probs.values()) - 1.0) < 1e-9

    def test_probs_in_unit_interval(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        probs = elo.predict("argentina", "france")
        for p in probs.values():
            assert 0.0 < p < 1.0

    def test_keys_are_home_draw_away(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        probs = elo.predict("argentina", "france")
        assert set(probs.keys()) == {"home", "draw", "away"}

    def test_raises_before_fit(self) -> None:
        with pytest.raises(RuntimeError, match="fit"):
            EloRatings().predict("argentina", "france")

    def test_neutral_vs_nonneutral(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        home_probs     = elo.predict("argentina", "france", neutral=False)
        neutral_probs  = elo.predict("argentina", "france", neutral=True)
        # With home advantage, home win prob should be higher than neutral
        assert home_probs["home"] > neutral_probs["home"]
        # Each should still sum to 1
        assert abs(sum(home_probs.values())    - 1.0) < 1e-9
        assert abs(sum(neutral_probs.values()) - 1.0) < 1e-9

    def test_unknown_team_uses_default_1500(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        # "new_zealand" never appeared in SMALL_HISTORY → default 1500
        assert elo.get_rating("new_zealand") == pytest.approx(1500.0)


class TestRatingsDataframe:
    def test_returns_48_rows(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        df = elo.ratings_dataframe()
        assert len(df) == 48

    def test_columns_present(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        df = elo.ratings_dataframe()
        assert {"team_id", "elo_rating", "n_train_matches", "confederation"} <= set(df.columns)

    def test_sorted_descending(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        df = elo.ratings_dataframe()
        ratings = df["elo_rating"].to_list()
        assert ratings == sorted(ratings, reverse=True)

    def test_no_negative_match_counts(self) -> None:
        elo = EloRatings()
        elo.fit(SMALL_HISTORY)
        df = elo.ratings_dataframe()
        assert df["n_train_matches"].min() >= 0
