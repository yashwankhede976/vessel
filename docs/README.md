# Intelligent Freight Forecasting & Vessel Chartering Platform

**Project (SIH 2026):** Development of an Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India.

**Codename:** Vessel

---

## What this is

Vessel is a decision-support platform for bulk cargo procurement teams and vessel chartering desks. It forecasts freight rates, models the total landed cost of importing bulk commodities (primarily thermal and coking coal) from overseas origins to India's East Coast ports, and recommends *when*, *from where*, *into which port*, and *under which contract structure* to buy and ship.

The core intent is to shift the chartering desk from **reactive daily spot-market exploration** to **proactive short-term and medium-term multi-voyage planning**, backed by explainable forecasts and India-East-Coast-specific operational intelligence (port congestion, berth and draft constraints, laycan windows, demurrage exposure, and weather/monsoon risk).

## Trade lanes in scope

**Origins:** Australia, Indonesia, Mozambique, USA, Russia
**Destination (East Coast India) ports:** Paradip, Visakhapatnam, Gangavaram, Gopalpur, Dhamra, Sagar / Sandheads, Haldia
**Primary cargo:** Bulk commodities, primarily coal (thermal and coking).

## Reference note

[Kpler](https://www.kpler.com/) is used only as a *high-level capability and user-experience reference* for the class of maritime/commodity intelligence products this platform belongs to. Vessel does not copy Kpler's branding, proprietary datasets, UI, textual content, visual identity, or implementation. Vessel's differentiation is a stronger **India-East-Coast-specific decision layer** that combines forecasting with local port, berth, laycan, demurrage, and monsoon intelligence.

## Documentation map

| Document | Purpose |
| --- | --- |
| [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md) | Master spec: objective, users, journeys, system boundaries, MVP and future scope, assumptions, limitations. |
| [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) | What is built vs pending, per layer and per capability. The authoritative progress view. |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture: layers, technology stack, request/ML/optimization/ingestion flows, repository structure. |
| [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md) | Branching, commits, PRs, coding standards, testing, environments, and the documentation golden rule. |
| [DATA_SOURCES.md](./DATA_SOURCES.md) | External data sources catalogue with access classification and per-field provenance rules. |
| [ENVIRONMENT.md](./ENVIRONMENT.md) | Environment & secrets guide: how to create `.env`, mandatory vs optional variables, keyless APIs, missing-credential handling. |
| [API_CONVENTIONS.md](./API_CONVENTIONS.md) | API contract: versioning, response envelope, errors, pagination, filtering, ordering, serializers, OpenAPI docs. |
| [DATA_INGESTION_AIS.md](./DATA_INGESTION_AIS.md) | AISStream WebSocket ingestion adapter: credentials, mapping to Vessel/AISPosition, robustness, testing. |
| [DATA_INGESTION_WEATHER.md](./DATA_INGESTION_WEATHER.md) | Open-Meteo weather ingestion adapter: captured fields, caching, provider limitations & licensing. |
| [DATA_INGESTION_IMD.md](./DATA_INGESTION_IMD.md) | IMD marine/cyclone warnings adapter: products, mapping to MarineObservation/CycloneObservation, availability caveats. |
| [FREIGHT_DATASET_SCHEMA.md](./FREIGHT_DATASET_SCHEMA.md) | Unified freight forecasting dataset: row grain, features, targets, temporal-integrity (no-leakage) rules. |
| [BUSINESS_REQUIREMENTS.md](./BUSINESS_REQUIREMENTS.md) | Business context, stakeholders, value drivers, success metrics (KPIs). |
| [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md) | The 23 platform capabilities specified as testable functional requirements. |
| [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md) | Performance, scalability, security, reliability, explainability, and compliance requirements. |
| [GLOSSARY.md](./GLOSSARY.md) | Shipping, chartering, freight, and platform terminology. |

## Capability summary

The platform delivers 23 major capabilities grouped into five layers:

1. **Forecasting & analytics** — freight forecasting, freight historical analytics.
2. **Vessel & voyage intelligence** — vessel availability, vessel tracking, vessel-port compatibility, ETA prediction, idle-vessel employment.
3. **Cargo, trade & port intelligence** — cargo/trade intelligence, port congestion, port & berth constraints, alternative-port recommendation.
4. **Decision & optimization** — demurrage risk, laycan optimization, market-entry timing, contract-type recommendation (spot vs short-term vs multi-voyage), total landed-cost calculation, multi-origin procurement optimization.
5. **Risk, explainability & delivery** — weather & marine risk, geopolitical/disruption risk, explainable AI, what-if simulation, alerts, executive dashboard.

Each capability is specified in detail in [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md).

## Status

Implementation is underway. The specification documents below define the target;
the platform now has a working foundation on top of them. See
[IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) for the authoritative
built-vs-pending breakdown.

**Built so far (high level):**

- **Backend (Django + DRF):** apps for `catalog` (core domain: ports, berths, vessels, commodities, origins, routes, cargo, freight observations), `operations` (AIS positions, port calls, congestion, weather/marine/cyclone, prices, trade, bunkers, forecasts, risk, recommendations), `decisions` (charter strategies, voyage/contract plans, candidates, scenarios, optimization runs/results), and `ingestion` (a reusable ingestion framework + the AISStream adapter). DRF is configured with `/api/v1/` versioning, a consistent response envelope, pagination, filtering, and OpenAPI docs.
- **APIs:** ports & berths (list/detail, filter by coast/commodity, constraints) and vessels (list/detail, filter by type/DWT/draft/position, availability).
- **Domain logic:** a deterministic, rule-based vessel–port–berth compatibility engine (no ML).
- **Data:** a curated, source-referenced East Coast India port dataset with a seed importer.
- **Frontend (React + TypeScript):** an application shell (layout, routing, reusable UI components), a typed API client, and a working Port Intelligence page.

**Not yet built:** the ML forecasting/ETA/risk models, the optimization solvers, most domain API endpoints (cargo/freight/forecasts/optimization/recommendations/alerts/scenarios are scaffolded routers), and the remaining feature pages. Provider ingestion beyond AISStream is pending.

## Repository layout & running it

See the [root README](../README.md) for the repository layout and local/Docker run instructions, and [ENVIRONMENT.md](./ENVIRONMENT.md) for configuration.
