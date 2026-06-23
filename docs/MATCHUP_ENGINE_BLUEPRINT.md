# MATCHUP_ENGINE_BLUEPRINT.md

**World Cup Oracle v2 — Football Intelligence Engine**
**Date:** 2026-06-20
**Status:** Architecture design document — no implementation code, no pipelines, no frontend

---

## 1. Philosophy

### 1.1 Why Team-Level Metrics Are Insufficient

The current Oracle architecture evaluates each team independently and then computes a match probability from the gap between their ratings. Team A has Elo 2041. Team B has Elo 1978. The engine knows how much stronger A is in aggregate, but it knows nothing about *how* that strength manifests — and therefore nothing about *whether that strength is relevant against this specific opponent*.

This is the central limitation of all rating-based prediction systems applied to football. A rating answers the question: "How good is this team on average?" Football demands a different question: "How does this team's style of strength interact with *this opponent's* style of weakness?"

The difference is not academic. Consider three illustrative matchup archetypes:

**The Possession Paradox.** A technically dominant, possession-based team (Elo 2041) faces a structured low-block defensive side (Elo 1930). Pure rating arithmetic says the stronger team should win handily. But if the stronger team's attacking pattern depends on positional buildup and short combinations in tight spaces, and the weaker team's entire structure is designed to collapse those spaces and invite pressure, the "weaker" team has systematically neutralized the "stronger" team's primary weapon. The match becomes a grinding 0-0 or 1-0 — not because the ratings were wrong, but because the stylistic interaction produces a game script that belongs in a different probability distribution than raw ratings imply. Spain vs Morocco, 2022 World Cup knockout round: 77% possession, 0 goals, eliminated on penalties.

**The High Line Trap.** A disciplined, tactically compact team (Elo 1960) faces a counter-attacking side with elite pace in transition (Elo 2010). The stronger team's preferred tactical structure — a high defensive line that compresses space and triggers pressing — is precisely what the weaker team is optimized to exploit. The defensive line height that makes them dangerous against possession teams becomes a structural vulnerability against a team that can cover 50 meters in four seconds. England vs Germany, 2010 World Cup — not pace but the same structural interaction; or more starkly: any time a technically mediocre team with fast forwards dismantles a more talented team that plays high.

**The Set Piece Asymmetry.** Two teams are evenly rated on all outfield quality metrics. But one generates corners at 7.8 per 90 and scores from set pieces at 0.42 goals per 90, while the other concedes corners at 6.1 per 90 and allows 0.38 set piece goals per 90. This creates a cumulative set-piece edge that does not appear anywhere in their head-to-head rating comparison, but materializes directly in the final scoreline with consistent probability. Uruguay vs Cameroon 2010: Uruguay's set piece efficiency was a known structural feature that aggregated ratings would never surface.

**The Discipline Trap.** A technically superior team (Elo 2020) plays an opponent (Elo 1950) whose defensive style generates aggressive physical duels and deliberately invites free kicks in dangerous positions. The superior team has players who attract fouls by running at defenders — they've received 2.3 yellow cards per 90 in competitive matches. The inferior team plays with organized aggression. The resulting match has a card market expectation significantly above the tournament mean, regardless of who wins.

In each case, the rating correctly identifies the stronger team. It completely fails to model the interaction. The Matchup Engine fills this gap.

### 1.2 Why Football Predictions Improve When Interactions Are Modeled

The football academic literature consistently demonstrates that match-level outcomes are better predicted by style-interaction features than by aggregate strength alone in cases where the team rating gap is small (< 100 Elo points). This covers approximately 65% of all World Cup group-stage matches, where the competition field is deliberately compressed by seeding.

Four mechanisms explain this improvement:

**Game script determination.** The tactical matchup between two teams heavily constrains which game script is likely to materialize. A high-press side facing a technically excellent buildup team is likely to produce a different game script than when those same two teams face a different opponent. Game scripts (attacking dominance, defensive siege, open game, cagey low-scoring) carry strong signals for specialty markets — corners, shots, cards — that aggregate ratings cannot capture.

**Stylistic multiplier effects.** A team's attacking weapons are not deployed in a vacuum; they are deployed against a specific defensive system. A cross-heavy attack is dramatically more effective against a team with poor aerial duel success rates than against a team with dominant aerial defenders. A high shot volume does not translate equally into goals when facing a goalkeeper of significantly different quality. The multiplicative interaction between a team's offensive pattern and the opponent's defensive shape produces outcomes that deviate systematically from what independent ratings predict.

**Opposition-specific defensive suppressibility.** Some teams concede shots freely but convert few into goals; others allow very few shots but allow high-quality chances. A team with elite shot creation faces dramatically different outcomes depending on whether the opponent is a high-volume, low-quality shot conceder or a low-volume, high-quality chance conceder. This is an interaction effect that requires both sides of the matchup to be modeled jointly.

**Tournament-specific form asymmetry.** A team that arrived at the tournament on a 6-match unbeaten competitive run but has looked disorganized in its two group-stage matches, faces an opponent who looked ragged in qualification but has been tactically dominant in-tournament. The within-tournament form trajectory of both teams interacts with each other's current vulnerability — neither team's absolute rating captures this dynamic.

### 1.3 Design Principle

The Matchup Engine does not replace the existing Elo/Dixon-Coles probability model. It augments it. The probability model answers: "How likely is each outcome?" The Matchup Engine answers: "What is the mechanism that makes this outcome more or less likely than the rating model implies, and which specific markets does that mechanism affect?"

Signals from the Matchup Engine feed into:
1. The explainability layer — richer, analyst-quality match intelligence narratives
2. Specialty market models (corners, cards, shots) — where stylistic interaction matters most
3. Uncertainty calibration — some matchups are more predictable than others due to strong stylistic consistency; this reduces the uncertainty interval for specific markets

The engine does not produce a single matchup score. It produces a vector of interaction signals, one per market or market cluster, each with its own signal strength, confidence, and supporting feature set.

---

## 2. Matchup Feature Groups

The 58 matchup features are organized into 10 interaction groups. All features are directional from the perspective of Team A (home/higher-rated) against Team B (away/lower-rated), but the engine applies symmetry — every feature produces a signed delta that indicates which side holds the edge.

---

### Group 1: Possession & Territorial Clash

This group models the expected territorial balance of the match — who controls the ball, where they control it, and whether that control is genuine possession or empty possession.

---

### Group 2: Shot Creation & Quality Clash

This group models how each team's attacking pattern interacts with the opponent's defensive pattern to determine the expected shot environment — volume, quality, and location.

---

### Group 3: Defensive Structure & Resistance Clash

This group models how penetrable each team's defensive organization is, and whether the opponent's attacking pattern is specifically calibrated to exploit that structure.

---

### Group 4: Tactical Style Interaction

This group models the specific tactical friction created by the interaction of two different playing systems — the direct interactions that produce the game script.

---

### Group 5: Set Piece & Aerial Clash

This group models the expected set piece environment and aerial battle outcomes, which are statistically significant drivers of corners, goal expectation, and BTTS.

---

### Group 6: Discipline & Foul Dynamics Clash

This group models how the interaction between an aggressive defensive style and a technical, foul-drawing attacking style determines the card and foul environment.

---

### Group 7: Tournament & Physical Context Clash

This group models asymmetric physical context — rest, travel, climate — that may advantage one team over the other independent of tactical quality.

---

### Group 8: Form & Momentum Clash

This group models the interaction between each team's current trajectory and the opponent's vulnerability profile.

---

### Group 9: Market Efficiency Interaction

This group models where the market's assessment of the matchup appears to diverge from the model's structural analysis of the interaction.

---

### Group 10: Player Quality Interaction

This group models specific individual player vs opponent structural interactions — the most granular layer, requiring Stage 2 lineup data.

---

## 3. Feature Definitions

Full specification for all 58 matchup features. Format consistent with FEATURE_STORE_BLUEPRINT.md.

**Important:** All matchup features are *derived* from base features in FEATURE_STORE_BLUEPRINT.md. They do not require new raw data sources — they require joint computation across both teams.

**Notation:** A = attacking team perspective (Team A in context), B = defensive team perspective. All deltas are signed: positive = Team A advantage.

---

### Group 1: Possession & Territorial Clash

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `possession_dominance_edge` | Expected possession advantage in this specific matchup | `poss_A - poss_B` where each poss is the team's historical mean possession adjusted for opponent typical possession share; `poss_A_adj = poss_A × (1 - poss_B / 100)` renormalized | `possession_pct_l6m` (both teams) | API-Football | Stage 2 | 3 | 1X2 (context), Corners, Shots | Use DC rating gap as proxy: `(λ_A - μ_B) / (λ_A + λ_B)` |
| 2 | `territorial_pressure_gap` | Which team is expected to play the majority of the match in the opponent's half | Derived from possession dominance + direct play index interaction: `poss_dominance_edge × (1 - direct_play_index_B)` — a possession dominant team against a high-block opponent has more territory despite less penetration | `possession_pct_l6m`, `direct_play_index` | API-Football | Stage 2 | 2 | Corners, Shots | Use shot creation ratio as proxy |
| 3 | `press_resistance_edge` | Team A's ability to withstand Team B's press given A's technical quality | `pass_completion_A - (1 - press_intensity_B)`; high pass completion + low press intensity = Team A is unlikely to be disrupted in buildup | `pass_completion_pct_l6m`, `pressing_intensity_proxy` | API-Football | Stage 2 | 3 | 1X2, Shots (affects shot creation volume) | null (model plays without this interaction) |
| 4 | `tempo_clash_score` | Expected match tempo — high-intensity/open vs low-intensity/compact | `(shots_A_per90 + shots_B_per90 + corners_A_per90 + corners_B_per90) / 4` normalized by tournament mean; high score = open, tempo-heavy match | `shots_total_per90_l6m`, `corners_for_per90_rolling` | API-Football | Stage 2 | 3 | O/U, Corners, Shots | Use `(goals_A + goals_B) × 4` as proxy |
| 5 | `buildup_disruption_index` | Probability that Team B's pressing disrupts Team A's buildup phase | `press_intensity_B × (1 - pass_completion_A) × direct_play_susceptibility_A` where `direct_play_susceptibility = 1 - direct_play_index`; high = B likely to disrupt A's buildup and force errors | `pressing_intensity_proxy`, `pass_completion_pct_l6m`, `direct_play_index` | API-Football | Stage 2 | 2 | Cards (forced errors → fouls), 1X2 | null |
| 6 | `ball_retention_clash` | Net ball retention advantage, integrating both teams' ability to hold possession under pressure | `(pass_completion_A × possession_A) - (pass_completion_B × possession_B)` normalized; positive = A expected to dominate ball retention | `pass_completion_pct_l6m`, `possession_pct_l6m` | API-Football | Stage 2 | 2 | Corners (possession-driven teams win more corners), Shots | Use goals_per_game ratio |

---

### Group 2: Shot Creation & Quality Clash

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 7 | `shot_volume_clash` | Expected net shot volume advantage for Team A | `shots_A_per90 - shots_B_conceded_per90`; negative of this computed for B; the matchup-adjusted shot expectation rather than raw team mean | `shots_total_per90_l6m`, `shots_conceded_per90_l6m` | API-Football | Stage 2 | 5 | Team Shots, O/U, Correct Score | Use `(dc_attack_A - dc_defense_B)` Poisson interaction |
| 8 | `shot_quality_clash` | Expected shot quality advantage — does A create high-xG chances against B's defensive structure | `xg_per_shot_A - xga_per_shot_B_conceded` where `xga_per_shot_conceded` = opponent's historical shot quality allowed; positive = A creates better quality chances than B normally allows | `xg_per90_historical`, `xga_per90_historical`, StatsBomb shot-level data | StatsBomb Open | Stage 1* | 4 | Correct Score, O/U, Anytime Scorer | Use DC model grid — `xg = λ × (1 + correction)` |
| 9 | `big_chance_creation_clash` | Probability that A creates disproportionate high-probability chances against B's shape | `big_chance_pct_A × (1 - defensive_stability_B)`; B's defensive stability derived from xGA vs xG opponent faced — stable defenders suppress big chance creation | `big_chance_pct_of_shots`, `xga_per90_historical` | StatsBomb Open + API-Football | Stage 1*/Stage 2 | 4 | Anytime Scorer, Correct Score | Use xG/shot differential |
| 10 | `xg_suppression_edge` | How effectively B suppresses A's typical attacking output | `xga_per_shot_conceded_B / xg_per_shot_A` ratio; < 1.0 = B suppresses A below their typical level; > 1.0 = B allows A better quality than A normally generates | StatsBomb xG rates (both teams) | StatsBomb Open | Stage 1* | 4 | O/U, BTTS, Correct Score | Use `dc_defense_B / dc_attack_A` ratio |
| 11 | `box_penetration_clash` | Expected frequency of entry into the opponent's penalty area, accounting for B's defensive compactness | `shots_A_in_box_pct × (1 - defensive_compactness_B)` where compactness derived from shots-conceded location ratio | StatsBomb spatial shot data | StatsBomb Open | Stage 1* | 3 | Shots on Target, Correct Score | null |
| 12 | `shot_location_profile_clash` | Interaction between A's shot location profile and B's zone-specific defensive weakness | `Σ (shot_share_A_zone_i × weakness_B_zone_i)` across central, left channel, right channel, outside-box; identifies if A's shooting zones align with B's weak zones | StatsBomb spatial data | StatsBomb Open | Stage 1* | 3 | Shots on Target, Correct Score | null — experimental |
| 13 | `counter_efficiency_clash` | A's counter-attack conversion rate against B's transition recovery speed | `counter_goal_rate_A × (1 - transition_recovery_B)`; counter_goal_rate derived from goals scored in fast-break sequences / total fast-break sequences | StatsBomb carry + transition events | StatsBomb Open | Stage 1* | 4 | 1X2 (key game script signal), O/U, Correct Score | Use `form_pts_l5 × direct_play_index` proxy |

---

### Group 3: Defensive Structure & Resistance Clash

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 14 | `defensive_block_depth_clash` | Whether A's attacking pattern can penetrate B's typical defensive block depth | `direct_play_index_A × defensive_line_height_B`; high direct play against a low block = low penetration effectiveness; high direct play against a high line = high effectiveness | `direct_play_index`, `defensive_line_height_proxy` | API-Football | Stage 2 | 4 | 1X2, O/U, Shots | Use DC matchup grid |
| 15 | `clean_sheet_probability_clash` | Matchup-adjusted clean sheet probability for each team | `CS_rate_B × (1 - shot_volume_A_per90 / tournament_mean_shots)`; B more likely to keep clean sheet when A generates fewer shots than average | `clean_sheet_rate_l12m`, `shots_total_per90_l6m` | API-Football | Stage 2 | 5 | BTTS, O/U (key input to both teams score), Correct Score | Use DC P(0 goals) |
| 16 | `defensive_line_height_vulnerability` | Probability that B's high defensive line is exploited by A's attacking pace | `defensive_line_height_B × transition_speed_A`; product > 0.7 = high vulnerability; requires both a genuinely high line and genuine pace in transition | `defensive_line_height_proxy`, `counter_efficiency_clash` (component) | API-Football | Stage 2 | 4 | 1X2 (directional toward A), Goals O/U | Use Elo gap if unavailable |
| 17 | `defensive_stability_gap` | How A's defensive solidity compares to B's attacking threat — from A's defensive perspective | `(clean_sheet_rate_A - goals_conceded_per_game_A / tournament_mean) - (goals_per_game_B / tournament_mean)` normalized; positive = A expected to hold | `clean_sheet_rate_l12m`, `goals_conceded_per_game_l12m`, `goals_per_game_l12m` | martj42 + API-Football | Stage 1 | 5 | BTTS, O/U, 1X2 | Direct from DC parameters |
| 18 | `recovery_speed_clash` | How quickly the conceding team reorganizes after losing possession, relative to the other team's transition pace | `transition_speed_A - recovery_speed_B`; derived from time-to-defensive-shape metric approximated by carry event pace in StatsBomb | StatsBomb carry events | StatsBomb Open | Stage 1* | 3 | 1X2 (game script), O/U | null |
| 19 | `aerial_defensive_edge` | Whether A's aerial threat in the box is greater than B's aerial defensive capability | `(aerial_goals_A_per90 + set_piece_goals_A_per90) - (aerial_goals_conceded_B_per90)`; positive = A has aerial advantage | `set_piece_goals_scored_per90`, StatsBomb aerial duel data | StatsBomb Open + API-Football | Stage 1*/Stage 2 | 4 | Corners, Set Piece, BTTS | Use height proxy if available |
| 20 | `press_trap_susceptibility_clash` | Whether A's high press is likely to trap B into errors, or whether B is press-resistant | `pressing_intensity_A × (1 - press_resistance_B)` where press resistance = pass completion under pressure; high = A press creates turnovers and dangerous transitions | `pressing_intensity_proxy`, `pass_completion_pct_l6m` | API-Football | Stage 2 | 3 | Cards (errors → fouls), 1X2, Shots | null |

---

### Group 4: Tactical Style Interaction

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 21 | `wide_attack_vs_narrow_defense_clash` | Whether A's wide attacking pattern is effective against B's defensive width and aerial coverage | `wide_attack_index_A × (1 - aerial_defensive_width_B)`; wide_attack_index = ratio of shots from wide positions; aerial_defensive_width = aerial duel success in wide zones | StatsBomb spatial data + API-Football | StatsBomb Open | Stage 1* | 4 | Corners (crossing teams generate more corners), Shots, 1X2 | null |
| 22 | `counter_attack_vs_high_line_clash` | The primary stylistic friction feature — does A counter-attack effectively against B's high defensive line | `counter_attack_style_flag_A × defensive_line_height_B`; binary × continuous; 1.0 = pure counter team vs extreme high line = maximum friction; 0 = either element absent | `counter_attack_style_flag`, `defensive_line_height_proxy` | API-Football | Stage 2 | 5 | 1X2 (most important for correct side prediction), O/U, Correct Score | Use form + DC interaction |
| 23 | `direct_play_vs_high_press_clash` | Whether A's direct/long-ball approach bypasses B's high-press effectively | `direct_play_index_A × high_press_proxy_B`; high = B presses high, A bypasses with long balls — the press is ineffective and A generates direct chances; low = both sides play the same compact game | `direct_play_index`, `high_press_proxy` | API-Football | Stage 2 | 4 | 1X2 (game script), Shots, O/U | null |
| 24 | `low_block_penetration_difficulty_index` | How difficult it is for A to break down B's defensive structure | `(1 - big_chance_creation_clash) × defensive_compactness_B × (1 - set_piece_edge_A)`; measures three routes through a low block — quality chances, compactness resistance, and set pieces; high = B is very hard to break | `big_chance_pct_of_shots`, `shots_conceded_per90_l6m`, `set_piece_total_edge` | API-Football + StatsBomb | Stage 2 | 4 | O/U (lower goals in high-difficulty penetration matchups), BTTS, Correct Score | DC interaction |
| 25 | `wing_dominance_clash` | Which team has relative advantage in the wide channels — including both defensive width and attacking width | `(wide_attack_index_A - wide_defense_index_B) - (wide_attack_index_B - wide_defense_index_A)` net; positive = A dominates wide channels | StatsBomb wide zone shot/cross data | StatsBomb Open | Stage 1* | 3 | Corners, Shots, 1X2 | null |
| 26 | `vertical_compactness_interaction` | How B's vertical compactness (distance between defensive and offensive lines) affects A's ability to play between the lines | `compactness_index_B × through_ball_tendency_A`; compact teams reduce space between lines; teams that prefer through-ball combinations are specifically disadvantaged | StatsBomb through-ball event data | StatsBomb Open | Stage 1* | 3 | Shots, O/U, 1X2 | null |
| 27 | `flank_overload_vs_defensive_width` | Whether A's tendency to overload one flank creates exploitable width against B's defensive shape | `flank_overload_index_A × defensive_width_vulnerbility_B`; derived from pass network asymmetry index and wide zone concession rate | StatsBomb pass network data | StatsBomb Open | Stage 1* | 2 | Corners (attacking down flanks generates corners), Shots | null |
| 28 | `transition_speed_asymmetry` | The differential in transition speed between the two teams — a high asymmetry means one team consistently beats the other in transitions | `|transition_speed_A - transition_speed_B|`; the direction tells us *who* wins transitions; the magnitude tells us *how decisively* | StatsBomb carry speed data | StatsBomb Open | Stage 1* | 4 | 1X2 (correct side), O/U, Counter Goals | null |

---

### Group 5: Set Piece & Aerial Clash

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 29 | `set_piece_total_edge` | Net set piece advantage combining offensive delivery quality vs defensive set piece vulnerability | `(set_piece_goals_A_per90 - set_piece_goals_conceded_B_per90)` + `(set_piece_goals_B_per90 - set_piece_goals_conceded_A_per90)` sign-adjusted; the combined set piece environment relative to match expectation | `set_piece_goals_scored_per90`, `set_piece_goals_conceded_per90` | StatsBomb Open | Stage 1* | 4 | BTTS, O/U, Correct Score (set pieces shift score distribution) | Use corner ratio proxy |
| 30 | `corner_generation_vs_concession_clash` | The primary corner market feature — interaction between A's corner generation rate and B's corner concession rate | `(corners_for_A_per90 + corners_against_B_per90) / 2 - tournament_corner_mean`; above zero = match expected to produce more corners than the tournament average; the matchup inflates or deflates the corner expectation | `corners_for_per90_rolling`, `corners_against_per90_rolling` | API-Football | Stage 2 | 5 | Corners O/U (this is the primary driver) | StatsBomb corner proxy at Stage 1 |
| 31 | `aerial_duel_dominance_clash` | Which team wins the aerial battle — critical for set pieces, long balls, and goal-line situations | `aerial_duel_success_rate_A - aerial_duel_success_rate_B`; derived from headed clearances, headed goals, and contested aerial events; positive = A wins most aerial duels | API-Football events (headed attempts) | API-Football | Stage 2 | 4 | Corners (dominant aerial teams convert corners), BTTS, Correct Score | Use `squad_avg_caps` × height proxy |
| 32 | `free_kick_delivery_vs_wall_clash` | Whether A's free kick delivery quality is matched against B's defensive free kick organization | `free_kick_threat_rating_A × (1 - defensive_free_kick_organization_B)`; derived from direct FK shots and FK-derived big chances per 90 | StatsBomb free kick event data | StatsBomb Open | Stage 1* | 3 | Correct Score (FK goals are low-frequency but predictable), Shots on Target | null |
| 33 | `penalty_box_aerial_edge` | Which team dominates aerial duels specifically inside the penalty area — the highest-value aerial contest | `headed_shots_A_per90 × (1 - aerial_clearance_success_B_in_box)` vs same for B; the winner of penalty box aerial battles controls set piece goal conversion | StatsBomb spatial aerial data | StatsBomb Open | Stage 1* | 4 | Correct Score, BTTS, Corners (secondary — corner takers aim for aerial targets) | null |
| 34 | `defensive_set_piece_vulnerability_index` | How susceptible B's set piece defense is to A's specific delivery style | Composite: `(goals_conceded_from_corners_B_per90 × corners_for_A_per90) + (goals_conceded_from_fks_B_per90 × free_kick_threat_A)`; measures the expected set piece goals in *this specific matchup* | StatsBomb + API-Football | Stage 1*/Stage 2 | 4 | BTTS, O/U, Correct Score | Use corner clash + set_piece_edge |

---

### Group 6: Discipline & Foul Dynamics Clash

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 35 | `card_risk_asymmetry` | Which team is structurally more likely to accumulate cards given the opponent's style | `(fouls_committed_A_per90 × foul_invitation_index_B) - (fouls_committed_B_per90 × foul_invitation_index_A)` where foul_invitation_index = fouls_suffered / ball_touches; positive = A more card-vulnerable in this matchup | `fouls_committed_per90_l6m`, API-Football player stats | API-Football | Stage 2 | 5 | Cards O/U, Player Cards | Use yellow_cards_per90 sum with match-type weight |
| 36 | `foul_invitation_clash` | Expected total fouls committed in the match — the foundational card market input | `(fouls_A_per90 × foul_invitation_B) + (fouls_B_per90 × foul_invitation_A) / 2`; the interaction multiplier increases total fouls when one team aggressively fouls a team that actively invites fouls | `fouls_committed_per90_l6m`, foul_suffered_per90 | API-Football | Stage 2 | 5 | Cards O/U, total fouls line | Sum of yellow cards per 90 both teams |
| 37 | `aggression_vs_technical_style_clash` | Whether B's aggressive defensive style specifically targets A's technical players who attract fouls | `high_press_B × technical_player_density_A`; technical player density = proportion of starting XI with high dribble attempt rate; when a press-heavy defensive side faces a team with many dribblers, card rates increase significantly | `high_press_proxy`, `pass_completion_pct_l6m` (proxy for technical density) | API-Football | Stage 2 | 4 | Cards O/U, 1X2 (style friction) | null |
| 38 | `referee_card_rate_interaction` | Match-specific card expectation modified by referee's historical tendencies in high-foul environments | `base_card_expectation × referee_card_rate_proxy`; the referee interaction modifies the baseline card rate; some referees threshold yellow card issuance significantly above or below mean | `referee_card_rate_proxy`, `foul_invitation_clash` | API-Football | Stage 2 | 4 | Cards O/U (single most important refinement of the base card model) | Use tournament mean referee rate |
| 39 | `accumulated_yellow_pressure_clash` | Whether players in this match are near the yellow card accumulation threshold (suspension risk) | Count of players on each team within 1 yellow card of suspension; asymmetric suspension risk changes in-match behavior — players on 4 cards in a 5-yellow-suspension tournament may play more cautiously | oracle suspension tracker | Internal | Stage 1 | 3 | Cards O/U (caution pressure suppresses cards paradoxically), 1X2 (behavioral change) | Count from oracle results pipeline |

---

### Group 7: Tournament & Physical Context Clash

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 40 | `fatigue_asymmetry` | Relative physical fatigue load between the two teams entering the match | `(90 - rest_days_B × 10) - (90 - rest_days_A × 10)` capped; more complex: `minutes_played_B_last_match - minutes_played_A_last_match` if overtime data available | `rest_days_since_last_match` (both teams) | Internal | Stage 1 | 4 | O/U (fatigued teams score fewer goals in final 15 min), 1X2 | Rest days delta |
| 41 | `rest_day_edge` | The absolute rest advantage one team has over the other | `rest_days_A - rest_days_B`; positive = A has more rest; WC context: range is typically 3–7 days between group stage matches; differences > 2 days are significant | `rest_days_since_last_match` | Internal | Stage 1 | 4 | 1X2 (advantage to rested team in tight matches), O/U | Direct from fixture schedule |
| 42 | `travel_load_gap` | Differential travel burden since last match | `travel_distance_km_B - travel_distance_km_A`; captures jet lag and physical fatigue from long flights; particularly relevant in a 3-host tournament where travel distances vary significantly | `travel_distance_km` | Internal | Stage 1 | 2 | 1X2, O/U | null if venue data missing |
| 43 | `climate_adaptation_edge` | Which team is better adapted to the specific match climate conditions | `heat_tolerance_A - heat_tolerance_B` where heat_tolerance is derived from the team's historical performance at matches in the same heat_index quartile; teams from hot-climate confederations perform better in heat | `heat_index`, climate performance history from martj42 filtered by venue temperature | martj42 + Open-Meteo | Stage 1 | 3 | 1X2 (mild effect, significant only in extreme conditions), O/U (fewer goals in high heat) | Use confederation_tier × heat_index |
| 44 | `altitude_experience_clash` | Differential altitude experience between teams for matches at Mexico City (2,240m), Denver, Dallas (high altitude) | `altitude_matches_played_A - altitude_matches_played_B`; both counted from martj42 filtered by venue_altitude_m > 1,500; teams that have played at altitude perform measurably better in altitude environments | `venue_altitude_m`, martj42 altitude filter | martj42 + Internal | Stage 1 | 4 | 1X2 (significant at ≥2000m venues — Mexico City), O/U (fewer goals at altitude historically) | Confederation × altitude (CONMEBOL teams adapt better) |
| 45 | `tournament_experience_edge` | Advantage of the team with more World Cup match experience in their squad | `wc_caps_mean_A - wc_caps_mean_B` where wc_caps = count of previous WC group stage + knockout appearances per player, averaged across starting XI | `squad_avg_caps` filtered for WC specifically | API-Football | Stage 2 | 2 | 1X2 (knockout stages specifically), Correct Score (experienced teams take fewer risks) | Use previous_wc_appearances_team proxy |

---

### Group 8: Form & Momentum Clash

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 46 | `form_momentum_clash` | Net form advantage entering this match — whose form trajectory is better | `form_pts_last5_A - form_pts_last5_B`; both time-decayed and match-type weighted; the direction and magnitude of the gap captures the form clash | `form_pts_last5_competitive` (both) | martj42 | Stage 1 | 5 | 1X2 (second most important matchup input after strength), DNB, DC | Direct from feature store |
| 47 | `tournament_trajectory_clash` | Which team has shown better form *within this World Cup*, adjusted for opponent quality | `wc2026_pts_rate_A × opponent_strength_A_faced - wc2026_pts_rate_B × opponent_strength_B_faced`; corrects for the fact that a team with 3 wins over weak groups appears better than a team with 2 wins over strong groups | `wc2026_win_rate`, `elo_rating_full` (opponents faced) | Internal + martj42 | Stage 1 | 5 | 1X2 (dominant in late tournament stages), Qual | wc2026_win_rate differential |
| 48 | `scoring_momentum_vs_defensive_run_clash` | The clash between a team on an attacking run and a team on a defensive run | `goals_per_game_A_l5 × (1 - clean_sheet_rate_B_l5) - goals_per_game_B_l5 × (1 - clean_sheet_rate_A_l5)`; positive = A's attack is currently in form vs B's defense is currently vulnerable; negative = B defense in form vs A attack underperforming | `form_goals_scored_l5`, `clean_sheet_rate_l12m` (rolling) | martj42 | Stage 1 | 4 | O/U, BTTS, Correct Score | Direct from feature store |
| 49 | `opponent_quality_adjusted_form_clash` | Form adjusted for the strength of recent opponents — prevents inflated form ratings against weak competition | `Σ (pts_A_i × elo_opponent_i / elo_mean) × w_i / Σ w_i - same for B`; teams that have performed well against strong opponents have higher adjusted form | `form_pts_last5_competitive` + opponent Elo from martj42 | martj42 | Stage 1 | 4 | 1X2, DNB | Raw form_pts differential |
| 50 | `head_to_head_recent_form_clash` | H2H record over last 5 competitive encounters, heavily time-decayed | `Σ (h2h_result_A × w_time_i × w_match_type_i)`; half-life = 365 days (H2H data is sparse, needs longer window); result is +1 win, 0 draw, -1 loss from A's perspective; **deliberately assigned low weight** — H2H at international level is mostly noise unless sample is large | martj42 H2H filter | martj42 | Stage 1 | 1 | 1X2 (1% weight — included for explainability only) | null if < 3 H2H matches |

---

### Group 9: Market Efficiency Interaction

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 51 | `matchup_model_market_gap` | Whether the market's implied probability reflects the specific matchup interactions or only the team ratings | `model_prob_A_matchup_adjusted - market_implied_A_prob`; where `model_prob_matchup_adjusted` incorporates top matchup signals as multipliers on DC model base probability | All matchup signals + market_profile features | Internal + The Odds API | Stage 1 | 5 | 1X2, DNB, DC (primary market gap) | Base model-market gap from oracle/betting/ |
| 52 | `opening_closing_drift_vs_matchup` | Whether the market's opening→closing drift is in the same direction as the matchup analysis predicts | `sign(opening_closing_drift_A) == sign(matchup_model_market_gap_A)`; concordance = market and matchup agree on the direction; divergence = market moved away from what the matchup implies, which may indicate market error or information the model lacks | `opening_closing_drift_1x2`, `matchup_model_market_gap` | Internal + The Odds API | Stage 1 | 4 | 1X2 (confidence modifier — concordance raises confidence, divergence raises uncertainty) | null |
| 53 | `specialty_market_matchup_gap` | Whether the market's specialty market line (corners, cards, shots) reflects the matchup interaction | `model_specialty_expectation - market_specialty_line` where model_specialty_expectation is built from the relevant matchup feature group (corners from Group 5, cards from Group 6) | Relevant matchup groups + The Odds API specialty odds | The Odds API + Internal | Stage 2 | 5 | Corners O/U, Cards O/U, Shots (each has its own version of this feature) | null at Stage 1 |
| 54 | `public_narrative_correction_edge` | Whether the publicly known narrative (favorite label, reputation) inflates the market price beyond what the matchup analysis supports | Approximated by: market_consensus > dc_model_prob by > 0.08 on the heavily favorited team — this suggests the market may be pricing public perception over statistical interaction; treated as a weak prior on the underdog | `market_implied_home_prob`, DC model prob | The Odds API + Internal | Stage 1 | 2 | 1X2 (underdog signal only), DC | null |

---

### Group 10: Player Quality Interaction

| # | feature_name | description | formula | required inputs | provider | stage | importance | markets | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 55 | `top_scorer_vs_goalkeeper_quality_clash` | Whether A's primary goal threat faces B's goalkeeper at a relative quality advantage or disadvantage | `top_scorer_form_goals_A - goalkeeper_quality_proxy_B`; goalkeeper_quality_proxy derived from saves-above-expected or clean sheet rate weighted by shot quality faced; positive = A's striker faces a beatable goalkeeper | `top_scorer_goals_l12m`, `clean_sheet_rate_l12m` (GK proxy), StatsBomb save events | API-Football + StatsBomb | Stage 2 | 4 | Anytime Scorer, Correct Score (specific goal scorer probability) | Use dc_attack_A vs dc_defense_B interaction |
| 56 | `key_player_vs_defensive_assignment_clash` | Whether A's most dangerous player is likely to face B's best defensive player or a mismatch | `key_player_quality_A × (1 - man_mark_quality_B)` where man_mark_quality is derived from B's central defender aerial and 1v1 duel success rates; positive = A's key player faces defensive mismatch | API-Football player stats + StatsBomb duel data | API-Football + StatsBomb | Stage 2 | 3 | Anytime Scorer, Player Shots, Player Cards | null |
| 57 | `squad_depth_pressure_clash` | Whether A's squad depth advantage becomes relevant in a match that goes to extra periods or requires rotations due to fatigue | `squad_depth_score_A - squad_depth_score_B` weighted by `fatigue_asymmetry`; most relevant in knockout matches where squad depth determines substitution quality | `squad_depth_score`, `fatigue_asymmetry` | Transfermarkt + Internal | Stage 1 | 2 | 1X2 (tournament futures context), Group Qualification (via tiebreak resilience) | Use squad_market_value_usd as depth proxy |
| 58 | `set_piece_specialist_vs_vulnerability_clash` | Whether A has a specific set piece delivery specialist whose quality compounds against B's known defensive set piece weakness | `(free_kick_threat_rating_A × defensive_set_piece_vulnerability_B) + (corner_conversion_A × corner_aerial_vulnerability_B)`; the compound interaction of a specialist delivery and a specifically vulnerable defense | `free_kick_threat_rating`, `defensive_set_piece_vulnerability_index`, `corner_conversion_to_shot` | StatsBomb Open | Stage 1* | 4 | Corners, BTTS, Correct Score (set piece goals) | Use `set_piece_total_edge` |

---

## 4. Matchup Importance Matrix

Rating scale: 5 = critical feature group, 4 = important, 3 = moderate, 2 = minor, 1 = weak supplementary.

For each market, the table shows the importance of each matchup group's contribution to the signal. Empty cells indicate the group has no meaningful contribution to that market.

| Matchup Group | 1X2 | Double Chance | Draw No Bet | O/U 1.5 | O/U 2.5 | O/U 3.5 | BTTS | Correct Score | Corners | Cards | Shots | Player Props | Tournament Futures |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1. Possession & Tempo** | 3 | 3 | 3 | 3 | 4 | 3 | 2 | 3 | 5 | 2 | 5 | 1 | 2 |
| **2. Shot Creation & Quality** | 4 | 4 | 4 | 5 | 5 | 5 | 4 | 5 | 3 | 1 | 5 | 4 | 3 |
| **3. Defensive Resistance** | 4 | 4 | 4 | 5 | 5 | 5 | 5 | 5 | 2 | 1 | 4 | 3 | 4 |
| **4. Tactical Style Interaction** | 5 | 4 | 5 | 4 | 4 | 3 | 3 | 4 | 4 | 2 | 4 | 2 | 3 |
| **5. Set Piece & Aerial** | 3 | 3 | 2 | 4 | 4 | 3 | 4 | 5 | 5 | 1 | 3 | 4 | 2 |
| **6. Discipline & Foul Clash** | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 2 | 5 | 1 | 5 | 1 |
| **7. Tournament Context** | 3 | 3 | 3 | 3 | 3 | 2 | 2 | 3 | 2 | 2 | 2 | 2 | 5 |
| **8. Form & Momentum** | 5 | 5 | 5 | 4 | 4 | 3 | 3 | 4 | 2 | 1 | 3 | 2 | 5 |
| **9. Market Efficiency** | 5 | 5 | 5 | 4 | 4 | 4 | 3 | 3 | 4 | 4 | 3 | 2 | 3 |
| **10. Player Quality Interaction** | 3 | 3 | 3 | 3 | 3 | 3 | 2 | 4 | 2 | 4 | 4 | 5 | 4 |

**Key observations:**

- **1X2, DNB, DC:** Driven primarily by tactical style interaction (Group 4), form momentum (Group 8), and market efficiency (Group 9). These are the markets where the matchup engine most directly supplements the base Elo model.

- **O/U markets:** Shot creation clash (Group 2) and defensive resistance (Group 3) are the strongest drivers, with possession/tempo (Group 1) as the context setter. This makes sense: goal expectation is primarily a function of how many quality chances are created and whether the defense can suppress them.

- **Corners:** Possession & tempo (Group 1) and set piece/aerial (Group 5) are co-primary drivers. Corner generation is fundamentally a function of attacking territorial pressure and wide-attack patterns.

- **Cards:** Discipline clash (Group 6) is almost exclusively the relevant group. This is the clearest single-group market in the matrix.

- **Shots:** Shot creation (Group 2) and possession/tempo (Group 1) are jointly primary. Player props (Group 10) adds the individual player allocation dimension.

- **Tournament Futures:** Tournament context (Group 7) and form/momentum (Group 8) become more important as the tournament progresses — cumulative fatigue and in-tournament trajectory matter more in knockout stages.

---

## 5. Matchup Signal Engine

### 5.1 Architecture Overview

The matchup signal engine transforms the 58 raw matchup feature values into a structured set of per-market signals with explicit strength, confidence, and uncertainty properties. It operates in three layers:

```
Layer 1: Raw Matchup Deltas
  For each feature: compute signed delta (Team A perspective)
  Apply normalization: z-score against historical distribution

Layer 2: Market Composite Scores
  For each market: weighted sum of relevant matchup feature z-scores
  Weight vector = importance_score from importance matrix
  Output: one composite matchup z-score per market

Layer 3: Signal Classification & Confidence
  Map composite z-score to signal level
  Compute confidence from sample quality + feature completeness
  Output: matchup_signal per market
```

### 5.2 Normalization

Each raw matchup feature is normalized against the empirical distribution of that feature across all historical competitive international matches:

```
z_feature = (value - μ_historical) / σ_historical
```

Where μ and σ are computed from at least 500 match observations to be stable. For features with skewed distributions (like card totals), use log-normalization before computing z-scores:

```
z_feature_cards = (log(value + 1) - μ_log) / σ_log
```

Normalization is critical because features operate on different scales (corners per 90 is ~4–10; possession pct is ~35–65; xG is ~0.5–2.5) and must be made comparable before aggregation.

### 5.3 Market Composite Score

For each market M, compute:

```
z_composite(M) = Σ [ importance_weight(feature_i, M) × z_feature_i ] / Σ importance_weight(feature_i, M)
```

Where importance_weight is taken from the importance matrix (Section 4), scaled to [0, 1]. Features with null values are excluded from the computation — the denominator adjusts accordingly. Features flagged as `experimental` receive a weight penalty of 0.5 regardless of their importance score, until they are validated on tournament data.

The resulting composite z-score is a signed quantity in units of standard deviations from the historical mean matchup environment for that market.

### 5.4 Signal Level Classification

```
|z_composite| < 0.5:      no_signal      (market and model structure agree — watchlist only)
0.5 ≤ |z_composite| < 1.0: watchlist     (moderate structural tilt, worth monitoring)
1.0 ≤ |z_composite| < 1.5: moderate_signal (clear structural tilt across multiple features)
|z_composite| ≥ 1.5:      strong_signal  (unusual alignment of multiple independent signals)
```

Sign of z_composite indicates direction: positive = Team A (home/higher-rated) advantage, negative = Team B advantage.

**Important constraint:** a signal is capped at `watchlist` when any of the following apply:
- `low_sample_flag = True` for either team on the critical features for that market
- Fewer than 3 matchup features are non-null for the relevant group
- `high_variance_flag = True` on the base model probability

A signal that would be `strong_signal` by composite score but fails a data quality gate is reported as `watchlist` with the failure reason in `uncertainty_flags`.

### 5.5 Confidence Scoring

Confidence is a separate dimension from signal strength. Signal strength measures the *size* of the detected interaction. Confidence measures *how much to trust the measurement*.

```
confidence_raw = 1.0

# Penalize for data quality issues
- If competitive_match_n < 10 on any primary feature: -0.30
- If lineup_confirmed = False: -0.15 (player interaction group only)
- If Stage 2 features are null (Stage 2 required for this market): -0.25
- If experimental features constitute > 40% of non-null inputs: -0.20
- If model_prob_std_bootstrap > 0.08: -0.15

# Boost for concordance
+ If opening_closing_drift_vs_matchup is concordant: +0.10
+ If ≥ 4 independent matchup groups all show the same directional signal: +0.10
+ If same signal was present in last WC 2026 match for this team: +0.05

confidence = max(0.10, min(1.0, confidence_raw))
```

Confidence is bucketed into: `low` (< 0.45), `medium` (0.45–0.70), `high` (> 0.70).

### 5.6 Uncertainty Propagation

Each input feature carries uncertainty from its underlying data (sample size, bootstrap variance). This uncertainty propagates through the composite score:

```
σ²_composite(M) = Σ [ weight_i² × σ²_z_feature_i ] / (Σ weight_i)²
```

The composite signal's 90% confidence interval is:

```
CI_90 = [z_composite - 1.645 × σ_composite, z_composite + 1.645 × σ_composite]
```

If this confidence interval crosses a signal-level threshold boundary (e.g., a signal at z=1.2 with σ=0.5 has CI that includes z < 0.5), the signal level is downgraded to the level corresponding to the lower CI bound, and a `high_uncertainty_range` flag is set in `uncertainty_flags`.

### 5.7 Worked Example — Corners Market

**Match:** Team A (corners for: 7.8/90) vs Team B (corners against: 6.4/90)

**Computation:**
```
corner_generation_vs_concession_clash:
  raw_value = (corners_A_for + corners_B_against) / 2 = (7.8 + 6.4) / 2 = 7.1
  tournament_mean = 4.8, tournament_σ = 1.2
  z_corner_clash = (7.1 - 4.8) / 1.2 = +1.92

possession_dominance_edge:
  A possession = 58%, B typical possession = 44%
  adj_possession_A = 58 × (1 - 44/100) = 32.5; adj_possession_B = 44 × (1 - 58/100) = 18.5
  normalized to: A = 64%, B = 36%
  z_possession = (64 - 50) / 9.5 = +1.47

set_piece_total_edge:
  set_piece_goals_A = 0.38/90, set_piece_goals_conceded_B = 0.31/90
  z_set_piece = (0.38 - 0.31 - mean) / σ = +0.81

wide_attack_vs_narrow_defense_clash:
  A is a wide attack team (wide attack index = 0.68)
  B plays a narrow defense (narrow defense index = 0.71)
  z_wide_clash = (0.68 × 0.71 - tournament_mean_interaction) / σ = +1.18

z_composite(Corners) = (5 × 1.92 + 4 × 1.47 + 3 × 0.81 + 4 × 1.18) / (5+4+3+4)
                     = (9.60 + 5.88 + 2.43 + 4.72) / 16
                     = 22.63 / 16
                     = 1.41
```

**Result:**
- Signal: `moderate_signal` (1.0 ≤ z < 1.5)
- Direction: Team A matchup inflates corner environment above tournament mean
- Confidence: `high` (all 4 contributing features are Stage 2, non-null, sample size > 20 matches)
- Uncertainty CI_90: [0.97, 1.85] — lower bound still in `watchlist` territory, so signal remains `moderate_signal` but `high_uncertainty_range` flag is NOT set (CI doesn't cross below 0.5)

**Market comparison:** If The Odds API shows corners O/U line at 9.5 and the model's expected corner total is 11.2, the signal gap = 1.7 corners, or +18% above the market line. Combined with moderate_signal + high confidence → reported as meaningful divergence.

---

## 6. Matchup Intelligence Output

### 6.1 matchup_intelligence.json Schema

One document per match. Consumed by the explainability layer and frontend signal display.

```json
{
  "match_id": "wc2026_m042",
  "home_team": "germany",
  "away_team": "netherlands",
  "snapshot_at": "2026-06-20T14:00:00Z",
  "kickoff_at": "2026-06-21T19:00:00Z",

  "matchup_scores": {
    "1x2": {
      "z_composite": 0.87,
      "direction": "home",
      "signal_level": "watchlist",
      "confidence": "medium",
      "confidence_score": 0.58,
      "ci_90_lower": 0.31,
      "ci_90_upper": 1.43,
      "contributing_groups": ["form_momentum_clash", "tactical_style_interaction", "market_efficiency_interaction"]
    },
    "ou_2_5": {
      "z_composite": 1.34,
      "direction": "over",
      "signal_level": "moderate_signal",
      "confidence": "high",
      "confidence_score": 0.72,
      "ci_90_lower": 0.88,
      "ci_90_upper": 1.80,
      "contributing_groups": ["shot_creation_clash", "defensive_resistance_clash", "possession_tempo_clash"]
    },
    "corners_ou": {
      "z_composite": 1.41,
      "direction": "over",
      "signal_level": "moderate_signal",
      "confidence": "high",
      "confidence_score": 0.74,
      "ci_90_lower": 0.97,
      "ci_90_upper": 1.85,
      "contributing_groups": ["corner_generation_concession_clash", "possession_dominance_edge", "wide_attack_vs_narrow_defense_clash"]
    },
    "cards_ou": {
      "z_composite": 0.23,
      "direction": "neutral",
      "signal_level": "no_signal",
      "confidence": "medium",
      "confidence_score": 0.61,
      "ci_90_lower": -0.19,
      "ci_90_upper": 0.65,
      "contributing_groups": ["discipline_clash"]
    },
    "btts": {
      "z_composite": 0.92,
      "direction": "yes",
      "signal_level": "watchlist",
      "confidence": "medium",
      "confidence_score": 0.55,
      "ci_90_lower": 0.38,
      "ci_90_upper": 1.46,
      "contributing_groups": ["shot_creation_clash", "defensive_resistance_clash", "set_piece_aerial_clash"]
    }
  },

  "primary_signals": [
    {
      "signal_id": "ou25_over_germany_netherlands",
      "signal_type": "goal_environment",
      "signal_level": "moderate_signal",
      "confidence": "high",
      "markets_impacted": ["ou_1_5", "ou_2_5", "btts", "correct_score"],
      "supporting_features": [
        {
          "name": "shot_volume_clash",
          "value_a": 14.8,
          "value_b": 12.1,
          "delta_z": 1.18,
          "description": "Germany averages 14.8 shots/90 vs Netherlands conceding 12.1/90 — above-average shot volume from the German side"
        },
        {
          "name": "shot_quality_clash",
          "value_a": 0.142,
          "value_b": 0.128,
          "delta_z": 0.81,
          "description": "Germany's xG per shot (0.142) marginally exceeds Netherlands' historical xG allowed per shot (0.128)"
        },
        {
          "name": "defensive_stability_gap",
          "value_a": 0.61,
          "value_b": 0.54,
          "delta_z": 0.74,
          "description": "Both teams have below-average defensive stability in this tournament — neither is shutting matches down"
        }
      ],
      "counter_features": [
        {
          "name": "clean_sheet_probability_clash",
          "note": "Netherlands have kept 1 clean sheet in their last 3 competitive matches — some defensive resilience remains"
        }
      ],
      "explanation": "Both teams are generating and conceding shots at above-tournament-average rates. Germany's high pressing style against Netherlands' technical buildup creates an open, high-tempo game script that historically produces above-average goal totals. The model detects a meaningful tilt toward an open match independent of which team wins.",
      "uncertainty_flags": []
    },
    {
      "signal_id": "corners_over_germany_netherlands",
      "signal_type": "corner_environment",
      "signal_level": "moderate_signal",
      "confidence": "high",
      "markets_impacted": ["corners_ou"],
      "supporting_features": [
        {
          "name": "corner_generation_vs_concession_clash",
          "value": 11.2,
          "tournament_mean": 9.4,
          "delta_z": 1.41,
          "description": "Combined corner expectation 11.2 vs tournament mean 9.4 — this matchup has structural corner inflation"
        },
        {
          "name": "wide_attack_vs_narrow_defense_clash",
          "value_a": 0.71,
          "value_b": 0.34,
          "delta_z": 1.18,
          "description": "Germany's wide attacking patterns push Netherlands' narrow defensive shape into corner situations"
        }
      ],
      "counter_features": [],
      "explanation": "Germany generates corners at 7.8 per 90 while Netherlands concedes at 6.4 per 90 — a structural environment that inflates corner totals 18% above the tournament mean line. Germany's tendency to attack through wide channels compounds this: when forced to defend wide, Netherlands consistently yields corner situations.",
      "uncertainty_flags": []
    }
  ],

  "matchup_summary": {
    "dominant_game_script": "high_tempo_open",
    "game_script_confidence": "medium",
    "most_actionable_market": "corners_ou",
    "most_uncertain_market": "1x2",
    "structural_features_available": 34,
    "structural_features_missing": 24,
    "stage_active": 2,
    "data_completeness": 0.59
  },

  "data_quality": {
    "lineup_confirmed_home": false,
    "lineup_confirmed_away": false,
    "stage_2_active": true,
    "experimental_features_used": 3,
    "low_sample_flag_home": false,
    "low_sample_flag_away": false,
    "warnings": [
      "Lineups not confirmed — player interaction features (Group 10) unavailable",
      "3 experimental StatsBomb features used — treat tactical style signals as supplementary"
    ]
  }
}
```

---

## 7. Explainability Layer

### 7.1 Design Principles

Professional football analysts do not say "the xG differential is 0.34 in favor of the home side." They say: "Spain's movement off the ball consistently disorganizes Morocco's defensive shape, creating pockets of space that Pedri exploits for his trademark switch passes — and it's exactly those second-ball situations that generated Spain's best chances."

The explainability layer must bridge between the statistical signal and the football story. The rules:

1. **Name the mechanism, not the statistic.** Explain *why* an edge exists, not just *that* it exists.
2. **Use both teams in the explanation.** Every sentence should reference how A's quality interacts with B's specific characteristic.
3. **Acknowledge the counter-case.** A signal is not a certainty. Acknowledge the strongest reason it might be wrong.
4. **Scale language to confidence.** High-confidence signals use declarative language. Low-confidence signals use conditional language.
5. **Name the game script.** Anchor the explanation in a recognizable football scenario.

### 7.2 Explanation Template

Each explanation is built from a four-component template:

```
[MECHANISM]: Describe the specific tactical/statistical interaction.
[MAGNITUDE]: Quantify the edge in natural language (significantly, marginally, historically).
[GAME SCRIPT]: What kind of match does this interaction tend to produce?
[MARKET IMPLICATION]: What does this mean for the specific market?
```

### 7.3 Twenty Example Explanations

**1 — Counter-attack vs High Line (1X2)**
"France's forward line is built for depth — Mbappé and Dembélé combined average 3.2 off-the-ball runs behind the defensive line per 90. England's high defensive block compresses midfield effectively but leaves significant space on the counter. The model detects a structural opportunity for France to exploit England's shape directly, which inflates France's goal expectation beyond what their headline rating alone suggests."

**2 — Set Piece Specialist vs Weak Aerial Defense (O/U)**
"Uruguay's set piece threat is one of the highest in this tournament — they have scored from 38% of corner kicks that reach the six-yard box. Their opponent has conceded more headed goals per 90 than any other team in the group stage. The matchup creates a meaningful above-average goal expectation through set pieces alone, independent of open play quality."

**3 — Possession vs Low Block (O/U — under signal)**
"Belgium have dominated possession at 68% in this tournament, but have attempted only 1.2 shots per 20 passes — significantly below the tournament average for possession-heavy teams. Their opponent's five-man defensive block is precisely calibrated to cede territory and invite pressure without opening spaces. The model sees an environment where possession is abundant but penetration is structurally suppressed — a scenario historically associated with lower than expected goal totals."

**4 — Direct Play Bypassing Press (1X2 toward underdog)**
"Italy's high press has generated 4.3 ball recoveries in the opposition half per 90 — effective against possession sides but vulnerable to teams that bypass the press with direct distribution. Ecuador's direct play index ranks in the top 5 of this tournament: long switches, diagonal balls, and third-man runs that physically bypass Italy's press structure. The model detects a moderate game script risk for the Italian side that the market does not fully price."

**5 — High Altitude Asymmetry (1X2 — Mexico City)**
"This match is played at Estadio Azteca (2,240m altitude). At this elevation, teams with metabolic adaptation — primarily CONMEBOL nations that qualify through high-altitude home matches — perform historically 6–8% better than their aggregate rating implies. Bolivia and Mexico train at altitude as a structural advantage. The opponent has played no competitive matches at altitude in the last 24 months. The altitude interaction is a meaningful but frequently underpriced contextual feature."

**6 — Press Resistance vs High Press (Shots — lower volume)**
"Japan's high press will be the defining tactical feature of this match. But Spain's pass completion rate under pressure ranks first in this tournament at 91.4% — their positional structure effectively neutralizes pressing traps. The model detects that Japan's primary defensive weapon is unlikely to force Spain into low-quality fast situations, which suppresses the shot volume that would typically accompany Japan's aggressive defensive shape."

**7 — Corner Generation Interaction (Corners O/U — over)**
"Germany's wide attacking system generates corners at 7.8 per 90 — they force the ball into wide positions and win corners through the flanks when blocked. Their opponent concedes corners at 6.4 per 90, the third highest in the tournament. The combined environment produces an expected corner total of 11.2 for this match — 18% above the market line of 9.5. The edge is supported by three independent matchup features rather than a single data point."

**8 — Narrow Attack vs Wide Defense (Corners O/U — under)**
"Argentina prefer central combination play through their double pivot — fewer than 22% of their attacking sequences end in wide positions. Their opponent defends with a wide back four specifically organized to force opponents into central combinations. The structural result is a corner-lean environment: Argentina will generate shots through central channels rather than wide crosses, systematically producing fewer corner situations than their general attacking quality implies."

**9 — Card Accumulation Risk (Cards O/U — over)**
"Brazil's technical players win fouls at the highest rate in this tournament — 4.2 fouls suffered per 90. Their opponent's defensive structure is physically aggressive: 13.8 fouls committed per 90 with 3.1 yellow cards per 90 in competitive matches. When Brazil's foul-inviting style faces this opponent's fouling pattern, the combined card environment is historically 40% above the tournament mean. The referee's historical card rate compounds this — they average 5.2 yellow cards per 90 in physically contested international matches."

**10 — Disciplined Underdog (Cards O/U — under)**
"Japan are facing a stylistically aggressive opponent, but Japan's defensive structure is disciplined rather than physical — they commit 9.1 fouls per 90 and have received 1.8 yellow cards per 90 in competitive matches, below the tournament average. Their opponent also tends not to invite fouls despite their high possession. The combined discipline profile produces an expected card environment below the market line."

**11 — Aerial Battle at Set Pieces (Correct Score)**
"Croatia's set piece delivery has produced 0.42 headed goal attempts per corner kick in competitive matches — among the highest in international football. Canada's aerial defensive record concedes 0.38 set piece goals per 90. The interaction suggests a meaningful probability of a headed set piece goal in this match, which systematically shifts the correct score distribution toward scorelines featuring at least one Croatia goal from a dead ball — 1-0, 2-1, and 1-1 are all structurally elevated above the base DC model."

**12 — BTTS Signal from Attacking Parity (BTTS — yes signal)**
"England and Germany both carry significant attacking threat and both have below-average defensive records in this tournament. England's expected goal total is 1.6 against Germany's defense; Germany's expected goal total is 1.4 against England's defense. Both teams have scored in their last five competitive matches. The matchup produces a bivariate Poisson probability of 67% for both teams to score — 8 percentage points above the implied market probability."

**13 — Dominant Goalkeeper vs High Shot Volume (BTTS — no signal)**
"Morocco's goalkeeper has faced 18 shots in this tournament and conceded 0 goals from open play — saves above expectation of +1.4. Their opponent generates shots freely but at below-average xG per shot (0.098 vs tournament mean 0.118). The interaction suggests Morocco's clean sheet probability is elevated beyond their raw defensive rating, making a BTTS outcome less likely than the market prices."

**14 — Midfield Pressing Disruption (1X2)**
"Spain maintain 72% possession and build through their midfield triangle — but that triangle requires time on the ball to function. Japan's midfield press has disrupted possession-based teams into giving the ball away in dangerous zones in both of their matches, leading to quick transitions. When Spain's midfield is compressed by Japan's press, Spain's characteristic spacing collapses, and their ability to progress through midfield — which drives their attacking output — is directly impaired. The model detects that Japan's tactical system is precisely calibrated to disrupt Spain's primary strength."

**15 — First Match of Tournament — Model Uncertainty (1X2 — low confidence)**
"Neither team has played in this World Cup yet. The model has no within-tournament form data, no lineup confirmation, and no match event data from these specific opponents in 2026. All signals are derived from pre-tournament form alone, which the model weights conservatively. Both teams' ratings carry elevated uncertainty. This signal should be treated as a macro orientation rather than a specific market edge — market data takes priority here."

**16 — Fatigue Asymmetry in Knockout (O/U — under)**
"Portugal played 120 minutes three days ago. Their opponents had a standard 90-minute match with four days rest. At this rest differential, teams with the shorter preparation historically produce 0.6 fewer shots and 0.2 fewer goals per match on average. The fatigue effect is not large enough to change the match winner probability materially, but it creates a meaningful lean toward a lower-scoring, more controlled game that the market may not fully price into the total goals line."

**17 — Transition Speed Mismatch (1X2 — directional signal)**
"Mexico's transition speed is the highest in this tournament — when they win the ball in their own half, they cover ground to the opponent's box in an average of 6.8 seconds. South Africa's defensive line is positioned high and takes 9.2 seconds on average to retreat and reorganize after losing possession. This 2.4-second asymmetry is significant: it means South Africa's defensive reorganization is regularly too slow to stop Mexico's transitions, creating high-probability counter-attack opportunities that the Elo-based model only partially captures."

**18 — Anytime Scorer — Key Player vs Goalkeeper Quality**
"Lamine Yamal has scored or assisted in four of his last five competitive international starts. He will face a goalkeeper whose save percentage against shots from his typical zones (right side of the box, 12–20 yards) is below the tournament average. The player-goalkeeper matchup favors Yamal producing a meaningful attacking contribution. This signal is available only with confirmed lineups and is rated high confidence when both are confirmed."

**19 — Player Cards — Technical Player Under Aggressive Defensive Pressure**
"Neymar draws fouls at a rate of 4.8 per 90 — the highest in Brazil's starting XI. His opponent's right back commits 2.9 fouls per 90 and has received 3 yellow cards in the last 8 competitive matches. When Neymar plays down the left flank against this specific defensive player, the historical card rate for the opposing right back increases materially. The model detects a moderate signal for the opposing right back's player card market."

**20 — Tournament Winner Futures — Bracket Path Difficulty**
"Spain's projected path to the final involves opponents ranked in the bottom third of the tournament field by Elo rating through the quarterfinals. France, by contrast, face a likely semifinal against Argentina or Brazil. The matchup engine detects a structural advantage in Spain's knockout bracket path that the tournament winner market does not fully reflect in the current odds differential between the two teams. This is a bracket difficulty signal, not a team quality signal — Spain's advantage is contextual, not absolute."

---

## 8. Prioritization

### 8.1 Ranking Methodology

Each matchup feature group is evaluated on four dimensions:

- **Predictive value (PV):** Estimated marginal improvement to market model accuracy if this group is implemented correctly, on a 1–10 scale.
- **Implementation difficulty (ID):** Engineering effort including data pipeline complexity, Stage 2 dependency, and validation requirements. 1 = easy (derived from existing features), 10 = hard (new data source + validation).
- **Data availability (DA):** How readily available is the required data today. 1 = mostly unavailable, 10 = fully available at Stage 1.
- **ROI:** Combined judgment of (PV / ID) × DA — the return on implementation investment.

| Rank | Group | PV | ID | DA | ROI | Primary market impact | Why this rank |
|---|---|---|---|---|---|---|---|
| 1 | **Form & Momentum Clash** | 9 | 2 | 10 | **45** | 1X2, DNB, Tournament Futures | Entirely derived from existing feature store features. Form momentum clash and tournament trajectory clash require zero new data. High predictive value because momentum is real and the Elo model has no in-tournament decay. Build this first. |
| 2 | **Shot Creation & Quality Clash** | 9 | 4 | 7 | **16** | O/U, BTTS, Correct Score, Shots | StatsBomb provides xG and shot quality at Stage 1 for historical priors. Shot volume clash requires Stage 2 but the quality features are immediately available. Opens O/U and shots markets that currently have no matchup signal. |
| 3 | **Defensive Resistance Clash** | 8 | 3 | 8 | **21** | O/U, BTTS, Correct Score, 1X2 | Primarily derived from clean sheet rates, goals conceded, and DC parameters — all Stage 1. Defensive stability gap is one of the most predictive individual features for O/U markets. Low implementation difficulty given existing feature store. |
| 4 | **Tournament & Physical Context Clash** | 7 | 2 | 9 | **32** | 1X2, O/U, Tournament Futures | Rest days, altitude, and climate features are already in the feature store — the matchup versions are simple deltas between the two teams. Altitude specifically is an underpriced, highly specific feature for WC 2026 given three hosts and the Mexico City venue. |
| 5 | **Set Piece & Aerial Clash** | 8 | 4 | 6 | **12** | Corners, BTTS, Correct Score | StatsBomb open data provides set piece goal rates. Corner generation vs concession clash is the single most important feature for the corners market — the highest ROI specialty market feature. Requires Stage 2 for live rolling data but StatsBomb priors cover WC historical calibration. |
| 6 | **Market Efficiency Interaction** | 8 | 2 | 9 | **36** | All markets (confidence modifier) | Implemented as a post-processing layer on top of all other matchup signals. The market comparison (matchup_model_market_gap, drift concordance) adds the most value as a signal quality filter, not a new signal source. Low effort, high leverage. |
| 7 | **Possession & Territorial Clash** | 7 | 5 | 5 | **7** | Corners, Shots, 1X2 context | Requires Stage 2 possession and pass completion data. Moderate predictive value — possession is a context setter for other signals more than a direct predictor. Implement after shot-based markets are live. |
| 8 | **Discipline & Foul Dynamics Clash** | 8 | 4 | 5 | **10** | Cards O/U, Player Cards | Cards market requires Stage 2 for all key inputs (fouls per 90, yellow cards per 90, referee card rate). High importance for the specific cards market but that market has zero signal at Stage 1. Priority moves up as soon as Stage 2 is active. |
| 9 | **Tactical Style Interaction** | 7 | 6 | 4 | **5** | 1X2, O/U, Shots | The most conceptually important group but the hardest to implement correctly. Counter-attack vs high line, direct play vs high press — these features require StatsBomb event-level tactical classification or Stage 2 possession/direct play metrics. High potential predictive value but hard to validate. Implement after all Stage 2 data is stable. |
| 10 | **Player Quality Interaction** | 6 | 7 | 4 | **3** | Anytime Scorer, Player Props | Requires confirmed lineups (Stage 2), player-level shot and card stats (Stage 2), and StatsBomb player event data. The most granular group with the lowest ROI relative to complexity. Implement last as a premium feature layer. |

### 8.2 Recommended Build Order

**Phase 1 — Immediate (Stage 1, derived features only):**
Form & Momentum Clash → Market Efficiency Interaction → Defensive Resistance Clash → Tournament Context Clash

These four groups require zero new data sources and are entirely derived from features already defined in FEATURE_STORE_BLUEPRINT.md. They unlock matchup intelligence for 1X2, DNB, O/U, and tournament futures markets immediately.

**Phase 2 — Stage 2 activation (API-Football + Odds API paid):**
Shot Creation & Quality Clash → Set Piece & Aerial Clash → Discipline Clash

These groups unlock the specialty market signals — corners, cards, shots, BTTS — that are the product differentiator over simple rating-based models.

**Phase 3 — Deep StatsBomb integration:**
Tactical Style Interaction → Possession & Territorial Clash

These groups require StatsBomb event-level tactical features — carry sequences, pressure maps, pass networks. High predictive value but require careful validation on international football data, which is sparser than club data in StatsBomb's open catalog.

**Phase 4 — Stage 2 maturity + lineup data:**
Player Quality Interaction

Only meaningful when lineups are confirmed and player-level statistics are stable. Build last.

### 8.3 Single Most Important Feature

If only one matchup feature could be implemented, the answer is `counter_attack_vs_high_line_clash`. It is the most statistically reliable tactical interaction in football — directly responsible for some of the largest upsets and prediction errors in World Cup history — and it requires only two Stage 2 features (`counter_attack_style_flag`, `defensive_line_height_proxy`) to produce a meaningful signal. No other single feature changes the 1X2 probability as sharply when triggered.

---

*End of MATCHUP_ENGINE_BLUEPRINT.md*
