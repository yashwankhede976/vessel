# Project Specification

**Project:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India
**Event:** Smart India Hackathon (SIH) 2026
**Codename:** Vessel
**Document type:** Master specification
**Status:** Draft v1.0 — specification only, no application code

---

## 1. Project objective

### 1.1 Problem statement

Bulk cargo importers and chartering desks that supply India's East Coast (utilities, steel plants, ports, and trading houses importing coal and other dry bulk) largely operate **reactively**. Each day the desk re-explores the spot market: it checks freight rates, hunts for available vessels, reacts to port congestion, and books voyages under time pressure. This produces:

- avoidable freight cost from booking into rising markets,
- demurrage exposure from poor laycan and berth planning,
- missed opportunities to lock favourable short-term or multi-voyage rates,
- fragmented, spreadsheet-based decisions with no shared, explainable basis.

### 1.2 Objective

Build an intelligent, explainable decision-support platform that:

1. **Forecasts freight rates** for the relevant origin→East-Coast-India lanes over short-term (days–weeks) and medium-term (weeks–months) horizons.
2. **Optimizes procurement and chartering decisions** — origin selection, destination port selection, timing (market entry), contract structure (spot vs short-term vs multi-voyage), and laycan windows — to minimize **total landed cost** at acceptable risk.
3. **Layers India-East-Coast-specific operational intelligence** — port congestion, berth and draft constraints, vessel-port compatibility, demurrage risk, monsoon/weather risk — onto the forecast so recommendations are operationally feasible, not just theoretically cheap.
4. **Explains every recommendation** so a chartering manager can trust, challenge, and act on it.

### 1.3 Success in one sentence

A chartering desk using Vessel plans multi-voyage procurement proactively — choosing origin, port, timing, and contract type with a forecasted, explainable, operationally-feasible total landed cost — instead of re-discovering the spot market each morning.

---

## 2. Users

### 2.1 Primary users

| User | Role | Core need from Vessel |
| --- | --- | --- |
| **Chartering Manager** | Owns vessel booking decisions | When to enter the market; spot vs short-term vs multi-voyage; which vessel; laycan window that avoids demurrage. |
| **Procurement / Commodity Buyer** | Owns cargo sourcing decisions | Which origin and grade to buy; total landed cost by origin; multi-origin split. |
| **Freight / Market Analyst** | Produces the forecasts and market view the desk relies on | Reliable freight forecasts with historical context and explainability; what-if analysis. |
| **Operations / Port Coordinator** | Manages vessel arrival, berthing, discharge | ETA, port congestion, berth/draft feasibility, demurrage risk, alternative-port options. |

### 2.2 Secondary users

| User | Role | Core need |
| --- | --- | --- |
| **Business / Commercial Head** | Executive owner of cost and margin | Executive dashboard, savings realized, risk exposure, decision audit trail. |
| **Risk / Compliance Officer** | Oversees geopolitical, sanctions, and marine risk | Disruption-risk view, flagged origins/lanes, audit of why a recommendation was made. |
| **Data / Platform Engineer** | Maintains data pipelines and models | System health, data freshness, model performance monitoring. |

### 2.3 User goals summary

- Reduce total landed cost of imported bulk cargo.
- Reduce demurrage and idle-time cost.
- Move from daily reactive booking to planned multi-voyage procurement.
- Make defensible, explainable, auditable chartering and procurement decisions.

---

## 3. User journeys

### 3.1 Journey A — Proactive medium-term multi-voyage planning (Chartering Manager + Buyer)

1. Manager opens the **Executive Dashboard** and reviews the freight forecast for coal lanes into Paradip and Visakhapatnam over the next 8–12 weeks.
2. The **Market-Entry Timing** module flags that rates on the Australia→East-Coast lane are forecast to rise; short-term booking now is favoured over waiting.
3. The buyer runs **Multi-Origin Procurement Optimization** to compare landed cost of Australian vs Indonesian vs USA coal for the same delivered tonnage and grade.
4. The **Contract-Type Recommendation** engine suggests a multi-voyage short-term charter covering three shipments rather than three separate spot fixtures, showing the forecasted saving.
5. Manager runs **What-If Simulation**: "What if bunker prices rise 10%?" and "What if Paradip congestion worsens?" to test robustness.
6. Manager reviews the **Explainable AI** panel (drivers behind the recommendation), accepts the plan, and the desk executes voyages against it.

### 3.2 Journey B — Reactive spot booking with feasibility guardrails (Chartering Manager + Ops)

1. A cargo needs to move now. Manager searches **Vessel Availability Intelligence** for suitable open tonnage near the origin.
2. **Vessel-Port Compatibility** filters vessels that fit the target port's draft, LOA, and berth constraints.
3. **ETA Prediction** and **Port Congestion Intelligence** estimate arrival and expected waiting time at the intended port.
4. **Laycan Optimization** proposes a laycan window that minimizes **Demurrage Risk** given congestion and weather.
5. If demurrage risk is high, **Alternative-Port Recommendation** suggests, e.g., Dhamra or Gangavaram instead of Haldia, with the landed-cost delta.
6. Manager books, and the voyage is added to **Vessel Tracking**.

### 3.3 Journey C — Voyage monitoring and disruption response (Operations Coordinator)

1. Coordinator monitors in-transit vessels on **Vessel Tracking** with live **ETA Prediction**.
2. **Weather & Marine Risk** flags a cyclone risk in the Bay of Bengal affecting Sandheads/Haldia approaches during the monsoon window.
3. **Geopolitical/Disruption Risk** flags a canal/strait or sanctions issue on an alternate lane.
4. **Alerts** notify the coordinator and chartering manager; the **Alternative-Port** and laycan modules propose mitigations.
5. Coordinator adjusts discharge plan and records the decision.

### 3.4 Journey D — Idle-vessel employment (Chartering Manager)

1. A chartered vessel is finishing discharge on the East Coast and will be open.
2. **Idle-Vessel Employment Recommendation** proposes the next best-value employment (back-haul or repositioning fixture) using forecast rates and vessel position.
3. Manager compares options with **Total Landed-Cost** / voyage-economics context and books the next employment.

### 3.5 Journey E — Analyst market review (Freight Analyst)

1. Analyst reviews **Freight Historical Analytics** — seasonality, monsoon effects, past congestion cycles at each port.
2. Analyst inspects **Freight Forecasting** accuracy and the current forecast with confidence bands.
3. Analyst uses **What-If Simulation** to publish a house view and shares it to the dashboard for the desk.

---

## 4. System boundaries

### 4.1 In scope

- Freight-rate forecasting for the defined origin→East-Coast-India dry-bulk lanes (primarily coal).
- Decision support: timing, origin, port, contract-type, laycan, multi-origin optimization, total landed cost.
- Operational intelligence: vessel availability, vessel tracking, ETA, port congestion, berth/draft constraints, vessel-port compatibility, demurrage risk.
- Risk intelligence: weather/marine and geopolitical/disruption risk.
- Explainability, what-if simulation, alerts, and an executive dashboard.
- Dry bulk focus with coal as the primary commodity.

### 4.2 Out of scope

- Executing actual charter contracts, payments, or fixture legal documentation (Vessel *recommends and supports*; the desk *transacts* in its own systems).
- Container, tanker (liquid), LNG/LPG, and break-bulk trades (dry bulk only for this project).
- West Coast / other Indian coastlines and non-Indian destinations (East Coast India only).
- Real-time trading/broking execution or an order-management system.
- Being an authoritative system of record for financial accounting.

### 4.3 External systems and data (interfaces, not owned)

- AIS / vessel position feeds (for tracking and ETA inputs).
- Freight market data and indices (for historical and current rate context).
- Port authority / congestion and berth data for East Coast ports.
- Weather and marine forecast services (including monsoon/cyclone data for the Bay of Bengal).
- Commodity/trade flow data for cargo and trade intelligence.
- Bunker (fuel) price data for landed-cost and voyage economics.

*Specific providers and licensing are to be finalized during implementation planning. Where authoritative feeds are unavailable, the platform will degrade gracefully with clearly labelled estimated or manually entered data.*

---

## 5. Assumptions

1. Historical freight-rate data for the relevant lanes is obtainable at sufficient depth to train and validate forecasting models.
2. AIS or equivalent vessel-position data is available for tracking and ETA estimation.
3. Port congestion, berth, and draft data for the seven East Coast ports can be sourced or reasonably estimated and periodically updated.
4. Users have basic domain literacy (understand laycan, demurrage, charter types).
5. Coal (thermal/coking) is the primary commodity; the data model is designed to extend to other dry bulk.
6. Forecasts are decision-support signals, not guarantees; users retain final decision authority.
7. Weather and geopolitical feeds are available at a granularity useful for Bay-of-Bengal and relevant lane risk.

---

## 6. Limitations

1. Forecast accuracy is bounded by data quality, market volatility, and unpredictable shocks (geopolitical events, sudden demand swings).
2. Third-party data latency, gaps, or licensing constraints can reduce coverage or freshness.
3. Port congestion and berth availability may rely on estimates where authoritative real-time feeds are unavailable.
4. The platform recommends but does not execute charters; realized savings depend on user action.
5. Monsoon/cyclone impacts in the Bay of Bengal introduce inherent uncertainty into ETA and demurrage predictions.
6. Initial models will focus on coal lanes; extension to other commodities requires additional data and validation.

---

## 7. MVP scope

The MVP proves the core loop — **forecast → optimize → explain** — for coal on a subset of lanes and ports.

**MVP includes:**

- Freight forecasting (short-term) for a prioritized subset of lanes (e.g., Australia and Indonesia → Paradip and Visakhapatnam).
- Freight historical analytics with seasonality/monsoon views.
- Vessel availability intelligence and basic vessel tracking (position + status).
- ETA prediction (baseline model).
- Port congestion intelligence and port/berth + draft constraints for the MVP ports.
- Vessel-port compatibility checks.
- Demurrage risk and laycan optimization (baseline).
- Total landed-cost calculation.
- Contract-type recommendation (spot vs short-term vs multi-voyage) and market-entry timing.
- Explainable AI for the above recommendations.
- Executive dashboard and basic alerts.

**Deferred from MVP (see Future scope):** full multi-origin optimization across all five origins, idle-vessel employment optimization, advanced geopolitical-risk modelling, full what-if simulation breadth, and coverage of all seven ports and all commodities.

---

## 8. Future scope

- Full coverage of all five origins and all seven East Coast ports, plus additional East Coast terminals.
- Extension beyond coal to other dry-bulk commodities (iron ore, fertilizers, grains, bauxite).
- Medium/long-term forecasting with scenario ensembles.
- Advanced multi-origin, multi-voyage optimization with fleet-level planning.
- Rich idle-vessel employment and repositioning optimization.
- Deeper geopolitical, sanctions, and disruption modelling.
- Automated alerting workflows and integrations with the desk's booking/ERP systems.
- Mobile executive view and configurable alerting.
- Continuous learning from realized-vs-forecast outcomes (model feedback loop).

---

## 9. Related documents

- [BUSINESS_REQUIREMENTS.md](./BUSINESS_REQUIREMENTS.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
- [GLOSSARY.md](./GLOSSARY.md)
