"""
Prediction ledger — Week 18.

Stores one row per prediction snapshot per match.  Outcome columns are
initially null and filled by the grading pipeline once a result is known.

Append-only semantics:
  - New entries are appended; no existing row is ever deleted.
  - Prediction columns (probs, recommendation) never change after capture.
  - Outcome/metric columns are filled in by the grading pipeline.
  - Duplicate prediction_id entries are silently skipped on append.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

_DEFAULT_LEDGER = Path("data/artifacts/prediction_ledger.parquet")

# ── Parquet schema ─────────────────────────────────────────────────────────────

LEDGER_SCHEMA: dict[str, pl.PolarsDataType] = {
    # Identity
    "prediction_id":        pl.Utf8,
    "generated_at":         pl.Utf8,
    "match_id":             pl.Utf8,
    "kickoff_at":           pl.Utf8,
    "home_team":            pl.Utf8,
    "away_team":            pl.Utf8,
    "group":                pl.Utf8,
    # Model probabilities
    "home_win_prob":        pl.Float64,
    "draw_prob":            pl.Float64,
    "away_win_prob":        pl.Float64,
    # Market probabilities
    "market_home_prob":     pl.Float64,
    "market_draw_prob":     pl.Float64,
    "market_away_prob":     pl.Float64,
    # Blend probabilities
    "blended_home_prob":    pl.Float64,
    "blended_draw_prob":    pl.Float64,
    "blended_away_prob":    pl.Float64,
    # Edge values (model – market)
    "edge_home":            pl.Float64,
    "edge_draw":            pl.Float64,
    "edge_away":            pl.Float64,
    # Recommendation snapshot
    "recommendation_type":       pl.Utf8,
    "recommendation_selection":  pl.Utf8,
    "recommendation_confidence": pl.Utf8,
    # Source metadata
    "model_version":        pl.Utf8,
    # ── Outcome fields (null until graded) ────────────────────────────────────
    "result_known":         pl.Boolean,
    "outcome":              pl.Utf8,     # "home_win" | "draw" | "away_win"
    "home_goals":           pl.Int32,
    "away_goals":           pl.Int32,
    "graded_at":            pl.Utf8,
    # ── Scoring metrics (null until graded) ───────────────────────────────────
    "brier":                pl.Float64,
    "rps":                  pl.Float64,
    "log_loss":             pl.Float64,
    "brier_market":         pl.Float64,
    "rps_market":           pl.Float64,
    "log_loss_market":      pl.Float64,
    "brier_blend":          pl.Float64,
    "rps_blend":            pl.Float64,
    "log_loss_blend":       pl.Float64,
    # CLV (model prob – market prob at capture; null if no market data)
    "clv_home":             pl.Float64,
    "clv_draw":             pl.Float64,
    "clv_away":             pl.Float64,
    # Derived grading
    "correct_side":         pl.Boolean,
    "probability_assigned": pl.Float64,  # model prob for actual outcome
    "surprise_score":       pl.Float64,  # 1 – probability_assigned
}


# ── Dataclass ──────────────────────────────────────────────────────────────────

@dataclass
class PredictionLedgerEntry:
    """One prediction snapshot for one match."""

    prediction_id:             str
    generated_at:              str
    match_id:                  str
    kickoff_at:                str | None
    home_team:                 str
    away_team:                 str
    group:                     str
    home_win_prob:             float | None
    draw_prob:                 float | None
    away_win_prob:             float | None
    market_home_prob:          float | None
    market_draw_prob:          float | None
    market_away_prob:          float | None
    blended_home_prob:         float | None
    blended_draw_prob:         float | None
    blended_away_prob:         float | None
    edge_home:                 float | None
    edge_draw:                 float | None
    edge_away:                 float | None
    recommendation_type:       str | None
    recommendation_selection:  str | None
    recommendation_confidence: str | None
    model_version:             str
    result_known:              bool   = False
    outcome:                   str | None = None
    home_goals:                int | None = None
    away_goals:                int | None = None
    graded_at:                 str | None = None
    brier:                     float | None = None
    rps:                       float | None = None
    log_loss:                  float | None = None
    brier_market:              float | None = None
    rps_market:                float | None = None
    log_loss_market:           float | None = None
    brier_blend:               float | None = None
    rps_blend:                 float | None = None
    log_loss_blend:            float | None = None
    clv_home:                  float | None = None
    clv_draw:                  float | None = None
    clv_away:                  float | None = None
    correct_side:              bool | None = None
    probability_assigned:      float | None = None
    surprise_score:            float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id":             self.prediction_id,
            "generated_at":              self.generated_at,
            "match_id":                  self.match_id,
            "kickoff_at":                self.kickoff_at,
            "home_team":                 self.home_team,
            "away_team":                 self.away_team,
            "group":                     self.group,
            "home_win_prob":             self.home_win_prob,
            "draw_prob":                 self.draw_prob,
            "away_win_prob":             self.away_win_prob,
            "market_home_prob":          self.market_home_prob,
            "market_draw_prob":          self.market_draw_prob,
            "market_away_prob":          self.market_away_prob,
            "blended_home_prob":         self.blended_home_prob,
            "blended_draw_prob":         self.blended_draw_prob,
            "blended_away_prob":         self.blended_away_prob,
            "edge_home":                 self.edge_home,
            "edge_draw":                 self.edge_draw,
            "edge_away":                 self.edge_away,
            "recommendation_type":       self.recommendation_type,
            "recommendation_selection":  self.recommendation_selection,
            "recommendation_confidence": self.recommendation_confidence,
            "model_version":             self.model_version,
            "result_known":              self.result_known,
            "outcome":                   self.outcome,
            "home_goals":                self.home_goals,
            "away_goals":                self.away_goals,
            "graded_at":                 self.graded_at,
            "brier":                     self.brier,
            "rps":                       self.rps,
            "log_loss":                  self.log_loss,
            "brier_market":              self.brier_market,
            "rps_market":                self.rps_market,
            "log_loss_market":           self.log_loss_market,
            "brier_blend":               self.brier_blend,
            "rps_blend":                 self.rps_blend,
            "log_loss_blend":            self.log_loss_blend,
            "clv_home":                  self.clv_home,
            "clv_draw":                  self.clv_draw,
            "clv_away":                  self.clv_away,
            "correct_side":              self.correct_side,
            "probability_assigned":      self.probability_assigned,
            "surprise_score":            self.surprise_score,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_prediction_id(match_id: str, date_bucket: str) -> str:
    """Deterministic prediction ID: sha256(match_id + date_bucket)[:16]."""
    raw = f"{match_id}__{date_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _entries_to_df(entries: list[PredictionLedgerEntry]) -> pl.DataFrame:
    if not entries:
        return pl.DataFrame(schema=LEDGER_SCHEMA)
    rows = [e.to_dict() for e in entries]
    return pl.DataFrame(rows, schema=LEDGER_SCHEMA)


# ── I/O ────────────────────────────────────────────────────────────────────────

def load_ledger(
    ledger_path: Path = _DEFAULT_LEDGER,
) -> pl.DataFrame:
    """Load existing ledger or return an empty DataFrame with the correct schema."""
    if not ledger_path.exists():
        return pl.DataFrame(schema=LEDGER_SCHEMA)
    try:
        return pl.read_parquet(ledger_path).cast(LEDGER_SCHEMA, strict=False)
    except Exception:
        return pl.DataFrame(schema=LEDGER_SCHEMA)


def append_to_ledger(
    new_entries: list[PredictionLedgerEntry],
    ledger_path: Path = _DEFAULT_LEDGER,
) -> tuple[int, int]:
    """Append new entries to the ledger, skipping duplicates.

    Returns
    -------
    (n_appended, n_skipped)
    """
    if not new_entries:
        return 0, 0

    existing = load_ledger(ledger_path)
    existing_ids: set[str] = set()
    if len(existing) > 0:
        existing_ids = set(existing["prediction_id"].to_list())

    to_add = [e for e in new_entries if e.prediction_id not in existing_ids]
    n_skipped = len(new_entries) - len(to_add)

    if not to_add:
        return 0, n_skipped

    new_df = _entries_to_df(to_add)
    combined = pl.concat([existing, new_df], how="diagonal")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    combined.write_parquet(ledger_path)

    return len(to_add), n_skipped


def save_ledger(df: pl.DataFrame, ledger_path: Path = _DEFAULT_LEDGER) -> None:
    """Overwrite the ledger with an updated DataFrame (used by grading step)."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(ledger_path)
