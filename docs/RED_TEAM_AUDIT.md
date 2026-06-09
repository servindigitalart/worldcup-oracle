# World Cup Oracle — Red-Team Audit

*A panel review written to be useful, not flattering. The proposal is competent. It is also, in places, solving the wrong problem.*

---

## The one-paragraph verdict

This is a **well-constructed engineering proposal for the wrong objective function.** It is framed as a betting-suggestion machine and reviewed (per your request) by people who beat betting markets for a living — and from that chair, the proposal commits the field's most common rookie error: **it never benchmarks against the betting market, treats bookmaker odds as a "comparison" feature instead of the thing to beat, and computes "expected value" against soft-book prices that already contain the vig.** That single framing error means its headline product ("suggested high-probability bets") is the part most likely to lose money and least likely to impress anyone who understands the domain. The good news: the *same engine*, reframed as a **transparent probabilistic forecaster + World Cup simulator**, is an excellent portfolio project — and most of the modeling layer should be *installed*, not *written*.

---

## Section 1 — Executive assessment (scored 1–10)

| Dimension | Score | One-line justification |
|---|---|---|
| Product vision | **5** | "Betting machine" is the weakest, most legally fraught framing of a strong underlying idea. |
| Data strategy | **6** | Good free-tier mapping; **badly mis-prioritizes** what actually predicts international football (squad value, market odds). |
| Modeling strategy | **6** | Textbook-correct and reuse-ignorant; no market anchor; over-indexed on in-tournament calibration that the sample size can't support. |
| Architecture | **6** | Pragmatic but **overbuilt for ~104 matches of tiny data**. You're provisioning a SaaS backend for a spreadsheet's worth of rows. |
| Scalability | **7** | Scales fine — but scalability is a non-problem here, so credit is hollow. |
| Reliability | **6** | Adapter/fallback thinking is good; scraper fragility and free-tier limits are underestimated. |
| UX | **7** | Strong instincts (confidence gauge, casual/nerd toggle). The dashboards are the real product and deserve more weight. |
| Open-source value | **5** | Reinvents maintained libraries (penaltyblog, socceraction, kloppy). Leverage left on the table. |
| Portfolio value | **7** | Already good; becomes a **9** if you (a) reuse libraries, (b) add a market benchmark, (c) reframe away from "betting." |
| Predictive potential | **4** | For 1X2 on a 48-team tournament, you will not beat the closing line. Honest expected edge ≈ zero. The *honesty about that* is where the value is. |

**Genuinely excellent:** the calibration-first instinct (RPS/Brier/log-loss, reliability curves), the "Avoid Betting" first-class output, No-Real-Money default, GitHub Actions cron instead of a standing worker, and the name-normalization-as-first-class-problem call. These are things people with scars make. Keep all of it.

**Average:** the model menu (correct, unremarkable, mostly library-provided), the schema (fine but heavy), the roadmap (sensible but front-loads infrastructure over signal).

**Weak:** treating odds as a late-stage "comparison"; deprioritizing Transfermarkt squad value; the 4-tier MVP→Pro ladder (ceremony); the Bayesian-hierarchical "Pro" tier (cool, low marginal ROI here).

**Naive:** (1) EV computed against soft-book odds = manufacturing fake edges out of the vig. (2) "The system improves during the tournament via calibration" — **104 matches is statistically too small to calibrate or meaningfully retrain.** That's the most important sentence in this document. (3) Implicit belief that a better model yields profitable bets on World Cup markets, which are among the most efficient and most heavily traded markets in sport.

---

## Section 2 — Data audit

### The mis-prioritization that matters most
International football is **data-starved**: ~10 matches/team/year, heavy squad churn, friendlies that lie. In that regime, **the strongest single feature is squad market value (Transfermarkt)** — it's the prior FiveThirtyEight's SPI leaned on precisely because recent results are too sparse to trust. The proposal files Transfermarkt under "hard/scrape, deprioritize." **Backwards.** It should be a Phase-1 feature. Squad value + a market-anchored prior will out-predict any amount of Dixon-Coles fiddling on this dataset.

The second-strongest signal is **the betting market itself** (de-vigged Pinnacle closing line). The research consensus is blunt: bookmaker consensus closing probabilities are very well calibrated and extremely hard to beat. So the market isn't a "comparison" — it's your **prior and your benchmark**. Ignoring it as a feature is leaving the best dataset in the building unused.

### Datasets, ranked by value-add for *this* project

1. **Transfermarkt squad valuations** (scrape via `worldfootballR`/`soccerdata`/`transfermarkt` scrapers) — *highest impact*. The best tournament prior. Difficulty: medium (scrape). Add: materially better pre-tournament ratings.
2. **De-vigged market odds, esp. Pinnacle/Betfair Exchange closing lines** — *highest impact*. Your benchmark and a feature. Exchange prices (Betfair) have the lowest effective margin and are the closest thing to "true" probabilities.
3. **martj42/international_results** — already in the proposal; correctly the spine. Keep.
4. **FiveThirtyEight SPI historical data (Kaggle mirror) + its published methodology** — *high*. 538's sports models are dead (Disney shuttered the site; Nate Silver left in 2023 with his models), but the SPI methodology (off/def ratings → Poisson, Transfermarkt priors, shot & non-shot xG) is a documented blueprint you can clone, and the historical SPI CSV is a ready-made strong baseline to benchmark against.
5. **StatsBomb Open Data** — *medium-high for learning, low for live*. Includes the 2018 men's World Cup, Women's World Cups, Euros — event-level data with xG. Great for building/learning an international xG and VAEP layer; not live, not 2026.
6. **Club Elo / eloratings.net** — *medium*. eloratings.net for nations (Club Elo is clubs — the proposal already flags this; good). Honestly, compute your own rating with uncertainty (below) and you need neither.
7. **Wyscout open data sample / StatsPerform** — *low-medium*. Useful only if you go deep on event data.
8. **openfootball (JSON/CSV on GitHub)** — *low-medium*. Clean fixtures/results, good fallback for schedule data without an API key.

### Open-source projects that already solved your problems (see also §5)
- **penaltyblog** — Dixon-Coles (Cython), bivariate Poisson, Elo/Massey/Colley/pi-ratings, **Kelly criterion, odds de-vigging (overround removal), backtesting, RPS, implied-odds tooling**, and FBref/Understat/ClubElo/FPL scrapers. This is ~60% of your modeling+betting-math layer, maintained and fast.
- **socceraction** (KU Leuven) — SPADL + **VAEP/xT** action values, loaders for StatsBomb/Opta/Wyscout. The credible path to a "team quality from underlying performance" signal. (Note: maintained for reproducibility, not actively featured.)
- **kloppy** (PySport) — vendor-independent event/tracking data model. The plumbing layer if you touch event data.
- **soccerdata** (already in proposal) — keep for scraping.

**Bottom line:** your "build a custom Dixon-Coles" task is reinventing a Cython-optimized, tested wheel. Install penaltyblog and spend the saved week on the market benchmark.

---

## Section 3 — Modeling audit

### What a quant betting desk actually deploys today
Not a fancier goal model. They deploy: **(1) the sharp market (Pinnacle/Betfair closing line) as ground truth, de-vigged**, (2) their own model **as a small, well-calibrated deviation from that prior**, and (3) ruthless **CLV tracking** — did you beat the closing line? — as the only metric that survives contact with reality. They size with **fractional Kelly** and they assume the market is right until proven otherwise on out-of-sample CLV. Most "edges" found against soft books are vig + overfitting; the research literature is full of paper-ROI strategies that evaporate against closing prices and fees.

So: **would they still use Dixon-Coles?** As a goal-market *layer* (over/under, BTTS, correct score, Asian handicap), yes — Poisson-family models remain the standard way to turn an expected-goals pair into a full score matrix, and a fund will still use bivariate Poisson / Skellam for that. As a *primary 1X2 predictor that beats the market?* No.

### Your specific questions, ranked by expected real-world impact (here, not in the abstract)

**Tier 1 — do these:**
- **Market odds as features + de-vigged closing line as a training target (distillation).** Highest impact, lowest effort. Teaches your model to track the sharpest available estimate.
- **Squad/transfer-market valuations as priors.** Best fundamental feature for sparse international data.
- **Dynamic, uncertainty-aware team ratings** — i.e. a **state-space / Kalman-filter rating**, or **Glicko/TrueSkill-style** ratings that carry a *variance*, not just a point. This is the *correct* upgrade over static Elo and what funds use for ratings: it knows when it doesn't know (exactly the WC problem — teams arrive with stale, high-variance form). **Bayesian dynamic rating ≈ Kalman ≈ TrueSkill** are the same idea; pick one, implement once.
- **Bivariate Poisson / Skellam goal layer** for the goal markets, anchored to the rating + market.
- **Isotonic calibration + Monte-Carlo tournament sim.** The sim is where the real product output lives (advancement / win-trophy probabilities); the per-match model is almost a detail by comparison.

**Tier 2 — marginal here:**
- **LightGBM/XGBoost/CatBoost** on engineered features: strong on data-rich club leagues, **marginal and overfit-prone on ~hundreds of relevant international rows.** Use only as a small ensemble member, heavily calibrated. CatBoost over XGBoost only if you have categorical features worth it; you mostly don't.
- **Player availability / lineup-strength models:** high impact *if* you had the data. You won't, cheaply. Approximate via squad value minus known absentees.

**Tier 3 — gimmicks for this project (high effort, ~zero edge on 104 matches):**
- **Deep learning, GNNs, transformers, sequence models, player embeddings.** These shine on **tracking/event data** (modeling player interactions, possessions) where samples are millions of actions — not on **result prediction with a few hundred informative internationals.** A GNN over a 48-team graph with sparse edges will overfit gloriously and lose to a Skellam model. If you want to *learn* GNNs, do it on StatsBomb event data as a separate study, not in the prediction path. Be honest in the README that you considered and rejected these *for sound reasons* — that's a stronger portfolio signal than bolting on a transformer that underperforms Elo.

**The uncomfortable summary:** ranked by realized impact on this tournament — *market anchor > squad-value prior > uncertainty-aware rating > Monte-Carlo sim > goal-market Poisson layer > GBM ensemble member >>> everything deep.* The proposal's "Pro = Bayesian hierarchical NumPyro" is intellectually lovely and near the bottom of the impact list.

---

## Section 4 — Missing features, ranked by ROI

| Feature | Impact | Difficulty | ROI | Verdict |
|---|---|---|---|---|
| **Closing-line value (CLV) tracking** | Very high | Low | ★★★★★ | The single most important missing thing. Without it you cannot claim any edge honestly. |
| **De-vigged market prior + "beat the market" benchmark** | Very high | Low | ★★★★★ | Turns the project from naive to credible. |
| **Squad-value-based priors** | High | Med | ★★★★☆ | Best fundamental feature. |
| **Line-movement / sharp-vs-public signal** | High | Med | ★★★★☆ | Opening vs closing line drift is real signal; needs odds snapshots over time (you have the `captured_at` field already). |
| **Leakage & p-hacking controls in "value bet" discovery** | High | Low | ★★★★☆ | Scanning many markets for "value" is a multiple-comparisons trap; you'll find noise. Add holdout + multiple-testing discipline. |
| **Wisdom-of-crowds / user prediction layer** | Med | Med | ★★★☆☆ | Good product/engagement; modest predictive value. |
| **Expert/consensus aggregation** | Med | Low | ★★★☆☆ | Cheap, decent baseline blend. |
| **Injury/news intelligence (LLM extraction)** | Med-High *if reliable* | High | ★★☆☆☆ | The only cheap route to data you admitted you can't get — but fragile. See §7. |
| **Social sentiment** | Low | High | ★☆☆☆☆ | Mostly noise/public-bias proxy. Gimmick. |
| **Tournament-narrative modeling** | Low | High | ★☆☆☆☆ | Content, not prediction. |

---

## Section 5 — Open-source leverage (reuse instead of build)

| Build task in proposal | Reuse instead | Hours saved | Risk reduced | Perf gained |
|---|---|---|---|---|
| Custom Dixon-Coles / bivariate Poisson | **penaltyblog** | ~20–40 | High (tested, Cython) | Equal+ (faster) |
| Elo / ratings | **penaltyblog** (Elo/Massey/Colley/pi) | ~10–20 | Medium | Equal |
| Odds de-vigging, Kelly, RPS, backtest | **penaltyblog** | ~20–30 | High | Equal |
| Scrapers (FBref/Understat/ClubElo) | **soccerdata** / penaltyblog | ~20–40 | High (maintenance) | Equal |
| Event-data ingestion + xG/VAEP | **socceraction** + **kloppy** | ~40–80 | High | New capability |
| Historical strong baseline | **FiveThirtyEight SPI** Kaggle CSV + methodology | ~20 | High | Strong baseline for free |

**Net: roughly 150–250 hours of build collapse into integration + glue.** Spend the recovered time on the two things no library gives you: the **market-benchmark/CLV harness** and the **2026-format Monte-Carlo simulator** (the new Round-of-32 + eight-best-third-place logic is genuinely custom and worth doing well).

---

## Section 6 — Product opportunities (beyond betting)

Ranked by *(portfolio value × audience × low-landmine)*:

1. **Transparent probabilistic World Cup forecaster + simulator** ★★★★★ — "538-for-2026 that's dead-honest about uncertainty and shows its calibration live." Same engine, no betting landmines, viral-friendly ("what are Mexico's chances?"), and the strongest possible portfolio story (calibration + simulation + clean engineering). **This is the pivot I'd make.**
2. **Content-generation engine** ★★★★☆ — auto-generated, numbers-grounded match previews/recaps (LLM over your structured outputs). High shareability, shows AI+data integration.
3. **Football-analytics teaching platform / "model that explains itself"** ★★★★☆ — nerd-mode as the product; great for a developer/analyst audience.
4. **Sports-intelligence dashboard (calibration & model-vs-market)** ★★★☆☆ — niche but credible.
5. **Prediction-market / play-money tournament among users** ★★★☆☆ — fun, engagement, sidesteps real-money law.
6. **Betting-suggestion SaaS** ★★☆☆☆ — worst option: legal/regulatory burden, app-store hostility, responsibility load, and the edge is ~zero. Keep the *simulator* public; keep "bets" as an opt-in, no-real-money, clearly-educational mode.

---

## Section 7 — AI opportunities (value vs gimmick)

**Real value:**
- **Grounded natural-language explanations** — pass the *actual numbers* (λ's, rating diff, market prob, EV) to an LLM under a strict template/structured-output contract so it narrates, never invents, the probabilities. This is the proposal's "casual/nerd" idea done right and is a genuine win.
- **LLM-as-extractor for injury/lineup news** — the *only* cheap way to get the data you admitted is unavailable: a scheduled agent reads team-news sources and emits a structured `{player, status, confidence, source}`. High value **if** you treat its output as a low-confidence, human-verifiable signal with citations — not ground truth.
- **Backtest/analysis copilot** — internal tooling to interrogate model performance. Quietly useful.

**Gimmicks (resist):**
- **Automated retraining over 104 matches** — there's nothing to learn from 104 noisy samples; "auto-retrain" is theater. Refit ratings online (cheap, principled); don't pretend the ML model is learning.
- **Multi-agent swarm architectures** — solving coordination problems you don't have. A nightly cron of three plain scripts beats an "agentic" framework here.
- **Sentiment/social agents** — mostly ingesting public bias as if it were signal.

**Rule of thumb:** AI that *narrates or extracts* structured facts = value. AI that *predicts the match better than a calibrated Skellam model* = you're fooling yourself.

---

## Section 8 — Architecture review

**The core critique: you are provisioning a SaaS for a dataset that fits in RAM.** 104 matches, 48 teams, a few thousand historical rows, updated a handful of times a day. That changes the right architecture.

| Component | Keep? | Verdict |
|---|---|---|
| **FastAPI** | **Optional** | If the site is statically generated nightly, you may not need a live API at all. Keep it only for the admin/trigger endpoints or if you want live in-tournament updates. |
| **Next.js** | **Yes** (or Astro) | Good. For a mostly-static, content-heavy forecaster, **Astro is arguably the better fit** (ship less JS, island the interactive sim). |
| **PostgreSQL / Supabase** | **Drop for MVP** | Overkill. **SQLite + DuckDB is plenty — forever — at this scale.** Add Postgres only if you add user accounts/predictions. |
| **DuckDB** | **Yes** | Perfect for the analytics/backtest layer over Parquet. The one storage choice I'd keep enthusiastically. |
| **APScheduler / Celery / Redis** | **Drop Celery/Redis** | No queue needed. |
| **GitHub Actions cron** | **Yes** | The smartest infra call in the proposal. Nightly job → recompute → commit JSON/SQLite artifact → site rebuilds. Zero standing servers. |

**The architecture I'd build today (solo, leverage-max):**
```
GitHub Actions (nightly cron)
   → Python job: pull (soccerdata/martj42/odds) → DuckDB/Parquet
   → ratings (penaltyblog + state-space) + market de-vig (penaltyblog)
   → Monte-Carlo sim (custom, 2026 rules) → calibrated probabilities
   → write static JSON + SQLite artifact to repo / object storage
Astro or Next (Vercel) reads the static artifacts → renders calendar, sim, dashboard
(Optional) thin FastAPI only if you want live odds refresh mid-tournament
LLM explanation step runs in the job, caches narrated text into the JSON
```
This is **cheaper, simpler, more reliable, and more impressive** (it shows you right-sized the system) than the multi-service stack. It also runs entirely on free tiers and reproduces from a clean clone.

---

## Section 9 — Biggest blind spots

**Top 10 risks (by impact):**
1. No market benchmark → you can't tell signal from vig. *(critical)*
2. EV computed on soft-book odds → systematically fake "value." *(critical)*
3. 104-match sample → in-tournament calibration/retraining is noise. *(critical)*
4. Scraper fragility (Transfermarkt/FBref change layouts; rate limits, IP bans).
5. Odds free-tier exhaustion (hundreds of req/month) during peak fixtures.
6. Name/entity resolution edge cases at tournament time (new qualifiers, alias gaps).
7. Multiple-comparisons p-hacking in "value bet" discovery.
8. Legal/responsibility exposure of the betting framing.
9. Over-scoped infra eating your 3 months in DevOps, not modeling.
10. Data leakage (training/feature code accidentally using post-kickoff info).

**Top 10 assumptions to challenge:**
1. "Better model → profitable bets." (Mostly false for WC markets.)
2. "Odds are a comparison." (They're the prior and the benchmark.)
3. "Bayesian hierarchical is the Pro tier." (Low marginal ROI here.)
4. "We'll improve during the tournament." (Too few games.)
5. "Build Dixon-Coles." (Install it.)
6. "Transfermarkt is low priority." (It's the top fundamental feature.)
7. "We need Postgres/Supabase." (SQLite/DuckDB suffices.)
8. "Corners/cards just need a paid source." (Even then, weakly modelable.)
9. "xG will help internationals." (Sparse; squad value helps more.)
10. "More markets = more value." (More markets = more ways to fool yourself.)

**Top 10 opportunities (by impact):**
1. Reframe to a transparent forecaster/simulator. 2. Add CLV as the headline metric. 3. De-vigged market prior + blend. 4. Squad-value priors. 5. Reuse penaltyblog/socceraction/kloppy. 6. State-space/uncertainty-aware ratings. 7. Right-size to static-site + cron. 8. Grounded LLM explanations. 9. A clean, public, *honest* calibration scoreboard (rare and credible). 10. A great 2026-format Monte-Carlo sim as the centerpiece.

---

## Section 10 — If this were my project (3 months, solo, strong AI tools)

**What I'd build:** a **public, honest, calibrated 2026 World Cup forecaster + simulator** that (a) anchors to the de-vigged market, (b) adds a squad-value-and-results prior with uncertainty-aware ratings, (c) simulates the real 48-team bracket thousands of times, (d) explains itself in plain language, and (e) **publicly tracks its own calibration and CLV** as the tournament unfolds. Betting suggestions exist only as an opt-in, no-real-money, "here's what EV means and why beating the market is hard" educational mode.

**What I'd remove:** the Postgres/Supabase tier (MVP), Celery/Redis, the custom Dixon-Coles (install penaltyblog), the GNN/transformer/deep ambitions (or quarantine them as a separate StatsBomb learning study), the 4-tier version ladder, and most of the 14-table schema (collapse to ~6 tables or just Parquet + SQLite).

**What I'd postpone:** the Bayesian-hierarchical NumPyro model, injury-news agents, user accounts, anything multi-agent.

### Revised roadmap (12 weeks)

- **Week 1 — Data spine & honesty harness.** martj42 + openfootball fixtures + a **de-vigged market snapshot** (Pinnacle/Betfair via an odds source) into DuckDB/Parquet. Build the **CLV/backtest harness first** so every later claim is measured. Seed the alias table for 48 teams.
- **Week 2 — Baselines that must be beaten.** Install **penaltyblog**: Elo/pi-ratings + Dixon-Coles + de-vig + RPS. Pull **FiveThirtyEight SPI historical** as a comparison baseline. Establish: *market closing line = the bar.*
- **Week 3 — Ratings done right.** State-space / uncertainty-aware team ratings + Transfermarkt squad-value prior. Blend model with de-vigged market; tune the blend on holdout by RPS/log-loss.
- **Week 4 — The simulator (centerpiece).** Custom Monte-Carlo of the **exact 2026 format** (12 groups, 8 best third-placed, Round of 32 → Final), producing advancement & win-trophy distributions with intervals.
- **Week 5 — Calibration & EV truth.** Isotonic calibration; EV only vs **de-vigged** prices; multiple-testing discipline on "value" flags; "Avoid Betting" as default when edge ≈ vig.
- **Weeks 6–7 — Frontend (Astro/Next on Vercel).** Calendar, match detail, the **simulator view**, and the **public calibration/CLV scoreboard** as the hero. Mobile-first, confidence gauge, risk badge.
- **Week 8 — Grounded LLM explanations.** Structured-output narration of the actual numbers; casual/nerd toggle; cached in the nightly job.
- **Week 9 — Cron + reproducibility.** GitHub Actions nightly pipeline → static artifacts → auto rebuild. `docker compose up` + clean-clone CI smoke test.
- **Week 10 — In-tournament behavior.** Online rating updates + market re-anchoring after each match; confidence decay on stale data. (No "retraining" theater.)
- **Week 11 — Polish, docs, model cards.** README reframed as a forecaster; honest "what we don't model and why" section (corners, deep learning) as a *credibility feature*.
- **Week 12 — Launch & write-up.** A blog post: "I tried to beat the World Cup market and here's the honest scoreboard." That post is worth more to your portfolio than any single feature.

---

## Final verdict

**Keep:** calibration-first ethos, responsible-gambling defaults, name-normalization rigor, GitHub Actions cron, DuckDB, the confidence/nerd UX.

**Fix (non-negotiable):** add a **market benchmark and CLV tracking**; compute EV only against **de-vigged** prices; **install** the modeling layer (penaltyblog/socceraction/kloppy) instead of writing it; **promote Transfermarkt squad value** to a core feature; **right-size the infra** to static-site + cron + SQLite/DuckDB.

**Reframe:** from "betting suggestion machine" to **"the most honest public World Cup forecaster on the internet."** It's the same engine, a stronger product, a cleaner conscience, and a far better portfolio story.

**The hard truth, stated plainly:** you are not going to beat the World Cup closing line with a public open-source model, and anyone who's worked a betting desk will know it on sight. The winning move is not to pretend otherwise — it's to build something that's *rigorously honest about uncertainty and calibration*, simulates the tournament beautifully, explains itself, and shows its own scoreboard win or lose. That earns more respect than a fictional edge ever could.
