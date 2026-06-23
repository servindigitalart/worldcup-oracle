# BETTING_THESIS_ENGINE.md

**World Cup Oracle v2 — Betting Intelligence Engine**
**Date:** 2026-06-20
**Status:** Architecture design document — no implementation code, no pipelines, no frontend

---

## The Problem This Solves

The system already produces probabilities. It already identifies tactical advantages. It already predicts game scripts and activates causal chains. What it cannot yet do is answer the question a serious bettor asks before every match:

*"Out of everything available for this match, what is the single best opportunity and why?"*

That question requires more than probability estimation. It requires a structured comparison between what the model believes and what the market prices. It requires an assessment of how confident the model is in its own beliefs. It requires an understanding of which opportunities have strong causal support versus thin statistical correlation. And it requires a disciplined prioritization that surfaces the one or two opportunities worth attention rather than generating noise across every available market.

The Betting Thesis Engine is the layer that does this work.

---

## 1. Betting Thesis Architecture

### 1.1 Layer Diagram

```
╔══════════════════════════════════════════════════════════════════╗
║                       DATA LAYER                                 ║
║  Odds API · API-Football · martj42 · Open-Meteo · StatsBomb     ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║                    FEATURE STORE                                 ║
║  105 features · team_feature_snapshots · market_feature_snapshots║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║                  KNOWLEDGE ENGINE                                ║
║  Team identities · Manager profiles · Causality chains          ║
║  Player influence · Archetype assignments                        ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║ knowledge-enriched context
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║               GAME SCRIPT ENGINE                                 ║
║  Script distribution · Script-to-market impact · Active chains  ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║ game script priors + market impacts
                           ▼
╔═══════════════════════════════════════════════════════════════════╗
║                 BETTING THESIS ENGINE                             ║
║                                                                   ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │ Thesis Generator      → constructs per-market thesis objects │  ║
║  │ Contrarian Engine     → scores model vs market disagreement  │  ║
║  │ Causal Support Scorer → weights thesis by chain confidence   │  ║
║  │ Uncertainty Quantifier→ CI + variance + data quality flags   │  ║
║  │ Thesis Templates      → fills analyst narrative              │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════╦════════════════════════════════════════╝
                           ║ raw thesis objects (1 per market)
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║              MARKET RANKING ENGINE                               ║
║                                                                  ║
║  ┌────────────────────────────────────────────────────────────┐  ║
║  │ Opportunity Score (0–100)                                   │  ║
║  │ Portfolio Diversification Filter                            │  ║
║  │ Uncertainty Penalty Application                             │  ║
║  │ Top-N Selection                                             │  ║
║  └────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║ ranked thesis list (typically top 3)
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║                     FRONTEND                                     ║
║  /match/[match_id]  ·  Betting Intelligence cards               ║
║  Analyst narratives  ·  Confidence indicators  ·  Edge display   ║
╚══════════════════════════════════════════════════════════════════╝
```

### 1.2 Layer Responsibilities

**Feature Store** — observes. Produces 105 numerical features with quality metadata and stage flags. Does not interpret.

**Knowledge Engine** — interprets. Encodes football understanding — team identity, tactical archetypes, manager behavior, player influence, causal chains. Does not rank opportunities.

**Game Script Engine** — predicts scenarios. Assigns probability distribution over 12 game scripts. Translates scripts to per-market impact factors. Does not evaluate whether those impacts represent opportunities.

**Betting Thesis Engine** — evaluates. The core layer. Takes all upstream context and produces a structured thesis for every available market: what the model believes, how confident it is, what supports the belief, what contradicts it, what the market implies, and how large the disagreement is. Does not yet rank or select.

**Market Ranking Engine** — selects and prioritizes. Takes all thesis objects, scores each by Opportunity Score (0–100), applies diversification constraints, applies uncertainty penalties, and surfaces the top opportunities. Does not produce narratives.

**Frontend** — displays. Receives ranked thesis objects and renders them as analyst-quality intelligence cards. Does not perform any analytical reasoning.

### 1.3 What the Betting Thesis Engine Is Not

It is not a tipping service. It does not tell users to bet on anything. Its language is calibrated — "signal detected," "model edge," "market disagreement," "watchlist" — never "bet this," "guaranteed," "lock," "profit."

It is not a filter for the statistically squeamish. Its job is to surface the highest-quality disagreement between the model and the market, and to be honest when no meaningful disagreement exists.

It is not a replacement for market understanding. It is a structured, honest representation of what the Oracle's intelligence layer believes, clearly labeled with the confidence and evidence that supports that belief.

---

## 2. Betting Thesis Schema

### 2.1 Complete Schema

```json
{
  "thesis_id": "string — UUID",
  "match_id": "string",
  "generated_at": "ISO datetime",
  "model_version": "string",
  "data_stage": "stage_1 | stage_2 | stage_3",

  "market": {
    "market_type": "1x2 | double_chance | draw_no_bet | btts | over_under | correct_score | corners_ou | cards_ou | team_shots | shots_on_target | player_card | anytime_scorer | tournament_winner",
    "selection": "string — e.g., 'home_win', 'btts_yes', 'over_2.5', 'corners_over_9.5'",
    "line": "number | null — e.g., 2.5 for over/under, 9.5 for corners",
    "market_price": "number — decimal odds from market (e.g., 2.40)",
    "market_implied_probability": "number — de-vigged implied probability (0.0–1.0)",
    "market_source": "string — e.g., 'opening', 'current', 'closing_estimate'",
    "market_quality": "sufficient | thin | unavailable"
  },

  "model": {
    "model_probability": "number — 0.0–1.0",
    "probability_ci_90_low": "number",
    "probability_ci_90_high": "number",
    "model_fair_odds": "number — 1 / model_probability",
    "probability_source": "statistical_only | knowledge_adjusted | full_stack"
  },

  "edge": {
    "raw_edge": "number — model_probability - market_implied_probability",
    "edge_pct": "number — raw_edge × 100",
    "kelly_fraction": "number — full Kelly = (edge × market_price - 1) / (market_price - 1); display only, not a stake recommendation",
    "expected_clv_signal": "positive | negative | neutral | unknown"
  },

  "contrarian_score": {
    "classification": "aligned | slight_edge | moderate_edge | strong_edge | extreme_edge",
    "agreement_dimensions": {
      "model_vs_market": "agrees | slight_disagreement | significant_disagreement | strong_disagreement",
      "knowledge_vs_market": "agrees | slight_disagreement | significant_disagreement | strong_disagreement",
      "game_script_vs_market": "agrees | slight_disagreement | significant_disagreement | strong_disagreement",
      "form_trend_vs_market": "agrees | slight_disagreement | significant_disagreement | strong_disagreement"
    },
    "contrarian_score_raw": "number — 0.0–1.0 (sum of disagreement dimensions, normalized)"
  },

  "confidence": {
    "overall_confidence": "number — 0.0–1.0",
    "confidence_label": "very_low | low | medium | high | very_high",
    "confidence_components": {
      "statistical_feature_confidence": "number — 0.0–1.0",
      "knowledge_layer_confidence": "number — 0.0–1.0",
      "causal_chain_confidence": "number — 0.0–1.0",
      "game_script_confidence": "number — 0.0–1.0",
      "market_quality_confidence": "number — 0.0–1.0"
    },
    "confidence_penalties": [
      {
        "penalty_type": "string — e.g., 'low_sample_size', 'lineup_unavailable', 'stage_2_data_missing'",
        "penalty_magnitude": "number — subtracted from overall confidence",
        "description": "string"
      }
    ],
    "confidence_boosts": [
      {
        "boost_type": "string — e.g., 'multi_chain_concordance', 'in_tournament_confirmation'",
        "boost_magnitude": "number",
        "description": "string"
      }
    ]
  },

  "risk": {
    "risk_level": "low | medium | high | very_high",
    "variance": "number — σ² of the model probability estimate",
    "volatility_factors": ["string — e.g., 'lineup_unconfirmed', 'script_is_bimodal'"],
    "upset_vulnerability": "low | medium | high",
    "late_market_movement_risk": "low | medium | high"
  },

  "supporting_factors": [
    {
      "factor_type": "feature | causal_chain | knowledge_profile | game_script | form_trend | market_drift",
      "factor_id": "string — e.g., 'G-01', 'counter_attack_vs_high_line_clash', 'scaloni_lead_protection'",
      "description": "string — one sentence analyst-quality",
      "weight": "number — relative importance 0.0–1.0",
      "confidence": "number — 0.0–1.0"
    }
  ],

  "counter_factors": [
    {
      "factor_type": "feature | causal_chain | knowledge_profile | game_script | form_trend | market_drift",
      "factor_id": "string",
      "description": "string",
      "weight": "number",
      "confidence": "number"
    }
  ],

  "active_causal_chains": [
    {
      "chain_id": "string — e.g., 'G-01'",
      "chain_name": "string",
      "activation_confidence": "number — 0.0–1.0",
      "direction": "supports | opposes",
      "market_impact_magnitude": "low | medium | high"
    }
  ],

  "active_game_scripts": [
    {
      "script_id": "string — e.g., 'counter_attack_trap'",
      "script_probability": "number — 0.0–1.0",
      "script_market_alignment": "supports | opposes | neutral"
    }
  ],

  "market_disagreement": {
    "primary_source_of_disagreement": "string — what specifically does the model know that the market doesn't?",
    "disagreement_hypothesis": "string — the specific claim being made about why the market is mispriced",
    "falsification_condition": "string — what would have to be true for the thesis to be wrong?"
  },

  "uncertainty": {
    "known_unknowns": ["string — e.g., 'lineup not confirmed', 'weather forecast uncertain'],
    "model_limitations": ["string — e.g., 'small sample size (n=6)', 'Stage 2 data unavailable'],
    "thesis_stability": "stable | moderately_stable | fragile",
    "thesis_sensitivity": [
      {
        "variable": "string — e.g., 'lineup_change'",
        "impact_if_changes": "invalidates | degrades | minor_adjustment"
      }
    ]
  },

  "human_explanation": {
    "headline": "string — max 80 chars, analyst-quality single claim",
    "body": "string — 100–200 words following template: tactical mechanism + specific values + game script + market implication + honest hedge",
    "confidence_language": "string — calibrated hedge based on overall_confidence (declarative if >0.75, conditional if 0.50–0.75, speculative if <0.50)",
    "key_risk_statement": "string — one sentence on the main way this thesis fails"
  },

  "opportunity_score": "number — 0–100 (computed by Market Ranking Engine)",
  "rank": "number — position in match's ranked thesis list",
  "display_tier": "featured | secondary | watchlist | insufficient_data"
}
```

### 2.2 Complete JSON Example — Corners Over vs Morocco/Spain

```json
{
  "thesis_id": "t-esp-mar-2026-corners-over",
  "match_id": "wc2026-esp-mar-r16",
  "generated_at": "2026-06-28T10:00:00Z",
  "model_version": "oracle-v2.1",
  "data_stage": "stage_2",

  "market": {
    "market_type": "corners_ou",
    "selection": "corners_over",
    "line": 9.5,
    "market_price": 1.87,
    "market_implied_probability": 0.512,
    "market_source": "current",
    "market_quality": "sufficient"
  },

  "model": {
    "model_probability": 0.698,
    "probability_ci_90_low": 0.631,
    "probability_ci_90_high": 0.759,
    "model_fair_odds": 1.43,
    "probability_source": "full_stack"
  },

  "edge": {
    "raw_edge": 0.186,
    "edge_pct": 18.6,
    "kelly_fraction": 0.228,
    "expected_clv_signal": "positive"
  },

  "contrarian_score": {
    "classification": "strong_edge",
    "agreement_dimensions": {
      "model_vs_market": "significant_disagreement",
      "knowledge_vs_market": "significant_disagreement",
      "game_script_vs_market": "significant_disagreement",
      "form_trend_vs_market": "slight_disagreement"
    },
    "contrarian_score_raw": 0.74
  },

  "confidence": {
    "overall_confidence": 0.77,
    "confidence_label": "high",
    "confidence_components": {
      "statistical_feature_confidence": 0.84,
      "knowledge_layer_confidence": 0.90,
      "causal_chain_confidence": 0.80,
      "game_script_confidence": 0.78,
      "market_quality_confidence": 0.72
    },
    "confidence_penalties": [
      {
        "penalty_type": "lineup_unavailable",
        "penalty_magnitude": 0.05,
        "description": "Morocco's starting eleven not confirmed — if Regragui shifts to higher block, corner generation changes"
      }
    ],
    "confidence_boosts": [
      {
        "boost_type": "multi_chain_concordance",
        "boost_magnitude": 0.12,
        "description": "Three independent causal chains (C-01, C-03, C-05) all point toward corner over — concordance bonus applied"
      }
    ]
  },

  "risk": {
    "risk_level": "medium",
    "variance": 0.031,
    "volatility_factors": [
      "Morocco could shift to higher block if they score first, reducing Spain's corner generation",
      "Spain's set piece delivery quality affects corner-to-threat conversion but not corner volume directly"
    ],
    "upset_vulnerability": "low",
    "late_market_movement_risk": "medium"
  },

  "supporting_factors": [
    {
      "factor_type": "causal_chain",
      "factor_id": "C-03",
      "description": "Spain's possession game generates corners systematically — when blocked from central penetration, wide drives result in crosses, cross blocks produce corners.",
      "weight": 0.40,
      "confidence": 0.79
    },
    {
      "factor_type": "causal_chain",
      "factor_id": "C-05",
      "description": "Morocco's defensive compactness deflects crosses reliably — their organization that prevents goals also generates corner counts for the attacking team.",
      "weight": 0.35,
      "confidence": 0.77
    },
    {
      "factor_type": "knowledge_profile",
      "factor_id": "spain_possession_control_archetype",
      "description": "Spain's Possession Control primary archetype produces the tournament's highest corner generation rate — 7.2 per 90 across WC 2026 group stage.",
      "weight": 0.15,
      "confidence": 0.90
    },
    {
      "factor_type": "game_script",
      "factor_id": "tactical_neutralization",
      "description": "The Tactical Neutralization script (35% probability) directly produces corner accumulation despite goallessness — possession circulates without penetration and corners compound.",
      "weight": 0.10,
      "confidence": 0.76
    }
  ],

  "counter_factors": [
    {
      "factor_type": "knowledge_profile",
      "factor_id": "morocco_set_piece_defensive_organization",
      "description": "Morocco's organized set piece defense clears corners efficiently, reducing second-phase corner chains. Corner volume may be high but quick clearances limit the chain sequences.",
      "weight": 0.55,
      "confidence": 0.71
    },
    {
      "factor_type": "feature",
      "factor_id": "heat_index_thermal_fatigue",
      "description": "Match kickoff temperature projects 34°C — thermal fatigue chain S-10 suggests second-half intensity drop which would reduce both teams' attacking commitment and corner frequency.",
      "weight": 0.45,
      "confidence": 0.67
    }
  ],

  "active_causal_chains": [
    {"chain_id": "C-03", "chain_name": "Possession → Corner", "activation_confidence": 0.79, "direction": "supports", "market_impact_magnitude": "high"},
    {"chain_id": "C-05", "chain_name": "Low Block Deflections → Corners Conceded", "activation_confidence": 0.77, "direction": "supports", "market_impact_magnitude": "high"},
    {"chain_id": "G-07", "chain_name": "Low Block Stalemate", "activation_confidence": 0.76, "direction": "supports", "market_impact_magnitude": "medium"},
    {"chain_id": "S-10", "chain_name": "Thermal Fatigue", "activation_confidence": 0.67, "direction": "opposes", "market_impact_magnitude": "low"}
  ],

  "active_game_scripts": [
    {"script_id": "tactical_neutralization", "script_probability": 0.35, "script_market_alignment": "supports"},
    {"script_id": "defensive_siege", "script_probability": 0.28, "script_market_alignment": "supports"},
    {"script_id": "counter_attack_trap", "script_probability": 0.18, "script_market_alignment": "neutral"},
    {"script_id": "open_shootout", "script_probability": 0.08, "script_market_alignment": "opposes"}
  ],

  "market_disagreement": {
    "primary_source_of_disagreement": "The market prices corners over at 51.2% implied probability — it is treating the corner market as though Morocco's organized defense suppresses corner volume. The model identifies that Morocco's defensive compactness is what *generates* corners for the attacking team, not what suppresses them. The market conflates 'Morocco defends well' with 'few corners' when the causal direction is the opposite.",
    "disagreement_hypothesis": "Morocco's low block is a corner generation machine for possession teams. The better Morocco defends in open play, the more corners Spain will earn.",
    "falsification_condition": "If Morocco shift to a mid-to-high block — abandoning their structural identity — Spain's crossing volume decreases and the corner thesis weakens. Additionally, if Spain adopt a direct attack style rather than positional buildup, the possession-to-corner chain is broken."
  },

  "uncertainty": {
    "known_unknowns": [
      "Morocco lineup not confirmed — block height could shift with personnel changes",
      "Referee corner decision-making rate (average 6.3 vs mean 5.8 per 90) not yet applied"
    ],
    "model_limitations": [
      "Corners data from only 4 WC 2026 matches per team — small in-tournament sample",
      "Heat interaction with corner frequency has low historical data density for this temperature range"
    ],
    "thesis_stability": "moderately_stable",
    "thesis_sensitivity": [
      {"variable": "morocco_block_height_shift", "impact_if_changes": "degrades"},
      {"variable": "spain_direct_attack_style_adoption", "impact_if_changes": "invalidates"},
      {"variable": "early_red_card", "impact_if_changes": "degrades"}
    ]
  },

  "human_explanation": {
    "headline": "Spain's possession structure makes Morocco's low block a corner generator",
    "body": "Morocco's 5-4-1 block is one of the most organized in this tournament — they will allow Spain to circle the ball without conceding central penetration. But this defensive discipline creates corners, not suppresses them. When Spain's wide players drive to the byline, Morocco's compact shape deflects crosses for corners. When Spain's positional buildup meets the block at the edge of the area, the clearance goes out for corners. In the tactical neutralization script — which the model estimates at 35% probability for this matchup — goal volume is low but corner volume is high. Spain have generated 7.2 corners per 90 in this tournament against organized defenses. The market prices corners over at 51% implied probability; the model estimates 70%.",
    "confidence_language": "The signal is present across three independent causal chains and the model's 90% confidence interval (63%–76%) sits entirely above the market's implied 51%. The primary risk is a Morocco tactical shift to a higher block, which would alter the structural dynamic.",
    "key_risk_statement": "If Morocco score first and shift to a more aggressive shape, Spain's corner generation mechanism weakens significantly."
  },

  "opportunity_score": 81,
  "rank": 1,
  "display_tier": "featured"
}
```

---

## 3. Market Mapping Engine

### 3.1 Design Principle

Every game script has a characteristic impact profile across markets. These impacts are not uniform — a counter-attack trap script affects the 1X2 market very differently from the corners market. The Market Mapping Engine encodes this two-dimensional relationship: script × market → direction and magnitude.

The mapping is directional (positive = over/favorite/yes, negative = under/underdog/no, neutral = no signal) and graded (low / medium / high magnitude).

### 3.2 Game Script × Market Impact Matrix

For each cell: direction (+/-/0) and magnitude (L=low, M=medium, H=high). Blank = no signal / insufficient evidence.

| Game Script | 1X2 | DC | DNB | BTTS | O/U | Correct Score | Corners | Cards | Shots | Player Props | Tournament |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Favorite Dominance** | +H (fav) | +H (fav or draw) | +H (fav) | -M (no) | +M (over) | lean 2-0 / 3-0 | +L | 0 | +H (fav shots) | +M (fav striker) | +L (fav path) |
| **Open Shootout** | 0 | +L (draw DC) | 0 | +H (yes) | +H (over) | lean 2-1 / 2-2 | +M | +M | +H (both) | +H (both) | 0 |
| **Defensive Siege** | +H (siege team) | +M (siege or draw) | +H (siege) | -H (no) | -H (under) | lean 1-0 / 0-0 | +M (for attacker) | -M | -M (attacker suppressed) | -M (attacker striker) | 0 |
| **Counter-Attack Trap** | +H (underdog) | +H (underdog or draw) | +H (underdog) | -M (no) | -H (under) | lean 1-0 underdog / 0-0 | -M | +L | -H (favorite suppressed) | -M (favorite striker) | +H (underdog path) |
| **Set-Piece War** | 0 | +L | 0 | +M (yes) | 0 | lean 1-1 / 1-0 | +H (both) | 0 | -L | +M (aerial sp) | 0 |
| **Cagey Knockout** | 0 | +H (draw) | 0 | -M (no) | -H (under) | lean 0-0 / 1-0 | -L | -M | -M (both) | -M | 0 |
| **Early Goal Chaos** | +H (scorer) | 0 | 0 | +H (yes) | +H (over) | lean 2-1 / 3-1 | +M | +H | +H | +M (scorer) | 0 |
| **Underdog Resistance** | +H (draw or under) | +H (draw or under) | -M (under) | 0 | -M (under) | lean 0-1 / 1-1 | +M (for attacker) | +M | +M (attacker) | 0 | +M (underdog) |
| **Tactical Neutralization** | 0 | +H (draw) | 0 | -H (no) | -H (under) | lean 0-0 | +H (attacker) | -L | -M (attacker) | -H (both strikers) | 0 |
| **High-Press Feast** | +M (presser) | +M | 0 | +M | +M (over) | lean 2-0 / 2-1 | +H | +H | +H (presser) | +M (presser) | 0 |
| **Late Equalizer Pressure** | 0 | +M (draw) | 0 | +H (yes) | +M (over) | lean 1-1 | 0 | +H (late) | 0 | 0 | 0 |
| **Rotation/Experiment** | 0 | +L (draw) | 0 | 0 | -L | lean 0-0 | -L | -L | -L | -L | -M (resting team) |

### 3.3 Script Impact Aggregation

When multiple scripts have non-zero probability, the Market Mapping Engine computes a probability-weighted impact vector for each market:

```
market_script_impact(M) = Σ [P(script_s) × direction(s,M) × magnitude(s,M)]
  for all scripts s where P(script_s) > 0.05
```

Where direction is encoded as: +H=+2, +M=+1, +L=+0.5, neutral=0, -L=-0.5, -M=-1, -H=-2.

The resulting market_script_impact score (negative to positive) is one of five inputs to the Opportunity Score formula.

### 3.4 Market Availability by Stage

Not all markets are available at every data stage. Markets that require Stage 2 data but are evaluated at Stage 1 receive a `market_quality: thin` flag and their thesis confidence is automatically penalized.

| Market | Stage 1 | Stage 2 | Stage 3 |
|---|---|---|---|
| 1X2 | Model + market | Model + market + closing line | Full CLV tracking |
| Double Chance | Model | Model + market | Full CLV |
| Draw No Bet | Model | Model + market | Full CLV |
| BTTS | Model (no market) | Model + market | Full |
| O/U 2.5 | Model (no market) | Model + market | Full |
| Correct Score | Model (no market) | Model + market | Full |
| Corners O/U | Model (no market) | Full (API-Football data) | Event-level |
| Cards O/U | Model (no market) | Full (API-Football) | Event-level |
| Team Shots | Unavailable | Full | Full |
| Anytime Scorer | Unavailable | Full | Full |
| Tournament Winner | Limited | Full | Full |

---

## 4. Market Prioritization Engine

### 4.1 The Opportunity Score

Every thesis object receives an Opportunity Score (0–100). This is the single number that determines ranking. It integrates five dimensions — edge, confidence, causal support, uncertainty, and market quality — into a unified prioritization signal.

```
Opportunity_Score = 
  w1 × Signal_Strength_Score     (0–25 points)
  + w2 × Confidence_Score        (0–25 points)
  + w3 × Causal_Support_Score    (0–20 points)
  + w4 × Market_Quality_Score    (0–15 points)
  + w5 × Contrarian_Score        (0–15 points)
  − Uncertainty_Penalty          (0–30 points deducted)
```

**Weights:**
- w1 = 1.0 (edge is the primary driver)
- w2 = 1.0 (confidence modulates edge quality)
- w3 = 1.0 (causal support determines whether edge is fundamental or accidental)
- w4 = 1.0 (market quality determines whether comparison is valid)
- w5 = 1.0 (contrarian score determines whether it's already priced in)

### 4.2 Signal Strength Score (0–25)

Signal strength measures the magnitude of the model-market disagreement, scaled and capped.

```
raw_signal = |model_probability - market_implied_probability|

signal_strength_score = min(25, raw_signal × 100)
```

Edge < 5 percentage points → 0–5 points (very low signal)
Edge 5–10 ppts → 5–10 points
Edge 10–15 ppts → 10–15 points
Edge 15–20 ppts → 15–20 points
Edge > 20 ppts → 20–25 points

If market_quality = "unavailable" → signal_strength_score = 0 (cannot compute edge without market price).

### 4.3 Confidence Score (0–25)

Confidence Score reflects how much trust the model has in its own probability estimate.

```
confidence_score = overall_confidence × 25
```

Overall confidence 1.0 → 25 points
Overall confidence 0.5 → 12.5 points
Overall confidence 0.3 → 7.5 points

Confidence below the minimum floor (0.30) → thesis is not ranked; it is tagged `display_tier: insufficient_data`.

### 4.4 Causal Support Score (0–20)

Causal Support measures whether the thesis has a strong structural, football-logic explanation or is based purely on statistical pattern.

```
causal_support_score = Σ [activation_confidence(chain_i) × direction_weight(chain_i) × magnitude_weight(chain_i)] × 20
  normalized to [0, 1] range
```

Where:
- `direction_weight`: supporting chains = +1, opposing chains = -0.5
- `magnitude_weight`: high impact = 1.0, medium = 0.7, low = 0.4

Maximum score requires at least 2 high-confidence supporting chains with no high-confidence opposing chains.

No active supporting chains → causal_support_score = 0 (statistical pattern only; marked `experimental`).

### 4.5 Market Quality Score (0–15)

Market quality measures the reliability of the market price that the model is disagreeing with.

| Market Quality | Score |
|---|---|
| Sufficient (major sportsbook, sufficient volume, multiple sources) | 15 |
| Thin (single source, limited volume, specialty market) | 8 |
| Unavailable (no market price available) | 0 |
| Closing estimate (modeled from opening + historical drift) | 11 |

### 4.6 Contrarian Score (0–15)

The Contrarian Score measures how much the signal disagrees across multiple independent dimensions. A thesis where only the statistical model disagrees with the market is weaker than one where the model, knowledge layer, game script, and form trend all disagree with the market simultaneously.

```
contrarian_score = (number of dimensions showing "significant" or "strong" disagreement) / 4 × 15
```

All 4 dimensions disagree strongly → 15 points
3 dimensions disagree → 11.25 points
2 dimensions → 7.5 points
1 dimension → 3.75 points
No dimensions → 0 points (but thesis may still rank on signal strength alone)

### 4.7 Uncertainty Penalty (0–30 deducted)

The Uncertainty Penalty reduces the Opportunity Score for theses that have high variance, fragile sensitivity, or critical known unknowns.

| Penalty Trigger | Deduction |
|---|---|
| Lineup not confirmed (for player-dependent thesis) | -8 |
| Stage 2 data unavailable for this market | -6 |
| Sample size < 8 matches for key feature | -5 |
| Thesis stability = "fragile" | -8 |
| Thesis sensitivity includes a variable rated "invalidates" | -7 |
| CI_90 width > 25 percentage points | -5 |
| Counter factor chain has confidence > 0.75 | -4 |
| Weather/climate factor unresolved | -3 |

Maximum penalty capped at -30 (floor Opportunity Score = 0).

### 4.8 Score Interpretation

| Score Range | Classification | Display Behavior |
|---|---|---|
| 80–100 | Strong signal | Featured card, top placement |
| 65–79 | Moderate signal | Secondary card |
| 50–64 | Watchlist | Collapsed watchlist section |
| 35–49 | Weak signal | Not displayed, logged for calibration |
| 0–34 | No signal | Not displayed |

---

## 5. Contrarian Engine

### 5.1 What the Contrarian Engine Measures

The market is not always wrong. But it is systematically wrong in predictable ways: it overweights public narrative, underweights structural tactical mismatches, and struggles with specialty markets that require football domain knowledge to price. The Contrarian Engine identifies where Oracle's model disagrees with the market and classifies that disagreement by strength.

A critical design principle: disagreement is not inherently valuable. The Contrarian Engine must also identify when the model agrees with the market — because that agreement confirms that a particular market is already efficiently priced and should not be featured.

### 5.2 Four Disagreement Dimensions

**Dimension 1: Model vs Market**
Compares the Oracle's statistical model probability to the market's de-vigged implied probability.

```
model_market_gap = model_probability - market_implied_probability

Classification:
|gap| < 0.03 → agrees (within noise)
|gap| 0.03–0.07 → slight_disagreement
|gap| 0.07–0.12 → significant_disagreement
|gap| > 0.12 → strong_disagreement
```

**Dimension 2: Knowledge vs Market**
Compares what the Knowledge Engine's team identity and causal chain analysis implies about this market to what the market prices.

The knowledge layer produces a directional modifier per market (from team identity profiles, manager behavioral patterns, and causality chain activation). This modifier is compared against the market's implied probability to determine directional agreement.

```
knowledge_market_agreement = 
  sign(knowledge_modifier) == sign(model_market_gap) → agrees (or at least not contradicting)
  sign(knowledge_modifier) != sign(model_market_gap) → opposes (knowledge contradicts model AND market)
  |knowledge_modifier| > 0.08 AND aligns with model → significant_disagreement with market
```

**Dimension 3: Game Script vs Market**
The Game Script Engine produces a market impact vector (from the matrix in Section 3). Compare that impact vector's direction to the market's implied probability.

```
game_script_market_gap = probability_weighted_script_impact - market_implied_probability_adjustment
```

If the dominant game scripts' combined market impact leans in a direction that contradicts the current market price, this is script-vs-market disagreement.

**Dimension 4: Form Trend vs Market**
The current market price reflects consensus expectations, which are often formed from prior match results and recent media narrative. The form trend dimension compares the Oracle's decay-weighted form trajectory (is this team getting better or worse over the last 4 matches?) to what the market implies.

```
form_trend_gap = model_form_trajectory_adjustment - market_trend_implied_adjustment
```

### 5.3 Disagreement Classification

The contrarian_score_raw (0.0–1.0) is computed from the four dimensions and then classified:

```
contrarian_score_raw = (
  agreement_score(model_vs_market) × 0.40
  + agreement_score(knowledge_vs_market) × 0.25
  + agreement_score(game_script_vs_market) × 0.25
  + agreement_score(form_trend_vs_market) × 0.10
)

Where agreement_score:
  "agrees" → 0.0
  "slight_disagreement" → 0.33
  "significant_disagreement" → 0.67
  "strong_disagreement" → 1.0
```

| contrarian_score_raw | Classification | Interpretation |
|---|---|---|
| 0.00–0.15 | **Aligned** | Model and market agree. No opportunity detected. Market is efficiently pricing this scenario. |
| 0.15–0.35 | **Slight Edge** | Minor disagreement. Worth monitoring but below threshold for featured display. |
| 0.35–0.55 | **Moderate Edge** | Meaningful disagreement across 1–2 dimensions. Watchlist to secondary card. |
| 0.55–0.75 | **Strong Edge** | Significant disagreement across 2–3 dimensions. Secondary to featured card. |
| 0.75–1.00 | **Extreme Edge** | Disagreement across all or most dimensions. Highest priority thesis. Apply extra scrutiny — extreme edge may indicate model error, not market error. |

### 5.4 The Aligned Case

When a thesis is classified "Aligned" — meaning the model agrees with the market — Oracle should display this information explicitly rather than hiding it. The Aligned classification is useful information: it tells the user that the model sees no disagreement with the current market price for this market, and therefore there is no identified opportunity here.

Aligned theses are not displayed as opportunities but are accessible in the full match analysis to show users which markets the model considers fairly priced.

### 5.5 Extreme Edge Scrutiny Protocol

A contrarian_score_raw > 0.75 triggers an additional internal check before the thesis is elevated to featured display:

1. **Model sanity check:** Is the model probability the result of a recent data quality issue? Is any key feature missing or defaulting?
2. **Knowledge consistency check:** Does the knowledge layer's explanation make football sense? Would a qualified football analyst agree with the causal logic?
3. **Market explanation check:** Is there a plausible reason the market is priced where it is — recent news, sharp money, line movement — that the model hasn't incorporated?
4. **Historical calibration check:** On theses with similar contrarian_score_raw values, how has the Oracle performed historically? An extreme-edge classification with poor historical calibration is a model error signal, not a market error signal.

If the extreme edge survives scrutiny → featured with `risk: very_high` flag.
If scrutiny reveals likely model error → confidence degraded, thesis moved to watchlist.

---

## 6. Betting Thesis Templates

### 6.1 Template Design Principles

Thesis templates are structured narrative fills, not free-form language generation. Each template follows the format:

```
[PRIMARY_MECHANISM] → [SPECIFIC_VALUE] → [GAME_SCRIPT_CONSEQUENCE] → [MARKET_IMPLICATION] → [HONEST_HEDGE]
```

Every explanation must contain a specific numerical value (not vague language), a football mechanism (not a statistical correlation), and a falsification condition. Templates calibrate their certainty language by confidence level:

- Confidence ≥ 0.80: declarative ("The structural configuration suggests...")
- Confidence 0.65–0.79: conditional ("If Morocco maintain their low block setup — which they have consistently done — then...")
- Confidence < 0.65: speculative ("The model identifies a possible edge, though with limited confidence due to...")

### 6.2 Fifty Thesis Template Examples

---

**1X2 THESIS TEMPLATES**

**[T-01] Counter-Attack Trap — 1X2 Underdog**
*Mechanism: Counter Attack vs High Defensive Line*
"[TEAM_A] operate their defensive line at an average of [X]m from goal in possession — among the highest in this tournament. [TEAM_B] have demonstrated the transition speed to exploit this configuration: their last three counter-attack sequences against high lines produced an average xG of [Y] per sequence. The model estimates [TEAM_B]'s win probability at [Z]% against a market-implied [W]%. In the Counter-Attack Trap script ([P]% probability for this matchup), [TEAM_B] absorb pressure and convert a single transition into the decisive moment. The falsification condition: if [TEAM_A]'s full-backs track deeper or [TEAM_B]'s primary transition threat is absent from the XI, this structural edge disappears."

---

**[T-02] Press Energy Cliff — Second-Half 1X2**
*Mechanism: High Press Energy Depletion after 60 min*
"[TEAM_A]'s pressing system generates its most dangerous football in the first 60 minutes. Their PPDA of [X] in minutes 1–60 drops to [Y] in minutes 61–90 across their last [N] competitive matches. [TEAM_B]'s attack — specifically [PLAYER] collecting in transition — is calibrated to exploit the space that appears when [TEAM_A]'s press drops. The market prices the full-match 1X2 as a static probability. The model estimates [TEAM_A]'s probability is [X]% higher in the first half than the full match and [Y]% lower in the second. This temporal structure is not yet reflected in the closing-time 1X2 market."

---

**[T-03] Structural Mismatch — Home Win Underpriced**
*Mechanism: Archetype Incompatibility*
"The tactical mismatch here is specific: [TEAM_A]'s [ARCHETYPE] identity directly exploits [TEAM_B]'s primary structural weakness. [TEAM_B]'s [WEAKNESS] has produced negative outcomes in [X] of their last [N] matches against [ARCHETYPE] opponents. The market prices [TEAM_A] win at [W]% implied — the model estimates [Z]%. The [N_CHAINS] causal chains activated for this matchup all point in the same direction: [MECHANISM]. The main risk is [MANAGER]'s known adaptability — if [TEAM_B] shift formation pre-match to a [COUNTER_SHAPE], the structural advantage is partially neutralized."

---

**[T-04] Manager Pattern — Pragmatic Favorite**
*Mechanism: Scaloni/Deschamps Lead Protection Behavioral Pattern*
"[MANAGER] has defended a 1-0 lead at 60 minutes on [N] occasions in tournament football. The outcome: [WIN_RATE]% converted to a full-time result of 1-0 or better. His tactical shift is automatic: [PLAYER] is replaced by [DEFENSIVE_PLAYER], the shape narrows to [SHAPE], and the team absorbs. The 1X2 market for the full match does not sufficiently distinguish between a [TEAM] in the 60th minute at [CURRENT_SCORE] and a [TEAM] before kickoff. In this specific game state, the probability of [TEAM] win is [Z]% — [X] percentage points above what the market implies."

---

**[T-05] First Tournament Match — Inexperienced Team**
*Mechanism: Tournament Debut Nerves*
"[TEAM] are playing their first ever World Cup match. Their opponent, [TEAM_B], have [N] combined WC appearances among their starting XI with [M] knockout-stage appearances. Tournament experience creates measurable first-half performance differences — inexperienced teams underperform their aggregate quality by approximately [X]% in their first match's first 45 minutes. The model applies this prior and estimates [TEAM_B]'s probability at [Z]% against a market-implied [W]%."

---

**BTTS THESIS TEMPLATES**

**[T-06] Dual Counter-Attack — BTTS Yes**
*Mechanism: Both Teams Counter Attack Archetype → Dual Transition Goals*
"Both [TEAM_A] and [TEAM_B] use counter-attack as their primary offensive mechanism. Neither team possesses the organized defensive structure that suppresses the other's primary weapon. When two counter-attacking teams meet, neither can sit deep comfortably — both need to create transition opportunities — and both create them. Historical data: counter vs counter matchups at this tournament level produce BTTS at [X]% frequency. The model estimates BTTS Yes at [Z]% against a market-implied [W]%."

---

**[T-07] Set Piece Both Teams — BTTS Yes**
*Mechanism: Dual Set Piece Threat + Aerial Vulnerability*
"[TEAM_A]'s corner delivery ([PLAYER]) is among the tournament's best — they have generated [X] xG from set pieces per 90 this tournament. [TEAM_B]'s [PLAYER] has scored from headers in [N] of [M] recent WC matches. Critically, [TEAM_A]'s aerial set piece defense is rated [RATING] — specifically vulnerable to the type of delivery [TEAM_B] uses. In the Set-Piece War script ([P]% probability), both teams score from dead balls regardless of open-play tactical outcome. BTTS Yes at [Z]% against [W]% market."

---

**[T-08] Elite Defense — BTTS No**
*Mechanism: GK Dominance + Structured Low Block → Clean Sheet Likely*
"[TEAM]'s defensive structure has conceded one open-play goal in [N] tournament matches. [GOALKEEPER]'s saves-above-expectation of +[X] represents the highest in this tournament. [OPPONENT]'s attack generates [Y] xG per 90 — but against [TEAM]'s low block structure, their chance quality index drops to [Z] — the lowest conversion environment in the model. BTTS No requires [TEAM] to not concede. The model estimates this at [Q]% probability versus [W]% market-implied."

---

**[T-09] Deschamps BTTS No Pattern**
*Mechanism: Manager First-Half Conservatism + Known Suppression Pattern*
"France under Deschamps have failed to produce BTTS in [X] of their last [N] competitive tournament matches. This is structural: Deschamps prioritizes first-half defensive organization above attacking commitment, limiting the opponent to fewer high-quality chances while France create selectively. BTTS requires the opponent to score. Against France's defensive organization, this requires the opponent to beat a system that has conceded [Y] open-play goals per 90 in competitive tournament football — the [RANK] lowest rate in this tournament."

---

**O/U THESIS TEMPLATES**

**[T-10] Thermal Fatigue — Under Goals**
*Mechanism: Heat Index → Pressing Collapse → Positional Slowdown*
"Match kickoff temperature projects [TEMP]°C heat index. At temperatures above 32°C, pressing intensity degrades systematically after minute 45–50 for non-altitude-adapted teams. Both teams in this match have based their attacking identity on pressing triggers or high-tempo transitions — mechanisms that require physical capacity that deteriorates in extreme heat. Historical WC matches in comparable heat conditions produce [X] fewer goals per match than equivalent matchups in neutral temperatures. The model estimates O/U [LINE] falls under at [Z]% vs market-implied [W]%."

---

**[T-11] Open Shootout — Over Goals**
*Mechanism: Both Teams Attack Freely + No Organized Defense*
"Neither [TEAM_A] nor [TEAM_B] has fielded an organized defensive structure in any of their [N] tournament matches. [TEAM_A]'s goals-conceded per 90 ([X]) and [TEAM_B]'s ([Y]) are both among the tournament's highest. The Open Shootout script carries [P]% probability for this matchup. In the Open Shootout script, conversion rates approach typical levels (rather than being suppressed by defensive organization), and the model estimates [X] expected total goals against a market line of [LINE]."

---

**[T-12] Elite GK Suppression — Under**
*Mechanism: Goalkeeper Dominance × High Shot Volume = Low Conversion*
"[TEAM_B]'s goalkeeper has faced [SHOTS] shots in this tournament and conceded [GOALS] goals. Their saves-above-expectation of +[X] represents significantly above-average performance. Against [TEAM_A]'s expected [Y] shots, the conversion rate drops from a tournament-average [BASE]% to a model-estimated [ADJUSTED]%. The O/U [LINE] under is priced at [W]% market-implied; the model estimates [Z]% after accounting for the goalkeeper quality interaction."

---

**[T-13] High Press × Low Press Resistance — Over First Half**
*Mechanism: Press Trap → Turnovers → Chances → Goals in First Half*
"[TEAM_A]'s pressing system generates its highest-quality chances in the first 60 minutes before energy depletion. [TEAM_B]'s pass completion under pressure ([X]%) is the [RANK] lowest in this tournament — indicating they cannot build through the press reliably. Press traps generate turnovers in dangerous positions. In [TEAM_A]'s recent matches against press-vulnerable opponents, first-half goal production averages [Y] per match. O/U [LINE] first-half over at [Z]% model vs [W]% market."

---

**CORNERS THESIS TEMPLATES**

**[T-14] Wing Overload × Narrow Defense — Corners Strongly Over**
*Mechanism: Wing Attack → Blocked Cross → Corner Chain*
"[TEAM_A] concentrates [X]% of their attacking output through wide channels. [TEAM_B] defends with a narrow [SHAPE] that concedes width deliberately to protect central zones. Against narrow defenses, [TEAM_A]'s wide players drive to the byline and cross — and those crosses are blocked for corners. [TEAM_A] have averaged [Y] corners per 90 in this tournament; against specifically narrow defensive setups, that average rises to [Z]. The model estimates [N] corners for [TEAM_A] vs a market line of [LINE]."

---

**[T-15] Possession Team × Compact Block — Systematic Corners**
*Mechanism: Possession Circulation → Peripheral Attacks → Corner Deflections*
"[TEAM_A]'s possession structure generates corners regardless of whether they score. When their positional buildup meets [TEAM_B]'s compact block, they shift wide, force a clearance-for-corner, and repeat. In [TEAM_A]'s last [N] matches against compact defenses (defensive shape rating < [THRESHOLD]), they averaged [X] corners per 90 — [Y] above their overall average. The match's dominant game script (Tactical Neutralization, [P]% probability) produces goallessness and corner accumulation simultaneously. Corners over [LINE] at [Z]% model vs [W]% market."

---

**[T-16] High Press Both Teams — Corners Generated from Clearances**
*Mechanism: Goalkeepers Pressed → Long Clearances → Second Ball → Wide Attack → Corner*
"Both teams press aggressively. Both goalkeepers will be forced into uncomfortable long clearances throughout the match. Those clearances generate second-ball contests, second balls generate wide attacks, wide attacks generate corners. This mechanism repeats regardless of which team is in possession. [TEAM_A] and [TEAM_B] have averaged a combined [X] corners per 90 in their matches against each other's archetype. The model estimates [N] total corners in this match."

---

**CARDS THESIS TEMPLATES**

**[T-17] Foul Generator vs Aggressive Defender — Player Cards**
*Mechanism: Technical Dribbler × High-Foul Defender → Yellow*
"[PLAYER_A] generates [X] fouls-drawn per 90 — the highest rate among players in their position at this tournament. The defender assigned to them ([PLAYER_B]) has committed [Y] fouls and received [N] yellows in [M] tournament matches. When a high-volume foul-generator faces a defender with reactive tackling tendencies, the yellow card expectation for that specific defender rises significantly. The model estimates [PLAYER_B]'s probability of receiving a yellow card at [Z]% — meaningfully above market."

---

**[T-18] Must-Win Group Match — Late Cards Elevated**
*Mechanism: Competitive Tension → Late Fouls → Discipline Breakdown*
"Both teams require a win to advance from the group stage. In must-win scenarios at this stage, card production in the final 20 minutes is [X]% above the tournament average as teams take increasingly desperate action to produce or prevent goals. Both teams enter this match with [A] and [B] yellow cards respectively in tournament play — indicating neither has been excessively physical, and the late-game card inflation comes from competitive desperation rather than accumulated aggressive play."

---

**[T-19] Strict Referee × Physical Match — Cards Over**
*Mechanism: Referee Profile × Physical Matchup = Elevated Discipline Environment*
"The appointed referee averages [X] yellow cards per 90 in competitive international matches — [Y] above the tournament mean of [Z]. This match has a physical profile: both teams rank in the top 8 for fouls committed per 90 in this tournament. A strict referee in a physically contested match typically produces [Q]% more cards than the market's baseline. Cards over [LINE] at [Z]% model vs [W]% market."

---

**[T-20] Press Failure Tactical Fouls — Cards**
*Mechanism: High Press Against Press-Resistant Team → Professional Fouls*
"[TEAM_A]'s pressing system depends on winning the ball quickly after losing it. Against [TEAM_B]'s technical press resistance (pass completion under pressure: [X]%), the press will fail repeatedly. When [TEAM_A]'s counter-press does not recover the ball technically, the fallback is a tactical foul to prevent dangerous transition. [TEAM_A]'s card rate in matches where their press completion rate falls below [THRESHOLD] is [Y] yellows per 90 vs [Z] in successful press matches."

---

**SHOTS THESIS TEMPLATES**

**[T-21] Shot Volume Structural Advantage — Team Shots Over**
*Mechanism: High Shot Generation vs High Shot Concession Rate*
"[TEAM_A] generate [X] shots per 90 in competitive matches. [TEAM_B] concede [Y] shots per 90 — the [RANK] highest among tournament teams. The matchup-specific product of [TEAM_A]'s shot generation profile against [TEAM_B]'s defensive openness produces a model estimate of [Z] shots for [TEAM_A] in this match, against a market line of [LINE]. The driving causal mechanism: [TEAM_B]'s [ARCHETYPE] identity requires them to commit attackers forward, leaving space for [TEAM_A]'s [PLAYER] to receive in transition zones and shoot."

---

**[T-22] Creative Hub Absence — Shots On Target Under**
*Mechanism: Press Breaker / Creative Hub Absent → Buildup Disrupted → Shot Quality Drops*
"[PLAYER] will not start this match. [PLAYER] functions as [TEAM]'s primary [ROLE] — receiving between the lines, creating through-ball opportunities, and setting attacking tempo. In [TEAM]'s last [N] matches without [PLAYER] in the starting lineup, shots on target averaged [X] per 90 versus [Y] with [PLAYER] present. The absence of the creative hub reduces shot quality even when shot volume is maintained. Shots on target under [LINE] at [Z]% model vs [W]% market."

---

**PLAYER PROP THESIS TEMPLATES**

**[T-23] Transition Threat vs High Line — Anytime Scorer**
*Mechanism: P-01 Chain — Forward Run into Space → 1v1 with GK → Goal*
"[PLAYER] scores from runs behind defensive lines at a higher frequency than any other player at this tournament — [X] goals from this mechanism in [N] matches. [OPPONENT] plays their defensive line at an average of [Y]m from their own goal. This is exactly the configuration [PLAYER] exploits most efficiently. The model estimates [PLAYER]'s xG for this match at [Z], producing an anytime scorer probability of [Q]% against a market-implied [W]%."

---

**[T-24] Set Piece Aerial Specialist — Anytime Scorer**
*Mechanism: Set Piece Specialist Delivery × Aerial Specialist Run × Aerial Defensive Vulnerability*
"[PLAYER] has scored [X] headed goals from corners and free kicks in the last [N] WC matches. [OPPONENT]'s aerial defensive rating at set pieces is [Y] — among the lowest in this tournament. [DELIVERY_PLAYER]'s corner delivery generates the highest xG-per-corner of any set piece taker in this squad. In this specific configuration — quality delivery + aerial specialist + aerial defensive vulnerability — the model estimates [PLAYER]'s headed goal probability at [Z]% per corner sequence."

---

**CORRECT SCORE THESIS TEMPLATES**

**[T-25] Tactical Neutralization — Correct Score 0-0**
*Mechanism: Low Block Stalemate + Possession Suppression + No Set Piece Conversion*
"The tactical interaction in this match produces the Tactical Neutralization script at [X]% probability — the highest script probability Oracle has assigned in this tournament. [TEAM_A]'s possession identity generates corners without penetration; [TEAM_B]'s low block structure prevents the central goal-scoring opportunities [TEAM_A] needs. Set piece conversion requires [TEAM_A] to beat [TEAM_B]'s aerial set piece defense, rated [Y]. 0-0 correct score at [Z]% model — [W]% market — represents the largest model-market gap in the correct score cluster."

---

**[T-26] 1-0 Set Piece Score — Correct Score**
*Mechanism: Set Piece Goal + Lead Protection Manager Pattern*
"This match's dominant offensive mechanism for [TEAM] is dead ball delivery. Their xG from set pieces per 90 ([X]) exceeds their open-play xG per 90 ([Y]) — meaning they are more likely to score from a corner or free kick than from open play. If [TEAM] score from a set piece, [MANAGER]'s lead-protection behavioral pattern activates immediately: the team drops to a defensive shape and the match finishes [SCORE]. The 1-0 for [TEAM] correct score is valued at [Z]% model vs [W]% market."

---

**TOURNAMENT FUTURES THESIS TEMPLATES**

**[T-27] Bracket Path Discount — Tournament Winner**
*Mechanism: Path Difficulty Asymmetry Not Priced*
"[TEAM_A] and [TEAM_B] are rated within [X] Elo points of each other. Their tournament winner market prices reflect nearly identical aggregate quality assessments. However, [TEAM_A]'s projected path to the final avoids all top-4 rated opponents until the semi-final; [TEAM_B]'s path likely intersects with [OPPONENT] — ranked [RANK] — in the quarter-final. Path difficulty adjustment produces a [Y] percentage point discount on [TEAM_B]'s tournament winner probability that is not reflected in current pricing."

---

**[T-28] Manager System Depth — Tournament Survival**
*Mechanism: Tactical Flexibility Advantage in Knockout Format*
"[TEAM]'s manager has deployed [N] distinct formations across [M] tournament matches. No other team in the competition shows this range. Tactical flexibility in the knockout format is specifically valuable: opponents have 96 hours to prepare between matches, neutralizing teams who show the same shape every game. [TEAM]'s ability to present a completely different face in each match creates a sustained tactical advantage that is worth approximately [X] percentage points on their per-match survival probability, compounded across [K] remaining required results."

---

**[T-29] Energy Management Cliff — Tournament Futures Downgrade**
*Mechanism: Bielsa/High-Press Energy Depletion × Deep Tournament*
"[TEAM]'s pressing system under [MANAGER] is among the most physically intensive in this tournament. This system creates a performance trajectory problem in deep tournament runs: match 4 and 5 are played by a team whose pressing capacity is significantly diminished compared to match 1. [MANAGER]'s coaching history shows a consistent pattern of strong early tournament form followed by performance degradation in 4th and 5th knockout matches. [TEAM]'s long-run tournament winner probability is [X]% below what their current form would imply when fatigue trajectory is modeled."

---

**[T-30] Goalkeeper Regression → Tournament Futures**
*Mechanism: Above-Expected Saves Rate → Regression Toward Mean in Deep Rounds*
"[GOALKEEPER] has performed +[X] saves above expectation in [N] tournament matches — an exceptional run that has carried [TEAM] through two knockout rounds. At this sample size, there is a meaningful probability that some portion of this outperformance is variance rather than permanent ability. The model assigns [P]% probability to performance regression toward [GOALKEEPER]'s career xGA baseline in the next [K] matches. [TEAM]'s tournament win probability from here assumes sustained above-expectation performance — an optimistic assumption."

---

*Templates T-31 through T-50 follow the same structure for the remaining market types: Double Chance, Draw No Bet, Half-Time/Full-Time, Total Cards (by team), Player Assists, Tournament Top Scorer, Group Winner, Both Teams Concede, Clean Sheet, and First Goal Scorer — each with a primary mechanism, specific values, game script consequence, market implication, and falsification condition.*

---

## 7. Opportunity Ranking System

### 7.1 The Ranking Problem

A typical match generates thesis objects for 12–20 available markets. Displaying all of them is overwhelming and counterproductive — it signals to the user that the system has an opinion on everything, which is the opposite of the disciplined, high-quality signal the system is designed to produce.

The Opportunity Ranking System selects the top 3 opportunities from all available theses, applying the Opportunity Score (Section 4) with three additional constraints: tie-breaking, uncertainty penalties, and portfolio diversification.

### 7.2 Primary Ranking Logic

Step 1: Compute Opportunity Score for every thesis where `overall_confidence ≥ 0.30` and `market_quality ≠ "unavailable"`.

Step 2: Eliminate any thesis where `display_tier = "insufficient_data"`.

Step 3: Apply portfolio diversification filter (Section 8). Remove correlated duplicates before ranking.

Step 4: Sort remaining theses by Opportunity Score (descending).

Step 5: Select top 3.

### 7.3 Tie-Breakers

When two theses have identical Opportunity Scores (within ± 2 points):

**Tie-breaker 1: Causal Support Score.** The thesis with more supporting causal chains and higher combined chain confidence wins.
*Rationale:* A statistically-derived edge with football causality support is more reliable than a statistically-derived edge without it.

**Tie-breaker 2: Market Quality Score.** The thesis where the market price is more reliable wins.
*Rationale:* A well-priced market's disagreement is a stronger signal than a thin market's disagreement.

**Tie-breaker 3: Thesis Stability.** The thesis with stability = "stable" beats "moderately_stable" beats "fragile."
*Rationale:* A stable thesis with a good score is more valuable than a fragile thesis with the same score.

**Tie-breaker 4: Stage priority.** A Stage 2 thesis beats a Stage 1 thesis at equal score (richer data → higher quality signal).

### 7.4 Uncertainty Penalties — Rank-Level Application

After sorting by Opportunity Score, apply a secondary rank-level uncertainty check before finalizing the top 3:

- If the #1 ranked thesis has `thesis_stability: fragile` AND `risk_level: very_high`, check whether the #2 ranked thesis is within 10 Opportunity Score points. If so, flag the #1 thesis with a `high_uncertainty_flag` and display a prominent risk disclaimer alongside it.

- If a ranked thesis has `thesis_sensitivity` containing a variable rated "invalidates" that has not yet been resolved (lineup unconfirmed, weather forecast pending), the thesis is moved to `display_tier: watchlist` and replaced in top-3 by the next eligible thesis.

- If the top 3 theses all have `overall_confidence < 0.55`, display a `low_confidence_match` warning: "Limited high-confidence signals identified for this match. Analysis displayed for completeness."

### 7.5 The No-Opportunity Case

Not every match produces a top-3. When no thesis exceeds an Opportunity Score of 35, Oracle displays:

> *"No meaningful model-market disagreement identified for this match across available markets. The model's probability estimates are broadly aligned with current market pricing. Analysis components remain available below."*

This is a feature, not a bug. A system that always finds an "opportunity" is not a signal system — it's a noise generator.

---

## 8. Portfolio Construction

### 8.1 The Correlation Problem

Betting opportunities are not independent. A thesis on Spain ML, a thesis on Spain DNB, and a thesis on Spain Double Chance (Spain or Draw) are three expressions of the same underlying belief: that Spain will not lose. Featuring all three in the top-3 is not three opportunities — it is one opportunity with redundant restatements.

Similarly, "Over 2.5 goals" and "BTTS Yes" are highly correlated in most match environments. "Argentina Win" and "Argentina Clean Sheet" share significant probability overlap. The Portfolio Construction layer prevents the top-3 from being dominated by correlated expressions of the same underlying model view.

### 8.2 Correlation Classification

Define correlation groups for markets. Markets within the same group are considered correlated:

**Group A: Outcome (Favorite Direction)**
1X2 Home Win, DNB Home Win, Double Chance (Home or Draw), Asian Handicap Home

**Group B: Outcome (Draw Direction)**
Draw 1X2, Double Chance (Draw or Away), Double Chance (Home or Draw)

**Group C: Outcome (Underdog Direction)**
1X2 Away Win, DNB Away Win, Double Chance (Away or Draw)

**Group D: Goals Over**
Over 1.5, Over 2.5, Over 3.5, BTTS Yes (strong correlation in over-goals environments)

**Group E: Goals Under**
Under 2.5, Under 3.5, BTTS No (strong correlation in under-goals environments)

**Group F: Set Piece / Aerial**
Corners Over, Set Piece Goals, Aerial Duel Totals

**Group G: Discipline**
Cards Over, Fouls Total, specific Player Card theses with same mechanism

**Group H: Shots**
Team Shots Over, Shots on Target Over, Shot-generating player anytime scorer

**Group I: Specific Outcome Cluster**
Correct Score theses that share the same score category (0-0, 1-0, 2-0 are all "low-scoring" outcomes)

Note: Groups are not mutually exclusive — a market can be removed from consideration because it overlaps with a higher-scoring market in a related group even if it is not in the exact same group.

### 8.3 Diversification Rules

**Rule 1: One thesis per correlation group.** If the top-5 includes two theses from the same correlation group, retain only the higher-scoring one. The other is moved to `display_tier: secondary` with a note: "Correlated with [primary thesis] — secondary view of the same signal."

**Rule 2: Maximum two outcome-direction theses.** Groups A, B, C together count as "outcome direction" theses. Maximum 2 of the top-3 may be outcome-direction theses, regardless of their individual Opportunity Scores. The third slot must be a specialty market (corners, cards, shots, player props, or correct score).
*Rationale:* Outcome direction is already the most heavily trafficked market. The system's differentiated value is in specialty markets where football knowledge has greater pricing advantage.

**Rule 3: Maximum one "under goals" thesis.** If Under 2.5, BTTS No, and Correct Score (low-scoring outcome) all rank highly, only the highest-scoring one is included in top-3. The others are secondary.

**Rule 4: Player prop limit.** Maximum one player-specific thesis in the top-3 per match (to avoid a top-3 dominated by props from the same team's attacking structure).

### 8.4 Diversification Override

If applying diversification rules leaves fewer than 3 qualifying theses (because most high-scoring theses are correlated), the system extends to secondary theses until 3 display items are available, labeling them explicitly:

- `featured` (score > 65, diversification-qualified)
- `secondary` (score 50–64, or high-scoring but correlated)
- `watchlist` (score 35–49)

The user always sees at least context, even when the primary opportunity set is limited.

---

## 9. Historical Validation

### 9.1 Why Validation Is Non-Negotiable

The Betting Thesis Engine produces claims about where the model disagrees with the market. Those claims are meaningless without evidence that the system has historically been correct when making similar claims. Validation is not an optional quality check — it is the foundation of the system's credibility.

Every metric in this section should be tracked per-market, per-confidence-band, per-contrarian-classification, and per-causal-chain-set. Aggregate numbers hide the structural failures that harm users.

### 9.2 Primary Validation Metrics

**Brier Score**
Measures the accuracy of the model's probability estimates.
```
BS = (1/N) × Σ (model_probability_i - outcome_i)²
```
Target: Brier Score per market below the market-implied Brier Score (i.e., Oracle's probabilities are more calibrated than the market's implied probabilities).
Tracking: Per market type, per confidence band (<0.50, 0.50–0.65, 0.65–0.80, >0.80).

**Ranked Probability Score (RPS)**
Extends Brier to ordered outcomes (e.g., 1X2, correct score clusters). Penalizes confidence that is directionally correct but ordinal-magnitude wrong.
```
RPS = (1/N) × Σ Σ (cumulative_probability_k,i - cumulative_outcome_k,i)²
```
Most relevant for: 1X2, O/U, correct score buckets.

**Closing Line Value (CLV)**
The gold-standard measure of signal quality for markets where closing line data is available.
```
CLV = model_probability - closing_line_implied_probability
```
Positive CLV → Oracle identified a real edge before the market corrected.
Negative CLV → Oracle disagreed with the market in the wrong direction (market was smarter).

Track: Average CLV per market, per contrarian classification. The "Extreme Edge" classification should have the highest positive average CLV if the model is performing correctly. If "Extreme Edge" has negative average CLV, the system is systematically wrong in its most confident cases — a critical calibration failure.

**Hit Rate**
The raw fraction of featured theses that were correct outcomes.
```
Hit Rate = outcomes_where_selection_correct / total_featured_theses
```
Hit rate is necessary but not sufficient — a system can have a high hit rate by always picking favorites. Track hit rate alongside the average market price of featured theses to determine whether the hit rate implies positive expected value.

**Calibration**
For theses where the model estimate was X%, approximately X% should win.
```
For all theses with model_probability in [0.60, 0.65]: ~62.5% should win.
For all theses with model_probability in [0.65, 0.70]: ~67.5% should win.
...
```
Calibration curves should be monotonically increasing. If they are not — if 65% model theses win at lower rates than 60% model theses — the model is incorrectly rank-ordering probabilities.

**Signal Stability**
Measures how much Oracle's probability estimate changes from match-announcement-time to kickoff. High volatility signals = model is sensitive to new information (which is correct) but also may indicate that the model is over-reacting to noise.
```
signal_stability = 1 - |p_final - p_initial| / p_initial
```
Track signal stability per market type. Very low stability (< 0.70) means the featured thesis was largely dependent on late-arriving information and should carry an automatic uncertainty flag at the time of publication.

**Thesis Stability**
Tracks whether thesis conclusions change when re-run with slightly different inputs (sensitivity testing). A thesis that flips direction when the model_probability changes by 2 percentage points is fragile and should be degraded in ranking.

**Market Stability**
Tracks whether the market moved in the direction Oracle's thesis predicted. Positive market movement = the market corrected toward Oracle's view after thesis publication. This is a proxy for CLV when exact closing lines are unavailable.
```
market_movement_alignment = sign(closing_probability - opening_probability) == sign(model_probability - opening_probability) ? "aligned" : "opposing"
```

### 9.3 Validation Architecture

**Historical Thesis Log**
Every thesis generated is stored permanently:
`data/artifacts/thesis_log.parquet`
Columns: thesis_id, match_id, market, selection, model_probability, market_implied_probability, opportunity_score, contrarian_classification, confidence, active_chains, game_script, outcome (populated post-match), clv (populated when closing line available).

**Post-Match Resolution**
After each match, a resolution script populates:
- `outcome: true/false` for each thesis selection
- `closing_line_implied_probability` (if available)
- `CLV` (computed)
- `market_final_price` (if available)

**Calibration Report**
Generated after every 50 resolved theses per market:
- Reliability diagram data
- Brier Score per market and confidence band
- CLV by contrarian classification
- Hit rate with average market price context

**Recalibration Triggers**
If any market shows:
- Brier Score > market-implied Brier Score over 30+ samples
- Average CLV < -0.03 over 30+ samples
- Calibration curve with non-monotonic section at any confidence level

→ Flag that market's thesis confidence for review and recalibration.

---

## 10. Implementation Roadmap

### Week 25D — Betting Thesis Engine Core

**Objective:** Build the layer that converts per-match intelligence (features + knowledge + game scripts) into structured thesis objects for every available market.

This week does not require frontend changes. It is a pure backend intelligence layer.

**Deliverables:**

`oracle/thesis/schema.py`
Dataclasses for: BettingThesis, MarketSpec, ModelEstimate, EdgeSpec, ContrarianScore, ConfidenceScore, RiskAssessment, SupportingFactor, CounterFactor, CausalChainActivation, GameScriptActivation, MarketDisagreement, UncertaintySpec, HumanExplanation. All fields from the schema in Section 2.

`oracle/thesis/generator.py`
`generate_thesis(match_id, market_type, selection, line=None)` → `BettingThesis`
- Reads feature snapshot + knowledge profile + game script distribution
- Computes model probability (from statistical model, knowledge-adjusted)
- Pulls market implied probability from `market_feature_snapshots`
- Computes edge, Kelly fraction
- Activates supporting and counter causal chains
- Fills all thesis fields
- Calls explanation template filler

`oracle/thesis/contrarian.py`
`compute_contrarian_score(thesis)` → `ContrarianScore`
Implements the four-dimension disagreement framework from Section 5.
Classifies: aligned / slight_edge / moderate_edge / strong_edge / extreme_edge.
Applies extreme edge scrutiny protocol flags.

`oracle/thesis/confidence.py`
`compute_thesis_confidence(thesis, feature_quality, knowledge_confidence)` → `ConfidenceScore`
Applies all penalties and boosts from Section 4. Returns overall_confidence with component breakdown.

`oracle/thesis/templates.py`
Template system for human_explanation generation.
Reads `data/seed/thesis_templates.json` (one per activated causal chain, per market type).
Fills placeholders with specific values from feature snapshot.
Applies confidence-level language calibration.

`data/seed/thesis_templates.json`
50 thesis templates from Section 6, encoded as structured template strings with placeholder slots.

`tests/test_thesis_generator.py`
Generate theses for Spain vs Morocco (from fixture seed data). Verify:
- Corners over thesis activates chains C-03, C-05, G-07
- 1X2 Morocco thesis activates G-07, knowledge_profile morocco_low_block
- BTTS No thesis has higher confidence than BTTS Yes
- No forbidden language in any human_explanation output

---

### Week 26 — Market Ranking Engine + Opportunity Score

**Objective:** Implement the Opportunity Score formula, the full ranking system, and portfolio diversification constraints. Begin surfacing ranked theses to the frontend.

**Deliverables:**

`oracle/thesis/scorer.py`
`compute_opportunity_score(thesis)` → `int (0–100)`
Implements the full Opportunity Score formula from Section 4.
All five component scores computed and stored in thesis for transparency.

`oracle/thesis/ranker.py`
`rank_match_theses(match_id)` → `list[BettingThesis]` (sorted, top-3 selected, diversified)
Applies:
- Thesis generation for all available markets
- Opportunity Score computation
- Uncertainty penalty application
- Portfolio diversification rules (Section 8)
- Tie-breaker logic (Section 7.3)
- Top-3 selection with display_tier assignment

`oracle/thesis/portfolio.py`
`apply_diversification(thesis_list)` → `thesis_list (filtered)`
Implements all 4 diversification rules from Section 8.
Marks correlated theses with `display_tier: secondary`.

`scripts/export_thesis_artifacts.py`
Exports: `data/artifacts/match_thesis_ranked_{match_id}.json` — the ranked thesis list per match.
Exports: `data/artifacts/thesis_log.parquet` — appends new entries to the historical log.

Frontend: `frontend/src/pages/match/[match_id].astro`
Add Betting Intelligence section above the existing Analyst Intelligence section.
Display: Top 3 thesis cards. Each card shows:
- Headline (from thesis.human_explanation.headline)
- Opportunity Score (styled as a gauge or label)
- Contrarian Classification (Aligned / Slight Edge / Moderate Edge / Strong Edge / Extreme Edge)
- Confidence label + component bars
- Supporting factors list (top 2)
- Key risk statement
- Body explanation (collapsible)

`tests/test_ranker.py`
Verify that Spain vs Morocco produces corners over as top-ranked thesis.
Verify that correlated outcome theses are deduplicated.
Verify that a match with no signals above 35 Opportunity Score produces the no-opportunity display state.

---

### Week 27 — Contrarian Engine + Historical Thesis Log

**Objective:** Implement the full four-dimension contrarian engine, begin populating the historical thesis log, and add post-match resolution logic.

**Deliverables:**

`oracle/thesis/contrarian_full.py`
Complete implementation of all 4 disagreement dimensions (Section 5).
Dimension 1 (model vs market): already implemented in Week 26.
Dimension 2 (knowledge vs market): reads knowledge_modifier from knowledge engine per market.
Dimension 3 (game script vs market): reads market impact vector from game script engine, compares to market.
Dimension 4 (form trend vs market): reads decay-weighted form trajectory from feature store.

`oracle/thesis/extreme_edge.py`
`extreme_edge_scrutiny(thesis)` → `ScrutinyResult(passes, degradation_reason)`
Implements the 4-step scrutiny protocol for theses with contrarian_score_raw > 0.75.

`oracle/validation/thesis_resolver.py`
`resolve_thesis_outcomes(match_id, final_score, corners_total, cards_total, ...)` → updates thesis_log.parquet with outcomes, CLV, market_final_price.

`data/artifacts/thesis_log.parquet`
Schema: thesis_id, match_id, generated_at, market_type, selection, model_probability, market_implied_probability, opportunity_score, contrarian_classification, overall_confidence, active_chains (list), game_scripts (list), outcome (nullable), clv (nullable).

`tests/test_contrarian.py`
Spain vs Morocco corners over: should classify as "strong_edge" (not "extreme_edge").
Spain win 1X2: should classify as "aligned" (model agrees with market favorite pricing).
Morocco +1X2 underdog: should classify as "moderate_edge".

---

### Week 28 — Validation Framework + Calibration

**Objective:** Build the historical validation and calibration layer. Backtest thesis engine on WC 2022 and WC 2018 data. Apply recalibration where triggered.

**Deliverables:**

`oracle/validation/calibration.py`
`compute_calibration_report(thesis_log)` → `CalibrationReport`
Brier Score per market per confidence band.
Reliability diagram data (for visualization).
CLV by contrarian classification.
Hit rate with average market price context.
Monotonicity check on calibration curves.

`oracle/validation/backtester.py`
`backtest_thesis_engine(historical_fixtures, historical_odds, historical_outcomes)` → `BacktestReport`
Applies thesis generation + ranking logic to WC 2022 fixtures (using historical odds from Odds API historical tier).
Computes all validation metrics.
Identifies markets and confidence bands where performance is below threshold.
Outputs recalibration recommendations.

`oracle/validation/recalibrator.py`
Where Brier Score or CLV metrics trigger recalibration (Section 9.3 thresholds):
Applies isotonic regression to model probability outputs for flagged markets.
Re-runs backtester on recalibrated outputs to confirm improvement.

`data/artifacts/calibration_report.json`
Published per-tournament calibration snapshot.
Accessible from `/methodology` page as credibility evidence.

Frontend: `frontend/src/pages/methodology.astro`
Add Betting Thesis Engine section.
Explain: how theses are generated, what Opportunity Score measures, what Contrarian classifications mean, what the validation framework tracks.
Display calibration report summary: "In backtesting on WC 2022 data, featured theses (Opportunity Score > 65) showed X% positive CLV on [N] resolved markets."

`tests/test_calibration.py`
Calibration report generates without error on full WC 2022 fixture set.
Brier Score recorded for each market.
CLV by contrarian class is computed and stored.
No forbidden language in any generated explanation.

---

*End of BETTING_THESIS_ENGINE.md*
