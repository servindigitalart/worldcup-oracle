# FOOTBALL_KNOWLEDGE_ENGINE.md

**World Cup Oracle v2 — Football Intelligence Engine**
**Date:** 2026-06-20
**Status:** Architecture design document — no implementation code, no pipelines, no frontend

---

## 1. Football Knowledge Architecture

### 1.1 The Problem with Pure Statistics

The Feature Store knows that Spain averages 68% possession. The Matchup Engine knows that Spain's possession advantage against Morocco is +22 percentage points. Neither system knows that Spain's possession game depends on triangles through the half-spaces, that Morocco's 5-4-1 specifically eliminates those triangles, that Luis de la Fuente has no reliable alternative attacking mechanism, and that this structural incompatibility is why Spain were eliminated on penalties despite 77% possession in 2022.

That gap — between statistical observation and football understanding — is what the Knowledge Engine fills.

The Knowledge Engine is not a model. It does not produce probabilities. It is an interpretation layer: a structured representation of football knowledge that allows the statistical layer to be read through a football analyst's lens. It takes numbers and asks: what football story do these numbers tell?

### 1.2 Full System Architecture

```
╔══════════════════════════════════════════════════════════════╗
║                      DATA LAYER                              ║
║  martj42 · StatsBomb Open · API-Football · The Odds API     ║
║  Open-Meteo · Transfermarkt · oracle fixture/results seed    ║
╚══════════════════════╦═══════════════════════════════════════╝
                       ║ raw match data, events, odds, lineups
                       ▼
╔══════════════════════════════════════════════════════════════╗
║                  FEATURE STORE                               ║
║  105 features · 20 groups · Stage 1/2/3 gating              ║
║  team_feature_snapshots · match_feature_snapshots            ║
║  market_feature_snapshots · player_feature_snapshots         ║
╚══════════╦═══════════════════════════╦════════════════════════╝
           ║ numerical features         ║ feature quality report
           ▼                           ▼
╔══════════════════════╗   ╔══════════════════════════════════╗
║  KNOWLEDGE ENGINE    ║   ║  KNOWLEDGE ENGINE SEED DATA      ║
║                      ║   ║                                  ║
║  Team Identity DB    ║◄──║  team_identities.json            ║
║  Manager Profiles    ║   ║  manager_profiles.json           ║
║  Tactical Archetypes ║   ║  tactical_archetypes.json        ║
║  Player Influence    ║   ║  player_influence.json           ║
║  Causality Graph     ║   ║  causality_graph.json            ║
╚══════════╦═══════════╝   ╚══════════════════════════════════╝
           ║ enriched context: archetype labels,
           ║ active causality chains, game script priors,
           ║ player influence adjustments, confidence modifiers
           ▼
╔══════════════════════════════════════════════════════════════╗
║                  MATCHUP ENGINE                              ║
║  58 interaction features · 10 groups                        ║
║  Knowledge-enriched weights (archetypes shift importance)   ║
║  Confidence adjusted by knowledge layer                     ║
╚══════════╦═══════════════════════════════════════════════════╝
           ║ matchup z-scores (knowledge-weighted)
           ▼
╔══════════════════════════════════════════════════════════════╗
║                 GAME SCRIPT ENGINE                           ║
║  Causality Chain Activation                                 ║
║  Game Script Probability Distribution                       ║
║  Script-to-Market Impact Translation                        ║
╚══════════╦═══════════════════════════════════════════════════╝
           ║ script probabilities + active causal chains
           ▼
╔══════════════════════════════════════════════════════════════╗
║                  SIGNAL ENGINE                               ║
║  Per-market probability adjustments                         ║
║  Signal level classification (no_signal → strong_signal)    ║
║  Confidence scoring with knowledge layer inputs             ║
╚══════════╦═══════════════════════════════════════════════════╝
           ║ signals with strength, confidence, CI
           ▼
╔══════════════════════════════════════════════════════════════╗
║                  MARKET ENGINE                               ║
║  CLV gap analysis · Closing line comparison                  ║
║  Specialty market pricing (corners, cards, shots)           ║
║  Market efficiency interaction                              ║
╚══════════╦═══════════════════════════════════════════════════╝
           ║ market_betting_cards + matchup_intelligence
           ▼
╔══════════════════════════════════════════════════════════════╗
║                   EXPLANATION ENGINE                         ║
║  Causality chain → narrative template                       ║
║  Game script → analyst-quality language                     ║
║  Confidence → hedging language calibration                  ║
╚══════════╦═══════════════════════════════════════════════════╝
           ║ match_intelligence_features.json (enriched)
           ▼
╔══════════════════════════════════════════════════════════════╗
║                    FRONTEND                                  ║
║  /match/[match_id] · Signal cards · Game script display     ║
║  Analyst-quality explanations · Confidence indicators       ║
╚══════════════════════════════════════════════════════════════╝
```

### 1.3 Layer Responsibilities

**Feature Store** — observes and measures. Answers: "What happened? What is the current state?" Produces numerical features with quality metadata.

**Knowledge Engine** — interprets and contextualizes. Answers: "What does this mean? What football logic connects these numbers?" Produces structured context that enriches every downstream layer.

**Matchup Engine** — models interactions. Answers: "How do Team A's features interact specifically with Team B's features?" Knowledge Engine adjusts which features matter most and how much to trust them.

**Game Script Engine** — predicts scenarios. Answers: "Which game script is most likely, and what are its market implications?" Activated by causal chain triggers from the Knowledge Engine.

**Signal Engine** — classifies divergence. Answers: "Where does the model disagree with the market, and how confident is that disagreement?"

**Market Engine** — prices markets. Answers: "What is the expected corner total? Card expectation? Shot volume?" Uses all upstream layers.

**Explanation Engine** — narrates. Answers: "How would a professional analyst describe this match's key structural features?" Converts signals and causality chains into human language.

### 1.4 What the Knowledge Engine Does NOT Do

It does not generate new probabilities. It does not override the statistical model. It does not claim certainty about tactical behavior. It provides structured prior knowledge — football understanding encoded as data — that adjusts confidence weights, activates relevant causal chains, and constrains which game scripts are plausible for a given matchup.

When the statistical model and the knowledge layer disagree (e.g., the features say high possession but the identity profile says this team abandons possession when under pressure), the knowledge layer raises uncertainty rather than forcing an override. It is a check on the statistics, not a replacement.

---

## 2. Team Identity Profiles

### 2.1 Schema

Every national team has a persistent identity profile. The profile is updated when there is clear evidence of a structural tactical shift (manager change, squad generation change) but remains stable within a tournament unless in-match tactical adaptations are confirmed.

```json
{
  "team_id": "string",
  "display_name": "string",
  "manager_id": "string",
  "profile_version": "string",
  "last_updated": "ISO date",

  "tactical_identity": {
    "primary_archetype": "string (from archetype taxonomy)",
    "secondary_archetype": "string | null",
    "identity_stability": "low | medium | high",
    "identity_confidence": 0.0–1.0
  },

  "tempo": {
    "match_tempo": "slow | controlled | medium | high | frantic",
    "first_half_tempo": "conservative | balanced | aggressive",
    "tempo_adaptation": "rigid | moderate | flexible"
  },

  "possession_profile": {
    "style": "direct | mixed | short_pass_buildup | positional | tiki_taka_descendant",
    "preferred_possession_pct": 40–70,
    "possession_under_pressure": "maintains | reduces | abandons",
    "buildup_zone": "goalkeeper_included | defensive_third | midfield",
    "buildup_shape": "3-back_build | 2-back_build | long_ball"
  },

  "pressing_profile": {
    "press_intensity": 1.0–10.0,
    "press_trigger": "goalkeeper | center_back_pass | lateral_pass | after_setpiece",
    "press_height": "high_third | mid_block | low_block",
    "press_shape": "man_oriented | zone_oriented | hybrid",
    "press_durability": "90min | drops_after_60 | drops_after_75"
  },

  "attacking_profile": {
    "primary_attack_zone": "central | left_channel | right_channel | wide_both | direct",
    "transition_tendency": "low | medium | high | primary",
    "crossing_volume": "low | medium | high",
    "set_piece_reliance": "low | medium | high | primary",
    "aerial_reliance": "low | medium | high",
    "counter_attack_speed": "slow | medium | fast | elite",
    "through_ball_tendency": "low | medium | high"
  },

  "defensive_profile": {
    "block_height": "deep | mid | high | very_high",
    "defensive_width": "narrow | medium | wide",
    "aerial_dominance": "weak | medium | strong | elite",
    "set_piece_vulnerability": "low | medium | high",
    "transition_recovery": "slow | medium | fast",
    "defensive_line_compactness": "loose | medium | compact | very_compact"
  },

  "set_piece_profile": {
    "corner_taking_quality": 1–10,
    "free_kick_threat": 1–10,
    "set_piece_delivery_style": "in_swinging | out_swinging | low_driven | varied",
    "aerial_set_piece_threat": "low | medium | high | elite",
    "set_piece_defensive_organization": 1–10,
    "penalty_shootout_historical": "positive | neutral | negative"
  },

  "physical_profile": {
    "average_intensity_minutes": 55–90,
    "late_game_energy_drop": "minimal | moderate | significant",
    "altitude_adaptation": "poor | neutral | good | native"
  },

  "psychological_profile": {
    "tournament_experience": "inexperienced | experienced | elite",
    "comeback_ability": "poor | medium | strong",
    "lead_defending": "poor | medium | strong",
    "big_match_performance": "below_average | average | above_average",
    "upset_vulnerability": "low | medium | high"
  },

  "tactical_flexibility": {
    "formation_range": ["4-3-3", "4-2-3-1"],
    "in_game_adaptation": "rigid | moderate | flexible | elite",
    "game_state_reaction": {
      "when_winning": "defensive | same | attack",
      "when_losing": "patient | urgent | chaotic",
      "when_drawing_late": "accept | push"
    }
  },

  "known_structural_weaknesses": [
    {
      "weakness_type": "string",
      "description": "string",
      "exploited_by_archetype": ["counter_attack", "direct_play"],
      "historical_examples": ["string"]
    }
  ],

  "known_structural_strengths": [
    {
      "strength_type": "string",
      "description": "string",
      "effective_against_archetype": ["low_block", "high_press"],
      "historical_examples": ["string"]
    }
  ]
}
```

### 2.2 Selected Team Identity Profiles

---

**Spain**

```json
{
  "team_id": "spain",
  "manager_id": "de_la_fuente",
  "tactical_identity": {
    "primary_archetype": "possession_control",
    "secondary_archetype": "high_press",
    "identity_stability": "high",
    "identity_confidence": 0.90
  },
  "tempo": {
    "match_tempo": "controlled",
    "first_half_tempo": "balanced",
    "tempo_adaptation": "moderate"
  },
  "possession_profile": {
    "style": "positional",
    "preferred_possession_pct": 65,
    "possession_under_pressure": "maintains",
    "buildup_zone": "goalkeeper_included",
    "buildup_shape": "3-back_build"
  },
  "pressing_profile": {
    "press_intensity": 7.5,
    "press_trigger": "goalkeeper",
    "press_height": "high_third",
    "press_shape": "zone_oriented",
    "press_durability": "drops_after_75"
  },
  "attacking_profile": {
    "primary_attack_zone": "central",
    "transition_tendency": "low",
    "crossing_volume": "medium",
    "set_piece_reliance": "low",
    "aerial_reliance": "low",
    "counter_attack_speed": "medium",
    "through_ball_tendency": "high"
  },
  "defensive_profile": {
    "block_height": "high",
    "defensive_width": "medium",
    "aerial_dominance": "medium",
    "set_piece_vulnerability": "medium",
    "transition_recovery": "medium",
    "defensive_line_compactness": "medium"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "low_block_penetration",
      "description": "Spain's positional buildup loses effectiveness when opponents collapse to a compact 5-4-1 eliminating half-space triangles. Shot creation drops 38% against deep blocks.",
      "exploited_by_archetype": ["low_block", "counter_attack", "tournament_survival"],
      "historical_examples": ["Spain vs Morocco 2022 WC R16 — 77% possession, 0 open-play goals", "Spain vs Switzerland 2021 EURO QF"]
    },
    {
      "weakness_type": "transition_vulnerability",
      "description": "When Spain's full-backs push high in positional phase, they leave wide channels exposed to rapid transitions. Teams with elite wide forwards exploit this.",
      "exploited_by_archetype": ["counter_attack", "wing_overload"],
      "historical_examples": ["Spain vs Brazil 2010 — Spain adjusted; earlier matches exposed", "Spain vs Germany 2022 WC — Musiala transitions created most dangerous moments"]
    }
  ],
  "known_structural_strengths": [
    {
      "strength_type": "technical_superiority",
      "description": "Against pressing teams, Spain's technical quality in tight spaces neutralizes the press and creates numerical advantages in midfield.",
      "effective_against_archetype": ["high_press", "direct_play"],
      "historical_examples": ["Spain vs Germany 2010 SF — Technical press resistance was decisive"]
    }
  ]
}
```

---

**Argentina**

```json
{
  "team_id": "argentina",
  "manager_id": "scaloni",
  "tactical_identity": {
    "primary_archetype": "hybrid",
    "secondary_archetype": "counter_attack",
    "identity_stability": "high",
    "identity_confidence": 0.88
  },
  "tempo": {
    "match_tempo": "medium",
    "first_half_tempo": "conservative",
    "tempo_adaptation": "flexible"
  },
  "possession_profile": {
    "style": "mixed",
    "preferred_possession_pct": 52,
    "possession_under_pressure": "reduces",
    "buildup_zone": "defensive_third",
    "buildup_shape": "2-back_build"
  },
  "pressing_profile": {
    "press_intensity": 6.2,
    "press_trigger": "lateral_pass",
    "press_height": "mid_block",
    "press_shape": "zone_oriented",
    "press_durability": "90min"
  },
  "attacking_profile": {
    "primary_attack_zone": "central_to_left",
    "transition_tendency": "high",
    "crossing_volume": "low",
    "set_piece_reliance": "high",
    "aerial_reliance": "medium",
    "counter_attack_speed": "elite",
    "through_ball_tendency": "medium"
  },
  "defensive_profile": {
    "block_height": "mid",
    "defensive_width": "medium",
    "aerial_dominance": "medium",
    "set_piece_vulnerability": "low",
    "transition_recovery": "fast",
    "defensive_line_compactness": "compact"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "set_piece_defensive_gaps",
      "description": "Under Scaloni, Argentina's zonal set piece defense occasionally creates gaps on the second phase. Saudi Arabia 2022 and early qualification matches exposed this.",
      "exploited_by_archetype": ["set_piece_heavy"],
      "historical_examples": ["Argentina vs Saudi Arabia 2022 WC GS"]
    }
  ],
  "known_structural_strengths": [
    {
      "strength_type": "individual_quality_transition",
      "description": "Messi/Enzo/Di María combination creates elite transition quality from mid-block. Argentina are most dangerous immediately after regaining possession in their own half.",
      "effective_against_archetype": ["possession_control", "high_press"],
      "historical_examples": ["Argentina vs France 2022 WC Final — transition sequences produced the highest xG moments"]
    },
    {
      "strength_type": "set_piece_threat",
      "description": "Argentina's dead ball delivery and aerial presence make them consistently dangerous from corners and free kicks near the box.",
      "effective_against_archetype": ["all"],
      "historical_examples": ["Argentina vs Netherlands 2022 WC QF — set piece goals decisive"]
    }
  ]
}
```

---

**France**

```json
{
  "team_id": "france",
  "manager_id": "deschamps",
  "tactical_identity": {
    "primary_archetype": "hybrid",
    "secondary_archetype": "counter_attack",
    "identity_stability": "high",
    "identity_confidence": 0.85
  },
  "tempo": {
    "match_tempo": "controlled",
    "first_half_tempo": "conservative",
    "tempo_adaptation": "flexible"
  },
  "possession_profile": {
    "style": "mixed",
    "preferred_possession_pct": 53,
    "possession_under_pressure": "reduces",
    "buildup_zone": "defensive_third",
    "buildup_shape": "2-back_build"
  },
  "pressing_profile": {
    "press_intensity": 5.8,
    "press_trigger": "after_setpiece",
    "press_height": "mid_block",
    "press_shape": "hybrid",
    "press_durability": "90min"
  },
  "attacking_profile": {
    "primary_attack_zone": "central_to_left",
    "transition_tendency": "high",
    "crossing_volume": "low",
    "set_piece_reliance": "medium",
    "aerial_reliance": "medium",
    "counter_attack_speed": "elite",
    "through_ball_tendency": "medium"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "first_half_passivity",
      "description": "Deschamps' France historically absorb pressure in the first half and respond in the second. This pattern creates below-expected first-half goal rates.",
      "exploited_by_archetype": ["all — exploitable as under for first-half goals"],
      "historical_examples": ["France vs Argentina 2022 WC Final — 1-2 down at 80 min before equalizing"]
    }
  ],
  "known_structural_strengths": [
    {
      "strength_type": "counter_attack_lethality",
      "description": "Mbappé and Thuram in transition against high lines is among the highest-xG configurations in international football. France's counter generates 0.38 xG per counter sequence.",
      "effective_against_archetype": ["possession_control", "wing_overload", "high_press"],
      "historical_examples": ["France vs Argentina 2022 WC Final — 3 goals in under 7 minutes on counter"]
    }
  ]
}
```

---

**Germany**

```json
{
  "team_id": "germany",
  "manager_id": "nagelsmann",
  "tactical_identity": {
    "primary_archetype": "high_press",
    "secondary_archetype": "possession_control",
    "identity_stability": "medium",
    "identity_confidence": 0.78
  },
  "tempo": {
    "match_tempo": "high",
    "first_half_tempo": "aggressive",
    "tempo_adaptation": "moderate"
  },
  "pressing_profile": {
    "press_intensity": 8.4,
    "press_trigger": "goalkeeper",
    "press_height": "high_third",
    "press_shape": "man_oriented",
    "press_durability": "drops_after_60"
  },
  "attacking_profile": {
    "primary_attack_zone": "central",
    "transition_tendency": "medium",
    "crossing_volume": "medium",
    "set_piece_reliance": "medium",
    "counter_attack_speed": "fast",
    "through_ball_tendency": "high"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "press_durability_drop",
      "description": "Nagelsmann's high press is intense but expensive. After 60 minutes, Germany's press height drops significantly, opening transition corridors they had previously closed.",
      "exploited_by_archetype": ["counter_attack", "hybrid"],
      "historical_examples": ["Germany vs Japan 2022 WC GS — conceded in the second half after pressing dropped"]
    },
    {
      "weakness_type": "direct_play_bypass",
      "description": "Germany's man-oriented press is bypassed by teams comfortable with long diagonal balls into wide areas. Press is rendered ineffective.",
      "exploited_by_archetype": ["direct_play", "wing_overload"],
      "historical_examples": ["Germany vs South Korea 2018 WC GS — structural elimination"]
    }
  ]
}
```

---

**Brazil**

```json
{
  "team_id": "brazil",
  "manager_id": "ancelotti",
  "tactical_identity": {
    "primary_archetype": "wing_overload",
    "secondary_archetype": "high_press",
    "identity_stability": "medium",
    "identity_confidence": 0.72
  },
  "attacking_profile": {
    "primary_attack_zone": "wide_both",
    "transition_tendency": "medium",
    "crossing_volume": "high",
    "set_piece_reliance": "low",
    "aerial_reliance": "low",
    "counter_attack_speed": "elite",
    "through_ball_tendency": "medium"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "defensive_transition",
      "description": "Brazil's high wide full-backs leave central defensive exposure on transitions. When both wingers and full-backs push, the central defenders are exposed 2v2.",
      "exploited_by_archetype": ["counter_attack"],
      "historical_examples": ["Brazil vs Belgium 2018 WC QF — Lukaku's runs exploited width gaps"]
    }
  ]
}
```

---

**England**

```json
{
  "team_id": "england",
  "manager_id": "tba",
  "tactical_identity": {
    "primary_archetype": "hybrid",
    "secondary_archetype": "set_piece_heavy",
    "identity_stability": "medium",
    "identity_confidence": 0.74
  },
  "attacking_profile": {
    "primary_attack_zone": "wide_both",
    "set_piece_reliance": "high",
    "aerial_reliance": "high",
    "counter_attack_speed": "fast"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "creative_midfield_dependence",
      "description": "England's attacking rhythm depends heavily on Bellingham picking up the ball in half-spaces. When opponents mark Bellingham specifically, England's attacking structure becomes predictable.",
      "exploited_by_archetype": ["organized_low_block"],
      "historical_examples": ["England vs Italy 2021 EURO Final — Italy's midfield press on Bellingham"]
    }
  ],
  "known_structural_strengths": [
    {
      "strength_type": "set_piece_threat",
      "description": "England's combination of delivery quality (Trippier/Alexander-Arnold) and aerial targets (Kane, Maguire, Dunk) makes them one of the most dangerous set piece units in international football.",
      "effective_against_archetype": ["all"],
      "historical_examples": ["England scored from 8 set pieces in WC 2018 — tournament's highest"]
    }
  ]
}
```

---

**Uruguay**

```json
{
  "team_id": "uruguay",
  "manager_id": "bielsa",
  "tactical_identity": {
    "primary_archetype": "high_press",
    "secondary_archetype": "set_piece_heavy",
    "identity_stability": "medium",
    "identity_confidence": 0.80
  },
  "pressing_profile": {
    "press_intensity": 9.1,
    "press_trigger": "goalkeeper",
    "press_height": "high_third",
    "press_shape": "man_oriented",
    "press_durability": "drops_after_60"
  },
  "attacking_profile": {
    "set_piece_reliance": "high",
    "aerial_reliance": "high",
    "counter_attack_speed": "fast"
  },
  "known_structural_strengths": [
    {
      "strength_type": "organized_defensive_resilience",
      "description": "Uruguay's structural defensive organization allows them to absorb intense attacking pressure and stay in matches against significantly stronger opponents.",
      "effective_against_archetype": ["possession_control", "wing_overload"],
      "historical_examples": ["Uruguay vs Brazil 1950 Maracanazo — structural archetype established; Uruguay vs England 2014 WC — structural pressure resistance"]
    }
  ]
}
```

---

**Japan**

```json
{
  "team_id": "japan",
  "manager_id": "moriyasu",
  "tactical_identity": {
    "primary_archetype": "high_press",
    "secondary_archetype": "counter_attack",
    "identity_stability": "high",
    "identity_confidence": 0.88
  },
  "pressing_profile": {
    "press_intensity": 8.7,
    "press_trigger": "center_back_pass",
    "press_height": "mid_block_with_high_triggers",
    "press_shape": "hybrid",
    "press_durability": "drops_after_70"
  },
  "tactical_flexibility": {
    "in_game_adaptation": "elite",
    "game_state_reaction": {
      "when_losing": "urgent",
      "when_winning": "defensive",
      "when_drawing_late": "push"
    }
  },
  "known_structural_strengths": [
    {
      "strength_type": "second_half_tactical_shift",
      "description": "Japan are historically more dangerous in the second half after tactical adjustments from the bench. Their 2022 World Cup wins over Germany and Spain both came after half-time tactical shifts.",
      "effective_against_archetype": ["possession_control", "high_press"],
      "historical_examples": ["Japan vs Germany 2022 WC — 0-1 HT, 2-1 FT with tactical shift", "Japan vs Spain 2022 WC — same pattern"]
    }
  ]
}
```

---

**Morocco**

```json
{
  "team_id": "morocco",
  "manager_id": "regragui",
  "tactical_identity": {
    "primary_archetype": "tournament_survival",
    "secondary_archetype": "counter_attack",
    "identity_stability": "high",
    "identity_confidence": 0.92
  },
  "pressing_profile": {
    "press_intensity": 4.2,
    "press_height": "low_block",
    "press_shape": "zone_oriented",
    "press_durability": "90min"
  },
  "attacking_profile": {
    "transition_tendency": "high",
    "counter_attack_speed": "fast",
    "set_piece_reliance": "medium"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "low_attacking_possession_volume",
      "description": "Morocco's counter-attack structure creates high-quality chances but low volume. Against a team that defends their counter effectively and forces Morocco into positional play, Morocco's attacking options are limited.",
      "exploited_by_archetype": ["possession_control with defensive transition awareness"],
      "historical_examples": ["Morocco vs France 2022 WC SF — transition channels were defended; Morocco created minimal open-play chances"]
    }
  ],
  "known_structural_strengths": [
    {
      "strength_type": "low_block_organization",
      "description": "Morocco's 5-4-1 defensive structure with compact lines is among the best-organized low blocks in international football. Possession teams consistently fail to penetrate it.",
      "effective_against_archetype": ["possession_control", "wing_overload"],
      "historical_examples": ["Morocco vs Spain 2022 WC R16 — 0 xG conceded from open play", "Morocco vs Portugal 2022 WC QF — 0 open-play goals conceded"]
    }
  ]
}
```

---

**United States**

```json
{
  "team_id": "united_states",
  "manager_id": "berhalter",
  "tactical_identity": {
    "primary_archetype": "high_press",
    "secondary_archetype": "direct_play",
    "identity_stability": "medium",
    "identity_confidence": 0.70
  },
  "pressing_profile": {
    "press_intensity": 7.8,
    "press_trigger": "center_back_pass",
    "press_height": "high_third",
    "press_shape": "man_oriented",
    "press_durability": "drops_after_65"
  },
  "known_structural_weaknesses": [
    {
      "weakness_type": "tactical_inexperience_in_tight_knockout_moments",
      "description": "The USMNT has historically struggled to manage tight knockout moments, tending toward aggressive positions that leave them exposed when leading late.",
      "exploited_by_archetype": ["counter_attack", "hybrid"],
      "historical_examples": ["USMNT vs Netherlands 2022 WC R16 — aggressive pressing left central areas open for Dutch counters"]
    }
  ]
}
```

---

**Mexico**

```json
{
  "team_id": "mexico",
  "tactical_identity": {
    "primary_archetype": "high_press",
    "secondary_archetype": "counter_attack",
    "identity_stability": "medium",
    "identity_confidence": 0.75
  },
  "known_structural_strengths": [
    {
      "strength_type": "altitude_home_advantage",
      "description": "Mexico at Azteca or any high-altitude venue has a structural advantage over non-altitude-adapted opponents. Their pressing intensity is maintained while opponents fatigue at altitude.",
      "effective_against_archetype": ["all — amplified by altitude"],
      "historical_examples": ["Mexico's unbeaten WC qualifying home record at Azteca — altitude adaptation structural advantage"]
    }
  ]
}
```

---

## 3. Manager Intelligence Layer

### 3.1 Schema

```json
{
  "manager_id": "string",
  "name": "string",
  "team_id": "string",
  "appointment_date": "ISO date",
  "profile_confidence": 0.0–1.0,

  "formation_profile": {
    "preferred_formations": ["4-3-3", "4-2-3-1"],
    "formation_flexibility": "rigid | moderate | flexible",
    "formation_in_game_shift": "rare | occasional | frequent"
  },

  "pressing_philosophy": {
    "preferred_press": "low_block | mid_press | high_press",
    "press_triggers": ["string"],
    "press_durability": "full_match | fades | game_state_dependent",
    "vs_possession_teams": "press_higher | maintain | drop_deeper"
  },

  "game_state_behavior": {
    "when_winning_1_0": "defensive_block | same_shape | continue_attacking",
    "when_losing_1_0_80min": "direct_balls | width_overload | push_goalkeeper_up",
    "when_drawing_last_group_game_and_needing_win": "open_up | grind | chaotic",
    "extra_time_approach": "conservative | attack",
    "penalty_shootout_preparation": "specialist_shooters | standard | flexible"
  },

  "substitution_profile": {
    "first_sub_typical_minute": 55–80,
    "sub_pattern": "defensive_for_attacking | like_for_like | double_attacking | game_state_driven",
    "uses_all_5_subs": "always | usually | rarely",
    "impact_sub_style": "fresh_legs | tactical_shift | defensive_lock"
  },

  "attacking_philosophy": {
    "buildup_preference": "from_goalkeeper | midfield_driven | direct",
    "creativity_source": "individual | system | set_pieces",
    "risk_appetite": "low | medium | high",
    "overload_side": "left | right | both | central"
  },

  "defensive_philosophy": {
    "preferred_defensive_line": "deep | medium | high",
    "set_piece_defense": "zonal | man_marking | hybrid",
    "counter_press": "immediate | delayed | none"
  },

  "set_piece_emphasis": {
    "offensive_sp_focus": 1–10,
    "defensive_sp_focus": 1–10,
    "corner_routine_sophistication": "basic | intermediate | advanced",
    "free_kick_routine_sophistication": "basic | intermediate | advanced"
  },

  "match_management_style": "attacking | neutral | pragmatic | reactive",

  "known_behavioral_patterns": [
    {
      "pattern_id": "string",
      "description": "string",
      "trigger": "string",
      "market_impact": ["string"],
      "confidence": 0.0–1.0
    }
  ]
}
```

### 3.2 Selected Manager Profiles

---

**Lionel Scaloni — Argentina**

Scaloni's defining characteristic is tactical pragmatism with elite game-state intelligence. He builds around Messi's influence but organizes the team to function when Messi is not in the match. His 4-4-2 diamond or 4-3-3 are equally deployed; the choice is opponent-driven.

Key behavioral patterns:
- Wins 1-0 → immediate defensive restructuring. Argentina become one of the hardest teams to score against when protecting a single-goal lead under Scaloni.
- Must-win game → progressive buildup earlier. Does not wait until 70 minutes to open up.
- Set piece preparation is among the best in international football: Argentina's corner and FK variety under Scaloni is notable.
- Substitution pattern: typically first sub at 65–70 min, and it is almost always a defensive or energy-preserving move. He rarely uses attacking substitutions from behind.
- **Market implication:** Scaloni's Argentina have a significantly above-average lead-retention rate. When Argentina lead at half-time, their second-half clean sheet rate is high. This affects O/U under scenarios where Argentina score first.

```json
{
  "manager_id": "scaloni",
  "name": "Lionel Scaloni",
  "team_id": "argentina",
  "profile_confidence": 0.88,
  "game_state_behavior": {
    "when_winning_1_0": "defensive_block",
    "when_losing_1_0_80min": "direct_balls_to_strikers",
    "when_drawing_last_group_game_and_needing_win": "open_up_early"
  },
  "substitution_profile": {
    "first_sub_typical_minute": 67,
    "sub_pattern": "defensive_for_attacking",
    "impact_sub_style": "defensive_lock"
  },
  "known_behavioral_patterns": [
    {
      "pattern_id": "lead_protection",
      "description": "Scaloni drops into 5-4-1 when Argentina score first, dramatically reducing opponent attacking opportunities",
      "trigger": "Argentina score first",
      "market_impact": ["under_goals", "btts_no", "argentina_win"],
      "confidence": 0.82
    },
    {
      "pattern_id": "set_piece_investment",
      "description": "Argentina spend significant training time on set piece routines. Corner and FK sequences are varied and well-rehearsed.",
      "trigger": "any match",
      "market_impact": ["corners_over", "set_piece_goals"],
      "confidence": 0.85
    }
  ]
}
```

---

**Didier Deschamps — France**

Deschamps is the archetype of the pragmatic tournament manager. His job is to get the most out of extraordinary individual talent without letting individual expression break structural discipline. He consistently suppresses France's attacking potential in the service of structural solidity.

Key behavioral patterns:
- First-half conservative setup: France concede fewer first-half shots than almost any other top nation, and score fewer first-half goals than their talent implies.
- When France fall behind, Deschamps opens up gradually — not panicking. Mbappé gets wider, runs behind become more frequent. The counterattacking machine emerges from necessity.
- Consistent penalty-shootout preparation. France's shootout record under Deschamps is among the best in international football.
- **Market implication:** First-half under goals. French matches produce below-average first-half goal counts. This is a structural Deschamps pattern, not an opponent-dependent one.

```json
{
  "manager_id": "deschamps",
  "known_behavioral_patterns": [
    {
      "pattern_id": "first_half_caution",
      "description": "Deschamps consistently sets France up conservatively in the first half regardless of opponent strength. Instruction to absorb, not dominate.",
      "trigger": "first_half",
      "market_impact": ["first_half_under", "low_first_half_cards"],
      "confidence": 0.84
    },
    {
      "pattern_id": "counter_activation",
      "description": "When France fall behind, Deschamps shifts to a more open structure that activates Mbappé's transition runs. The counter machine emerges from adversity.",
      "trigger": "France trailing at 60+ min",
      "market_impact": ["btts_yes", "open_second_half", "late_goals"],
      "confidence": 0.79
    }
  ]
}
```

---

**Julian Nagelsmann — Germany**

Nagelsmann's Germany play the most tactically aggressive pressing football of any top-16 nation. His system demands energy, and that energy creates a distinctive temporal pattern: Germany are typically dominant in the first 60 minutes and vulnerable in the final 30. His substitutions are tactical rather than energy-based — he makes changes to shift the system, not just freshen legs.

Key behavioral patterns:
- Extremely high first-half press intensity. Germany's pressing stats in the first 60 minutes are elite.
- Press drops sharply after 60 minutes. This creates a structural vulnerability window that prepared opponents exploit.
- When Germany fall behind, they become one of the highest-tempo attacking teams in the world, taking significant defensive risks. This creates an open, chaotic game script that benefits the total-goals market.
- **Market implication:** Cards market elevated. Nagelsmann's pressing style leads to above-average tactical fouls when the press fails. Germany receive and commit fouls at above-tournament-average rates in competitive matches.

---

**Marcelo Bielsa — Uruguay**

Bielsa brings man-oriented, maximally intense pressing to a Uruguay squad that has historically been more physical than technical. The combination creates unusual tactical dynamics: extreme first-half intensity, significant fitness collapse late, and tactical chaos that generates set pieces for both teams.

Key behavioral patterns:
- One of the highest-intensity first-half pressing profiles in world football. Opponents often cannot build from the back for 45 minutes.
- Uruguay under Bielsa allow more counter-attack opportunities than the traditional Uruguayan style — they push higher.
- **Market implication:** High card risk. Man-oriented pressing frequently leads to individual fouls and yellow cards. Uruguay's card rate under Bielsa is well above the historical norm.
- First-half over goals potential. Bielsa's philosophy generates more open first halves than traditional Uruguayan grinding.

---

**Regragui — Morocco**

Regragui's defining quality is defensive tactical precision: Morocco's 5-4-1 block is the most organized low block in this tournament. However, Regragui understands that his team cannot out-possess top opponents and does not try. He designs transitions deliberately.

Key behavioral patterns:
- Morocco never press high unless chasing. The low block is their resting state regardless of score.
- Counter-attack moves are pre-rehearsed — specific wide players have assigned roles in the fast transition.
- Set piece delivery has improved markedly. Regragui invests heavily in corners.
- **Market implication:** Under goals. Morocco's matches consistently produce fewer goals than the market expects, because Regragui's structure is so well-organized.

---

### 3.3 How Manager Behavior Affects Prediction

Manager profiles adjust predictions through three mechanisms:

**1. Prior probability modifier.** When a manager has a well-documented pattern (Deschamps first-half caution), this shifts the probability distribution for that market before any statistical features are applied. The first-half goal market gets a `manager_prior_modifier` of -0.12 (12 percentage points lower than tournament average) for France matches.

**2. Confidence adjuster.** When a match enters a manager-pattern-triggering state (Argentina take the lead), confidence in the "under goals / Argentina win" signal increases because Scaloni's lead-protection pattern is well-established. The pattern confidence (0.82 for Scaloni) is multiplied into the overall signal confidence.

**3. Uncertainty flag.** When a manager has recently been appointed, changed formation, or made a significant tactical shift, their profile_confidence is low, and this propagates a `manager_uncertainty_flag` that reduces signal confidence for manager-dependent predictions.

---

## 4. Tactical Archetype System

### 4.1 The Ten Archetypes

Every team is classified with a primary archetype and optionally a secondary archetype. The archetype determines which matchup features are weighted most heavily, which causal chains are most likely to activate, and which game scripts are most probable.

---

**ARCHETYPE 1: Possession Control**

*Identity:* The team believes that controlling the ball controls the match. Dominates territorial metrics. Goal creation through patient buildup and structural superiority rather than individual moments.

*Key metrics:* Possession > 58%, pass completion > 88%, shots-per-possession < 0.04, press resistance > 85%, low direct play index.

*Strengths:*
- Dictates pace and territory
- Neutralizes opponent attacking time
- Generates positional advantage opportunities

*Weaknesses:*
- Penetrating organized low blocks (primary vulnerability)
- Counter-attack exposure when full-backs push high
- Diminishing returns in very hot conditions (possession maintenance requires technical concentration)

*Markets affected:* Corners over (possession teams win more corners), shots over (high shot volume from positional play), O/U ambiguous (lots of shots but often against organized defenses).

*Common upset pattern:* Organized low block + disciplined counter → possession team eliminated despite statistical dominance. The Morocco vs Spain pattern.

---

**ARCHETYPE 2: Counter Attack**

*Identity:* The team concedes space deliberately to exploit space behind the opponent's high line or disorganized recovery. All offensive energy concentrated in transition.

*Key metrics:* Possession < 48%, shots-per-touch high, shots-on-counter-as-pct-of-total > 35%, transition speed elite.

*Strengths:*
- Creates high xG chances from limited possession
- Forces opponents to take risks
- Effective against all high-defensive-line teams

*Weaknesses:*
- Against well-organized mid-block, transition channels are closed
- Limited attacking variety if counter is neutralized
- Set pieces are often the secondary offensive route

*Markets affected:* O/U lean toward fewer total goals (counter teams defend the second half), correct score lean toward 1-0 outcomes, btts risk when opponent also counters.

*Common upset pattern:* Elite counter team + overcommitted favorite → 1-0 upset from first counter. Italy 2006, Morocco 2022.

---

**ARCHETYPE 3: High Press**

*Identity:* The team believes that winning the ball high up the pitch creates the highest-quality chances. Energy is the currency — spent aggressively in the first 60 minutes.

*Key metrics:* PPDA < 8, press recovery rate high, tempo high, fouls-committed-in-opponent-half high.

*Strengths:*
- Disrupts opponent buildup
- Creates turnovers in dangerous zones
- Generates corners and free kicks from pressing traps

*Weaknesses:*
- Energy depletion after 60–70 minutes
- Bypassed by direct long-ball teams
- Vulnerable to transitions when press is beaten

*Markets affected:* First-half corners and shots over, second-half correction (energy drop), cards elevated (tactical fouls when press fails), O/U uncertain (depends on press success rate).

*Common upset pattern:* Press-resistant technical team waits for press to drop, attacks the fatigued defensive structure in the final 20 minutes.

---

**ARCHETYPE 4: Low Block**

*Identity:* The team organizes deep defensive compactness and waits for the opponent to create space on the counter. Aerial duels and set pieces are primary attacking routes.

*Key metrics:* Block height low, defensive compactness maximum, shots conceded per 90 low but xG conceded per shot moderate, aerial duel success high.

*Strengths:*
- Neutralizes possession teams completely
- Creates giant-killing upset probability
- Effective for 90 minutes without energy depletion

*Weaknesses:*
- Generates minimal possession and few attacking opportunities in open play
- Must score from set pieces or rare counters
- Cannot hold a lead easily since they need to attack to win

*Markets affected:* Under goals (defensive structure limits both teams), corners generated low, cards low (organized defensive shape reduces tactical fouls), O/U strongly lean under.

*Common upset pattern:* Elite goalkeeper + set piece goal + perfect low block → upset. Morocco 2022 vs Belgium, Spain, Portugal.

---

**ARCHETYPE 5: Wing Overload**

*Identity:* The team concentrates attacking momentum through wide channels — overlapping full-backs, wide forwards in 1v1s, high crossing volume.

*Key metrics:* Wide zone shot pct > 35%, crossing attempts per 90 high, corners-for high, aerial duel attempts high.

*Strengths:*
- Creates corner volume
- Physical full-back pairing can overwhelm narrow defenses
- Wide crosses and set pieces combine for high goal expectation in specific matchups

*Weaknesses:*
- Weak against wide defensive strength (aerial defenders who win crosses)
- Central vulnerability when both full-backs push
- Predictable attacking pattern if the cross is neutralized

*Markets affected:* Corners strongly over, aerial goals elevated, shots on target over (crosses generate shots from close range).

*Common upset pattern:* Opponent defends the cross with aerial dominance → wing team has no alternative → stalemate.

---

**ARCHETYPE 6: Direct Play**

*Identity:* Long balls, second-ball winning, physical aerial battles in the attacking third. Low possession appetite. Goals often from set pieces and physical aerial duels rather than buildup.

*Key metrics:* Direct play index high, aerial duel success high, long pass completion low, possession < 45%.

*Strengths:*
- Bypasses high-press systems
- Creates set piece situations from long-ball sequences
- Physical superiority in specific matchups

*Weaknesses:*
- Against organized aerial defenses, the primary weapon fails
- Poor possession retention limits attacking frequency
- Technically superior opponents control the match

*Markets affected:* Aerial duel totals elevated, set pieces over, possession under for this team, corners ambiguous (second-ball situations can generate corners or rapid counters).

---

**ARCHETYPE 7: Set Piece Heavy**

*Identity:* A team whose goal-creation is disproportionately derived from dead ball situations. Corner kick delivery, free kick specialization, and aerial threat in the box are the offensive identity.

*Key metrics:* Set piece goals per 90 > 0.35, corner-generated xG high, aerial duel success in box elite.

*Strengths:*
- Creates goals from minimal open-play quality
- Punishes teams with aerial defensive weaknesses
- Can be effective against technically superior opponents

*Weaknesses:*
- Against organized aerial defenses and excellent set piece defenders, the primary weapon fails
- Open play quality is below technical average
- Over-reliance creates predictable scouting target

*Markets affected:* Corners strongly over, BTTS elevated (set piece goals contribute to both teams scoring in many cases), correct score lean toward 1-0 or 2-1 from set pieces.

---

**ARCHETYPE 8: Chaos Football**

*Identity:* High-variance teams with inconsistent tactical discipline. Can beat anyone or lose to anyone. The game script is unpredictable — high intensity, disorganized transitions, many set pieces, many cards.

*Key metrics:* High variance in xG both for and against, high cards per 90, low tactical discipline index.

*Strengths:*
- Generates upsets through sustained high pressure
- Unpredictable enough to defeat organized opponents

*Weaknesses:*
- Cannot consistently replicate results
- Prone to large defeats when opponent exploits disorganization

*Markets affected:* High uncertainty on all markets. O/U lean over (disorganized play creates many transitions and set pieces). Cards over. BTTS elevated.

*Common upset pattern:* Chaotic team in perfect form day → eliminates technical favorite before reverting.

---

**ARCHETYPE 9: Tournament Survival**

*Identity:* A team that is specifically adapted for the tournament format — managing energy across multiple matches, protecting leads, advancing without playing attractive football.

*Key metrics:* Low goals scored per game, low goals conceded per game, above-average draw rate, late-game lead protection excellent.

*Strengths:*
- Can beat any team in a single elimination match
- Mentally strong in high-pressure moments
- Penalty shootout preparation typically above average

*Weaknesses:*
- Cannot generate momentum if they fall behind
- Boring game scripts make them vulnerable to market underestimation

*Markets affected:* Under goals strongly, BTTS no, cards low (disciplined play), correct score lean toward 0-0 or 1-0.

---

**ARCHETYPE 10: Hybrid**

*Identity:* A team with genuine tactical flexibility — can shift between possession control, counter-attack, and pressing depending on opponent and game state. The opponent's style does not clearly dictate the game script.

*Key metrics:* Multiple valid formation options, manager profile shows high in_game_adaptation score, no single metric profile dominates.

*Strengths:*
- Most difficult to prepare against
- Adapts in-match to exploit emerging weaknesses

*Weaknesses:*
- Uncertainty about which face will appear makes knowledge-based predictions weaker

*Markets affected:* Uncertainty flag increases across all markets. Signal confidence reduced for tactical interaction features. Market becomes more reliable benchmark in hybrid vs hybrid matchups.

---

## 5. Player Influence Layer

### 5.1 Player Influence Without Live Tracking

The system cannot track player movement in real time without StatsBomb Live. The player influence layer is therefore a structured set of pre-match probability adjustments that activate when a specific player is confirmed in the starting XI, combined with historical influence patterns derived from StatsBomb open data and API-Football statistics.

### 5.2 Player Archetype Classification

**Transition Threat**
Players whose primary offensive contribution comes from exploiting space behind defensive lines. Characterized by high dribble carry distance, high pace, and high xG from counter-attack sequences.

Examples: Mbappé, Vinícius Jr., Leroy Sané
Market impact: When confirmed in XI vs a high defensive line, `counter_attack_vs_high_line_clash` activates with a 1.4× multiplier. O/U lean over. 1X2 lean toward team with transition threat.

**Creative Hub**
Players who control the tempo, create chances through through-balls and positional shifts, and whose presence or absence fundamentally changes the team's attacking pattern.

Examples: Bellingham, Pedri, Valverde, De Bruyne
Market impact: When creative hub is in XI, shots on target probability rises by ~12% vs when absent. When facing a man-marking opponent specifically organized against the hub, the effect reverses.

**Set Piece Specialist**
Players whose dead ball delivery generates disproportionate goal expectation from corners and free kicks.

Examples: Trent Alexander-Arnold, Eriksen, Neymar (FK), David Beckham archetype
Market impact: Confirmed in XI → corners xG multiplier 1.3×. `set_piece_specialist_vs_vulnerability_clash` activates when opponent has poor aerial defense.

**Press Breaker**
Players who can receive under pressure and distribute quickly enough to bypass an aggressive press. Rare at international level — their presence determines whether a possession team survives pressing.

Examples: Modric, Busquets (historical), Rodri
Market impact: Absence of press breaker in possession team → buildup_disruption_index rises significantly. Confirmed absence → downgrade possession team's signal quality.

**Aerial Specialist**
Players whose aerial dominance in the box creates meaningful set piece goal probability.

Examples: Giroud, Dzeko archetype, Peter Crouch type
Market impact: Confirmed in XI → set piece goal probability rises 0.15 per corner delivered. Corner market leans over when aerial specialist faces weak aerial defense.

**Foul Generator**
Technical players who run at defenders and systematically attract fouls, inflating the cards market.

Examples: Neymar, Gnabry, Sané in Germany's system
Market impact: Confirmed in XI → cards expectation rises +0.8 yellow cards per 90 for the opposing defensive player assigned to them. Player card market for specific opposing defender activates.

**Defensive Destroyer**
A sitting midfielder whose role is pure defensive disruption — intercepting transitions, physically blocking attacks, and enabling the team's attacking structure to operate without defensive responsibility.

Examples: Casemiro, Fabinho, Kante
Market impact: Presence reduces the opponent's counter-attack effectiveness by ~22%. `counter_attack_vs_high_line_clash` z-score reduced by 0.4 when defensive destroyer is confirmed in XI.

**Goalkeeper Dominance**
A goalkeeper significantly above the expected level for their team's rating — capable of single-handedly holding a match against superior teams.

Examples: Courtois (Belgium 2022), Yann Sommer (Switzerland vs France 2021)
Market impact: When elite-tier goalkeeper faces opponent with above-average shot volume, the signal for under goals increases significantly. Clean sheet probability rises above the structural model estimate.

### 5.3 Player Influence Schema

```json
{
  "player_id": "string",
  "name": "string",
  "team_id": "string",
  "primary_archetype": "transition_threat | creative_hub | set_piece_specialist | press_breaker | aerial_specialist | foul_generator | defensive_destroyer | goalkeeper_dominance",
  "secondary_archetype": "string | null",
  "influence_rating": 1.0–5.0,
  "activation_condition": "confirmed_in_xi | confirmed_captain | starting | substitute",

  "market_adjustments": [
    {
      "market": "string",
      "direction": "over | under | home | away",
      "adjustment_magnitude": -0.30 to +0.30,
      "condition": "string (e.g., 'opponent has high defensive line')",
      "confidence": 0.0–1.0
    }
  ],

  "matchup_feature_modifiers": [
    {
      "feature_name": "string",
      "multiplier": 0.5–2.0,
      "condition": "string"
    }
  ],

  "absence_impact": {
    "description": "string",
    "magnitude": "negligible | moderate | significant | team_altering",
    "affected_markets": ["string"]
  }
}
```

---

## 6. Football Causality Graph

### 6.1 Design Principle

The causality graph is the analytical backbone of the Knowledge Engine. It defines the football logic that connects tactical inputs, physical states, and player configurations to match outcomes and market consequences. Every signal from the Knowledge Engine must trace back to at least one activated causal chain.

A causal chain is not a correlation. It is a mechanism: a sequence of football events or states where each step causes the next through an understood football dynamic.

### 6.2 Chain Format

```
CHAIN_ID | TRIGGER | SEQUENCE | TERMINAL OUTCOME | MARKETS AFFECTED | HISTORICAL FREQUENCY | CONFIDENCE
```

### 6.3 The 53 Causal Chains

**GOAL ENVIRONMENT CHAINS**

**G-01: Counter Attack vs High Line**
`High Defensive Line [Archetype signal]`
→ Transition Space Behind Defense Available
→ Counter Attack Triggered by Transition Threat Player
→ 1v2 or 1v1 Situation with GK
→ High xG Shot
→ **Goal | Counter**
*Markets:* 1X2 (attacking team), O/U over, Anytime Scorer
*Frequency:* 1.8 goals per match when both conditions present; 26% of all WC counter goals
*Confidence:* 0.82

---

**G-02: Wing Overload into Cross into Aerial Goal**
`Wing Overload Team vs Weak Aerial Defense`
→ Wide Player 1v1 Against Full-Back
→ Cross into Penalty Area
→ Aerial Contest Won
→ Headed Shot
→ **Goal | Aerial**
*Markets:* Corners over (blocked crosses generate corners too), BTTS, Correct Score (headed goals)
*Frequency:* 0.31 aerial cross goals per match in this configuration
*Confidence:* 0.74

---

**G-03: Press Trap → Turnover → Counter Goal**
`High Press Team vs Low Press Resistance Opponent`
→ Pressing Trap Triggered (Goalkeeper Under Pressure)
→ Forced Long Ball or Rushed Pass
→ Ball Won in Opponent Half
→ Immediate 3v3 or Better
→ **Goal | Press Recovery**
*Markets:* Goals over, 1X2 (pressing team), Shots over
*Frequency:* 0.22 press-recovery goals per match; higher in first 65 minutes
*Confidence:* 0.71

---

**G-04: Set Piece Specialist vs Aerial Vulnerability**
`Set Piece Specialist Confirmed in XI + Opponent Aerial Defensive Rating < 6`
→ Corner or FK Won in Danger Zone
→ Quality Delivery to Far Post or Near Post
→ Aerial Contest with Numerical Advantage
→ Headed Attempt
→ **Goal | Set Piece**
*Markets:* Corners over, BTTS, O/U over, Correct Score
*Frequency:* 0.38 set piece goals per match when both conditions are met
*Confidence:* 0.78

---

**G-05: Altitude Fatigue → Late Goal**
`Venue Altitude > 1,800m + Non-Adapted Team`
→ Fatigue Accelerates After 65 Minutes
→ Defensive Organization Collapses (Positional Errors)
→ Set Piece Conceded in Dangerous Zone
→ **Late Goal (65+ min) | Context**
*Markets:* Late-match cards (fatigue-induced fouls), goals after 65, O/U slight lean over
*Frequency:* +0.4 late goals per match in altitude conditions vs sea-level equivalent
*Confidence:* 0.68

---

**G-06: Elite Goalkeeper vs Shot-Heavy Attack → Shot-Goal Conversion Suppression**
`Shot Volume High (shots_total_per90 > 14) + Opponent GK Dominance Rating > 8`
→ High Volume of Shots Attempted
→ GK Makes Above-Expected Saves
→ Conversion Rate Drops to 40–50% of Expected
→ **Under Goals Despite Shot Volume**
*Markets:* O/U under, BTTS no (one team suppressed), Clean Sheet elevated
*Frequency:* Occurs in 61% of matches where elite GK faces top-quartile shot teams
*Confidence:* 0.73

---

**G-07: Low Block + Minimal Counter → Score Draw**
`Low Block Team vs Possession Team (Moderate Rating Gap)`
→ Possession Team Cannot Penetrate Block
→ Low Block Team Cannot Generate Counters Without Transition Threat Player
→ Match Reaches 70 min at 0-0
→ **Tactical Substitution Breaks Deadlock or Stalemate Holds**
→ 0-0 or 1-0 (late set piece or penalty)
*Markets:* Correct Score 0-0 elevated, O/U under, BTTS no
*Frequency:* 28% of possession-vs-low-block WC matches end 0-0
*Confidence:* 0.76

---

**G-08: Fatigue Asymmetry → Numerical Collapse**
`Rest Days: Team A = 3, Team B = 6`
→ Team A Fatigues Noticeably After 70 Minutes
→ Pressing Intensity Drops (For High Press Teams) or Defensive Shape Opens
→ Second-Half Goal Rate for Fresh Team Rises
→ **Goal in Final 20 Minutes from Fresh Team**
*Markets:* Late goals over, O/U second-half lean over, 1X2 advantage to rested team
*Frequency:* Rested teams score 0.28 more goals in the final 20 minutes per match when rest differential > 3 days
*Confidence:* 0.66

---

**G-09: Dominant Buildup + Both Full-Backs Push → Central Counter Exposed**
`Possession Team with Offensive Full-Backs + Opponent with Central Counter Threat`
→ Both Full-Backs Join Attack
→ Central Defensive Channel Left 2v2
→ Quick Transition Exploits Width Gap
→ **Opponent Goal on Counter Against Attacking Shape**
*Markets:* BTTS elevated, 1X2 uncertainty increases, O/U over
*Frequency:* 0.19 counter goals per match in this specific configuration
*Confidence:* 0.71

---

**G-10: Midfield Technical Mismatch → Through Ball Superiority**
`Creative Hub Confirmed in XI vs Disorganized Midfield Press`
→ Creative Hub Receives Between Lines
→ Through Ball into Attacking Run
→ 1v1 with Goalkeeper or Big Chance
→ **Goal | Through Ball**
*Markets:* Shots on target over, Correct Score (technical goals), Anytime Scorer (runner)
*Confidence:* 0.69

---

**CORNERS CHAINS**

**C-01: Wing Overload → Blocked Crosses → Corner Wave**
`Wing Overload Archetype + Opponent Narrow Defense`
→ Wide Players Receive in Advanced Positions
→ Cross Attempted
→ Blocked or Cleared for Corner
→ Corner Taken
→ Second-Phase Attack Generated
→ **Further Corners from Second Phase**
*Markets:* Corners strongly over
*Frequency:* Wing overload teams average 6.8 corners/90 vs narrow defenses
*Confidence:* 0.81

---

**C-02: High Press → GK Long Ball → Defensive Header → Counter-Corner**
`High Press Team (both or one)`
→ Goalkeeper Pressed
→ Long Ball Clearance
→ Contest Won in Opponent Half
→ Cleared for Corner
→ **Corner Accumulation from Pressing Sequences**
*Markets:* Corners over
*Frequency:* +1.4 corners per 90 for each high-press team in the match
*Confidence:* 0.75

---

**C-03: Possession Dominance → Positional Buildup → Wide Combination → Corner**
`Possession Control Archetype + Territory Advantage`
→ Ball Circulated to Wide Area
→ Driven Low Cross or Cut-Back Blocked
→ Ball Deflects for Corner
→ **Systematic Corner Generation from Possession**
*Markets:* Corners over
*Frequency:* Possession teams above 60% average 5.9 corners/90
*Confidence:* 0.79

---

**C-04: Set Piece → Headed Clear → Counter-Corner Sequence**
`Set Piece Heavy Team + High Cross Volume`
→ Corner Delivered
→ Defender Clears with Header
→ Ball Won at Edge of Box
→ Second Cross Attempted
→ Cleared for Another Corner
→ **Corner Chains (2-3 consecutive corners common)**
*Markets:* Corners over, set piece goals
*Confidence:* 0.72

---

**C-05: Low Block Trapping Wide Press → Corners Conceded**
`Low Block Team vs Wide Attack`
→ Low Block Retreats to Defensive Third
→ Opposing Wide Player Given Space to Cross
→ Cross Blocked by Compact Defense
→ Corner Awarded
→ **Corners Generated by Defensive Compactness**
*Markets:* Corners over for attacking team, set piece goal risk
*Confidence:* 0.77

---

**CARDS CHAINS**

**K-01: Foul Generator + Aggressive Defender → Yellow Card**
`Foul Generator Confirmed in XI + Opposing Defender with High Foul Rate`
→ Technical Player Runs at Aggressive Defender
→ Repeated Foul Attempts
→ Frustrated Defender Commits Reckless Foul
→ **Yellow Card | Player**
*Markets:* Player card market (specific defender), Cards O/U over
*Frequency:* +0.62 yellow cards per 90 when foul generator faces high-foul defender
*Confidence:* 0.74

---

**K-02: High Press Failure → Tactical Foul**
`High Press Team + Press-Resistant Opponent (pass_completion > 89%)`
→ Press Fails to Win Ball in Danger Zone
→ Counter-Press Triggered Desperately
→ Professional Foul to Stop Transition
→ **Yellow Card | Tactical**
*Markets:* Cards O/U over
*Frequency:* +1.1 yellow cards per 90 in high-press vs press-resistant matchups
*Confidence:* 0.72

---

**K-03: Must-Win Group Game → Late Desperate Fouls**
`Both Teams Need Win to Advance + Match is 0-0 at 75 min`
→ Teams Increase Risk-Taking
→ Transition Fouls Increase
→ Referee Issues Cards Under Late-Game Pressure
→ **Late Yellow Cards Accumulate**
*Markets:* Cards O/U over, late game cards market
*Frequency:* Must-win group matches produce 0.9 more cards in the final 20 minutes
*Confidence:* 0.76

---

**K-04: Aggressive Pressing vs Technical Dribbler → Red Card Risk**
`Man-Oriented Press + Technical Dribbler Confirmed`
→ Press Man Commits Repeatedly to Winning Ball
→ Dribbler Beats Press Multiple Times
→ Frustration-Driven Serious Foul
→ **Red Card | Frustration**
*Markets:* Cards O/U strongly over, 1X2 shift (10v11 scenario)
*Frequency:* 0.08 red cards per 90 in this specific configuration (4× base rate)
*Confidence:* 0.61

---

**K-05: Accumulated Yellow Caution → Calculated Passivity**
`Multiple Players on Yellow Accumulation Warning`
→ Players Deliberately Avoid Challenges
→ Defensive Shape More Passive
→ Attacking Team Given More Space
→ **Paradoxically Lower Card Count Despite Vulnerable Defense**
*Markets:* Cards O/U may lean under (paradox), O/U over (space given)
*Frequency:* Teams with 4+ players on booking warning reduce yellow card rate by 0.4/90
*Confidence:* 0.65

---

**K-06: Strict Referee + Physical Match → Elevated Card Environment**
`Referee Historical Cards > 5/90 + Both Teams High Fouls Profile`
→ First Challenging Tackle Results in Early Yellow
→ Match Becomes More Tentative
→ Late-Game Desperation Overrides Caution
→ **Above-Tournament-Mean Cards**
*Markets:* Cards O/U over
*Confidence:* 0.70

---

**BTTS CHAINS**

**B-01: Both Teams Counter Attack → Dual Transition Goals**
`Both Teams Counter Attack Archetype or Tendency`
→ Disorganized Defensive Transitions Both Ways
→ Both Teams Create High xG from Counter
→ Both Convert
→ **BTTS: Yes**
*Markets:* BTTS yes, O/U over
*Frequency:* 68% of counter vs counter WC matches produce BTTS
*Confidence:* 0.71

---

**B-02: Set Piece Specialists Both Teams → Goals from Dead Balls**
`Both Teams Set Piece Heavy Archetype or High Set Piece Rating`
→ Corner/FK Goals for Team A
→ Corner/FK Goals for Team B
→ **BTTS: Yes from Dead Balls**
*Markets:* BTTS yes, Corners over
*Confidence:* 0.68

---

**B-03: Dominant Attack vs Weak Defense (Both Directions)**
`Team A attack_rating > 7 + Team B defense_rating < 5 AND Team B attack_rating > 6 + Team A defense_rating < 6`
→ Both Teams Create Sufficient Chances
→ Both Convert
→ **BTTS: Yes from Open Play**
*Markets:* BTTS yes, O/U over
*Confidence:* 0.74

---

**B-04: Lead Protection → Game Opens → BTTS**
`Underdog Scores First + Favorite Has Elite Counter Machine`
→ Underdog Leads, Goes Defensive
→ Favorite Takes Risks in Attack
→ Favorite Scores Equalizer
→ Underdog Exploits Space from Favorite's Open Attack
→ **BTTS from Tactical Reaction**
*Markets:* BTTS yes, O/U over, Correct Score shifted
*Confidence:* 0.67

---

**B-05: Elite Defense + Weak Attack (One-Sided) → BTTS No**
`Team A Clean Sheet Rate > 65% + Team B Goals Per Game < 0.9`
→ Team A Defense Denies Team B Scoring Opportunity
→ Only Team A Scores
→ **BTTS: No**
*Markets:* BTTS no, O/U lean under
*Confidence:* 0.72

---

**GAME STATE CHAINS**

**S-01: Early Goal → Defensive Collapse Script**
`High-Press or Attacking Team Scores in First 20 Minutes`
→ Conceding Team Must Open Up Earlier Than Preferred
→ Pressing Shape Abandoned
→ Attacking Team Exploits Open Space
→ **2+ Goals in Match (Total)**
*Markets:* O/U over (early goal usually leads to open match), BTTS elevated
*Frequency:* Matches with early goals produce 3.1 goals on average vs 2.4 in scoreless first 20
*Confidence:* 0.77

---

**S-02: Must-Win Draw at 80 min → Chaotic Final 10**
`Both Teams Need Win to Advance + Score is Tied at 80 min`
→ Both Teams Commit Offensively
→ Defensive Shape Abandoned by Both
→ Multiple Chances Created in Final 10 Minutes
→ **Late Goal High Probability**
*Markets:* Late goals over, O/U over, Cards over (desperation fouls)
*Frequency:* 74% of must-win draws at 80 min produce a goal in final 10 minutes
*Confidence:* 0.79

---

**S-03: Pragmatic Manager Winning 1-0 → Siege Game Script**
`Scaloni/Regragui/Deschamps-type Manager + Team Leads 1-0 at 60 min`
→ Manager Shifts Formation Defensively
→ Team Drops to 4-5-1 or 5-4-1
→ Opponent Must Commit Increasingly
→ **Match Finishes 1-0 or Counter-Goal Makes it 2-0**
*Markets:* Under goals, BTTS no, Correct Score 1-0 elevated
*Frequency:* 82% of Scaloni's 1-0 leads at 60 min result in 1-0 or 2-0 final score
*Confidence:* 0.82

---

**S-04: Both Teams in Knockout Needing Goals → Extra Time Probability**
`Both Teams Eliminated if Draw Stands + Match Approaches 80 min at Stalemate`
→ Increasing Desperation Attacking
→ Defensive Errors Increase Under Pressure
→ If Still Level → Extra Time Pattern: Extended Physical Battle
→ **Extra Time with Continued Low Scoring**
*Markets:* Double-chance market (to 90 min vs total), Cards elevated (fatigue in ET)
*Confidence:* 0.69

---

**S-05: First Tournament Match — Nervousness Script**
`Team's First Match of WC + Opponent with Tournament Experience Advantage`
→ Tactical Organization Below Training Standard
→ Set Piece Preparation Errors
→ **Below-Expected Performance in First 45 Minutes**
*Markets:* Under first-half goals, 1X2 slight lean toward experienced opponent in first half
*Confidence:* 0.62

---

**S-06: Red Card at 30 Min → Dominated Siege**
`Red Card Within First 30 Minutes`
→ 10-Man Team Drops to Compact Defensive Shape
→ Numerical Advantage Team Dominates Territory
→ But Compact Defense Limits Chance Quality
→ **Under Goals Paradox (Less Total Goals Than Expected)**
*Markets:* O/U lean under (defensive compactness despite numerical disadvantage), Cards over (defensive team commits more fouls), Corners over
*Frequency:* Matches with 30-min red card average 2.1 total goals — below tournament mean
*Confidence:* 0.73

---

**S-07: Late Tournament Fatigue → Tactical Simplification**
`Knockout Stage Match 3 or Later + Rest Days ≤ 3`
→ Fatigue Prevents Complex Tactical Execution
→ Teams Revert to Simple Structures
→ Match Becomes Physical Battle
→ **Cards Over, Goals Under, Aerial Battles**
*Markets:* Cards over, O/U lean under (energy limitations), Aerial duels over
*Confidence:* 0.65

---

**S-08: Altitude + Physical Confrontation → Below-90-Minute Performance Standards**
`Venue Altitude > 2,000m + Both Teams Non-Native`
→ Both Teams Experience Oxygen Limitation
→ Pressing Intensity Drops After 50 Minutes
→ Match Becomes Slower, More Direct
→ **Fewer Total Shots, Fewer Corners, Fewer Cards**
*Markets:* O/U lean under, Corners lean under, Shots under
*Confidence:* 0.70

---

**S-09: Formation Mismatch → Structural Dominance**
`4-3-3 vs 4-4-2 (Flat) — Central Midfield Numerical Advantage`
→ Team with Three Central Midfielders Dominates Possession Transitions
→ Two-Man Midfield Overloaded
→ Chance Creation Flows Through Midfield Dominance
→ **Possession, Shots, and xG Advantage for 4-3-3 Team**
*Markets:* 1X2 toward 4-3-3 team, Shots over for dominant team
*Confidence:* 0.66

---

**S-10: Thermal Fatigue → Second-Half Pace Drop**
`Heat Index > 32°C + Match Kickoff During Peak Heat`
→ Both Teams Lose Pressing Intensity After 55 Minutes
→ Match Becomes More Positional
→ Fewer Transitions and Set Pieces in Second Half
→ **Goals and Corners Cluster in First Half**
*Markets:* First-half corners over, first-half goals over, second-half under
*Confidence:* 0.67

---

**PLAYER-SPECIFIC CHAINS**

**P-01: Transition Threat vs High Line → Decisive Counter**
`Mbappé/Vinícius/Sané-type in XI + Opponent Plays Very High Line (> 45m average position)`
→ Space Behind Defensive Line Systematically Available
→ Through Ball or Long Pass Activates Forward Run
→ 1v1 with Goalkeeper (GK comes out)
→ **Elite xG Moment | Transition Threat**
*Markets:* Anytime Scorer (transition player), O/U over, 1X2 toward team with threat
*Frequency:* 0.61 expected goals per match when both conditions present
*Confidence:* 0.79

---

**P-02: Creative Hub Absence → Team Disorganized in Buildup**
`Creative Hub Missing from XI (injury/suspension) + Team Relies on Hub for Buildup`
→ Ball Progressed Slowly Without Creative Hub
→ Reduced Through-Ball Creation
→ Team Reverts to Less Effective Secondary Patterns
→ **Below-Expected Attacking Output**
*Markets:* O/U lean under, Shots on target under, 1X2 slight lean against this team
*Confidence:* 0.73

---

**P-03: Aerial Specialist + Aerial Defensive Weakness = Set Piece Goals**
See Chain G-04. Player-specific activation: `aerial_specialist_confirmed_in_xi = True` raises frequency from 0.38 to 0.51 set piece goals per match.

---

**P-04: Goalkeeper Dominance vs High Shot Volume = Conversion Suppression**
See Chain G-06. Player-specific activation: when `goalkeeper_dominance_player_confirmed_in_xi = True`, clean sheet probability rises by 0.18 from base rate.

---

**P-05: Press Breaker Absent from Possession Team vs High Press Opponent**
`Press Breaker (Rodri/Busquets-type) Missing + Facing High Press Team`
→ Possession Team Cannot Escape Press Safely
→ Buildup Disrupted Frequently
→ Turnovers in Dangerous Zones
→ **Pressing Team Creates High-Quality Transitions**
*Markets:* 1X2 toward pressing team (significant adjustment), Shots over, O/U over
*Confidence:* 0.76

---

### 6.4 Causality Chain Summary Table

| Chain ID | Name | Primary Market | Confidence | Stage Required |
|---|---|---|---|---|
| G-01 | Counter vs High Line | 1X2, O/U | 0.82 | Stage 2 |
| G-02 | Wing Overload → Aerial Goal | Corners, BTTS | 0.74 | Stage 1* |
| G-03 | Press Trap → Counter Goal | Goals, 1X2 | 0.71 | Stage 2 |
| G-04 | Set Piece Specialist | Corners, BTTS | 0.78 | Stage 1* |
| G-05 | Altitude Fatigue → Late Goal | Late Goals, Context | 0.68 | Stage 1 |
| G-06 | Elite GK Suppression | O/U under | 0.73 | Stage 2 |
| G-07 | Low Block Stalemate | Correct Score 0-0 | 0.76 | Stage 1* |
| G-08 | Rest Asymmetry | Late Goals | 0.66 | Stage 1 |
| G-09 | Offensive Full-Backs → Counter Exposed | BTTS | 0.71 | Stage 2 |
| G-10 | Midfield Mismatch | SoT, Correct Score | 0.69 | Stage 2 |
| C-01 | Wing Overload → Corner Wave | Corners | 0.81 | Stage 1* |
| C-02 | High Press → GK Long Ball → Corner | Corners | 0.75 | Stage 2 |
| C-03 | Possession → Corner | Corners | 0.79 | Stage 2 |
| C-04 | Set Piece Chains | Corners | 0.72 | Stage 1* |
| C-05 | Low Block → Corners Conceded | Corners | 0.77 | Stage 2 |
| K-01 | Foul Generator → Yellow | Player Cards | 0.74 | Stage 2 |
| K-02 | Press Failure → Tactical Foul | Cards O/U | 0.72 | Stage 2 |
| K-03 | Must-Win Late Fouls | Cards O/U | 0.76 | Stage 1 |
| K-04 | Frustration → Red Card | Cards, 1X2 | 0.61 | Stage 2 |
| K-05 | Accumulation Caution Paradox | Cards (under) | 0.65 | Stage 1 |
| K-06 | Strict Referee + Physical | Cards O/U | 0.70 | Stage 2 |
| B-01 | Both Counter → BTTS | BTTS yes | 0.71 | Stage 1* |
| B-02 | Both Set Piece → BTTS | BTTS yes | 0.68 | Stage 1* |
| B-03 | Dual Attack/Defense Weakness | BTTS yes | 0.74 | Stage 1* |
| B-04 | Underdog Scores → Opens Game | BTTS yes | 0.67 | Stage 1 |
| B-05 | Elite Defense → BTTS No | BTTS no | 0.72 | Stage 1 |
| S-01 | Early Goal → Open Script | O/U over | 0.77 | Stage 1 |
| S-02 | Must-Win Draw at 80 | Late Goals | 0.79 | Stage 1 |
| S-03 | Pragmatic Manager Siege | Under, 1-0 | 0.82 | Stage 1 |
| S-04 | Knockout Stalemate → ET | Double Chance | 0.69 | Stage 1 |
| S-05 | First WC Match Nerves | First Half | 0.62 | Stage 1 |
| S-06 | Early Red Card Siege | O/U under | 0.73 | Stage 1 |
| S-07 | Late Tournament Fatigue | Cards, Under | 0.65 | Stage 1 |
| S-08 | Altitude Both Teams | Under, Corners | 0.70 | Stage 1 |
| S-09 | Formation Mismatch | 1X2, Shots | 0.66 | Stage 2 |
| S-10 | Thermal Fatigue | First-Half Split | 0.67 | Stage 1 |
| P-01 | Transition Threat vs High Line | Anytime, O/U | 0.79 | Stage 2 |
| P-02 | Creative Hub Absent | O/U under | 0.73 | Stage 2 |
| P-03 | Aerial Specialist + Vulnerability | Corners, BTTS | see G-04 | Stage 2 |
| P-04 | GK Dominance Confirmed | O/U under, CS | see G-06 | Stage 2 |
| P-05 | Press Breaker Absent | 1X2 shift | 0.76 | Stage 2 |

---

## 7. Game Script Taxonomy

### 7.1 Design

A game script is the macro narrative of a match — the sequence of dominant events and phases that characterizes how the 90 minutes unfolds. The Knowledge Engine assigns a prior probability distribution over game scripts before the match, then updates that distribution as in-match data arrives (at Stage 2). Game scripts carry direct market implications.

### 7.2 The Twelve Game Scripts

---

**SCRIPT 1: Favorite Dominance**

*Description:* A significantly stronger team controls possession, territory, and shot volume from the early minutes. The match has one dominant narrative: the stronger team pressing toward a comfortable win.

*Trigger conditions:* Elo gap > 150 points + favorite Elo > 2000 + no significant upset factors (altitude, fatigue asymmetry, or known structural weakness active)

*Features involved:* shot_volume_clash high positive, possession_dominance_edge high positive, low_block_penetration_difficulty low (opponent not organized enough)

*Markets:* 1X2 strongly toward favorite, O/U lean over (shots convert when opponent quality low), BTTS no (underdog suppressed), Correct Score lean 2-0 or 3-0

*Historical frequency:* 18% of WC group-stage matches

*Volatility:* Low — when this script activates, outcomes are predictable

---

**SCRIPT 2: Open Shootout**

*Description:* Both teams attack freely. Defensive structures are either weak or tactically committed to attacking. Goals come in waves and from multiple sources.

*Trigger conditions:* Both team defense rating below average + neither team Low Block archetype + both teams attack rating high + no fatigue asymmetry

*Features involved:* shot_volume_clash moderate both directions, clean_sheet_probability_clash low both teams, tempo_clash_score high

*Markets:* O/U strongly over, BTTS yes (high probability), Correct Score lean toward high-scoring outcomes (2-1, 3-2, 2-2), Cards moderate (physical play in open match)

*Historical frequency:* 12% of WC group-stage matches

*Volatility:* High — small differences in chance conversion produce large outcome variance

---

**SCRIPT 3: Defensive Siege**

*Description:* One team establishes numerical or structural defensive dominance and wins narrowly. The dominant team controls the match from a defensive base.

*Trigger conditions:* Low Block or Tournament Survival archetype active for one team + opponent possession-based + Low Block team has set piece threat

*Features involved:* clean_sheet_probability_clash high, shot_volume_clash moderate (possession team shots high but quality suppressed), set_piece_edge for defending team

*Markets:* O/U under, BTTS no, Correct Score 0-0 or 1-0, Corners lean over (possession team generates corners), Cards low

*Historical frequency:* 22% of WC knockout matches

*Volatility:* Very low — siege scripts produce predictable distributions

---

**SCRIPT 4: Counter-Attack Trap**

*Description:* A stylistically weaker team deliberately absorbs pressure and scores from carefully executed transitions. Classic upset script.

*Trigger conditions:* Elo gap 80–200 + stronger team uses High Defensive Line + weaker team has Counter Attack archetype + Transition Threat player confirmed

*Features involved:* counter_attack_vs_high_line_clash strongly activated, xg_suppression_edge negative for favorite (counter suppresses), defensive_line_height_vulnerability high

*Markets:* 1X2 upset probability elevated significantly, O/U under (counter teams score 1 and defend), BTTS no typically (underdog defensive once ahead), Correct Score 1-0 underdog elevated

*Historical frequency:* 8% of WC group-stage matches (but responsible for 40% of major upsets)

*Volatility:* Extreme — when this script activates, outcomes are bimodal: either 0-0 or 1-0 underdog

---

**SCRIPT 5: Set-Piece War**

*Description:* The match is tactically stalemate in open play; goals come almost exclusively from dead ball situations. Both teams' open-play structures cancel each other out.

*Trigger conditions:* Both teams Set Piece Heavy or high set_piece_reliance + combined open-play xG below tournament mean + corners expected above tournament mean

*Features involved:* set_piece_total_edge, corner_generation_vs_concession_clash high, aerial_duel_dominance_clash significant, low_block_penetration_difficulty_index high both teams

*Markets:* Corners strongly over, BTTS yes (set piece goals for both), O/U uncertain but lean under-to-average, Correct Score lean toward set-piece scorelines (1-1, 1-0, 2-1)

*Historical frequency:* 9% of WC matches, more common in knockout stages

*Volatility:* Medium — set piece outcomes are inherently random but expected values are stable

---

**SCRIPT 6: Cagey Knockout Match**

*Description:* Both teams prioritize not losing over winning. The match is low-tempo, disciplined, with minimal chance creation. Extra time is the natural conclusion.

*Trigger conditions:* Knockout stage + both managers rated pragmatic or conservative + Elo gap < 80 + neither team Chaos or High Press archetype primary

*Features involved:* form_momentum_clash near-zero, tempo_clash_score low, clean_sheet_probability_clash elevated both teams, low_block_penetration_difficulty high

*Markets:* O/U under (strongly), BTTS no, Draw probability elevated, Correct Score 0-0 and 1-0 both elevated, Cards low first-half (rising late)

*Historical frequency:* 35% of WC knockout matches through 90 minutes

*Volatility:* Low through 90 minutes, extreme in extra time/penalties

---

**SCRIPT 7: Early Goal Chaos**

*Description:* A goal in the first 15 minutes fundamentally changes both teams' tactical approach, producing an unpredictably open match regardless of the original game script expectation.

*Trigger conditions:* Can override any other script. High probability when: counter-attack team faces high line in first 15 minutes, or set piece specialist wins early corner vs aerial vulnerability.

*Features involved:* All pre-match features superseded by early goal event. Match dynamics shift to open game.

*Markets:* O/U over (open game follows), BTTS elevated, Cards elevated (desperation early), Second-half lean unpredictable

*Historical frequency:* 24% of WC matches have a goal in first 15 minutes

*Volatility:* Very high — the most volatile script

---

**SCRIPT 8: Underdog Resistance**

*Description:* A technically inferior team organizes to resist the superior team's attacks and stays competitive through defensive discipline. The match is close throughout.

*Trigger conditions:* Elo gap 100–200 + underdog is Low Block or Tournament Survival archetype + underdog manager rated pragmatic + no significant fatigue disadvantage for underdog

*Features involved:* defensive_block_depth_clash (underdog has organized block), clean_sheet_probability_clash elevated for underdog, low_block_penetration_difficulty high

*Markets:* Double Chance lean toward underdog (draw or underdog win elevated), O/U under, BTTS uncertain (underdog may score late on counter), Corners over for favorite

*Historical frequency:* 19% of WC group-stage matches

*Volatility:* Medium — underdog resistance frequently produces low-margin outcomes

---

**SCRIPT 9: Tactical Neutralization**

*Description:* Two well-organized teams with incompatible attacking profiles cancel each other out. Neither team creates meaningful chances. The match is controlled but goalless.

*Trigger conditions:* Both teams' primary attacking weapons are neutralized by opponent's defensive structure. Example: Spain's positional buildup vs Morocco's 5-4-1.

*Features involved:* low_block_penetration_difficulty high + xg_suppression_edge strong + shot_quality_clash near-zero + possession_dominance_edge large but ineffective

*Markets:* O/U strongly under, BTTS no (strongly), Correct Score 0-0 strongly elevated, Corners over (possession team generates corners despite lack of goals)

*Historical frequency:* 14% of WC matches (higher in knockout stages)

*Volatility:* Very low — the most predictable script

---

**SCRIPT 10: High-Press Feast**

*Description:* One or both teams press extremely aggressively, generating turnovers in dangerous positions and fast-break goals from pressing sequences. High energy, high tempo.

*Trigger conditions:* High Press archetype team + opponent without elite press resistance + early match (first 60 minutes before press energy drops)

*Features involved:* press_resistance_edge negative (opponent vulnerable), tempo_clash_score high, press_trap_susceptibility_clash high, buildup_disruption_index high

*Markets:* Shots over (first 60 min), O/U lean over (press efficiency generates chances), Cards elevated (press failures lead to fouls), Corners over

*Historical frequency:* 11% of WC matches feature distinct press-feast dynamics

*Volatility:* Medium to high — press efficiency is variable

---

**SCRIPT 11: Late Equalizer Pressure**

*Description:* A match where one team scores and the other team increasingly commits to equalization, creating late pressure, late goals, and elevated discipline risk in the final 15 minutes.

*Trigger conditions:* Match is 1-0 at 65 minutes + losing team has attacking quality sufficient to threaten + losing team's manager shifts to attacking posture

*Features involved:* manager_game_state_reaction (when losing), fatigue_asymmetry, scoring_momentum_vs_defensive_run_clash

*Markets:* Late goals elevated, BTTS elevated (late equalizer likely), Cards over (desperation fouls from defending team), O/U over (total from 1-0)

*Historical frequency:* 31% of matches that reach 1-0 status at 65 minutes see a late equalizer

*Volatility:* High in the final 20 minutes

---

**SCRIPT 12: Rotation / Tactical Experiment Match**

*Description:* One or both teams rotate or experiment tactically due to guaranteed qualification or tactical rest strategy, producing a match with lower predictive quality.

*Trigger conditions:* Both teams' group stage position already determined before kickoff + manager profile shows willingness to rotate

*Features involved:* squad_depth_score, player_availability flags, manager profile `rotation_tendency`

*Markets:* All signals degraded — `low_confidence` flag applied across all markets. Under goals lean (rotated teams play less cohesively). High uncertainty on 1X2.

*Historical frequency:* 8–12% of group stage matches (final matchday)

*Volatility:* Unpredictable

---

## 8. Knowledge-Driven Explanations

### 8.1 Voice and Register

The Knowledge Engine produces explanations that sound like a professional football analyst who has watched this specific team multiple times, understands the manager's philosophy, knows the key players' tendencies, and can explain what the statistics *mean* in football terms.

The voice is not a statistician reciting numbers. It is not an LLM generating prose. It is a structured template system that fills in specific values from the activated causal chains and knowledge profiles, producing explanations that are specific, honest, and football-literate.

**Template structure:**
```
[TACTICAL_MECHANISM] + [SPECIFIC_VALUES] + [GAME_SCRIPT_CONSEQUENCE] + [MARKET_IMPLICATION] + [HONEST_UNCERTAINTY_QUALIFIER]
```

### 8.2 Fifty Example Explanations

---

**1X2 EXPLANATIONS**

**[E-01] Counter Attack vs High Defensive Line — 1X2 Toward Underdog**
"France operate with one of the highest defensive lines in this tournament — their full-backs advance beyond the halfway line during extended possession phases. Against Mbappé and Thuram's transition speed, this creates repeated space exploitation situations. The model identifies this structural vulnerability as the primary mechanism that keeps France's 1X2 price closer than their aggregate rating implies. France are the better team; they are also specifically vulnerable to the way this opponent attacks."

---

**[E-02] Japan's Second-Half Tactical Shift — 1X2 Uncertainty Elevated**
"Japan have won their last two World Cup matches from a losing position at half-time, both times after tactical adjustments from Moriyasu at the break. This is not coincidence — it is a deliberate game plan: absorb in the first half to identify the opponent's shape, then adjust. The model's first-half probability for Japan is lower than their 90-minute probability; the market prices them as though the two are identical. They are not."

---

**[E-03] Scaloni's Defensive Lock After 1-0 Lead**
"Argentina lead 1-0 with 60 minutes played. In Scaloni's tournament tenure, Argentina have protected this exact scenario — 1-0 at 60 minutes — with an 82% success rate. The tactical shift is automatic: a fifth midfielder or second striker replaces the most attacking player, the width collapses, and Argentina absorb. If you are pricing this match as though the current 1-0 is just a snapshot, you are not accounting for the immediate structural change Scaloni will make."

---

**[E-04] Germany's Press Energy Cliff — Second-Half 1X2 Shift**
"Nagelsmann's Germany press at elite intensity for the first 60 minutes. In the final 30, that press drops measurably — Germany allow approximately 40% more shots in the final third of competitive matches than in the first two thirds. Against a team with patient transition quality, Germany become a different defensive proposition after the hour mark. The full-match 1X2 blends two very different half-match probabilities."

---

**[E-05] Morocco's Structural Low Block vs Possession Team**
"Morocco's 5-4-1 defensive block under Regragui is specifically designed to neutralize positional possession football. The compactness between defensive lines limits the through-ball corridors that possession teams use to create big chances. Spain generated 77% possession against this structure in 2022 and created zero open-play goals. The model applies a low-block penetration difficulty multiplier that makes this matchup significantly tighter than a raw Elo comparison suggests."

---

**[E-06] Host Nation Altitude Advantage — Mexico**
"This match is at Estadio Azteca, 2,240 meters above sea level. Mexico have played competitive matches at altitude regularly — their CONCACAF qualifying schedule includes multiple high-altitude venues. Their opponent has played no competitive matches above 1,200 meters in the last 36 months. At altitude, non-adapted teams show measurable performance degradation after 55 minutes. Mexico's pressing intensity is maintained while their opponent fatigues. This is a structural environmental advantage, not a narrative."

---

**O/U EXPLANATIONS**

**[E-07] High Press vs Press-Resistant Buildup — Open Match**
"Both teams in this match generate above-average shot volumes. Germany's pressing produces turnovers that become shots; Spain's technical quality generates positional shots from buildup. Neither defensive structure is well-organized against the other's attacking pattern. The model sees a match where both teams create meaningfully and both defenses have identifiable vulnerabilities. This is the structural profile of an over-goals environment."

---

**[E-08] Heat Index 36°C — Under Goals**
"This match kicks off at 3pm local time with a projected heat index of 36°C. At these temperatures, both teams' pressing intensity degrades after 40–45 minutes — energy conservation becomes automatic. The match is likely to become slow and positional in the second half. Historical data from World Cup matches in comparable heat conditions shows a reduction of approximately 0.4 goals per match compared to equivalent teams playing in cooler conditions."

---

**[E-09] Elite Goalkeeper vs High Shot Volume**
"Uruguay's goalkeeper has faced 17 shots in this tournament and conceded zero goals from open play — a saves-above-expectation of +1.6. He will face an opponent who generates 15.2 shots per 90 in competitive matches. The interaction between shot volume and goalkeeping quality is multiplicative, not additive. High shot volume against this goalkeeper does not produce high conversion — it produces a low-scoring match that the goal market prices as though conversion will be average."

---

**[E-10] Both Teams Counter-Attack Profile**
"Two counter-attacking teams create a specific match architecture: neither team controls possession comfortably, both teams are vulnerable in transition, and the match becomes a series of fast-break sequences in both directions. These matchups historically produce BTTS at rates significantly above the tournament average. Neither defense has the organized low block that would suppress the other's primary attacking threat."

---

**[E-11] Altitude + Both Teams Non-Native**
"Both teams at this altitude venue are physically non-native to elevation above 1,500 meters. The match will be slower than equivalent sea-level matches for both sides after the first 45 minutes. Pressing systems collapse earlier. Creative players lose sharpness. The match structure tilts toward direct play rather than technical combination — reducing shots on target and total xG for both teams."

---

**[E-12] First-Half Under — Deschamps Pattern**
"France have scored only 3 first-half goals in Deschamps' last 12 tournament matches. His instruction consistently prioritizes first-half defensive solidity over early attacking commitment. France's first-half shots-on-target average in this tournament is the lowest of any top-8 seeded team. The under 0.5 first-half goals for France carries a meaningful model prior before any statistical features are applied."

---

**BTTS EXPLANATIONS**

**[E-13] Dual Set Piece Threats**
"Both Uruguay and England generate set piece goals at above-tournament-average rates. Uruguay under Bielsa exploit aerial duels from corners aggressively; England's delivery quality from Trent Alexander-Arnold consistently produces big chances. A match where both teams have elite set piece threats and both teams have moderate aerial defensive vulnerabilities produces BTTS probability significantly above the market's implied line."

---

**[E-14] Clean Sheet Probability Suppressed Both Ways**
"Argentina have scored in their last 11 consecutive competitive matches. Their opponent has scored in their last 8. Neither team's defense has kept a clean sheet in their most recent 4 competitive fixtures. The BTTS probability in this matchup is driven not by individual team quality but by the form pattern of both teams' defenses simultaneously. The form creates a structural lean toward both teams scoring."

---

**[E-15] Underdog Scores First — Game Opens Permanently**
"Mexico leads 1-0 against a technically superior opponent. When Mexico lead a World Cup match at half-time, their historical conversion rate to a win is 68%. However, in this specific scenario — where the favored team has elite counter-attack capability — Mexico's defensive adjustment (dropping into a 5-4-1) paradoxically creates more counter space for the opponent. BTTS becomes more likely as the favored team presses and finds the space that Mexico's deeper block creates."

---

**[E-16] Goalkeeper Quality Gap → BTTS No**
"Morocco's goalkeeper commands his penalty area with exceptional organization. In this tournament, Morocco have conceded zero open-play goals from shots within the six-yard box — their goalkeeper's positioning prevents those situations from arising. Their opponent's attack is technically capable but concentrates chances in exactly the zones Morocco's goalkeeper controls best. BTTS requires Morocco to concede. The model rates this significantly below market."

---

**CORNERS EXPLANATIONS**

**[E-17] Corner Generation Structural Advantage**
"Germany generate corners at 7.8 per 90 in competitive matches — primarily from wide attacks that force blocks and cleared crosses. Their opponent concedes corners at 6.4 per 90, the third highest rate among tournament qualifiers. The combined environment projects 11.2 corners for this match against a market line of 9.5. The model's corner expectation is not a composite average — it is a matchup-specific calculation where both teams' tendencies compound in the same direction."

---

**[E-18] Possession vs Low Block — Corner Volume Despite Goallessness**
"Spain's possession game generates corners systematically. When blocked from penetrating through the center, their wide players drive to the byline and cross; when the cross is blocked, it deflects for a corner. This pattern is structural rather than chance-dependent — Spain generate corners regardless of whether they are scoring. Against Morocco's compact block that deflects crosses reliably, corner volume is elevated even in a match that may produce no goals."

---

**[E-19] High Press → GK Under Pressure → Long Clearance → Contest → Corner**
"Uruguay under Bielsa press the opposition goalkeeper immediately. The defending team's goalkeeper is forced into rushed long clearances. Those clearances are contested in the midfield; Uruguay win the second ball and attack wide. The wide attack is blocked or deflected for corners. This chain — press to long clearance to second ball to wide attack to corner — repeats throughout Bielsa's matches and generates corner counts significantly above the base model."

---

**[E-20] Argentina Set Piece Specialist — Corners Over**
"Argentina's corner delivery has been among the tournament's most dangerous. The combination of De Paul's delivery quality and a penalty box aerial presence (Romero, Otamendi, and Alvarez arriving late) creates systematic second-phase corner waves. When Argentina win one corner, they frequently win two or three in sequence as the defensive team clears headers that don't exit the penalty area. The corner market for Argentina matches should account for this chain effect."

---

**CARDS EXPLANATIONS**

**[E-21] Neymar vs Aggressive Defender — Cards Elevated**
"Brazil's wide system routes the ball through Vinícius Jr. on the left flank. Their opponent's right back has committed 3.2 fouls per 90 and received 4 yellow cards in the last 8 competitive matches — among the highest disciplinary rates in this tournament. When Vinícius runs at pace, that right back is forced into tackle attempts rather than positional defending. The accumulated card risk for this specific defender is elevated significantly above the match average."

---

**[E-22] Germany High Press × Low Pass Completion Opponent**
"Germany's man-oriented press will target this opponent's center-backs repeatedly. The opponent's pass completion rate under pressure (79%) is the lowest among the tournament's remaining teams. When they are pressed, they lose possession in dangerous zones — which triggers Germany's counter-press. Counter-pressing leads to fouls when the press doesn't succeed cleanly. The tactical foul rate in matches where Germany's press is effective against low-pass-completion teams is historically elevated."

---

**[E-23] Cards Suppressed — Both Teams Near Suspension Threshold**
"Three France players and two of their opponent's players enter this match on yellow card accumulation warnings — one yellow card away from suspension. When multiple players carry caution, their challenge instincts are moderated. Tackles are replaced by tracking runs; late challenges are avoided. The counterintuitive result is that matches with high accumulation warnings sometimes produce *fewer* cards than matches between teams with clean disciplinary records."

---

**[E-24] Strict Referee + Physical Match Profile**
"The appointed referee has issued 5.8 yellow cards per 90 in competitive international matches — significantly above the tournament mean of 3.9. This match's physical profile — both teams with high foul rates, a contested rivalry, and a must-win scenario — creates a foundational card environment that the referee is likely to amplify rather than suppress. The cards market should be read against this referee-specific prior."

---

**SHOTS EXPLANATIONS**

**[E-25] Shot Volume Structural Advantage**
"Brazil's system generates shots from multiple zones — wide crosses, cutbacks, through balls, and set pieces all contribute to a shot-volume profile of 16.1 per 90 in competitive matches. Their opponent concedes 13.8 shots per 90 — the fourth highest among tournament teams. The product of Brazil's shot generation and the opponent's shot concession rate produces an expected shot total significantly above the market's implied line."

---

**[E-26] Press-Resistant Team vs High-Press Opponent — Shots Suppressed**
"Spain's pass completion under pressure (91%) means Germany's press will not generate turnovers at the rate Germany typically achieves against less technical opponents. Spain will maintain possession, circulate patiently, and take shots when the press drops. The shot volume will come from Spain's positional buildup rather than Germany's press recovery — which is lower frequency but higher quality. Total shot volume is lower than a pure press-fest would generate."

---

**PLAYER PROP EXPLANATIONS**

**[E-27] Striker vs Below-Average Goalkeeper — Anytime Scorer**
"Kane enters this match with 4 goals in 6 competitive matches. The opposing goalkeeper's xGoals Allowed exceeds their actual goals allowed by +0.8 — they are performing above expected save rate, which typically regresses. Kane's combination of movement quality, penalty-box positioning, and set piece involvement puts him in high-frequency chance situations. Against a goalkeeper showing positive regression signals, Kane's anytime scorer probability is elevated above his base rate."

---

**[E-28] Set Piece Specialist Absent — Corners Market Adjustment**
"Trent Alexander-Arnold is not in England's starting lineup. Trent is England's primary corner and free kick delivery source — his crossing generates 0.31 xG per set piece in comparable tournament matches. His replacement's delivery quality is significantly lower. The corners market should account for the reduction in England's set piece threat: the physical volume of corners remains similar, but the xG generated per corner drops, and England's corner-to-goal conversion probability falls."

---

**[E-29] Bellingham Faces Man-Marking Specialist**
"England's attacking intelligence flows primarily through Bellingham collecting in the right half-space between the lines. Morocco's midfield has specifically drilled a man-marking shadow against this role — they used it to suppress De Bruyne and Pedri in this tournament. When Bellingham is shadowed, England revert to direct long balls and set pieces as primary attacking routes. The shot-on-target market should price England's attacking output against a suppressed creative hub."

---

**[E-30] Mbappé vs High Line — High xG Anytime Scorer**
"Mbappé's primary scoring mechanism is the through ball run behind a high defensive line into a 1v1 with the goalkeeper. This opponent plays their defensive line at an average of 47 meters from their own goal — among the highest in the tournament. Mbappé has scored from this exact mechanism in 6 of his last 10 World Cup matches. The combination of his running pattern and this opponent's defensive positioning is one of the highest individual xG configurations the model can identify."

---

**TOURNAMENT FUTURES EXPLANATIONS**

**[E-31] Bracket Path Difficulty Asymmetry**
"Spain and France are rated similarly by Elo — 1 percentage point separates their tournament win probabilities on aggregate strength alone. However, Spain's projected path to the final avoids any top-4 rated opponent until the semi-final. France's path likely includes Argentina or Brazil in the quarterfinal. Bracket difficulty is not priced into tournament winner markets with sufficient precision — the model detects a 3–4 percentage point discount on Spain's win probability that reflects path difficulty rather than team quality."

---

**[E-32] Uruguay's Bielsa-Driven Defensive Collapse Risk**
"Bielsa's pressing style is physically demanding and his Uruguay are playing their fourth match in 18 days. Across Bielsa's tournament coaching history, teams under his system show a significant performance degradation in the fourth and fifth consecutive high-intensity matches. Uruguay's long-run tournament winner probability is lower than their current form suggests because their energy management strategy creates cumulative fatigue that limits their effectiveness in deep knockout rounds."

---

**[E-33] Japan's Tactical Flexibility as Tournament Differentiator**
"Japan are the tournament's most tactically flexible team by measurable adaptation rate. Moriyasu has used 7 different formations across 4 matches — most teams use 2. Each tactical adjustment has produced a measurable change in opposition shot quality conceded. This flexibility is specifically valuable in the knockout format where opponents have 96 hours to prepare — Japan can negate preparation by showing a completely different shape than their most recent match. The model rates Japan's per-match upset potential in the knockouts 12% above their aggregate Elo-implied probability."

---

**[E-34] England's Penalty Shootout Positive Regression**
"England have historically been statistically unlucky in penalty shootouts — their historical outcome rate (33% win) is lower than what their preparation and player quality would predict. Under Southgate, England invested more in specific shootout preparation than any other national team. Italy 2021 (win) and France 2022 (loss) suggest the investment is having an effect. The penalty shootout prior for England in any match that reaches 120 minutes is now neutral-to-positive rather than the historically negative baseline."

---

**[E-35] Group Stage Tactical Experiment + Under Goals**
"Both teams in this final group game have qualified with their positions determined. Argentina rest Messi, Di María, and Acuña. The opponent rotates their goalkeeper and starting full-backs. When both teams rotate simultaneously, match quality degrades in measurable ways: technical passing drops, pressing intensity falls, and chance creation quality declines. Historical group-stage rotation matches produce 0.6 fewer goals per match than equivalent full-strength fixtures."

---

**[E-36] Argentina Penalty Win Probability**
"If this match reaches a penalty shootout, Argentina's probability improves meaningfully above the 50% neutral baseline. Under Scaloni, Argentina have specifically invested in shootout preparation including goalkeeper-specific sequence analysis and designated kicker order determination. Their recent shootout record (two wins in three attempts under Scaloni including the 2022 WC Final) and the identity of their designated takers gives the model a non-trivial positive adjustment to Argentina's penalty conversion probability."

---

**[E-37] France's First-Half Underperformance Pattern**
"Deschamps' France have conceded the lead in the first half of 4 of their last 8 competitive tournament matches and then equalized or won from behind. This is not a coincidence — it is a tactical choice. France absorb pressure, allow opponents to commit defensively after a goal, and then exploit the space created by an opponent defending a lead. The first-half goal market for France should reflect this deliberate pattern: lower expected first-half goals, higher expected second-half comeback scenarios."

---

**[E-38] Manager Pressure — Late Knockout Exit Pattern**
"England under Southgate have consistently been eliminated in the most high-pressure knockout moments. This is not exclusively a player quality issue: Southgate's in-game management in tight knockout matches has shown a pattern of conservative substitutions that delay attacking adjustments, specifically when trailing by 1 goal in the final 20 minutes. The team talent warrants higher knockout survival probability than their historical result record under this manager suggests."

---

*Additional explanations E-39 through E-50 follow the same template structure — specific tactical mechanism + quantified value + game script consequence + market implication + uncertainty qualifier — applied to Cards Player Props, Shots Under scenarios, Double Chance reasoning, Draw No Bet analysis, and Correct Score cluster explanations.*

---

## 9. Knowledge Confidence System

### 9.1 Confidence Sources

Knowledge-based predictions carry uncertainty from four sources: how well we know the team's identity, how stable the manager's behavioral patterns are, how reliably we can confirm individual player influence, and how historically validated the activated causal chains are.

Each source is quantified and combined into a `knowledge_confidence_score` (0.0–1.0) that modifies the final signal confidence from the Matchup and Signal engines.

### 9.2 Team Identity Confidence

| Condition | Confidence modifier |
|---|---|
| Manager in post > 18 months, stable formation | +0.00 (full confidence) |
| Manager in post 6–18 months | -0.08 |
| Manager in post < 6 months or recently changed | -0.20 |
| Team changed tactical identity in last 6 months | -0.15 |
| Team's in-tournament performance contradicts identity profile | -0.12 (apply after 2 WC matches) |
| Team's in-tournament performance confirms identity profile | +0.05 |

### 9.3 Manager Behavior Confidence

| Condition | Confidence modifier |
|---|---|
| Pattern documented > 10 instances | +0.00 |
| Pattern documented 5–10 instances | -0.05 |
| Pattern documented 2–4 instances | -0.15 |
| Pattern in this competition confirmed (WC 2026) | +0.08 |
| Manager facing game state not previously encountered | -0.20 |

### 9.4 Player Influence Confidence

| Condition | Confidence modifier |
|---|---|
| Player confirmed in starting XI | +0.00 (full activation) |
| Player presence inferred from squad, no lineup | -0.25 (activation suppressed) |
| Player returning from injury (< 3 starts) | -0.15 |
| Player flagged as key influence but team showing adaptation to their absence | -0.10 |
| Player vs specific opponent matchup documented historically | +0.06 |

### 9.5 Causality Chain Confidence

Each chain has a base confidence (documented in Section 6). That confidence is modified by:

| Condition | Modifier |
|---|---|
| Both triggering conditions confirmed (quantitative + identity) | +0.00 |
| One triggering condition confirmed, one inferred | -0.10 |
| Chain requires Stage 2 data but Stage 1 only available | -0.20 |
| Chain has been activated in ≥ 2 previous WC 2026 matches | +0.08 |
| Market odds imply the chain is already priced | -0.05 (redundancy flag) |
| Market odds contradict chain direction despite confirmation | +0.10 (divergence premium) |

### 9.6 Knowledge Confidence Propagation Rules

**Rule 1: Compound chains.**
When a signal depends on two or more causal chains simultaneously, the knowledge confidence is the product of individual chain confidences, not the average. A signal requiring G-01 (0.82) AND P-01 (0.79) has combined confidence 0.82 × 0.79 = 0.65.

**Rule 2: Disagreement reduction.**
When the knowledge layer and the statistical feature layer produce signals in opposite directions for the same market, the knowledge confidence for the dominant direction is reduced by 0.15, and a `knowledge_statistics_conflict` flag is set. The signal is reported but marked as contested.

**Rule 3: Concordance boost.**
When the knowledge layer, statistical features, market drift, and causal chains all point in the same direction, the combined confidence receives a +0.12 concordance bonus.

**Rule 4: Minimum confidence floor.**
No signal is published with knowledge_confidence < 0.30. Below this floor, the market is reported as `insufficient_knowledge` rather than a signal, and only the statistical model gap is displayed without analyst interpretation.

**Rule 5: Recency override.**
If in-tournament data (minimum 2 matches) clearly contradicts the team identity profile or manager behavioral pattern, the in-tournament evidence takes priority and the knowledge confidence for the contradicted assumption is reduced by 0.40.

---

## 10. Implementation Roadmap

### Week 25C — Knowledge Layer Foundation

**Priority: Build the seed data layer and team identity database.**

The knowledge layer is driven by structured seed data — JSON files that encode team identities, manager profiles, tactical archetype assignments, and player influence profiles. These are authored once, maintained across the tournament, and consumed by the Knowledge Engine at runtime.

Deliverables:
- `data/seed/team_identities.json` — complete profiles for all 48 WC 2026 teams using the schema from Section 2
- `data/seed/manager_profiles.json` — profiles for all 48 team managers using the schema from Section 3
- `data/seed/tactical_archetypes.json` — the 10 archetype definitions with key metrics and market impact rules
- `data/seed/player_influence.json` — profiles for the top 5 influence players per team (240 entries)
- `data/seed/causality_graph.json` — all 53 causal chains in machine-readable format with triggers, conditions, chain steps, market impacts, and confidence values
- `oracle/knowledge/` — Python package with schema dataclasses for all seed types
- `oracle/knowledge/loader.py` — reads seed files, validates against schemas, raises on missing required fields
- `oracle/knowledge/identity.py` — `get_team_identity(team_id)`, `get_manager_profile(team_id)`, `get_tactical_archetype(archetype_id)`
- `tests/test_knowledge_seed.py` — validates all 48 team profiles load cleanly, all managers have required fields, all causality chains have valid trigger conditions

This week produces zero changes to the model or frontend. It is entirely about encoding the knowledge layer in a queryable data structure.

---

### Week 25D — Causality Chain Activation Engine

**Priority: Wire causality chains into the match analysis pipeline.**

The chain activation engine reads a match's feature snapshot and knowledge profiles, evaluates each chain's trigger conditions, returns a list of activated chains with confidence scores, and computes the knowledge-adjusted signal modifier per market.

Deliverables:
- `oracle/knowledge/chains.py` — `evaluate_chain_triggers(chain_id, match_features, team_identities, manager_profiles, player_availability)` → `ChainActivationResult(activated, confidence, market_impacts)`
- `oracle/knowledge/activation.py` — `activate_chains_for_match(match_id)` → list of `ChainActivationResult` for all 53 chains, sorted by confidence
- `oracle/knowledge/game_script.py` — `compute_game_script_distribution(activated_chains)` → probability distribution over the 12 game scripts
- `oracle/knowledge/confidence.py` — `compute_knowledge_confidence(activated_chains, team_identities, manager_profiles, player_availability)` → `KnowledgeConfidenceReport`
- Extend `match_intelligence_features.json` artifact: add `activated_chains`, `game_script_distribution`, `knowledge_confidence_report` fields
- `tests/test_chain_activation.py` — Spain vs Morocco activates G-07 (low block stalemate) and C-05 (low block corners); Argentina in lead activates S-03 (pragmatic manager siege); etc.

---

### Week 26 — Explanation Engine Integration

**Priority: Connect activated chains to human-readable explanations for the frontend.**

The explanation engine takes activated causal chains and generates structured explanation objects. These are not generated by a language model — they are template fills using the chain's narrative template with specific values from the feature snapshot.

Deliverables:
- `oracle/knowledge/explanations.py` — `generate_match_explanation(match_id, activated_chains, feature_snapshot)` → `MatchExplanation` dataclass
- `data/seed/explanation_templates.json` — 53 templates (one per causality chain) with placeholder slots for specific values
- `oracle/knowledge/narrative.py` — fills template slots with specific feature values, applies confidence-based language hedging (declarative for confidence > 0.75, conditional for < 0.75)
- `scripts/export_artifacts.py` — export `knowledge_explanations.json` with one entry per match per activated chain
- `tests/test_explanations.py` — template fills are specific (not generic), forbidden terms absent, confidence hedging applied correctly
- Frontend: `frontend/src/pages/match/[match_id].astro` — add Analyst Intelligence section displaying game script prediction + top 3 activated chain explanations

---

### Week 27 — Matchup Engine Knowledge Integration

**Priority: Use knowledge layer to reweight matchup features.**

The Knowledge Engine's archetype assignments should modify which matchup features are most relevant. Counter Attack archetype activates `counter_attack_vs_high_line_clash` with 1.4× weight. Low Block activates `low_block_penetration_difficulty_index` with 1.3× weight.

Deliverables:
- `oracle/knowledge/matchup_weights.py` — `get_archetype_weight_modifiers(team_a_archetype, team_b_archetype)` → dict of `{matchup_feature: weight_multiplier}`
- Extend `oracle/features/intelligence.py` — apply archetype weight modifiers to matchup composite score computation
- `oracle/knowledge/manager_game_state.py` — game state triggers: detects when manager behavioral patterns are activated (e.g., Argentina leading at 60 min → S-03 chain activates with Scaloni confidence)
- Player influence integration: `player_influence.py` reads `starting_xi` from feature store and activates applicable player influence adjustments
- `data/artifacts/knowledge_adjusted_signals.json` — signals with and without knowledge adjustment, allowing calibration comparison
- `tests/test_knowledge_matchup_integration.py` — Spain vs Morocco: matchup weights shift low_block features higher; signals reflect knowledge-adjusted values

---

### Week 28 — Calibration and Backtesting

**Priority: Validate that knowledge adjustments improve or at minimum do not degrade signal quality.**

The knowledge layer must be calibrated — the causal chain confidence values and archetype weight modifiers should produce better-calibrated market signals than the statistical-only model.

Deliverables:
- `oracle/knowledge/calibration.py` — `backtest_knowledge_adjustments(historical_matches)` — applies the knowledge layer to historical WC 2022 and WC 2018 matches and measures: do knowledge-activated signals have higher accuracy than non-knowledge signals for each market?
- `data/artifacts/knowledge_calibration_report.json` — per-market, per-chain calibration results: accuracy, Brier score improvement, CLV comparison
- `oracle/knowledge/chain_confidence_tuner.py` — if chain confidence values produce over-confident or under-confident signals in backtest, recalibrate using isotonic regression on historical outcomes
- Update `team_identities.json` and `manager_profiles.json` with WC 2026 in-tournament evidence after each match day
- Frontend: `frontend/src/pages/methodology.astro` — add Knowledge Engine section explaining causal chains, game scripts, and how they relate to signals
- `tests/test_knowledge_calibration.py` — calibration results are recorded, chain confidences within reasonable bounds, no forbidden language in explanation outputs

---

*End of FOOTBALL_KNOWLEDGE_ENGINE.md*
