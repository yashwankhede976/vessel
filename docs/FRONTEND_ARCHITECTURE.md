# Frontend Architecture

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Architecture note
**Status:** v1.0

The React decision-platform frontend. It is a thin, typed consumer of the Django
API: it renders backend output and never duplicates backend business logic
(rule: React only consumes Django APIs).

---

## 1. Stack

- **Vite 5 + React 18 + TypeScript 5** (strict), **react-router-dom 6**.
- **Vitest + @testing-library/react + jsdom** for tests.
- No charting library and no map library — charts and the locator map are
  hand-rolled inline SVG (lightweight, dependency-free, easily testable). The
  env reserves `VITE_MAP_*` for an optional MapLibre upgrade later.
- Build: `npm run build` (`tsc -b && vite build`). Tests: `npm test`.

## 2. Layers

```
src/
  api/            typed HTTP client + per-domain endpoint modules
    client.ts     fetch wrapper: envelope unwrap, retry (GET), timeout, errors
    useApi.ts     React hook: {data, loading, error, refetch} with cancellation
    endpoints/    one module per API area (ports, vessels, analytics, system, …)
    resources.ts  TypeScript types mirroring the backend DTOs
    types.ts      envelope / pagination / error shapes
  components/
    ui/           reusable kit: Card, Badge, Table, ChartContainer, Modal,
                  FormField, Loading, ErrorState
    layout/       AppLayout, PageHeader, Sidebar, TopNav
    domain/       decision-platform primitives: DecisionCard, LineChart (SVG),
                  ScoreBar, StatTile, DataLabel, DataFreshnessStrip
  pages/          one component per route (see the page/endpoint matrix below)
  lib/format.ts   money/number/percent/humanize display helpers
  navigation.ts   single source of truth for the sidebar
  routes.tsx      route table (mounts AppLayout + pages)
```

## 3. API consumption

Every network call goes through `src/api/client.ts`, which unwraps the backend
envelope (`{success, data, errors, pagination}`), retries idempotent GETs on
transient errors, enforces a timeout, and normalizes every failure to `ApiError`
(with `.displayMessage`). Pages consume data either via the `useApi` hook (for
on-mount GETs) or a local `async` handler for POST compute endpoints, always
rendering three states: `Loading`, `ErrorState` (with retry), and an empty
state. **No component calls `fetch` directly.**

The base URL comes from `VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`).
API keys are never present in the frontend — provider credentials live only on
the backend, and the external-services endpoint returns a `configured` boolean,
never a key.

## 4. Data provenance labelling

`components/domain/DataLabel` renders a Badge tagging any value/panel as
**REAL / SYNTHETIC / ESTIMATED / FORECAST / UNKNOWN**. Forecast series are
labelled FORECAST; analyst signal inputs (market pressure, scenario levers) are
ESTIMATED; live catalogue/AIS data is REAL; missing values render UNKNOWN
(never a fabricated number). The `DataFreshnessStrip` shows how current each
dataset is (LIVE/STALE/…) from `GET /system/data-freshness/`.

## 5. Design system

Uses the existing CSS custom-property tokens in `src/styles/theme.css`
(colors, spacing `--sp-*`, typography `--fs-*`, radii, shadows, layout). Plain
per-component CSS files with a BEM-like convention (`ui-*` for the kit, page
prefixes elsewhere). Desktop-first, responsive at ≤900px (sidebar becomes a
drawer; multi-column page grids collapse to one column). Professional
maritime/enterprise palette; no Kpler branding or assets are used.

## 6. Page → backend endpoint matrix

| Page (route) | Backend endpoint(s) consumed |
|---|---|
| Dashboard `/dashboard` | `POST market-pressure/`, `GET forecasts/freight/`, `POST fix-wait/`, `POST contract-strategy/compare/`, `GET alerts/`, `GET system/data-freshness/`, `GET ports/`, `GET vessels/` |
| Market Intelligence `/market` | `POST market-pressure/`, `GET system/data-freshness/` |
| Freight Forecast `/forecasts` | `GET forecasts/freight/` |
| Vessels `/vessels` | `GET vessels/` |
| Ports `/ports` | `GET ports/`, `GET ports/{id}/` (+ berths) |
| Cargo `/cargo` | `POST landed-cost/compare/` |
| Idle Vessels `/idle-vessels` | `GET vessels/available/`, `POST idle-vessel/` |
| Chartering `/chartering` | `POST recommendations/vessels/`, `POST fix-wait/`, `POST contract-strategy/compare/`, `POST alternative-port/` |
| Optimizer `/optimizer` | `POST optimization/multi-voyage/` |
| Scenarios `/scenarios` | `POST voyage-cost/`, `POST risk/` |
| Risk `/risk` | `POST risk/` |
| Alerts `/alerts` | `GET alerts/`, `POST alerts/{id}/acknowledge/`, `POST alerts/{id}/resolve/` |
| AI Assistant `/assistant` | composes `market-pressure/`, `fix-wait/`, `landed-cost/compare/` |
| Settings `/settings` | `GET system/external-services/` |

All of these paths are registered in `backend/apps/api/v1/urls.py`. Pages
deliberately avoid the scaffold-only list endpoints (e.g. `recommendations/`
list, `cargo/` CRUD) in favour of the implemented decision endpoints.

## 7. Testing

`npm test` runs Vitest with jsdom. Tests mock the `../api` module and render
pages/components with a `MemoryRouter`, covering routing, loading/error/empty
states, the forecast chart, the vessel and alert tables (including
acknowledge/resolve), the chartering recommendation workflow, scenario
simulation, and map interactions. No network is touched.

## 8. Known limitations

- Several backend list endpoints (cargo CRUD, freight observations, forecast
  list, scenarios, optimization runs) remain scaffolds; the frontend uses the
  implemented compute/composed endpoints instead, so those pages are fully
  functional without them.
- The map is a schematic inline-SVG locator, not a tiled basemap. The
  `VITE_MAP_*` env vars reserve a MapLibre upgrade that can replace
  `EastCoastMap` without changing its props contract.
- Some compute endpoints are demonstrated with representative default inputs
  (e.g. a spot rate on the dashboard) where no cargo context is selected; these
  are clearly analyst inputs (ESTIMATED), not real market quotes.
