"""Tests: Dixon-Coles goal model wrapper."""
from __future__ import annotations

import math
from datetime import date, timedelta

import polars as pl
import pytest

from oracle.ratings.dixon_coles import DixonColesRatings


# ---------------------------------------------------------------------------
# Synthetic training data (no network required)
# ---------------------------------------------------------------------------

def _make_synthetic(n: int = 200, seed: int = 42) -> pl.DataFrame:
    """Return a synthetic match DataFrame with enough variety for DC to converge."""
    import random
    rng = random.Random(seed)
    teams = [
        "france", "germany", "brazil", "argentina", "spain",
        "england", "italy", "netherlands", "portugal", "belgium",
        "japan", "senegal", "morocco", "australia", "croatia",
    ]
    base = date(2015, 1, 1)
    rows = []
    for i in range(n):
        h, a = rng.sample(teams, 2)
        rows.append({
            "date":       base + timedelta(days=i * 3),
            "home_team":  h,
            "away_team":  a,
            "home_score": rng.randint(0, 4),
            "away_score": rng.randint(0, 4),
            "tournament": rng.choice(["Friendly", "Qualifier", "FIFA World Cup"]),
            "neutral":    rng.choice([True, False]),
            "home_team_id": h,
            "away_team_id": a,
        })
    return pl.DataFrame(rows)


SYNTH = _make_synthetic()


class TestDixonColesFit:
    def test_fits_without_error(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        assert dc._fitted

    def test_n_train_recorded(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        assert dc._n_train == len(SYNTH)

    def test_raises_on_missing_columns(self) -> None:
        bad = pl.DataFrame({"date": [date(2020, 1, 1)], "home_team": ["x"]})
        with pytest.raises(ValueError, match="missing columns"):
            DixonColesRatings().fit(bad)

    def test_raises_on_empty_after_filter(self) -> None:
        # All rows have null scores
        df = pl.DataFrame({
            "date":       [date(2020, 1, 1)],
            "home_team":  ["france"],
            "away_team":  ["germany"],
            "home_score": [None],
            "away_score": [None],
        })
        with pytest.raises(ValueError, match="No rows"):
            DixonColesRatings().fit(df)

    def test_max_date_filter(self) -> None:
        dc_all  = DixonColesRatings()
        dc_trim = DixonColesRatings(max_date=date(2015, 6, 1))
        dc_all.fit(SYNTH)
        dc_trim.fit(SYNTH)
        # Trimmed model trains on fewer rows
        assert dc_trim._n_train < dc_all._n_train

    def test_null_scores_excluded(self) -> None:
        df = SYNTH.with_columns([
            pl.when(pl.arange(0, len(SYNTH)) < 10)
            .then(None)
            .otherwise(pl.col("home_score"))
            .alias("home_score"),
        ])
        dc = DixonColesRatings()
        dc.fit(df)
        assert dc._n_train == len(SYNTH) - 10

    def test_xi_stored(self) -> None:
        dc = DixonColesRatings(xi=0.003)
        dc.fit(SYNTH)
        assert dc.xi == pytest.approx(0.003)


class TestDixonColesPredict:
    def test_probs_sum_to_one(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        p = dc.predict("france", "germany")
        assert abs(sum(p.values()) - 1.0) < 1e-6

    def test_keys_are_home_draw_away(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        p = dc.predict("france", "germany")
        assert set(p.keys()) == {"home", "draw", "away"}

    def test_all_probs_positive(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        p = dc.predict("france", "germany")
        assert all(v > 0 for v in p.values())

    def test_raises_before_fit(self) -> None:
        with pytest.raises(RuntimeError, match="fit"):
            DixonColesRatings().predict("france", "germany")

    def test_neutral_changes_probs(self) -> None:
        # Build training data with a strong home-advantage signal:
        # home team always wins at home, results are neutral away
        import random
        rng = random.Random(0)
        teams = ["france", "germany", "brazil", "argentina", "spain",
                 "england", "italy", "netherlands", "portugal", "belgium"]
        base = date(2015, 1, 1)
        rows = []
        for i in range(300):
            h, a = rng.sample(teams, 2)
            # Home games: home team wins convincingly
            rows.append({
                "date": base + timedelta(days=i * 3),
                "home_team": h, "away_team": a,
                "home_score": 2, "away_score": 0,
                "home_team_id": h, "away_team_id": a,
                "neutral": False,
                "tournament": "Qualifier",
            })
        df = pl.DataFrame(rows)
        dc = DixonColesRatings()
        dc.fit(df)
        p_home    = dc.predict("france", "germany", neutral=False)
        p_neutral = dc.predict("france", "germany", neutral=True)
        # Both must sum to 1
        assert abs(sum(p_home.values())    - 1.0) < 1e-6
        assert abs(sum(p_neutral.values()) - 1.0) < 1e-6
        # With strong home-advantage training, home prob should be higher non-neutral
        assert p_home["home"] > p_neutral["home"]

    def test_probs_sum_to_one_varied_data(self) -> None:
        # Extra coverage: DC probs sum to 1 on a different team pair
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        for home, away in [("brazil", "argentina"), ("spain", "japan"), ("morocco", "senegal")]:
            p = dc.predict(home, away, neutral=True)
            assert abs(sum(p.values()) - 1.0) < 1e-6, f"Failed for {home} vs {away}"


class TestDixonColesRatingsDataframe:
    def test_returns_62_rows(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        df = dc.ratings_dataframe()
        assert len(df) == 62

    def test_columns_present(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        df = dc.ratings_dataframe()
        assert {"team_id", "attack", "defence", "confederation"} <= set(df.columns)

    def test_trained_teams_have_valid_params(self) -> None:
        dc = DixonColesRatings()
        dc.fit(SYNTH)
        df = dc.ratings_dataframe()
        # Teams in synthetic data should have finite attack params
        trained = {"france", "germany", "brazil", "argentina"}
        for tid in trained:
            row = df.filter(pl.col("team_id") == tid)
            assert len(row) == 1
            att = row["attack"][0]
            assert att is not None and not math.isnan(att)

    def test_raises_before_fit(self) -> None:
        with pytest.raises(RuntimeError, match="fit"):
            DixonColesRatings().ratings_dataframe()
