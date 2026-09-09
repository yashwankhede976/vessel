# External Data Sources

**Project:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India
**Codename:** Vessel
**Document type:** Data Sources Catalogue
**Status:** Draft v1.0

This document catalogues all **planned** external data sources. It informs the data ingestion layer (see [ARCHITECTURE.md](./ARCHITECTURE.md) §6) but defines **no** API client code — integration is a later task.

---

## How to read this document

Each source is tagged with an **access classification**:

| Tag | Meaning |
| --- | --- |
| `FREE_API` | Programmatic API available at no charge (may still require registration). |
| `FREE_DOWNLOAD` | Files/datasets downloadable at no charge (portal, bulk file, or scrape of published documents). |
| `REGISTRATION_REQUIRED` | A free account / API key must be created before access. Often combined with `FREE_API`. |
| `LICENSED/COMMERCIAL` | Paid subscription and/or a data licence is required for lawful use. |
| `MANUAL_CURATED` | No stable API; data is manually collected/curated from published documents into our own store. |

### Verification & accuracy notice

Access terms, endpoints, quotas, and licensing change over time and were only spot-checked at the time of writing (see the per-source *Verification* line). **No source is claimed "free" unless verified**, and where a detail is unconfirmed it is marked *unverified — confirm before relying on it*. Confirm the current terms and licence of every source before production use. Treat all fetched data as untrusted input (NFR-SEC-5) and record provenance/freshness (NFR-DATA-1..4).

---

## 1. AISStream

- **Access classification:** `FREE_API` + `REGISTRATION_REQUIRED`
- **Purpose:** Real-time vessel positions and identity for vessel tracking (FR-VT), ETA inputs (FR-ETA), and vessel availability signals (FR-VA).
- **Data obtained:** Live AIS messages streamed over WebSocket (position reports, static/voyage data) for vessels within subscribed geographic bounding boxes; supports optional MMSI and message-type filtering.
- **Expected fields (typical AIS):** MMSI, IMO (where present), vessel name, position (lat/lon), SOG (speed over ground), COG (course over ground), heading, navigational status, timestamp, ship type, draught, destination, ETA (as reported by the vessel), dimensions.
- **Endpoint / location:** WebSocket `wss://stream.aisstream.io/v0/stream`; subscription is a JSON message declaring bounding box(es) and filters; the API key is carried in the subscription payload (not an HTTP header). Registration at https://aisstream.io/.
- **Authentication:** Free API key obtained by registration.
- **Free / paid:** Free (single free tier; no paid tiers advertised).
- **Rate limits:** No published per-message billing; practical limits (connection/subscription constraints) *unverified — confirm before relying on it*.
- **Licensing considerations:** Review AISStream's terms of use for redistribution/commercial-use conditions before production. AIS data quality/coverage depends on receiver networks.
- **Update frequency:** Real-time streaming.
- **Production suitable:** Partially — good for tracking; validate coverage of the Bay of Bengal / Indian Ocean lanes and terms for production. Consider a commercial AIS provider as backup for coverage/SLA.
- **SIH prototype suitable:** Yes.
- **Fallback source:** NOAA/MarineCadastre (historical/US-coastal AIS) for offline development; a commercial AIS provider (e.g. terrestrial+satellite) for production coverage/SLA.
- **Verification:** aisstream.io and third-party API catalogues, at time of writing — free WebSocket AIS with a free registered API key.

## 2. data.gov.in (Open Government Data Platform India)

- **Access classification:** `FREE_API` + `REGISTRATION_REQUIRED` (API key) / `FREE_DOWNLOAD`
- **Purpose:** Indian government open datasets for port throughput, coal, trade, and logistics context feeding cargo/trade intelligence (FR-CT) and port context (FR-PC/FR-PB background).
- **Data obtained:** Varies by dataset — e.g. port cargo/traffic statistics, coal production/dispatch, commodity and trade figures published by ministries.
- **Expected fields:** Dataset-dependent (e.g. port, commodity, period, tonnage, value). Each dataset defines its own schema.
- **Endpoint / location:** https://data.gov.in — dataset APIs typically via `https://api.data.gov.in/resource/<resource-id>` with an API key; many datasets also offer CSV/XLSX/JSON download.
- **Authentication:** Free API key from data.gov.in for the API; direct downloads may not require a key.
- **Free / paid:** Free.
- **Rate limits:** Per-key limits apply; specifics *unverified — confirm before relying on it*.
- **Licensing considerations:** Governed by the National Data Sharing and Accessibility Policy (NDSAP) / Government Open Data Licence — India; check per-dataset licence and attribution terms.
- **Update frequency:** Dataset-dependent (one-off, monthly, annual).
- **Production suitable:** Yes for the datasets that are actively maintained; verify freshness per dataset.
- **SIH prototype suitable:** Yes.
- **Fallback source:** Direct ministry publications (Ministry of Coal, port authorities), UN Comtrade for trade figures.
- **Verification:** Not re-verified at time of writing — treat endpoints/quotas as *unverified* and confirm at integration.

## 3. Ministry of Coal (Government of India)

- **Access classification:** `FREE_DOWNLOAD` / `MANUAL_CURATED`
- **Purpose:** Domestic coal production, dispatch, stock, and import context to inform cargo/trade intelligence (FR-CT) and demand signals feeding freight forecasting (FR-FC).
- **Data obtained:** Coal production and dispatch statistics, import/consumption reports, provisional monthly statistics, and policy/notice documents.
- **Expected fields:** Period, coal type (thermal/coking), company/source (e.g. CIL/SCCL), production, dispatch, imports, stock — as published in reports/tables.
- **Endpoint / location:** https://coal.gov.in (statistics/reports sections); some figures mirrored on data.gov.in.
- **Authentication:** None (public).
- **Free / paid:** Free to access published material.
- **Rate limits:** N/A (document/portal access).
- **Licensing considerations:** Government publications; confirm reuse/attribution terms. Likely no stable machine API — treat as curated download.
- **Update frequency:** Periodic (often monthly/annual reports).
- **Production suitable:** Yes as a context feed via curated ingestion; not a low-latency API.
- **SIH prototype suitable:** Yes.
- **Fallback source:** data.gov.in coal datasets; Coal India Ltd / SCCL published reports.
- **Verification:** Not re-verified at time of writing — confirm current publication locations at integration.

## 4. UN Comtrade

- **Access classification:** `FREE_API` + `REGISTRATION_REQUIRED`
- **Purpose:** International commodity trade flows (imports/exports by country and commodity) for cargo/trade intelligence (FR-CT) and demand drivers behind freight forecasts (FR-FC).
- **Data obtained:** Bilateral trade statistics in goods (e.g. coal — HS codes such as 2701) by reporter/partner, period, and flow.
- **Expected fields:** Reporter, partner, period (year/month), trade flow (import/export), HS commodity code, quantity, net weight, trade value (USD).
- **Endpoint / location:** UN Comtrade API (Comtrade Plus), `https://comtradeapi.un.org/...`; data portal at https://comtrade.un.org.
- **Authentication:** Free registration for a subscription key; anonymous users can preview via UI but must register to download.
- **Free / paid:** Free public tier available; premium/subscriber tiers exist for higher limits.
- **Rate limits:** Free tier limited (reported ~500 calls/day, up to ~100,000 records per query). Confirm current quotas.
- **Licensing considerations:** UN Comtrade terms of use; attribution expected. Check redistribution terms.
- **Update frequency:** Monthly and annual releases, updated as countries report.
- **Production suitable:** Yes for periodic trade-flow features (batch ETL), within free-tier quotas or via subscription.
- **SIH prototype suitable:** Yes.
- **Fallback source:** data.gov.in trade datasets; national customs/DGCIS publications for India-specific flows.
- **Verification:** UN Comtrade documentation/wiki, at time of writing — free public API with registration; ~500 calls/day and ~100k rows/query on the free tier.

## 5. IMD (India Meteorological Department)

- **Access classification:** `FREE_DOWNLOAD` / `FREE_API` (where offered) — `MANUAL_CURATED` for some products
- **Purpose:** Weather, monsoon, and cyclone information for weather & marine risk (FR-WR), feeding ETA (FR-ETA) and demurrage-risk (FR-DR) models, especially Bay-of-Bengal seasonality.
- **Data obtained:** Weather forecasts/warnings, cyclone bulletins and tracks, monsoon updates, port/coastal warnings.
- **Expected fields:** Location/region, issue time, forecast period, parameters (wind, rainfall, sea state), warning category, cyclone track points (lat/lon, intensity, time).
- **Endpoint / location:** https://mausam.imd.gov.in and related IMD portals/bulletins; RSS/bulletin products where available.
- **Authentication:** Generally none for public bulletins; specific data services may differ.
- **Free / paid:** Public bulletins free; some datasets/services may have charges — *unverified — confirm before relying on it*.
- **Rate limits:** N/A / *unverified*.
- **Licensing considerations:** Government data; confirm reuse and attribution. Machine-readable access may be limited (curate from bulletins).
- **Update frequency:** Frequent for warnings/forecasts (multiple times daily during active weather).
- **Production suitable:** Yes for warnings/context; for numerical marine parameters, combine with INCOIS/NOAA.
- **SIH prototype suitable:** Yes.
- **Fallback source:** INCOIS (ocean/marine), NOAA (global weather/marine models), commercial weather APIs.
- **Verification:** Not re-verified at time of writing — confirm IMD product endpoints/terms at integration.

### 5a. Open-Meteo (implemented default prototype weather provider)

- **Access classification:** `FREE_API` (keyless on the free tier)
- **Purpose:** Hourly weather **forecasts** (temperature, wind, precipitation, WMO condition) for the East Coast ports, feeding weather risk (FR-WR) and ETA/demurrage context. This is the **implemented** default prototype weather source (adapter: `apps.ingestion.sources.open_meteo`).
- **Endpoint:** `https://api.open-meteo.com/v1/forecast` — no API key on the free tier.
- **Free / paid:** Free tier (fair-use, non-commercial). Paid/self-hosted tiers exist for commercial use / SLA.
- **Licensing:** Open licence (CC BY 4.0) with attribution to Open-Meteo required; confirm current terms before production.
- **Limitations:** model forecasts (not point measurements); meteorological only (no waves/currents — use INCOIS/NOAA for marine). Response cached to avoid repeat calls.
- **Full detail:** see [DATA_INGESTION_WEATHER.md](./DATA_INGESTION_WEATHER.md).

## 6. INCOIS (Indian National Centre for Ocean Information Services)

- **Access classification:** `FREE_DOWNLOAD` (Ocean State Forecast products) / `LICENSED/COMMERCIAL` or charged (some in-situ datasets) — mixed
- **Purpose:** Ocean-state forecasts (waves, currents, sea state) for weather & marine risk (FR-WR) and marine-condition inputs to ETA (FR-ETA) on Indian Ocean / Bay-of-Bengal approaches.
- **Data obtained:** Ocean State Forecast (OSF) — wave height/direction, currents, SST, sea-level; in-situ observations (Argo, moored/drifting buoys, tide gauges) via data services.
- **Expected fields:** Location/grid, forecast/observation time, significant wave height, wave direction/period, current speed/direction, SST, sea level.
- **Endpoint / location:** https://incois.gov.in and https://services.incois.gov.in; Live Access Server (LAS) for gridded/observational data; OSF bulletins.
- **Authentication:** Public products generally open; some data services/requests may require a request process or account.
- **Free / paid:** OSF products publicly available; **some in-situ data carry charges** (INCOIS publishes data charges) — do not assume all INCOIS data is free.
- **Rate limits:** N/A / *unverified*.
- **Licensing considerations:** Confirm per-product terms; charged datasets have their own conditions. Attribution to ESSO-INCOIS/MoES.
- **Update frequency:** OSF issued regularly (daily forecast horizon of several days); observations vary.
- **Production suitable:** Yes for OSF marine risk context; budget/licence for any charged in-situ data.
- **SIH prototype suitable:** Yes (use free OSF products).
- **Fallback source:** NOAA marine/wave models, IMD, commercial marine-weather APIs.
- **Verification:** INCOIS documents, at time of writing — public OSF products; a published in-situ data-charges schedule exists (so not uniformly free).

## 7. World Bank — Indicators (WDI)

- **Access classification:** `FREE_API`
- **Purpose:** Macroeconomic indicators (GDP, industrial/energy indicators, trade) as contextual demand features for freight forecasting (FR-FC) and market-entry timing (FR-MT).
- **Data obtained:** Country-level time-series indicators from the World Development Indicators and related databases.
- **Expected fields:** Country/region code, indicator code/name, year, value; metadata (units, source).
- **Endpoint / location:** World Bank Indicators API, `https://api.worldbank.org/v2/...` (JSON/XML); portal at https://data.worldbank.org.
- **Authentication:** None (open API).
- **Free / paid:** Free.
- **Rate limits:** Generous/open; specific throttles *unverified — confirm before relying on it*.
- **Licensing considerations:** Predominantly Creative Commons Attribution (CC BY 4.0) for World Bank datasets; verify per-dataset terms and attribute appropriately.
- **Update frequency:** Periodic (annual/quarterly depending on indicator).
- **Production suitable:** Yes (batch ETL of slow-moving context features).
- **SIH prototype suitable:** Yes.
- **Fallback source:** IMF, OECD, national statistics offices.
- **Verification:** Not re-verified at time of writing — World Bank API is widely documented as open/free; confirm indicator availability at integration.

## 8. World Bank — Commodity Markets ("Pink Sheet")

- **Access classification:** `FREE_DOWNLOAD`
- **Purpose:** Monthly commodity price series (including coal and energy) as price/context features for freight forecasting (FR-FC), landed-cost context (FR-LC), and market-entry timing (FR-MT).
- **Data obtained:** Monthly commodity price data and indices (energy incl. coal, metals, agriculture) published as the "Pink Sheet".
- **Expected fields:** Commodity, period (month), price, unit; index values by group.
- **Endpoint / location:** World Bank Commodity Markets page https://www.worldbank.org/en/research/commodity-markets; monthly Pink Sheet files (PDF/XLSX) under thedocs.worldbank.org.
- **Authentication:** None.
- **Free / paid:** Free download.
- **Rate limits:** N/A (file download).
- **Licensing considerations:** World Bank terms (typically CC BY 4.0 for data); attribute. Confirm current file terms.
- **Update frequency:** Monthly.
- **Production suitable:** Yes (scheduled monthly XLSX ingestion).
- **SIH prototype suitable:** Yes.
- **Fallback source:** IMF Primary Commodity Prices; national coal price references.
- **Verification:** World Bank Commodity Markets page, at time of writing — monthly Pink Sheet published as free downloadable files.

## 9. NOAA / MarineCadastre

- **Access classification:** `FREE_DOWNLOAD` / `FREE_API`
- **Purpose:** Historical AIS (US/coastal via MarineCadastre) for model development and offline testing, and NOAA weather/marine model data for weather & marine risk (FR-WR) and ETA inputs (FR-ETA) where useful.
- **Data obtained:** MarineCadastre historical AIS archives; NOAA meteorological/oceanographic model and observation data (winds, waves, tropical systems).
- **Expected fields:** AIS (MMSI, timestamp, lat/lon, SOG, COG, heading, vessel type/dimensions); NOAA (grid/point, time, parameter values).
- **Endpoint / location:** MarineCadastre https://marinecadastre.gov/ais/ (downloads); NOAA services (e.g. NWS/NCEP model data, tropical products) under noaa.gov domains.
- **Authentication:** Generally none for public downloads/APIs.
- **Free / paid:** Free.
- **Rate limits:** Varies by NOAA service; *unverified — confirm before relying on it*.
- **Licensing considerations:** US Government works are generally public domain; confirm per-product terms and attribution norms.
- **Update frequency:** MarineCadastre AIS is historical/periodic; NOAA model products are frequent.
- **Production suitable:** NOAA weather/marine yes; MarineCadastre AIS is primarily for development/backfill (US-centric coverage), not live Indian-waters tracking.
- **SIH prototype suitable:** Yes (excellent for offline AIS/model development).
- **Fallback source:** IMD/INCOIS for Indian marine specifics; AISStream/commercial AIS for live tracking.
- **Verification:** Not re-verified at time of writing — NOAA/MarineCadastre widely available as free public data; confirm specific product endpoints at integration.

## 10. Baltic Exchange

- **Access classification:** `LICENSED/COMMERCIAL`
- **Purpose:** Authoritative dry-bulk freight benchmarks (e.g. Baltic Dry Index and route/vessel-class assessments) as the primary target/label and features for freight forecasting (FR-FC) and historical analytics (FR-HA).
- **Data obtained:** Daily dry-bulk (and tanker) freight assessments and indices — composite indices (BDI) and route/vessel-class time series (Capesize/Panamax/Supramax).
- **Expected fields:** Index/route code, date, assessment value, vessel class, route definition.
- **Endpoint / location:** Baltic Exchange data services / Market Data API (see balticexchange.com data-services); access via subscription.
- **Authentication:** Subscriber credentials / API keys under a data agreement.
- **Free / paid:** **Paid.** Commercial subscription; a valid Baltic Data licence is required, and a settlement licence is required when Baltic data is referenced in contracts.
- **Rate limits:** Per the commercial API agreement — *unverified — confirm with provider*.
- **Licensing considerations:** Significant. Licensed/commercial data with contractual redistribution and usage restrictions; do **not** ingest or redistribute without a licence. Not to be scraped.
- **Update frequency:** Daily assessments (business days).
- **Production suitable:** Yes if licensed — the preferred freight benchmark for production.
- **SIH prototype suitable:** **No** by default (licensing). For the prototype, use a public proxy/benchmark or synthetic/derived rates and clearly label them as non-authoritative (NFR-DATA-4).
- **Fallback source:** Public freight proxies (where available/licensed appropriately), World Bank/IMF price context as weak proxies, or manually curated indicative rates for the prototype only.
- **Verification:** balticexchange.com FAQs/data-services, at time of writing — commercial/licensed data; settlement/data licence required.

## 11. Individual Indian Port Authority documents

- **Access classification:** `MANUAL_CURATED` (from `FREE_DOWNLOAD` public documents)
- **Purpose:** Port and berth constraints (FR-PB), vessel-port compatibility (FR-VP), and port congestion context (FR-PC) for the seven East Coast ports (Paradip, Visakhapatnam, Gangavaram, Gopalpur, Dhamra, Sagar/Sandheads, Haldia).
- **Data obtained:** Port handbooks, berth specifications, draft/LOA/DWT limits, tariff/notices, and (where published) daily/periodic vessel position/berth/anchorage reports.
- **Expected fields:** Port, berth ID/name, max draft, max LOA/beam/DWT, cargo-handling capability, tidal notes, and (if available) waiting/berth-occupancy figures with dates.
- **Endpoint / location:** Individual port authority websites (e.g. Paradip Port Authority, Visakhapatnam Port Authority, Syama Prasad Mookerjee Port/Haldia, and private terminals Gangavaram/Dhamra/Gopalpur). Documents are typically PDFs/pages.
- **Authentication:** None (public documents).
- **Free / paid:** Free to access published documents.
- **Rate limits:** N/A.
- **Licensing considerations:** Confirm reuse/attribution for each port's material; some private terminals may restrict reuse. No stable machine API — curate into our own constraint tables with effective dates (FR-PB-3).
- **Update frequency:** Infrequent for constraints (updated when infrastructure changes); congestion/daily reports where published are more frequent.
- **Production suitable:** Yes as a curated, versioned constraint dataset; congestion figures may need estimation where not published (NFR-PC-4, NFR-DATA-4).
- **SIH prototype suitable:** Yes.
- **Fallback source:** data.gov.in port datasets; AIS-derived congestion estimates (vessels waiting near port from AISStream/MarineCadastre) as a proxy for berth/anchorage reports.
- **Verification:** Not verified per-port at time of writing — each port's document locations and reuse terms must be confirmed during curation.

---

## Source → feature mapping (ML / optimization)

Links each source to the capability, ML model, or optimization solver it feeds. Capability IDs refer to [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md); layers to [ARCHITECTURE.md](./ARCHITECTURE.md).

| # | Source | Classification | Primary consumer (ML / optimization / domain) | Capabilities fed |
| --- | --- | --- | --- | --- |
| 1 | AISStream | FREE_API + REGISTRATION | ML: ETA models; feature store: positions/tracks (PostGIS); domain: tracking/availability | FR-VT, FR-ETA, FR-VA, FR-PC (AIS-derived congestion) |
| 2 | data.gov.in | FREE_API + REGISTRATION / FREE_DOWNLOAD | ML: freight-forecast demand features; domain: trade/port context | FR-CT, FR-FC, FR-PC/FR-PB (context) |
| 3 | Ministry of Coal | FREE_DOWNLOAD / MANUAL_CURATED | ML: freight-forecast demand features (coal supply/dispatch) | FR-CT, FR-FC |
| 4 | UN Comtrade | FREE_API + REGISTRATION | ML: freight-forecast trade-flow features | FR-CT, FR-FC |
| 5 | IMD | FREE_DOWNLOAD / FREE_API / MANUAL_CURATED | ML: demurrage-risk & ETA weather features; domain: weather-risk assembly | FR-WR, FR-ETA, FR-DR |
| 6 | INCOIS | FREE_DOWNLOAD (mixed/charged) | ML: ETA marine features; domain: marine-risk assembly | FR-WR, FR-ETA, FR-DR |
| 7 | World Bank Indicators | FREE_API | ML: freight-forecast macro-context features | FR-FC, FR-MT |
| 8 | World Bank Pink Sheet | FREE_DOWNLOAD | ML: freight-forecast price features; domain: landed-cost/timing context | FR-FC, FR-LC, FR-MT |
| 9 | NOAA / MarineCadastre | FREE_DOWNLOAD / FREE_API | ML: model development (historical AIS), weather/marine features | FR-ETA, FR-WR (dev + production weather) |
| 10 | Baltic Exchange | LICENSED/COMMERCIAL | ML: freight-forecast **target/label** + benchmark features | FR-FC, FR-HA (production, if licensed) |
| 11 | Indian port authority docs | MANUAL_CURATED | Domain/optimization: port & berth constraints; solvers (laycan, sourcing, alt-port) | FR-PB, FR-VP, FR-PC, FR-LY, FR-MO, FR-AP |

### Optimization inputs (derived)

Optimization solvers (see [ARCHITECTURE.md](./ARCHITECTURE.md) §8) consume **domain-assembled** inputs rather than raw feeds:

| Solver | Uses forecasts/predictions from | Uses constraints/context from |
| --- | --- | --- |
| Multi-origin sourcing (FR-MO) | Freight forecast (Baltic/proxy + WB prices), demurrage risk | Port constraints (port docs), availability (AIS), trade context (Comtrade, Coal) |
| Laycan optimization (FR-LY) | ETA (AIS + IMD/INCOIS/NOAA), demurrage risk | Congestion (port docs / AIS-derived), berth windows (port docs), weather (IMD/INCOIS) |
| Idle-vessel employment (FR-IV) | Freight forecast, ETA | Vessel positions/availability (AIS), port constraints (port docs) |
| Alternative-port recommendation (FR-AP) | Landed cost (WB prices + forecast), demurrage risk | Port constraints & compatibility (port docs), congestion (port docs / AIS) |

---

## Access-classification summary

| Source | Classification | Prototype OK | Production OK |
| --- | --- | --- | --- |
| AISStream | FREE_API + REGISTRATION | Yes | Partial (verify coverage/terms) |
| data.gov.in | FREE_API + REGISTRATION / FREE_DOWNLOAD | Yes | Yes (per dataset) |
| Ministry of Coal | FREE_DOWNLOAD / MANUAL_CURATED | Yes | Yes (curated) |
| UN Comtrade | FREE_API + REGISTRATION | Yes | Yes (within quotas/subscription) |
| IMD | FREE_DOWNLOAD / FREE_API / MANUAL_CURATED | Yes | Yes |
| INCOIS | FREE_DOWNLOAD (mixed/charged) | Yes (free OSF) | Yes (licence charged data) |
| World Bank Indicators | FREE_API | Yes | Yes |
| World Bank Pink Sheet | FREE_DOWNLOAD | Yes | Yes |
| NOAA / MarineCadastre | FREE_DOWNLOAD / FREE_API | Yes | Yes (weather); AIS dev-only |
| Baltic Exchange | LICENSED/COMMERCIAL | No (default) | Yes (if licensed) |
| Indian port authority docs | MANUAL_CURATED | Yes | Yes (curated, versioned) |

**Prototype freight-benchmark note:** because the authoritative freight benchmark (Baltic Exchange, #10) is licensed, the SIH prototype should train/evaluate freight forecasts on a lawful public proxy or clearly-labelled synthetic/curated rates, and treat production integration of Baltic data as a licensed, post-prototype step.

## Related documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
- [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md)
- [GLOSSARY.md](./GLOSSARY.md)
