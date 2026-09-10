# UX Workflow

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** UX / workflow note
**Status:** v1.0

How a logistics / procurement professional moves through the platform, and the
UX principles behind it. The product is a decision platform: every screen works
toward answering **what is happening → what will happen → what should I do**.

---

## 1. Primary workflow (procurement decision)

```
Dashboard  ──────────────  the daily read: current freight, market pressure,
   │                        the headline FIX/WAIT decision, new alerts, fleet map
   ▼
Market Intelligence  ─────  is the market tight or weak right now? (0–100 index)
   │
   ▼
Freight Forecast  ────────  where are rates on my lane heading? (7/14/30-day)
   │
   ▼
Chartering  ──────────────  the core decision surface: enter a cargo requirement,
   │                        get a ranked vessel, timing (FIX/WAIT), contract
   │                        strategy, alternative ports — one DECISION CARD + Why
   ▼
Optimizer  ───────────────  cover a multi-voyage requirement at minimum cost
   │
   ▼
Scenarios  ───────────────  stress-test the plan with what-if levers
   │
   ▼
Risk / Alerts  ───────────  monitor exposure and act on material events
```

Supporting intelligence pages (Vessels, Ports, Cargo, Idle Vessels) feed the
decision, and Settings/Chatbot round out the system.

## 2. The Decision Card

The headline output (Dashboard + Chartering) is a single, high-contrast card:

```
RECOMMENDATION
FIX NOW
Capesize · Australia → Paradip
Multi-Voyage
Expected saving: $94,700    Risk: MEDIUM    Confidence: 72%
[ Why? ] → the actual backend factors (top vessel, suitability, market
           pressure, expected freight move) — never invented copy.
```

Every number in it comes from a backend engine (fix/wait, contract strategy,
vessel recommendation). The "Why?" expander lists the real drivers so the
recommendation is auditable, not a black box.

## 3. UX principles

- **Clear hierarchy.** Each page opens with a `PageHeader` (title + one-line
  description + primary action). The most important output (the decision) is
  visually dominant; supporting detail sits in consistent `Card`s and `Table`s.
- **Consistent states.** Every data view renders a **loading** spinner, an
  **error** state with a retry, and an **empty** state — never a blank screen.
- **Honest data.** Values are labelled REAL / SYNTHETIC / ESTIMATED / FORECAST,
  and a freshness strip shows how current the inputs are, so a user always knows
  how much to trust a recommendation. UNKNOWN factors are shown as UNKNOWN.
- **Minimal motion.** No gratuitous animation; transitions are limited to hover
  affordances and respect `prefers-reduced-motion`.
- **Professional, accessible.** Enterprise maritime palette with sufficient
  contrast; focus-visible outlines; semantic roles (dialog, alert, status,
  button) on interactive elements.
- **Desktop-first, tablet-capable.** Optimised for the wide screens procurement
  desks use; at ≤900px the sidebar collapses to a drawer and multi-column
  layouts stack.

## 4. Interaction patterns

- **Filters** use the `FormField` render-prop pattern for selects; tables sort
  and filter client-side where the dataset is already loaded.
- **Compute pages** (Market, Risk, Scenarios, Optimizer, Chartering) gather
  inputs and POST to a backend engine on an explicit action, then render the
  result — keeping the interaction predictable and the backend authoritative.
- **Alerts** support acknowledge/resolve inline, with optimistic refetch.
- **Map**: clicking a port or vessel opens contextual detail; the map overlays
  live vessel positions and (where available) port congestion status.

## 5. Non-goals / guardrails

- The UI never mutates production data during what-if simulation — Scenarios is
  stateless and recomputes from the sliders.
- No external API keys are ever exposed to the browser.
- No Kpler branding, logo, copy, or proprietary UI is used; Kpler informs only
  the breadth of capabilities, not the visual identity.
