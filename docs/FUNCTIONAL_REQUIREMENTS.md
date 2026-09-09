# Functional Requirements

**Project:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India
**Codename:** Vessel
**Document type:** Functional Requirements Document (FRD)
**Status:** Draft v1.0

---

## How to read this document

Each of the 23 platform capabilities is specified as a functional area with:

- **Intent** — what the capability is for.
- **Requirements** — numbered, testable statements (`FR-<area>-<n>`). "Shall" denotes mandatory behaviour.
- **Inputs / Outputs** — principal data in and decisions out.
- **Acceptance signals** — how we know it works.

Priority tags: **[MVP]** in-scope for the minimum viable product; **[POST-MVP]** deferred (see [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md) §7–8). Terminology is defined in [GLOSSARY.md](./GLOSSARY.md).

Lane convention: an **origin** (Australia, Indonesia, Mozambique, USA, Russia) → an **East Coast India port** (Paradip, Visakhapatnam, Gangavaram, Gopalpur, Dhamra, Sagar/Sandheads, Haldia). Primary cargo: coal.

---

## Layer 1 — Forecasting & Analytics

### 1. Freight Forecasting `[MVP]`

**Intent:** Predict freight rates for in-scope lanes over short-term and medium-term horizons to drive timing and contract decisions.

- **FR-FC-1** The system shall produce freight-rate forecasts per lane for short-term (days–weeks) and medium-term (weeks–months) horizons.
- **FR-FC-2** Each forecast shall include a central estimate and an uncertainty/confidence band.
- **FR-FC-3** Forecasts shall be refreshed on a defined schedule and whenever material new data arrives.
- **FR-FC-4** The system shall express forecasts in per-tonne and per-voyage terms where applicable.
- **FR-FC-5** The system shall record forecast-vs-realized outcomes to enable accuracy measurement. `[POST-MVP: automated feedback retraining]`
- **FR-FC-6** The system shall segment forecasts by vessel class (e.g. Panamax, Supramax, Capesize) where data supports it.
- **Inputs:** historical freight, bunker prices, seasonality, congestion signals, trade-flow demand, vessel supply.
- **Outputs:** per-lane forecast curve with confidence bands and key drivers.
- **Acceptance signals:** forecasts generated for all MVP lanes; accuracy tracked against realized rates; confidence bands present.

### 2. Freight Historical Analytics `[MVP]`

**Intent:** Give analysts and managers historical context — trends, seasonality, and monsoon/congestion cycles.

- **FR-HA-1** The system shall present historical freight-rate series per lane over selectable time ranges.
- **FR-HA-2** The system shall visualize seasonality, including monsoon-period effects on East Coast lanes.
- **FR-HA-3** The system shall allow comparison of multiple lanes/origins on one view.
- **FR-HA-4** The system shall correlate historical rates with drivers (bunker, congestion, demand) for context.
- **FR-HA-5** The system shall support export of historical views/data.
- **Acceptance signals:** users can retrieve and compare historical rates and see seasonal patterns per lane.

---

## Layer 2 — Vessel & Voyage Intelligence

### 3. Vessel Availability Intelligence `[MVP]`

**Intent:** Identify suitable open/available tonnage for a required cargo, origin, and timeframe.

- **FR-VA-1** The system shall list vessels available/open within a specified region and time window.
- **FR-VA-2** The system shall filter by vessel class, DWT, and readiness date.
- **FR-VA-3** The system shall rank candidate vessels by suitability for the intended lane and cargo.
- **FR-VA-4** The system shall link each candidate to its compatibility and tracking views.
- **Inputs:** vessel positions/status, specifications, open dates.
- **Outputs:** ranked list of candidate vessels with key attributes.
- **Acceptance signals:** a manager can find and shortlist feasible vessels for a given requirement.

### 4. Vessel Tracking `[MVP]`

**Intent:** Monitor position and status of relevant/booked vessels.

- **FR-VT-1** The system shall display current position and voyage status for tracked vessels (from AIS or equivalent).
- **FR-VT-2** The system shall show recent track history and current speed/heading where available.
- **FR-VT-3** The system shall associate a tracked vessel with its voyage, cargo, and destination port.
- **FR-VT-4** The system shall indicate data freshness and flag stale/missing position data.
- **Acceptance signals:** tracked vessels show up-to-date positions with clear freshness indicators.

### 5. Vessel-Port Compatibility `[MVP]`

**Intent:** Ensure a vessel physically and operationally fits the target East Coast port/berth.

- **FR-VP-1** The system shall check vessel draft against port/berth draft limits.
- **FR-VP-2** The system shall check LOA, beam, and DWT against berth constraints.
- **FR-VP-3** The system shall flag incompatibilities and explain the limiting constraint.
- **FR-VP-4** The system shall support tidal/partial-load considerations for draft-limited ports where data allows. `[POST-MVP: full tidal windows]`
- **Inputs:** vessel specs, port/berth constraint data.
- **Outputs:** compatible / not-compatible verdict with limiting factor.
- **Acceptance signals:** incompatible vessel-port pairs are correctly flagged with the binding constraint named.

### 6. ETA Prediction `[MVP]`

**Intent:** Predict arrival time at the destination port, accounting for transit and expected port waiting.

- **FR-ETA-1** The system shall predict estimated time of arrival at the destination port for a tracked/planned voyage.
- **FR-ETA-2** ETA shall account for route distance, speed, weather, and expected congestion/waiting.
- **FR-ETA-3** ETA shall update as new position, weather, or congestion data arrives.
- **FR-ETA-4** ETA shall be presented with an uncertainty range.
- **Acceptance signals:** ETAs are produced and updated; ranges narrow as the vessel approaches.

### 17. Idle-Vessel Employment Recommendation `[POST-MVP]`

**Intent:** Recommend productive next employment for vessels finishing discharge / becoming open.

- **FR-IV-1** The system shall detect vessels approaching open/idle status.
- **FR-IV-2** The system shall recommend next-best employment options (e.g. back-haul, repositioning) using forecast rates and vessel position.
- **FR-IV-3** The system shall rank options by expected voyage economics.
- **FR-IV-4** The system shall explain each recommendation.
- **Acceptance signals:** for an open vessel, ranked employment options with economics are produced.

---

## Layer 3 — Cargo, Trade & Port Intelligence

### 7. Cargo / Trade Intelligence `[MVP]`

**Intent:** Provide demand/supply and trade-flow context that influences freight and procurement decisions.

- **FR-CT-1** The system shall present trade-flow context (volumes/direction) for in-scope commodities and lanes.
- **FR-CT-2** The system shall surface demand/supply signals relevant to freight movements.
- **FR-CT-3** The system shall relate trade-flow signals to the freight forecast as explanatory drivers.
- **Acceptance signals:** trade-flow context is available and linked to forecast explanations.

### 8. Port Congestion Intelligence `[MVP]`

**Intent:** Quantify current and expected congestion/waiting at East Coast ports.

- **FR-PC-1** The system shall report current congestion / vessels-waiting and expected waiting time per port.
- **FR-PC-2** The system shall show congestion trends over time per port.
- **FR-PC-3** Congestion estimates shall feed ETA prediction and demurrage risk.
- **FR-PC-4** The system shall indicate confidence/source when congestion is estimated rather than measured.
- **Acceptance signals:** each MVP port shows a congestion/waiting estimate feeding downstream modules.

### 9. Port & Berth Constraints `[MVP]`

**Intent:** Maintain the physical and operational constraints of each East Coast port/berth.

- **FR-PB-1** The system shall store per-port/berth constraints: max draft, LOA, beam, DWT, cargo-handling capability.
- **FR-PB-2** The system shall expose these constraints to compatibility, alternative-port, and laycan modules.
- **FR-PB-3** The system shall support updates to constraint data with an effective date.
- **Acceptance signals:** constraint data exists for all MVP ports and is consumed by compatibility checks.

### 16. Alternative-Port Recommendation `[MVP]`

**Intent:** Recommend a different East Coast port when the primary is congested, incompatible, or risk-exposed.

- **FR-AP-1** The system shall propose alternative ports when the primary port is infeasible or unfavourable.
- **FR-AP-2** Each alternative shall show the total-landed-cost delta vs the primary port.
- **FR-AP-3** Recommendations shall respect vessel-port compatibility and berth constraints.
- **FR-AP-4** The system shall explain why the alternative is proposed (congestion, draft, risk, cost).
- **Acceptance signals:** when a primary port is flagged, feasible alternatives with cost deltas are shown.

---

## Layer 4 — Decision & Optimization

### 10. Demurrage Risk `[MVP]`

**Intent:** Estimate the risk and expected cost of demurrage for a planned voyage.

- **FR-DR-1** The system shall estimate demurrage risk (probability and expected cost) for a voyage/port/laycan.
- **FR-DR-2** Demurrage risk shall incorporate congestion, ETA uncertainty, weather, and laytime terms.
- **FR-DR-3** The system shall express risk in a form usable by laycan optimization and recommendations.
- **FR-DR-4** The system shall explain the main contributors to the risk.
- **Acceptance signals:** demurrage risk is produced per voyage and changes appropriately with congestion/weather inputs.

### 11. Laycan Optimization `[MVP]`

**Intent:** Recommend laycan windows that minimize demurrage risk and cost while remaining feasible.

- **FR-LY-1** The system shall recommend laycan windows for a planned voyage.
- **FR-LY-2** Recommendations shall minimize expected demurrage/waiting subject to congestion, weather, and berth availability.
- **FR-LY-3** The system shall present trade-offs between candidate windows.
- **FR-LY-4** The system shall explain the recommended window.
- **Acceptance signals:** for a given voyage, a recommended laycan with rationale and alternatives is produced.

### 12. Market-Entry Timing `[MVP]`

**Intent:** Advise whether to book now or wait, based on the freight forecast.

- **FR-MT-1** The system shall recommend act-now vs wait for a lane/horizon using the forecast trajectory.
- **FR-MT-2** The recommendation shall quantify expected cost of waiting vs acting.
- **FR-MT-3** The recommendation shall include confidence and key assumptions.
- **FR-MT-4** The recommendation shall be explainable and reproducible.
- **Acceptance signals:** timing guidance with expected-cost impact and confidence is produced per lane.

### 13. Contract-Type Recommendation (Spot vs Short-Term vs Multi-Voyage) `[MVP]`

**Intent:** Recommend the contract structure that minimizes cost/risk across the expected requirement.

- **FR-CR-1** The system shall recommend among spot, short-term, and multi-voyage structures for a stated requirement (tonnage over a period).
- **FR-CR-2** The recommendation shall compare expected total cost and risk across structures using the forecast.
- **FR-CR-3** The system shall show the forecasted saving of the recommended structure vs alternatives.
- **FR-CR-4** The recommendation shall be explainable.
- **Acceptance signals:** for a multi-shipment requirement, a ranked contract-structure recommendation with savings is produced.

### 14. Total Landed-Cost Calculation `[MVP]`

**Intent:** Compute the all-in delivered cost per tonne for an origin/port/vessel/timing option.

- **FR-LC-1** The system shall compute total landed cost = cargo cost + freight + bunker-adjusted voyage cost + port/handling + expected demurrage + applicable duties/other. `[cargo cost input; duties configurable]`
- **FR-LC-2** The system shall express landed cost per tonne and per voyage.
- **FR-LC-3** The system shall allow comparison of landed cost across origins and destination ports.
- **FR-LC-4** The system shall itemize the cost breakdown for transparency.
- **Acceptance signals:** landed cost is computed and itemized for each option and is comparable across origins/ports.

### 15. Multi-Origin Procurement Optimization `[POST-MVP]` (MVP: pairwise comparison)

**Intent:** Choose the origin mix that delivers required tonnage at least total landed cost and acceptable risk.

- **FR-MO-1** The system shall compare total landed cost across origins for equivalent delivered tonnage/grade. `[MVP]`
- **FR-MO-2** The system shall recommend an optimal single-origin or multi-origin split for a requirement. `[POST-MVP]`
- **FR-MO-3** Optimization shall respect port feasibility, vessel availability, and risk constraints.
- **FR-MO-4** The system shall explain the recommended sourcing plan.
- **Acceptance signals (MVP):** origins can be compared on landed cost for the same delivered tonnage.

---

## Layer 5 — Risk, Explainability & Delivery

### 18. Weather & Marine Risk `[MVP]`

**Intent:** Surface weather/marine risk (notably Bay-of-Bengal monsoon/cyclone) affecting transit, ETA, and demurrage.

- **FR-WR-1** The system shall present weather/marine risk relevant to in-scope lanes and East Coast approaches.
- **FR-WR-2** The system shall flag monsoon/cyclone windows affecting the destination ports.
- **FR-WR-3** Weather risk shall feed ETA and demurrage-risk models.
- **FR-WR-4** The system shall raise alerts when significant weather risk affects a tracked/planned voyage.
- **Acceptance signals:** weather risk is shown per lane/port and influences ETA and demurrage outputs.

### 19. Geopolitical / Disruption Risk `[POST-MVP]` (MVP: informational flags)

**Intent:** Surface geopolitical, sanctions, and route-disruption risk on lanes and origins.

- **FR-GR-1** The system shall flag geopolitical/sanctions/disruption risk relevant to origins and lanes. `[MVP informational]`
- **FR-GR-2** The system shall relate disruption risk to affected lanes/ports and recommendations. `[POST-MVP]`
- **FR-GR-3** The system shall raise alerts for material new disruptions.
- **FR-GR-4** The system shall explain the basis of a flagged risk.
- **Acceptance signals:** relevant lanes/origins can be flagged for disruption risk with an explanatory note.

### 20. Explainable AI Recommendations `[MVP]`

**Intent:** Make every recommendation understandable, challengeable, and auditable.

- **FR-XAI-1** Every recommendation (timing, contract, laycan, port, sourcing, employment) shall present its key drivers.
- **FR-XAI-2** Each recommendation shall show confidence and the main assumptions used.
- **FR-XAI-3** The system shall let users trace a recommendation to its input data and forecast.
- **FR-XAI-4** Explanations shall use domain language a chartering manager understands.
- **Acceptance signals:** for any recommendation, a user can see why it was made, with what confidence, and from what inputs.

### 21. What-If Simulation `[MVP]` (baseline)

**Intent:** Let users test how changes in key variables affect cost, risk, and recommendations.

- **FR-WI-1** The system shall let users adjust key variables (e.g. bunker price, congestion, demand, timing) and recompute outcomes.
- **FR-WI-2** The system shall show the impact of a scenario on landed cost, demurrage risk, and recommendations.
- **FR-WI-3** The system shall allow comparison of a scenario against the base case.
- **FR-WI-4** Scenarios shall be savable/shareable. `[POST-MVP: shareable scenario library]`
- **Acceptance signals:** a user can change an input and immediately see the effect on outputs vs the base case.

### 22. Alerts `[MVP]`

**Intent:** Proactively notify users of material events, risks, and opportunities.

- **FR-AL-1** The system shall generate alerts for material events: forecast shifts, congestion spikes, weather/geopolitical risk, demurrage-risk breaches, and open-vessel opportunities.
- **FR-AL-2** Users shall be able to configure which alerts they receive. `[POST-MVP: fine-grained rules]`
- **FR-AL-3** Alerts shall link to the relevant view/recommendation.
- **FR-AL-4** Alerts shall record timestamp and basis for audit.
- **Acceptance signals:** defined trigger conditions produce timely, actionable alerts linked to context.

### 23. Executive Dashboard `[MVP]`

**Intent:** Give leadership a concise view of cost, risk, opportunities, and the current market.

- **FR-ED-1** The dashboard shall summarize freight forecasts, landed-cost position, active recommendations, and key risks.
- **FR-ED-2** The dashboard shall show KPIs (see [BUSINESS_REQUIREMENTS.md](./BUSINESS_REQUIREMENTS.md) §6) such as cost vs benchmark and proactive-booking share.
- **FR-ED-3** The dashboard shall highlight top opportunities and top risks.
- **FR-ED-4** The dashboard shall allow drill-down into any summarized item.
- **Acceptance signals:** an executive sees a single view of market, cost, risk, and opportunities with drill-down.

---

## Traceability

| # | Capability | Primary FR prefix | Business req. |
| --- | --- | --- | --- |
| 1 | Freight Forecasting | FR-FC | BR-1 |
| 2 | Freight Historical Analytics | FR-HA | BR-1 |
| 3 | Vessel Availability Intelligence | FR-VA | BR-9 |
| 4 | Vessel Tracking | FR-VT | BR-9 |
| 5 | Vessel-Port Compatibility | FR-VP | BR-8 |
| 6 | ETA Prediction | FR-ETA | BR-9 |
| 7 | Cargo / Trade Intelligence | FR-CT | BR-1 |
| 8 | Port Congestion Intelligence | FR-PC | BR-7 |
| 9 | Port & Berth Constraints | FR-PB | BR-7, BR-8 |
| 10 | Demurrage Risk | FR-DR | BR-6 |
| 11 | Laycan Optimization | FR-LY | BR-6 |
| 12 | Market-Entry Timing | FR-MT | BR-2 |
| 13 | Contract-Type Recommendation | FR-CR | BR-3 |
| 14 | Total Landed-Cost Calculation | FR-LC | BR-4 |
| 15 | Multi-Origin Procurement Optimization | FR-MO | BR-5 |
| 16 | Alternative-Port Recommendation | FR-AP | BR-10 |
| 17 | Idle-Vessel Employment Recommendation | FR-IV | BR-12 |
| 18 | Weather & Marine Risk | FR-WR | BR-11 |
| 19 | Geopolitical / Disruption Risk | FR-GR | BR-11 |
| 20 | Explainable AI Recommendations | FR-XAI | BR-13 |
| 21 | What-If Simulation | FR-WI | BR-14 |
| 22 | Alerts | FR-AL | BR-15 |
| 23 | Executive Dashboard | FR-ED | BR-15 |

## Related documents

- [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md)
- [BUSINESS_REQUIREMENTS.md](./BUSINESS_REQUIREMENTS.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
- [GLOSSARY.md](./GLOSSARY.md)
