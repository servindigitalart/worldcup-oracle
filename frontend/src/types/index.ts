export interface TeamProb {
  team: string;
  qualify: number;
  r16: number;
  qf: number;
  sf: number;
  final: number;
  champion: number;
}

export interface BlendedPrediction {
  match_id: string;
  home_team: string;
  away_team: string;
  group: string;
  blend_home: number;
  blend_draw: number;
  blend_away: number;
  market_weight: number;
  model_weight: number;
  has_market_data: boolean;
  label: string;
}

export interface MarketComparison {
  match_id: string;
  home_team: string;
  away_team: string;
  group: string;
  model_home: number | null;
  model_draw: number | null;
  model_away: number | null;
  market_home: number | null;
  market_draw: number | null;
  market_away: number | null;
  gap_home: number | null;
  gap_draw: number | null;
  gap_away: number | null;
  max_gap_selection: string | null;
  max_gap_value: number | null;
  has_market_data: boolean;
  label: string;
}

export interface ClosingCandidate {
  match_id: string;
  status: string;
  n_snapshots: number;
  opening_captured_at: string | null;
  latest_captured_at: string | null;
  hours_of_coverage: number;
  has_closing_line: boolean;
}

export interface SimSummary {
  generated_date: string;
  n_sims: number;
  seed: number;
  locked_model: string;
  goals_model: string;
  goals_model_version: string;
  top_champion_probs: Array<{ team: string; champion: number }>;
  disclaimers: Record<string, string>;
}

export interface BacktestSummary {
  generated_at: string;
  total_matches: number;
  uniform_rps: number;
  small_sample_note: string;
  per_year: Record<string, {
    n_matches: number;
    train_cutoff: string;
    n_train: number;
    rps: Record<string, number>;
    beats_uniform: Record<string, boolean>;
  }>;
  aggregate: Record<string, { mean_rps: number; beats_uniform: boolean }>;
}

export interface HoldoutSummary {
  holdout_name: string;
  train_cutoff: string;
  n_train_matches: number;
  n_holdout_total: number;
  n_holdout_scored: number;
  uniform_rps: number;
  model_version: string;
  mean_rps: number;
  beats_uniform: boolean;
  generated_at: string;
}

export interface ModelComparison {
  generated_at: string;
  total_matches: number;
  uniform_rps: number;
  small_sample_note: string;
  models: Array<{
    model: string;
    mean_rps: number;
    beats_uniform: boolean;
    rank: number;
  }>;
}

export interface MarketBlend {
  generated_date: string;
  market_weight: number;
  model_weight: number;
  n_matchups_total: number;
  n_with_market: number;
  n_model_only: number;
  disclaimers: Record<string, string>;
}

export interface FixtureScheduleEntry {
  kickoff_at: string | null;
  venue: string | null;
  city: string | null;
  host_country: string | null;
  group: string;
}

export interface GroupStanding {
  group: string;
  team: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  points: number;
  rank: number;
  status_label: 'qualified_top2' | 'eliminated' | 'alive' | 'unknown';
}

export interface QualificationProb {
  team: string;
  qualify: number;
  qualify_top2: number;
  qualify_third: number;
  r16: number;
  qf: number;
  sf: number;
  final: number;
  champion: number;
}

export interface TournamentStateSummary {
  generated_at: string;
  generated_date: string;
  n_sims: number;
  seed: number;
  locked_model: string;
  goals_model: string;
  goals_model_version: string;
  n_known_results: number;
  n_finished: number;
  fixture_source: {
    source: string | null;
    is_official: boolean;
    is_placeholder: boolean;
    n_fixtures: number;
  };
  disclaimers: Record<string, string>;
  top_champion_probs: Array<{ team: string; champion: number }>;
}

export interface Recommendation {
  match_id: string;
  home_team: string;
  away_team: string;
  group: string;
  kickoff_at: string | null;
  recommendation_type: 'no_recommendation' | 'model_gap_detected' | 'market_aligned' | 'avoid' | 'watch';
  market: string;
  selection: string | null;
  model_probability: number | null;
  market_probability: number | null;
  blended_probability: number | null;
  model_market_gap: number | null;
  confidence: 'low' | 'medium' | 'high' | 'unknown';
  risk_label: 'low' | 'medium' | 'high' | 'unknown';
  data_quality: 'complete' | 'partial' | 'missing_market' | 'placeholder' | 'stale' | 'unknown';
  status: 'pre_match' | 'live' | 'finished' | 'unavailable';
  reason: string;
  warnings: string[];
  is_actionable: boolean;
  edge_confidence: 'low' | 'medium' | 'high' | 'very_high' | 'none';
  generated_at: string;
}

export interface MethodologyInput {
  model_version: string;
  goals_model: string;
  blend_version: string;
  inputs_used: string[];
  inputs_not_used: string[];
  limitations: string[];
  elo: {
    name: string;
    version: string;
    what_it_is: string;
    what_it_does: string;
    strengths: string[];
    weaknesses: string[];
  };
  dixon_coles: {
    name: string;
    version: string;
    what_it_is: string;
    what_it_does: string;
    strengths: string[];
    weaknesses: string[];
  };
  market_blend: {
    name: string;
    version: string;
    market_weight: number;
    model_weight: number;
    why_it_exists: string;
    why_not_follow_market_blindly: string;
    why_calibration_matters: string;
    caveat: string;
  };
  generated_at: string;
}

export interface CalibrationBucket {
  bucket: string;
  predicted: number;
  actual: number;
  samples: number;
  gap: number;
}

export interface CalibrationHistory {
  source: string;
  years: number[];
  total_matches: number;
  note: string;
  primary_model: string;
  buckets: CalibrationBucket[];
  models: Record<string, CalibrationBucket[]>;
  generated_at: string;
}

export interface ModelReliability {
  primary_model: string;
  uniform_rps: number;
  rps: number | null;
  log_loss: number | null;
  brier: number | null;
  ece: number | null;
  sharpness: number | null;
  calibration_badge: 'excellent' | 'good' | 'fair' | 'poor' | 'unknown';
  note: string;
  models: Record<string, {
    model_version: string;
    n_matches: number;
    rps: number;
    log_loss: number;
    brier: number;
    ece: number;
    sharpness: number;
    calibration_badge: string;
    beats_uniform: boolean;
    formulas: Record<string, string>;
  }>;
  generated_at: string;
}

export interface MarketAgreementMatch {
  match_id: string;
  home_team: string;
  away_team: string;
  group: string;
  model_home: number | null;
  model_draw: number | null;
  model_away: number | null;
  market_home: number | null;
  market_draw: number | null;
  market_away: number | null;
  max_gap: number | null;
  has_market_data: boolean;
  agreement: 'HIGH' | 'MEDIUM' | 'LOW' | 'NO_DATA';
}

export interface MarketAgreement {
  matches: MarketAgreementMatch[];
  summary: {
    total: number;
    high: number;
    medium: number;
    low: number;
    no_data: number;
    thresholds: { high_max_gap: number; medium_max_gap: number; description: string };
  };
  generated_at: string;
}

export interface DataSources {
  historical_matches: number;
  world_cup_matches: number;
  world_cups: number;
  world_cup_years: number[];
  qualifier_matches: number;
  friendly_matches: number;
  continental_matches: number;
  n_distinct_tournaments: number;
  qualifiers: boolean;
  friendlies: boolean;
  continental_tournaments: boolean;
  date_range: { earliest: string | null; latest: string | null };
  source: string;
  source_url: string;
  license: string;
  note: string;
  generated_at: string;
}

export interface RecommendationsSummary {
  generated_at: string;
  total_matches: number;
  n_no_recommendation: number;
  n_watch: number;
  n_market_aligned: number;
  n_model_gap_detected: number;
  n_avoid: number;
  n_actionable: number;
  n_missing_market: number;
  has_real_market_data: boolean;
  language_policy: {
    forbidden_terms: string[];
    safe_terms: string[];
  };
  disclaimer: string;
}

export interface MatchResult {
  match_id: string;
  home_team: string;
  away_team: string;
  group: string;
  home_goals: number | null;
  away_goals: number | null;
  status: string;
}

export interface LiveResult {
  match_id: string;
  home_team: string;
  away_team: string;
  group: string;
  home_goals: number | null;
  away_goals: number | null;
  status: 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled' | 'unknown';
  source: 'manual' | 'local_json' | string;
  source_event_id: string | null;
  kickoff_at: string | null;
  finished_at: string | null;
  captured_at: string;
}

export interface ResultsFeedReport {
  generated_at: string;
  n_manual: number;
  n_external: number;
  n_merged: number;
  n_duplicates: number;
  n_finished: number;
  n_live: number;
  overrides: Array<{
    match_id: string;
    manual_status: string;
    external_status: string;
    manual_goals: string;
    external_goals: string;
  }>;
  unresolved: Array<{
    source: string;
    home_team: string;
    away_team: string;
    match_id: string | null;
    reason: string;
  }>;
  warnings: string[];
  manual_seed_path: string;
  provider_json_path: string;
  provider_json_present: boolean;
}

export interface RefreshStep {
  name: string;
  status: 'success' | 'skipped' | 'failed' | 'warning';
  started_at: string;
  finished_at: string;
  duration_seconds: number;
  message: string;
  artifacts: string[];
}

export interface RefreshReport {
  generated_at: string;
  success: boolean;
  strict: boolean;
  build_frontend: boolean;
  include_market_capture: boolean;
  steps: RefreshStep[];
  artifacts_written: string[];
  warnings: string[];
  errors: string[];
  summary: string;
  n_steps_total: number;
  n_steps_success: number;
  n_steps_failed: number;
  n_steps_skipped: number;
  n_steps_warning: number;
  total_duration_seconds: number;
}

// ── Week 18: Prediction grading ───────────────────────────────────────────────

export interface PredictionLedgerEntry {
  prediction_id: string;
  generated_at: string;
  match_id: string;
  kickoff_at: string | null;
  home_team: string;
  away_team: string;
  group: string;
  home_win_prob: number | null;
  draw_prob: number | null;
  away_win_prob: number | null;
  market_home_prob: number | null;
  market_draw_prob: number | null;
  market_away_prob: number | null;
  blended_home_prob: number | null;
  blended_draw_prob: number | null;
  blended_away_prob: number | null;
  edge_home: number | null;
  edge_draw: number | null;
  edge_away: number | null;
  recommendation_type: string | null;
  recommendation_selection: string | null;
  recommendation_confidence: string | null;
  model_version: string;
  result_known: boolean;
  outcome: 'home_win' | 'draw' | 'away_win' | null;
  home_goals: number | null;
  away_goals: number | null;
  graded_at: string | null;
  brier: number | null;
  rps: number | null;
  log_loss: number | null;
  brier_market: number | null;
  rps_market: number | null;
  log_loss_market: number | null;
  brier_blend: number | null;
  rps_blend: number | null;
  log_loss_blend: number | null;
  clv_home: number | null;
  clv_draw: number | null;
  clv_away: number | null;
  correct_side: boolean | null;
  probability_assigned: number | null;
  surprise_score: number | null;
}

export interface GradingSummary {
  generated_at: string;
  total_predictions: number;
  graded_predictions: number;
  pending_predictions: number;
  newly_graded: number;
  n_correct_side: number;
  accuracy_rate: number | null;
  mean_brier: number | null;
  mean_rps: number | null;
  mean_log_loss: number | null;
  disclaimer: string;
}

export interface ClvSummary {
  generated_at: string;
  n: number;
  average_clv: number | null;
  median_clv: number | null;
  positive_clv_rate: number | null;
  note: string;
}

export interface RecommendationPerformance {
  generated_at: string;
  n_total: number;
  n_actionable: number;
  n_push: number;
  n_won: number;
  n_lost: number;
  hit_rate: number | null;
  by_edge_bucket: Record<string, { n: number; won: number; lost: number; hit_rate: number | null }>;
  by_confidence: Record<string, { n: number; won: number; lost: number; hit_rate: number | null }>;
  note: string;
}

export interface ModelVsMarket {
  generated_at: string;
  n_graded: number;
  winner: 'model' | 'market' | 'blend' | null;
  brier: { model: number | null; market: number | null; blend: number | null; n_model: number; n_market: number; n_blend: number };
  rps:   { model: number | null; market: number | null; blend: number | null; n_model: number; n_market: number; n_blend: number };
  log_loss: { model: number | null; market: number | null; blend: number | null };
  disclaimer: string;
}

export interface PerformanceTrendsWindow {
  window: number | null;
  n_matches: number;
  mean_brier: number | null;
  mean_rps: number | null;
  mean_log_loss: number | null;
  mean_brier_market: number | null;
  mean_rps_market: number | null;
  mean_brier_blend: number | null;
  mean_rps_blend: number | null;
  positive_clv_rate: number | null;
  rec_hit_rate: number | null;
}

export interface PerformanceTrends {
  generated_at: string;
  n_graded_total: number;
  windows: PerformanceTrendsWindow[];
  disclaimer: string;
}

// ── Week 20: Market lifecycle & True CLV ──────────────────────────────────────

export interface ClosingLineSummary {
  generated_at: string;
  n_matches: number;
  n_with_opening: number;
  n_with_closing: number;
  n_with_h24: number;
  n_closing_locked: number;
  by_closing_status: Record<string, number>;
  validation: {
    n_valid: number;
    n_with_warnings: number;
    warnings: string[];
  };
  note: string;
}

export interface MarketMovementEntry {
  match_id: string;
  home_team: string;
  away_team: string;
  kickoff_at: string | null;
  closing_status: string;
  opening_captured_at: string;
  closing_captured_at: string;
  opening_home_prob: number;
  opening_draw_prob: number;
  opening_away_prob: number;
  closing_home_prob: number;
  closing_draw_prob: number;
  closing_away_prob: number;
  home_move: number;
  draw_move: number;
  away_move: number;
  max_abs_move: number;
  biggest_mover: 'home' | 'draw' | 'away';
  biggest_mover_direction: 'up' | 'down';
}

export interface MarketMovement {
  generated_at: string;
  n_matches_with_movement: number;
  avg_max_abs_movement: number | null;
  matches: MarketMovementEntry[];
  disclaimer: string;
}

export interface TrueClvSummary {
  generated_at: string;
  n: number;
  average_true_clv: number | null;
  median_true_clv: number | null;
  positive_true_clv_rate: number | null;
  note: string;
}

export interface RecommendationClvEntry {
  match_id: string;
  home_team: string | null;
  away_team: string | null;
  recommendation_selection: string;
  recommendation_confidence: string | null;
  rec_result: string | null;
  model_prob: number | null;
  closing_market_prob: number | null;
  closing_status: string;
  true_clv: number | null;
}

export interface RecommendationClv {
  generated_at: string;
  n_recommendations: number;
  n_with_closing_line: number;
  average_true_clv: number | null;
  median_true_clv: number | null;
  positive_true_clv_rate: number | null;
  recommendations: RecommendationClvEntry[];
  note: string;
  disclaimer: string;
}

// ── Week 21: Knockout bracket engine ─────────────────────────────────────────

export interface BestThird {
  rank: number;
  team: string;
  group: string;
  points: number;
  gd: number;
  gf: number;
  qualifies: boolean;
}

export interface BestThirdsArtifact {
  generated_at: string;
  n_groups: number;
  n_thirds_ranked: number;
  n_qualifying: number;
  all_thirds: BestThird[];
  note: string;
}

export interface BracketTeam {
  team: string;
  slot: string;
  group: string;
  finish: '1st' | '2nd' | '3rd';
}

export interface BracketMatch {
  match_id: string;
  round_name: string;
  match_index: number;
  slot_a: string;
  slot_b: string;
  team_a: BracketTeam | null;
  team_b: BracketTeam | null;
  winner: string | null;
  p_a_wins: number | null;
}

export interface BracketRound {
  round_name: string;
  n_matches: number;
  matches: BracketMatch[];
}

export interface BracketStructure {
  bracket_note: string;
  generated_at: string;
  rounds: BracketRound[];
}

export interface PathDifficultyEntry {
  team: string;
  slot: string;
  group: string;
  r32_opponent: string | null;
  expected_r16_opponent: string | null;
  expected_qf_opponent: string | null;
  expected_sf_opponent: string | null;
  avg_opponent_elo: number | null;
  max_opponent_elo: number | null;
  cumulative_elo: number | null;
  difficulty_score: number | null;
}

export interface BracketPaths {
  generated_at: string;
  n_teams: number;
  disclaimer: string;
  paths: PathDifficultyEntry[];
}

export interface KnockoutProjectionMatch {
  match_id: string;
  team_a: string | null;
  team_b: string | null;
  slot_a: string;
  slot_b: string;
  p_a_wins: number | null;
  p_b_wins: number | null;
  projected_winner: string | null;
}

export interface KnockoutProjection {
  generated_at: string;
  n_r32_matches: number;
  r32_matches: KnockoutProjectionMatch[];
  bracket_note: string;
  disclaimer: string;
}

export interface CaptureStatus {
  generated_at: string;
  has_real_api_key: boolean;
  n_new_rows: number;
  n_total_snapshots: number;
  n_matches: number;
  by_status: {
    no_market_data: number;
    opening_only: number;
    latest_available: number;
    closing_candidate: number;
    closing_locked: number;
  };
  n_closing_locked: number;
  note: string;
}

// ── Week 22: Betting intelligence ─────────────────────────────────────────────

export interface BetMarketProbability {
  match_id: string;
  market_type: string;
  selection: string;
  probability: number;
  fair_decimal_odds: number | null;
  model_source: string;
  confidence: 'low' | 'medium' | 'high' | 'unknown';
  risk_label: 'low' | 'medium' | 'high';
  data_quality: 'complete' | 'model_only';
  signal_level: 'no_signal' | 'watch' | 'moderate_signal' | 'strong_signal' | 'model_probability_only';
  market_probability: number | null;
  market_gap: number | null;
  reason: string;
  warnings: string[];
  generated_at: string;
}

export interface MatchBettingCard {
  match_id: string;
  group: string;
  kickoff_at: string | null;
  venue: string | null;
  city: string | null;
  home_team: string;
  away_team: string;
  n_markets: number;
  n_signals: number;
  markets: BetMarketProbability[];
  top_signals: BetMarketProbability[];
  no_signal_reason: string;
  generated_at: string;
}

export interface BettingSummary {
  generated_at: string;
  n_matches: number;
  n_with_dc_grid: number;
  n_signals: number;
  n_strong_signal: number;
  n_moderate_signal: number;
  n_watch: number;
  n_no_signal: number;
  n_model_only: number;
  disclaimer: string;
  language_policy: { forbidden_terms: string[] };
}
