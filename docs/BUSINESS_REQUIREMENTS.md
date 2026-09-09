# Business Requirements

**Project:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India
**Codename:** Vessel
**Document type:** Business Requirements Document (BRD)
**Status:** Draft v1.0

---

## 1. Business context

Importing bulk cargo (primarily coal) to India's East Coast is a high-value, high-volatility activity. Freight is a large and swinging component of landed cost; a single lane can move materially in days. Chartering desks today plan **reactively**: they re-explore the spot market daily, book under time pressure, and absorb avoidable cost through poorly timed fixtures, weak laycan planning, and demurrage at congested ports.

Meanwhile, the operational reality of the East Coast — draft-limited ports, berth congestion, monsoon and cyclone exposure in the Bay of Bengal, and vessel-port compatibility limits — is often handled separately from the freight decision, in spreadsheets and tribal knowledge. The result is decisions that are neither cost-optimal nor operationally robust.

Vessel exists to close this gap: fuse **freight forecasting** with an **India-East-Coast-specific operational and risk decision layer**, and turn daily spot reactions into planned short-term and multi-voyage procurement.

## 2. Business objectives

| ID | Objective | Rationale |
| --- | --- | --- |
| BO-1 | Reduce total landed cost of imported bulk cargo | Freight and demurrage are large, addressable cost components. |
| BO-2 | Shift the desk from reactive spot booking to proactive short/medium-term multi-voyage chartering | Planning ahead captures better rates and reduces last-minute premiums. |
| BO-3 | Reduce demurrage and port-waiting cost | Better laycan and berth planning at congested East Coast ports. |
| BO-4 | Improve decision quality, consistency, and auditability | Replace fragmented spreadsheets with a shared, explainable basis. |
| BO-5 | Reduce operational and market risk exposure | Surface weather, congestion, and geopolitical risk before booking. |
| BO-6 | Increase asset utilization | Employ idle/open vessels productively via recommendations. |

## 3. Stakeholders

| Stakeholder | Interest | Influence |
| --- | --- | --- |
| Chartering Manager | Booking cost, timing, demurrage avoidance | High — primary decision maker |
| Procurement / Commodity Buyer | Origin choice, grade, delivered cost | High |
| Freight / Market Analyst | Forecast quality, market view | High — produces the analytical basis |
| Operations / Port Coordinator | ETA, congestion, berthing feasibility | Medium–High |
| Business / Commercial Head | Margin, realized savings, risk | High — executive sponsor |
| Risk / Compliance Officer | Geopolitical, sanctions, marine risk | Medium |
| Data / Platform Engineer | Data quality, uptime, model health | Medium — enabler |

## 4. Value drivers

1. **Freight cost avoidance** — entering the market at forecast-favourable times and choosing efficient contract structures.
2. **Demurrage reduction** — laycan windows aligned to real congestion, berth, and weather conditions.
3. **Origin arbitrage** — choosing the origin/grade with the lowest *total landed* cost, not just the lowest FOB or freight.
4. **Contract optimization** — multi-voyage/short-term structures vs repeated spot fixtures.
5. **Risk avoidance** — steering around monsoon/cyclone windows, congested ports, and disrupted lanes.
6. **Asset productivity** — employing idle vessels and reducing ballast/idle time.
7. **Decision confidence** — explainable, auditable recommendations that executives and risk officers trust.

## 5. Business requirements

| ID | Requirement | Supports |
| --- | --- | --- |
| BR-1 | The platform shall forecast freight rates for the in-scope origin→East-Coast-India lanes over short-term and medium-term horizons. | BO-1, BO-2 |
| BR-2 | The platform shall recommend market-entry timing (act now vs wait) based on forecasts. | BO-1, BO-2 |
| BR-3 | The platform shall recommend contract structure: spot vs short-term vs multi-voyage. | BO-1, BO-2 |
| BR-4 | The platform shall compute total landed cost per origin and destination-port option. | BO-1 |
| BR-5 | The platform shall optimize multi-origin procurement for delivered tonnage at least cost/risk. | BO-1 |
| BR-6 | The platform shall estimate and help minimize demurrage risk through laycan optimization. | BO-3 |
| BR-7 | The platform shall provide East-Coast port congestion, berth, and draft intelligence. | BO-3, BO-5 |
| BR-8 | The platform shall check vessel-port compatibility for the target port. | BO-3, BO-5 |
| BR-9 | The platform shall provide vessel availability, tracking, and ETA prediction. | BO-2, BO-3 |
| BR-10 | The platform shall recommend alternative ports when the primary port is unfavourable. | BO-3, BO-5 |
| BR-11 | The platform shall surface weather/marine and geopolitical/disruption risk relevant to lanes and ports. | BO-5 |
| BR-12 | The platform shall recommend employment for idle/open vessels. | BO-6 |
| BR-13 | The platform shall explain every recommendation (drivers, confidence, assumptions). | BO-4 |
| BR-14 | The platform shall support what-if simulation of key variables. | BO-4, BO-5 |
| BR-15 | The platform shall provide alerts and an executive dashboard summarizing cost, risk, and opportunities. | BO-4, BO-6 |
| BR-16 | The platform shall retain a record of recommendations and inputs for audit. | BO-4 |

## 6. Success metrics (KPIs)

| KPI | Definition | Target direction |
| --- | --- | --- |
| Freight cost per tonne vs benchmark | Landed freight cost vs a market benchmark for the lane | Lower |
| Demurrage cost per voyage | Demurrage paid per completed voyage | Lower |
| Forecast accuracy | Error (e.g. MAPE) of freight forecasts vs realized rates | Lower error |
| Proactive booking share | Share of tonnage booked via short-term/multi-voyage vs pure spot | Higher |
| Laycan adherence | Share of voyages arriving within the planned laycan window | Higher |
| Idle/ballast time | Average idle/open days per vessel | Lower |
| Recommendation adoption | Share of recommendations acted upon | Higher (with quality) |
| Risk incidents avoided | Voyages re-planned before a flagged risk materialized | Higher |

*Targets are set with the desk during implementation once baselines are measured.*

## 7. Constraints and dependencies

- **Data availability & licensing:** dependent on access to freight, AIS, port, weather, and trade data; some feeds may be estimated where authoritative sources are unavailable.
- **Domain literacy:** users are assumed to understand core chartering concepts (see [GLOSSARY.md](./GLOSSARY.md)).
- **Decision authority:** Vessel advises; users transact in their own booking/ERP systems.
- **Scope discipline:** dry bulk only, East Coast India only, coal-first (see [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md) §4).
- **Reference boundary:** Kpler is a capability/UX reference only; no proprietary content, branding, or UI is reused.

## 8. Related documents

- [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
- [GLOSSARY.md](./GLOSSARY.md)
