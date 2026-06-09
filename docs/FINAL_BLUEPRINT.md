# World Cup 2026 — What I Would Actually Build

*Written from the Head-of-Quant-Research chair: comp tied to calibration and long-run EV, 90 days, solo, Claude Code. No academic theater, no resume padding. The parts that make money (or credibility) and nothing else.*

---

## Part 1 — The real objective function

Most people building this optimize "predict the winner." That's the amateur tell. Here is the hierarchy I'd actually optimize, in order:

**Primary: calibration-weighted forecasting accuracy, scored by proper scoring rules (RPS for 1X2, log-loss for binary markets), benchmarked against the de-vigged market closing line.**

Why this and not "betting profitability": because I have twenty years of watom-out paper-ROI strategies dying against the closing line. World Cup markets are among the most liquid, most-bet, most-efficient markets in sport. As a solo dev with public data, **my realistic ceiling is to roughly match the closing line, not beat it.** Optimizing for "profit" would just optimize for overfitting to the vig. Proper scoring rules can't be gamed, compound directly into EV, and are the only honest currency.

**Secondary: closing-line value (CLV) as a diagnostic, not a target.** I track whether my number systematically beat or lagged the closing price. Positive CLV = I might have real edge. But I use it to *audit myself*, not to optimize toward — because optimizing toward CLV on small samples is how you fool yourself.

**Tertiary, and where I'd actually spend my differentiation budget: tournament-simulation quality.** This is the insight most people miss. There are two different objective functions hiding here:
- *"Predict this match"* → I tie the market at best. Low marginal return on effort.
- *"Simulate the tournament correctly and propagate uncertainty"* → I can be genuinely, visibly **better than 95% of public sims**, because almost all of them botch the 2026 format (the eight best third-placed teams, the new Round of 32) and almost none propagate *parameter* uncertainty ("we're not sure how good Morocco is") into advancement probabilities.

So the real objective function is: **be as calibrated as the market on individual matches, be honest about it, and be the best tournament simulator on the public internet.** That's a target I can actually win.

---

## Part 2 — Throw away 80%. What survives.

**Keep (this is the 20% that carries the project):**
1. Historical results spine (martj42).
2. **Market odds — but as the prior and the benchmark, not a "comparison."**
3. Calibration harness: RPS / log-loss / Brier / reliability diagrams / isotonic. Built *first*.
4. Monte-Carlo tournament simulator (the product).
5. The honest UX: a public **calibration + CLV scoreboard**, confidence, casual/nerd explanation.
6. GitHub Actions cron → static artifacts. DuckDB.

**Burn (low leverage / negative leverage):**
- Custom Dixon-Coles / Elo / Poisson code → `pip install penaltyblog`.
- The MVP→V1→V2→Pro ladder (ceremony).
- Bayesian-hierarchical NumPyro "Pro tier" (the *idea* survives cheaply; the MCMC machinery doesn't earn its keep).
- Postgres/Supabase, Celery/Redis, the 14-table schema.
- 90% of the REST API surface.
- Corners/cards markets (unmodelable on free data).
- All deep learning (NN/Transformer/GNN/RL).
- ~80% of the "creative features." Keep "Avoid Betting," "Model vs Market," upset/advancement views. Cut chaos index, hype-trap, sentiment.
- Injury-monitoring agent (postpone — unreliable, high maintenance).

**Ruthless principle:** every component must either improve a proper scoring rule, improve the simulator, or improve honesty/credibility. If it does none of those, it dies.

---

## Part 3 — My prediction engine

Six components. Each exists for a reason I can defend in a risk meeting.

### 1. Rating system — dynamic, uncertainty-aware team strength *(the core)*
Not static Elo. I maintain **time-decayed attack/defense ratings** (Dixon-Coles weighting, ξ decay so a 2024 match counts more than a 2019 one) **with a variance attached to each team.** Implementation: penaltyblog's time-weighted Dixon-Coles refit on a rolling window, wrapped so each team also carries an uncertainty estimate (bootstrap the fit, or a Glicko-style rating-deviation). *Why:* in a tournament you must know **when you don't know.** A team with five recent competitive matches is a tighter estimate than a qualifier you've barely seen. That uncertainty must flow into the sim.

### 2. Goal/score model — bivariate Poisson / Dixon-Coles + Skellam view
Turns (attack, defense, home/host adjustment) into a full **score-probability matrix** → every market (1X2, O/U, BTTS, Asian handicap) read off one matrix. The **Skellam distribution** (difference of two Poissons) gives a clean 1X2 / goal-difference view and handles handicaps elegantly. *Why:* this is the standard, it's library-provided, and it's *good enough* — the goal model is not where the edge is.

### 3. Fundamental prior — Transfermarkt squad value
Pre-tournament and for thin-data teams, I regularize ratings toward a prior built from **squad market value** (+ confederation/era adjustments). *Why:* this is the single best fundamental feature for sparse international data — it's exactly the lever FiveThirtyEight's SPI pulled. For a 48-team field with weak qualifiers who've played almost no comparable opponents, this prevents the model from being clueless about the long tail.

### 4. Market integration — *the actual secret sauce*
- **De-vig the closing line properly** — Shin's method or the power method, **not** naive normalization, because the favorite-longshot bias matters. (penaltyblog has overround removal.)
- **Blend** model probabilities with market probabilities. Honest default weighting is **market-heavy** (≈ 75–90% market / 10–25% model), tuned on holdout by log-loss. *Why:* the market is more accurate than me on liquid markets. My model earns its weight in two places: (a) markets that aren't posted (group-permutation and deep-knockout hypotheticals), and (b) defensible divergences (a late injury, an obvious public overreaction). Everywhere else, I defer to the market and say so.

### 5. Simulation engine — see Part 8
Monte Carlo over the exact 2026 bracket, **sampling team strengths from their posterior each run**, not just match outcomes. *Why:* that's the difference between a real forecast and a toy. Most public sims fix the ratings and only randomize results; they understate uncertainty badly.

### 6. Calibration, confidence, updating
- **Calibration:** isotonic regression fit on a *large* out-of-sample set (club leagues, where I have thousands of matches with closing odds), then applied to internationals — because 104 internationals can't calibrate anything. Reliability diagrams published live.
- **Confidence:** a function of market liquidity/agreement, rating posterior variance for those teams, data freshness, and the model-vs-market gap (a *big* unexplained gap lowers confidence — it usually means I'm wrong, not the market).
- **Updating:** after each match, update ratings **online** (cheap, principled, Bayesian) and **re-anchor to the new market** for the next round. I do **not** "retrain an ML model on 104 rows" — that's noise cosplaying as learning.

---

## Part 4 — Data, ranked by *actual* predictive value

The top 5 carry ~80% of achievable signal. Everything from 11 down is diminishing returns I'd add only if cheap.

| # | Source | Why | Free? |
|---|---|---|---|
| 1 | **De-vigged closing odds (Pinnacle / Betfair Exchange)** | The benchmark *and* the best single feature. Exchange = lowest effective margin = closest to truth. | Snapshots free-ish; historical international = scarce (collect your own at kickoff) |
| 2 | **Opening→closing line movement** | Sharp-money signal; where the smart money moved. | Needs repeated snapshots (you have `captured_at`) |
| 3 | **Transfermarkt squad market value** | Best fundamental prior, esp. for thin-data teams. | Scrape |
| 4 | **Historical international results (martj42)** | The spine; powers ratings, form, H2H. | Free/open |
| 5 | **Self-computed time-decayed attack/defense ratings (w/ uncertainty)** | Derived, but the core strength estimate. | Free (compute) |
| 6 | **Elo (eloratings.net)** | Cheap decent rating; partly redundant with #5. | Free |
| 7 | **Confirmed lineups (~1h pre-KO)** | High value *if* obtainable; mostly isn't free. | Scrape/paid |
| 8 | **Key injuries/suspensions of stars** | High value *if* reliable; fragile. | Scrape/LLM-extract |
| 9 | **Match context: host advantage, altitude (Mexico City!), travel, rest, heat** | Real and cheap; 2026 has three hosts + altitude + summer heat. | Free (derive) |
| 10 | **FIFA ranking** | Weak feature; also used in real 2026 seeding. | Free |
| 11 | **Team xG / underlying perf (FBref where available)** | Sparse for nations; modest. | Scrape |
| 12 | **Squad experience: caps, age, continuity** | Cheap, modest. | Scrape |
| 13 | **Opponent-adjusted recent form** | Derived; modest, partly in ratings. | Free |
| 14 | **Competitive-vs-friendly weighting** | Data-quality signal, not a feature per se. | Free |
| 15 | **Head-to-head** | Mostly noise at international level; tiny weight. | Free |
| 16 | **Set-piece / penalty propensity** | Marginal; matters for shootout prior. | Scrape |
| 17 | **Weather at venue (extremes only)** | Marginal except heat/altitude. | Free API |
| 18 | **Manager/tactical-change flags** | Hard, marginal. | Manual |
| 19 | **Public betting % / ticket counts** | Fade-the-public signal; hard to get free. | Paid |
| 20 | **Social sentiment** | Mostly noise / public-bias proxy. Lowest. | Scrape |

**The honest line:** if I could only have three, I'd take **closing odds, squad value, and historical results** and beat a kitchen-sink model built on the other seventeen.

---

## Part 5 — What I install vs build

**Install (don't you dare reimplement):**
- **penaltyblog** — Dixon-Coles, bivariate Poisson, Elo/Massey/Colley/pi ratings, **overround removal, Kelly, RPS, backtesting**, FBref/Understat/ClubElo scrapers. ~60% of the engine.
- **soccerdata** — scraping ClubElo/FBref/etc. into pandas.
- **scipy / scikit-learn** — isotonic calibration, stats.
- **polars + duckdb** — data layer.
- *(Optional, only if I go event-data deep, which I probably won't for the core)* **socceraction** (VAEP/xT) + **kloppy** (event-data standardization).

**Datasets:**
- **martj42/international_results** (spine), **FiveThirtyEight SPI historical** (Kaggle — dead model, but a free strong baseline to benchmark against), **StatsBomb Open Data** (optional xG study), **Transfermarkt** (scrape).

**Build (because nothing good exists):**
- The **2026-format Monte-Carlo simulator** (new format → genuinely custom; worth doing perfectly).
- The **market-blend + CLV + calibration harness** (your differentiator).
- The **frontend + scoreboard.**

**Time saved by reuse: ~150–250 hours.** That recovered time goes entirely into the simulator and the honesty harness — the only places I can out-execute the field.

---

## Part 6 — Models: use / reject

| Model | Verdict | Reason |
|---|---|---|
| **Dixon-Coles (time-decayed)** | **Use** (goal layer) | Standard, library-provided, good enough. The edge isn't here. |
| **Bivariate Poisson / Skellam** | **Use** | Clean score matrix + handicap/1X2 view. |
| **Elo / Glicko / dynamic ratings** | **Use** | Cheap, robust rating with uncertainty. The right core. |
| **Bayesian hierarchical** | **Use the *idea*, skip the machinery** | Partial pooling + uncertainty is exactly right; full NumPyro/Stan MCMC is low marginal ROI here. Get the same benefit from a dynamic rating with variance. |
| **LightGBM** | **Use sparingly** | Only as a small, heavily-calibrated ensemble member / feature explorer. Low weight. |
| **XGBoost / CatBoost** | **Reject as primary** | Marginal over LightGBM; data-starved on internationals. |
| **Neural nets** | **Reject** | A few hundred informative matches. Overfits. Loses to Skellam. |
| **Transformers / sequence models** | **Reject** | No sequence data at the right scale; pure novelty cost. |
| **GNNs** | **Reject (for prediction)** | Shine on tracking/event graphs with millions of actions, not 48 sparse nodes. Quarantine as a separate StatsBomb learning study if you want it on the résumé. |
| **Reinforcement learning** | **Reject** | No environment, no reward signal that isn't already the market. Pure theater. |
| **LLM-as-predictor** | **Reject** | Hallucinated probabilities. LLMs narrate and extract; they don't forecast. |

**One-line doctrine:** *Poisson-family for goals, dynamic ratings for strength, the market for truth, isotonic for honesty. Everything fancier is ego.*

---

## Part 7 — Strongest architecture (90 days, reputation on the line)

Strongest ≠ most scalable. The data is tiny (48 teams, 104 matches, a few thousand historical rows). **The strongest architecture is the simplest one that is reproducible, honest, and lets me iterate the model daily without touching infra.**

```
GitHub Actions  (nightly cron + post-match trigger)
  └─ Python job (Polars):
       pull  → soccerdata / martj42 / Transfermarkt / odds snapshot
       store → DuckDB + Parquet  (raw append-only ▸ curated layers)
       model → penaltyblog ratings + dynamic uncertainty
             + Transfermarkt prior + de-vig + market blend
       sim   → 2026 Monte-Carlo (NumPy/Numba, seeded)
       score → isotonic calibration, RPS/log-loss vs market, CLV
       narrate → LLM explanations (structured-output, cached)
       emit  → static JSON + SQLite artifact  → repo / R2
  Astro (mostly static, islands for the sim)  →  Vercel
  (optional) thin FastAPI only for live mid-tournament odds refresh
```

- **Storage:** DuckDB/Parquet for everything analytical; SQLite snapshot for the site. **No Postgres until there are user accounts** (there won't be in 90 days).
- **Backend:** essentially none. The "API" is a folder of versioned JSON. *(This is a feature, not a limitation — it shows I right-sized the system.)*
- **Frontend:** Astro > Next here (ship less JS; island the interactive simulator). Vercel free tier.
- **CI/CD:** GitHub Actions runs tests + the scheduled pipeline; a clean-clone smoke test gates merges; the sim runs with fixed RNG seeds so published numbers are reproducible.
- **Monitoring:** the **public calibration/CLV scoreboard is the monitoring** — I'm grading myself in the open. Plus pipeline-failure alerts and a data-freshness banner.

---

## Part 8 — The simulator (the centerpiece, done properly)

### Format (encode exactly, from the official source)
48 teams → 12 groups of 4 → round-robin (3 matches each). Within-group ranking cascade: **points → goal difference → goals scored → head-to-head → disciplinary/fair-play → drawing of lots.** Advance: **top 2 per group (24) + the 8 best third-placed teams (of 12)** → **Round of 32 → R16 → QF → SF → Final** (+ third-place playoff). Third-placed ranking uses the same cascade across the 12 groups; the eight qualifiers are slotted into the bracket via FIFA's **predetermined assignment table** (the mechanism the Euros use — implement the official lookup; don't improvise it). Knockouts level after 90' → extra time (scale goal rates to ~⅓ for 30'), then **penalty shootout** modeled as ~50/50 with a small skill/historical prior.

### Algorithm (per simulation run)
1. **Sample each team's strength** (attack/defense) from its posterior — *parameter uncertainty, not just match noise.*
2. For each group match, draw a scoreline from the bivariate Poisson given sampled strengths + host/venue adjustment.
3. Build all 12 group tables with the **exact tiebreak cascade.**
4. Rank the 12 third-placed teams; select the **best 8**; map them to bracket slots via the official assignment table.
5. Simulate knockouts (score → ET → shootout) to the Final.
6. Record each team's furthest stage.

Aggregate over all runs → **win-group, reach-R16/QF/SF/Final, win-trophy**, each with a Monte-Carlo standard error.

### How many sims
Driven by the precision I need on small probabilities. MC standard error ≈ √(p(1−p)/N). For a 1% trophy probability:
- N = 100k → SE ≈ 0.0003 (≈3% relative) — fine for display.
- N = 500k → SE ≈ 0.00014 — when I want clean tails for dark-horse teams.

So I run **100k nightly, 500k for the published pre-tournament forecast and after big shifts.** Vectorize in NumPy (or Numba) — 100k full-tournament runs land in seconds-to-low-minutes. Re-run nightly and after every match (ratings updated online, then re-anchored to the new market). **Reconcile** to de-vigged market outright odds where they exist — the sim shouldn't silently contradict the market on who wins the trophy.

### Validation (non-negotiable)
- Unit-test the tiebreak + best-third-place + bracket-assignment logic on hand-built synthetic standings.
- Backtest the sim machinery on 2014/2018/2022 — confirm advancement probabilities are calibrated against what actually happened.

---

## Part 9 — Impressive vs fluff

**Creates real signal (quants, MLEs, sports analysts, hiring managers all clock this instantly):**
- A **live public calibration + CLV scoreboard** grading the model honestly against the market. **Almost no portfolio project does this. It is the single most credible thing you can ship.**
- **Correct market de-vigging** (Shin/power), and a transparent **model↔market blend** with a defended weight.
- **Parameter-uncertainty propagation** through the simulator.
- A **correct, tested 2026-format simulator** (third-place logic + bracket assignment).
- A **right-sized, reproducible pipeline** (cron → static artifacts) — shows judgment, not just ability.
- A writeup using **proper scoring rules** with the honest conclusion: *"Did we beat the market? Mostly no. Here's exactly where we diverged and why."*

**Resume fluff (actively hurts you with people who know):**
- A transformer/GNN/RL model that underperforms Elo.
- Microservices, Kubernetes, a 14-table schema for 104 matches.
- Headline features named "Chaos Index" / "Hype Trap" / sentiment.
- Any claim of "high-probability bets" or profitability.
- A model zoo with no benchmark and no calibration.

The meta-signal: **maturity.** Knowing what *not* to build, and being honest about the ceiling, is what separates someone who's shipped real systems from someone who read a Medium post.

---

## Part 10 — Final blueprint

**The product:** *"The most honest public World Cup 2026 forecaster on the internet."* A calendar, match pages showing **model + de-vigged market + the blend** with a grounded plain-language explanation, a beautiful **interactive tournament simulator** as the hero, and a **live calibration/CLV scoreboard** as the credibility centerpiece. Betting suggestions exist only as an opt-in, no-real-money, educational "here's what EV means and why beating the market is hard" mode.

**Built on:** penaltyblog + martj42 + Transfermarkt + odds snapshots; DuckDB/Parquet; Astro on Vercel; GitHub Actions cron; LLM for narration only.

**What I will NOT build:** any deep model, Postgres/Supabase, a queue, a microservice, corners/cards markets, an injury agent, a profitability claim.

### 12-week roadmap

| Wk | Goal | Deliverable | Done-when |
|---|---|---|---|
| 1 | **Honesty harness first** | DuckDB/Parquet ingest (martj42 + fixtures + a market snapshot); CLV/backtest skeleton; 48-team alias table | Every team resolves to one id; a dummy prediction gets scored vs market |
| 2 | **Baselines to beat** | Install penaltyblog: ratings + DC + de-vig + RPS; pull SPI historical as comparison | Closing line + SPI baseline graded by RPS/log-loss on holdout |
| 3 | **Ratings done right** | Time-decayed attack/defense **with uncertainty** + Transfermarkt squad-value prior | Ratings carry variance; thin-data teams regularize to prior |
| 4 | **Market blend** | Shin/power de-vig + tuned model↔market blend | Blend beats model-alone *and* isn't worse than market on holdout log-loss |
| 5 | **Simulator core** | 2026 Monte-Carlo: groups + best-8-thirds + bracket assignment, parameter sampling | Tiebreak/third-place unit tests pass; 100k runs in <2 min |
| 6 | **Sim validation + calibration** | Backtest sim on 2014/18/22; isotonic calibration on club data | Advancement probs calibrated historically; reliability diagram clean |
| 7 | **Frontend skeleton (Astro/Vercel)** | Calendar + match page (model/market/blend) | Reads static JSON; mobile-first |
| 8 | **Hero: interactive simulator + scoreboard** | Advancement/trophy view; **live calibration/CLV scoreboard** | Both render from artifacts; numbers reproduce with seeds |
| 9 | **Grounded LLM explanations** | Structured-output narration (casual/nerd), cached in the job | Explanations never state a number the model didn't produce |
| 10 | **Pipeline + reproducibility** | GitHub Actions nightly + post-match trigger → artifacts; docker compose; clean-clone CI | One command reproduces; cron green |
| 11 | **In-tournament behavior + polish** | Online rating update + market re-anchor; confidence decay; "what we don't model & why" page | Post-match update is idempotent; honesty page live |
| 12 | **Launch + writeup** | Blog: *"I tried to forecast the World Cup honestly — here's the scoreboard, win or lose"* | Public, reproducible, graded against the market |

**The bet I'm making:** I won't beat the World Cup closing line, and I'll say so in the README. What I *will* ship is a rigorously calibrated, beautifully simulated, self-grading forecaster that is more honest than anything else public — and in this domain, demonstrable honesty is the rarest and most valuable signal there is. That's the project that gets me hired onto the desk, not a fictional edge.
