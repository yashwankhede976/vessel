# Non-Functional Requirements

**Project:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India
**Codename:** Vessel
**Document type:** Non-Functional Requirements Document (NFRD)
**Status:** Draft v1.0

---

## How to read this document

Requirements are numbered `NFR-<area>-<n>` and are **testable**. Targets are baseline expectations to be confirmed against real data volumes and infrastructure during implementation. "Shall" denotes mandatory.

---

## 1. Performance & responsiveness

- **NFR-PERF-1** Interactive dashboard and analytics views shall render within ~3 seconds for typical queries under normal load.
- **NFR-PERF-2** On-demand recommendations (timing, contract, laycan, landed cost, alternative port) shall return within ~5 seconds for a single voyage/lane request.
- **NFR-PERF-3** What-if simulation of a single scenario shall recompute affected outputs within ~5 seconds.
- **NFR-PERF-4** Scheduled forecast/batch jobs shall complete within their allotted window and shall not degrade interactive performance.
- **NFR-PERF-5** Vessel-tracking/position views shall reflect the latest ingested data within its defined freshness SLA (see §5).

## 2. Scalability

- **NFR-SCAL-1** The system shall scale to all five origins and all seven East Coast ports without architectural change.
- **NFR-SCAL-2** The data model shall extend to additional dry-bulk commodities beyond coal without schema redesign.
- **NFR-SCAL-3** The system shall handle growth in tracked vessels, historical depth, and concurrent users via horizontal scaling of stateless components.
- **NFR-SCAL-4** Forecasting and optimization workloads shall scale independently of the interactive/API layer.

## 3. Availability & reliability

- **NFR-REL-1** The platform shall target 99.5% availability for interactive services during business hours (baseline; confirm with sponsor).
- **NFR-REL-2** The system shall degrade gracefully when an upstream feed is unavailable, clearly labelling stale, estimated, or missing data rather than failing silently.
- **NFR-REL-3** Batch/ingestion failures shall be retried and shall raise operational alerts; a failed feed shall not corrupt existing data.
- **NFR-REL-4** The system shall recover to a consistent state after restart with no manual data repair for routine failures.

## 4. Accuracy, quality & model governance

- **NFR-ACC-1** Freight forecasts shall be accompanied by a measurable accuracy metric (e.g. MAPE) tracked over time.
- **NFR-ACC-2** Forecasts and risk outputs shall always carry a confidence/uncertainty indication; no point estimate shall be shown without it where uncertainty is material.
- **NFR-ACC-3** Model versions shall be recorded so any historical recommendation can be tied to the model and data that produced it.
- **NFR-ACC-4** The system shall retain forecast-vs-realized records to support periodic model evaluation.
- **NFR-ACC-5** Material model or methodology changes shall be logged and, where relevant, surfaced to users.

## 5. Data freshness & integrity

- **NFR-DATA-1** Each data domain (freight, AIS/position, congestion, weather, trade, bunker) shall have a defined refresh cadence and a visible freshness/last-updated indicator.
- **NFR-DATA-2** The system shall validate incoming data (ranges, schema, plausibility) and quarantine or flag anomalous records.
- **NFR-DATA-3** The provenance/source of each key data point shall be traceable to support explainability and audit.
- **NFR-DATA-4** Estimated or manually entered values shall be clearly distinguished from authoritative feed data throughout the UI and outputs.

## 6. Explainability & transparency (product-level NFR)

- **NFR-XAI-1** Every recommendation shall be explainable: drivers, confidence, and key assumptions shall be retrievable (aligns with FR-XAI in [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)).
- **NFR-XAI-2** Explanations shall be reproducible: the same inputs and model version shall yield the same explanation.
- **NFR-XAI-3** Explanations shall use domain terminology (see [GLOSSARY.md](./GLOSSARY.md)) and avoid opaque, unexplained scores.

## 7. Security

- **NFR-SEC-1** All data in transit shall be encrypted (TLS); sensitive data at rest shall be encrypted.
- **NFR-SEC-2** Access shall require authentication; the system shall support role-based access control aligned to user roles (chartering, procurement, analyst, ops, executive, risk, engineer).
- **NFR-SEC-3** Third-party API credentials and secrets shall be stored securely (secret store / environment configuration), never in source or logs.
- **NFR-SEC-4** The system shall follow least-privilege for internal services and external integrations.
- **NFR-SEC-5** Externally sourced content and feed data shall be treated as untrusted input and validated before use.
- **NFR-SEC-6** Commercially sensitive information (rates, positions, sourcing plans) shall be protected from unauthorized access and disclosure.

## 8. Auditability & traceability

- **NFR-AUD-1** The system shall record recommendations, their inputs, model version, and timestamp for audit (aligns with BR-16).
- **NFR-AUD-2** Alerts shall be logged with trigger basis and timestamp.
- **NFR-AUD-3** User actions that change plans or accept recommendations shall be attributable to a user and time.
- **NFR-AUD-4** Audit records shall be retained per an agreed retention policy.

## 9. Usability & accessibility

- **NFR-USE-1** Primary user journeys (see [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md) §3) shall be achievable without specialist training beyond domain literacy.
- **NFR-USE-2** Key decisions shall be reachable within a small number of steps from the dashboard.
- **NFR-USE-3** The UI shall follow accessibility best practices (keyboard navigation, sufficient contrast, screen-reader-friendly labels). Full WCAG conformance requires separate manual and assistive-technology testing.
- **NFR-USE-4** Units, currencies, dates/times, and time zones shall be presented unambiguously (freight in per-tonne/per-voyage; explicit currency; clear time zone for ETAs).

## 10. Interoperability & integration

- **NFR-INT-1** External data sources shall be integrated behind well-defined interfaces so a provider can be replaced without changing core logic.
- **NFR-INT-2** The system shall expose APIs for its own outputs (forecasts, recommendations, landed cost) to support future integration with booking/ERP systems. `[POST-MVP integration]`
- **NFR-INT-3** Data exchange shall use standard, documented formats.

## 11. Maintainability & observability

- **NFR-MNT-1** The codebase shall be modular along the five capability layers to allow independent evolution.
- **NFR-MNT-2** The system shall emit logs, metrics, and health indicators for data freshness, job status, model performance, and errors.
- **NFR-MNT-3** Configuration (lanes, ports, constraints, cost parameters, duties) shall be externalized from code and updatable without redeployment where practical.
- **NFR-MNT-4** The system shall support monitoring dashboards/alerts for operational health (for the Data/Platform Engineer role).

## 12. Portability & deployment

- **NFR-DEP-1** The system shall be deployable in a reproducible manner (infrastructure-as-code / containerized components).
- **NFR-DEP-2** Environments (dev, test, prod) shall be separable with isolated data and credentials.
- **NFR-DEP-3** The architecture shall avoid hard dependence on a single proprietary platform where reasonable alternatives exist.

## 13. Compliance, licensing & ethics

- **NFR-CMP-1** Use of third-party data shall respect the data provider's licensing and terms.
- **NFR-CMP-2** The platform shall not reuse Kpler's (or any third party's) proprietary content, branding, UI, visual identity, or implementation; Kpler is a capability/UX reference only.
- **NFR-CMP-3** Sanctions/geopolitical-risk features shall be advisory and shall not be presented as legal or compliance determinations.
- **NFR-CMP-4** The platform shall not be used to facilitate evasion of sanctions or applicable law; recommendations shall surface, not hide, such risk.
- **NFR-CMP-5** Recommendations are decision-support only; the platform shall make clear that users retain final decision authority.

## 14. Localization & regional fit

- **NFR-LOC-1** The platform shall be tuned to East-Coast-India operational realities: monsoon/cyclone seasonality, draft-limited ports, and local congestion patterns.
- **NFR-LOC-2** Time and scheduling features shall correctly handle Indian Standard Time alongside origin/vessel time zones.
- **NFR-LOC-3** Currency handling shall support the currencies relevant to freight (typically USD) and landed-cost reporting as configured.

## Related documents

- [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md)
- [BUSINESS_REQUIREMENTS.md](./BUSINESS_REQUIREMENTS.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)
- [GLOSSARY.md](./GLOSSARY.md)
