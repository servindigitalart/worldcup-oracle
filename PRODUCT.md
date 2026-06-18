# Product

## Register

split: brand (homepage hero) · product (all other surfaces)

The homepage `/` operates in brand register — it makes a position, introduces the product, and earns trust before the user has done anything. Every other surface (`/matches`, `/match/*`, `/recommendations`, `/tournament`, `/bracket`, `/paths`, `/best-thirds`, `/lab/*`) operates in product register — design serves the analysis, not the other way around.

## Users

Sports bettors and analytically-minded World Cup fans who distrust raw odds and want a second opinion from a statistical model. They arrive pre-match, in a research mode. Their primary question on any screen is: "What does the model think, and does the market agree?" They are comfortable with probabilities and implied odds. They are not beginners who need gambling explained to them, and they are not professional quants who need raw Kelly criterion inputs — they sit in between: informed, skeptical, statistically literate.

On mobile, they are likely checking before placing a bet, scrolling quickly, looking for a number or a signal badge that confirms or challenges their instinct. On desktop, they explore more methodically — comparing matches, reading methodology, cross-referencing signals.

## Product Purpose

World Cup Oracle compares Elo and Dixon-Coles model probabilities against bookmaker market odds to surface match-level signals — where model and market agree, where they diverge, and by how much. It is an educational intelligence tool, not a betting recommendation service. Success is a user who finishes a session with a clearer picture of where the model sees value and where it doesn't — regardless of what they do with that information.

## Brand Personality

Expert · Calm · Signal-to-noise

The tool speaks with precision but never certainty. It shows its working. It does not hype, does not imply guaranteed outcomes, and does not demand the user's attention. The emotional register is: "the smartest analyst in the room who lets the numbers do the talking."

Voice: declarative, spare, confident. "The model favors Brazil at 67%." Not: "Brazil are huge favorites here!" Explanation when useful, silence when not. Numbers formatted consistently; labels that mean something specific.

## Anti-references

**Hard bans — nothing from this aesthetic family:**
- Bet365, FanDuel, Betway: neon-orange on dark, flashing odds tickers, "Bet Now" CTA density
- Crypto dashboards: electric green/purple on black, animated price tickers, "APY" energy
- Generic SaaS dashboards: slate-on-white with indigo accent, identical metric-card rows, enterprise blandness
- AI-generated sports sites: 3-column equal-width feature grids, stock photography of players, Inter-only typography
- Sportsbook promotional UI: countdown clocks, offer banners, dopamine streaks, odds "boosted" badges
- Tipster and gambling influencer brands: aggressive calls-to-action, implied certainty, testimonial stacks
- Prediction apps that imply certainty: "Pick of the Day" framing, lock icons, win-rate claims
- Flashy sports media: animated score tickers, hot-take design, "fire" iconography
- TradingView terminals: multi-panel dense dark UI, overlapping chart data, numeric overload
- Over-gamified leaderboards: XP bars, streak counters, achievement badges

## Design Principles

1. **Signal over noise.** Every element earns its place by helping the user understand a probability, a gap, or a context. Decoration that doesn't carry information should be removed. If a section is on the page and the user can't immediately explain why it's there, it shouldn't be.

2. **Expert confidence.** The interface states its position clearly and without hedging in the UI itself. "67%" not "approximately 67%." "Model gap detected" not "there may be a potential opportunity." The language of uncertainty lives in the methodology, not the display.

3. **Honest defaults.** When data is missing or pre-tournament, say so directly. No fake zeros masquerading as "zeroes." No fallback fabrications. An honest "—" is always better than a made-up number.

4. **Calm persistence.** Nothing in the interface flashes, pulses, demands, or rewards attention. The background stays dark and quiet. Signals emerge from structure and weight, not color saturation or animation.

5. **The model is the hero.** Probabilities and market gaps are the product; the chrome is just scaffolding. Typography, spacing, and color all direct attention toward numbers, not toward UI chrome.

## Accessibility & Inclusion

WCAG AA minimum throughout. Known requirements:
- All interactive elements must have visible focus states (`focus-visible`) — keyboard-accessible cards, nav links, search inputs.
- Color is never the sole signal carrier — every signal badge uses both color and a text label ("Model edge", "Watch", "Avoid").
- `prefers-reduced-motion` must be honored on every animation and transition.
- `text-slate-600` and `text-slate-700` used as informational labels fail 4.5:1 contrast against `#06091A` — these must be bumped to `text-slate-500` minimum for readable text (contrast ≈ 4.5:1 on `#06091A`).
- Probability bars must have accessible text alternatives (percentages already in adjacent labels — confirm they remain visible at all viewport sizes).
