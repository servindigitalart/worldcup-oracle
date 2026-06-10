"""
Methodology declarations — what data goes in, what stays out, what the limits are.

These are authoritative constants, not runtime-configurable.  Any change here
intentionally signals a methodology version bump.
"""
from __future__ import annotations

INPUTS_USED: list[str] = [
    "historical_results",          # martj42 dataset, 1872–present
    "elo_rating",                  # full-history Elo (elo-baseline-v0.2)
    "elo_recent_rating",           # post-2010 Elo variant
    "dixon_coles_attack",          # per-team attack parameter (dixon-coles-v0.3)
    "dixon_coles_defense",         # per-team defense parameter
    "time_decay_weights",          # xi=0.0018 exponential decay on training data
    "market_odds",                 # de-vigged closing-line 1X2 probabilities
]

INPUTS_NOT_USED: list[str] = [
    "injuries",
    "lineups",
    "weather",
    "xg_expected_goals",
    "player_ratings",
    "social_media_sentiment",
    "expert_opinions",
    "squad_market_value",
    "referee_assignments",
    "travel_distance",
    "altitude",
    "head_to_head_h2h_records",    # implicitly captured by Elo via match history
    "home_advantage_per_venue",    # neutral-venue flag used, not per-city adjustment
    "fatigue_schedule_density",
    "psychological_pressure",
]

LIMITATIONS: list[str] = [
    "Based on historical results only — no squad-level or in-tournament context.",
    "Thin-data teams (< 20 historical appearances) receive noisy parameter estimates.",
    "Neutral-venue approximation used; no per-city or per-stadium home-advantage model.",
    "Market odds are de-vigged but closing-line capture is incomplete pre-tournament.",
    "All probability estimates carry wide uncertainty at 36–144 match sample sizes.",
    "Model has not yet been validated against WC 2026 outcomes.",
    "Market is treated as the primary prior; blend does not correct for systematic market bias.",
    "Dixon-Coles is re-fit on a fixed training set — not updated as the tournament progresses.",
    "Group-stage results only used for backtesting; knockout-round calibration is untested.",
]
