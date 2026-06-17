# Design Skills

Three vendored Claude Code design skills for World Cup Oracle. All live in `.claude/skills/` and are activated by referencing them in a prompt or using their slash commands.

---

## Skills installed

### 1. Impeccable — `.claude/skills/impeccable/`

**Source:** https://github.com/pbakaus/impeccable (v3.7.1)
**Invocation:** `/impeccable [command] [target]`

A comprehensive frontend design skill covering the full spectrum from raw craft to production polish. 23 sub-commands spanning build, evaluate, refine, enhance, and fix categories.

**Vendored files:**
- `SKILL.md` — full skill definition and routing rules
- `reference/` — 8 key command references: `audit`, `polish`, `craft`, `shape`, `codex`, `hooks`, `product`, `brand`
- `scripts/` — 5 Node.js helper scripts: `context.mjs`, `context-signals.mjs`, `detect.mjs`, `palette.mjs`, `pin.mjs`

**Setup (required before first use):**
Impeccable expects a `PRODUCT.md` at the repo root describing what the product is, and optionally a `DESIGN.md` documenting the visual system. Run `/impeccable init` to generate these.

**Key commands for this project:**
| Command | Use case |
|---|---|
| `/impeccable audit [page]` | Score a page against the AI-slop heuristic detector |
| `/impeccable polish [page]` | Final quality pass before shipping a page redesign |
| `/impeccable craft [feature]` | Build a new UI feature end-to-end with design intent |
| `/impeccable typeset` | Improve typography hierarchy on any page |
| `/impeccable colorize` | Add strategic color to monochromatic sections |
| `/impeccable distill` | Strip unnecessary complexity from a crowded page |
| `/impeccable harden` | Audit for edge cases, empty states, and error handling |

**Governs:** All Astro pages in `frontend/src/pages/` and components in `frontend/src/components/`. Register is `product` (tool/dashboard) for all pages except the homepage hero, which has brand-register qualities.

---

### 2. Hallmark — `.claude/skills/hallmark/`

**Source:** https://github.com/nutlope/hallmark (v1.1.0)
**Invocation:** `hallmark [audit|redesign|study] [target]`

An anti-AI-slop design skill focused on structural variety. Insists that two pages built by Hallmark should not share the same section rhythm. Encodes 58 slop-test gates, 21 named macrostructures, and a strict typographic/color system.

**Vendored files:**
- `SKILL.md` — full skill definition, verbs, and design flow
- `references/anti-patterns.md` — named AI-slop tells (purple gradient hero, 3-col feature grid, etc.)
- `references/slop-test.md` — 58 gates to pass before shipping
- `references/typography.md` — display/body pairing rules, the 2+1 rule, type scale ratios
- `references/color.md` — OKLCH-only palette construction, one-accent rule
- `references/layout-and-space.md` — asymmetry, spacing scale, grid-breaking
- `references/macrostructures.md` — 21 named page shapes (Bento Grid, Long Document, etc.)
- `references/component-cookbook.md` — 50 component archetypes
- `references/structure.md` — structural variety rules

**Use when:** Asked to audit a page for AI-slop tells, redesign a page from scratch, or ensure two redesigns don't share structure. Run the 58-gate slop test before any major page ships.

**Governs:** Structural decisions on hero sections, page-level layouts, and any new page that doesn't follow the established product register. Especially useful for `/matches`, `/tournament`, and `/recommendations` which are high-visibility editorial surfaces.

---

### 3. Emil Kowalski — `.claude/skills/emil-design-eng/`

**Source:** https://github.com/emilkowalski/skill
**Invocation:** Reference by name — "apply Emil Kowalski principles to..." or "using the Emil design engineering skill..."

Encodes Emil Kowalski's design engineering philosophy: the invisible details that make software feel right. Deep focus on animation decisions, component micro-interactions, and polish at the component level.

**Vendored files:**
- `SKILL.md` — full skill definition with animation decision framework, spring physics, CSS transform mastery, gesture patterns, performance rules, and component building principles

**Core rules (always apply):**
- Animate `transform` and `opacity` only — never layout properties
- `ease-out` for entering elements, `ease-in-out` for on-screen movement
- UI animations under 300ms; button press feedback 100–160ms
- Never `scale(0)` — start from `scale(0.95)` with `opacity: 0`
- Popovers scale from their trigger; modals scale from center
- Use CSS transitions (not keyframes) for interruptible UI
- `prefers-reduced-motion` is mandatory on every animated element
- Never animate keyboard-initiated actions (used 100+ times/day)

**Governs:** All client-side interactive behavior — the Group Navigator pill transitions in `/matches`, signal badge hover states, mobile nav open/close, card hover effects, and any future drawer or modal UI.

---

## How Claude Code should use these skills

**For a new page or major redesign:** Invoke Impeccable `craft` or `shape` to plan the UX before writing code. Run Hallmark's slop-test against the output before shipping.

**For polish on existing pages:** Use Impeccable `polish` or `audit`. Cross-check against Hallmark's anti-patterns list.

**For any animation or interaction:** Consult Emil Kowalski before writing transition/animation CSS. Run the animation decision framework (Should it animate? What easing? How fast?).

**For typography or color decisions:** Hallmark's `typography.md` and `color.md` are the references. Impeccable's `codex.md` and `brand.md` provide the product-register lens.

**Slop gates** from `hallmark/references/slop-test.md` should be run mentally (or explicitly) before any page redesign ships:
- No Inter-everywhere (display must differ from body)
- No purple-gradient heroes
- No 3-column identical-card feature grids
- Accent occupies ≤3% of viewport
- Every animated element has `prefers-reduced-motion` fallback

---

## What these skills do NOT govern

- Backend Python pipeline (models, simulations, data ingestion)
- JSON artifact formats or data schema
- Build system (Makefile targets, CI/CD)
- Betting calculation logic or probability models
- Any page that correctly uses the existing design system — these skills advise on deviations and improvements, not rewrites for their own sake
