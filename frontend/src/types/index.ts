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
