# Vessel — Total Project Flow

Visual, end-to-end map of the **Vessel** platform: an intelligent freight-forecasting and vessel-chartering decision-support system for bulk cargo procurement into India's East Coast ports (SIH 2026).

This document is diagram-first. Every diagram below is a [Mermaid](https://mermaid.js.org/) block that renders on GitHub and in most Markdown viewers. For prose specs see [`../docs/`](../docs/README.md); this file traces *how data and requests flow* through the whole stack.

> **Data labelling.** Values are tagged by nature: **REAL** (observed/stored), **FORECAST** (model output), **ESTIMATED** (derived/heuristic), **SYNTHETIC** (seed/demo). The decision engine never fabricates numbers — every value traces back to a source or a labelled planning default.

---

## 1. System context (bird's-eye)

How the pieces fit: a React SPA talks to a Django/DRF API, which composes domain engines over a modelled database that is populated by an ingestion layer pulling from external providers. A separate ML layer produces forecasts.

```mermaid
flowchart TB
    subgraph Client["🖥️ Frontend — React + TypeScript (Vite)"]
        UI["Pages: Dashboard, Decision, Chartering,\nFreight Forecast, Market Intel, Risk,\nOptimizer, Idle Vessels, Cargo, Vessels,\nAlerts, Chatbot, Scenarios, Ports"]
        APIClient["api/client.ts\n(fetch wrapper, envelope unwrap, retry)"]
        UI --> APIClient
    end

    subgraph Backend["⚙️ Backend — Django + DRF"]
        Router["API v1 URL router\n/api/v1/*"]
        Views["DRF Views / Serializers\n(HTTP adapters only)"]
        Engines["Decision & Domain Engines\n(apps/decisions/services)"]
        Models["ORM Models\n(catalog + operations)"]
        Ingest["Ingestion pipeline\n(apps/ingestion)"]
        Router --> Views --> Engines --> Models
        Ingest --> Models
    end

    subgraph ML["🤖 ML Layer (pure compute)"]
        MLmodels["datasets / features / models\nfreight, ETA, demurrage"]
    end

    subgraph Ext["🌐 External Data Sources"]
        AIS["AISStream (vessel positions)"]
        Weather["Open-Meteo (weather)"]
        IMD["IMD / INCOIS (marine, cyclone)"]
        Trade["Comtrade / World Bank / India Open Data"]
    end

    DB[("🗄️ Database\nSQLite (dev) / PostgreSQL + PostGIS")]

    APIClient -- "HTTPS JSON\n{success,data,errors,pagination}" --> Router
    Models <--> DB
    Ext --> Ingest
    MLmodels -- "FreightForecast / ETA rows" --> Models
    Engines -. "reads forecasts" .-> Models
```

---

## 2. Layered architecture

The stack is strictly layered. HTTP views are thin adapters; all business logic lives in engines; engines read from models; models are populated by ingestion and ML.

```mermaid
flowchart TB
    L1["**Presentation** — React pages & components"]
    L2["**API client** — client.ts, endpoints/*, useApi hook"]
    L3["**HTTP / API** — DRF views, serializers, pagination, renderers, exceptions"]
    L4["**Decision layer** — decision_engine composes domain engines"]
    L5["**Domain engines** — recommendations, market_pressure, spot_vs_contract,\nrisk_engine, fix_wait, voyage_economics, landed_cost, vessel_suitability,\nidle_vessel, alternative_port, optimization, contract_portfolio, chatbot"]
    L6["**Data model** — catalog + operations ORM"]
    L7["**Ingestion** — fetch → dedup → normalize → validate → persist"]
    L8["**Storage** — SQLite / PostgreSQL + PostGIS"]

    L1 --> L2 --> L3 --> L4 --> L5 --> L6 --> L8
    L7 --> L6
    ML["ML layer\n(forecast/ETA/demurrage)"] --> L6

    classDef ui fill:#e3f2fd,stroke:#1565c0;
    classDef api fill:#e8f5e9,stroke:#2e7d32;
    classDef logic fill:#fff3e0,stroke:#ef6c00;
    classDef data fill:#f3e5f5,stroke:#6a1b9a;
    class L1,L2 ui;
    class L3 api;
    class L4,L5 logic;
    class L6,L7,L8,ML data;
```

---

## 3. The core flow — unified decision (`POST /api/v1/decision/`)

This is the heart of the product. A single request composes forecast + vessel + port + cost + contract + risk + timing into one explainable recommendation. The view contains **no business logic** — it adapts HTTP to `evaluate_decision`, which orchestrates the domain engines.

```mermaid
sequenceDiagram
    autonumber
    participant U as User (SPA)
    participant C as api/client.ts
    participant V as DecisionView (DRF)
    participant S as DecisionRequestSerializer
    participant E as evaluate_decision()
    participant R as recommend_vessels
    participant DB as ORM / DB

    U->>C: submit chartering requirement
    C->>V: POST /api/v1/decision/ (JSON)
    V->>S: validate payload
    S-->>V: DecisionRequest (typed)
    V->>E: evaluate_decision(request)

    Note over E,R: 1. Vessel recommendation (open vessels only)
    E->>R: recommend_vessels(...)
    R->>DB: query vessels, berths, routes
    R-->>E: ranked + excluded vessels\n(compat, congestion, ETA, demurrage, voyage econ, suitability)

    Note over E,DB: 2. Freight band (real FreightForecast, else labelled default)
    E->>DB: latest FreightForecast for lane
    DB-->>E: low / mid / high band

    Note over E: 3. Market pressure  4. Unified risk  5. Spot vs contract\n6. Fix/Wait timing  7. Total landed cost
    E->>E: compose engines + apply scenario what-ifs
    E-->>V: DecisionResult (+ explainability)
    V-->>C: {success, data: {...}}
    C-->>U: recommendation, savings, timing,\nreasons, risk, freshness
```

### What the decision engine composes

```mermaid
flowchart LR
    REQ["DecisionRequest\ncommodity, tonnes, origin,\ndestination, laycan, scenario"]

    REQ --> REC["recommend_vessels"]
    REC --> COMPAT["berth compatibility"]
    REC --> CONG["congestion"]
    REC --> ETA["ETA"]
    REC --> DEM["demurrage"]
    REC --> VOY["voyage economics"]
    REC --> SUIT["suitability ranking"]

    REQ --> FB["freight band\n(FreightForecast)"]
    REQ --> MP["market_pressure"]
    REQ --> RISK["risk_engine"]
    REQ --> SVC["spot_vs_contract"]
    REQ --> FW["fix_wait timing"]
    REQ --> LC["landed_cost"]

    COMPAT & CONG & ETA & DEM & VOY & SUIT & FB & MP & RISK & SVC & FW & LC --> RES

    RES["DecisionResult\nrecommended vessel • freight forecast •\ntotal landed cost • contract • risk •\nFIX_NOW / WAIT / PARTIAL_FIX / MONITOR •\nexpected savings • confidence"]

    RES --> EXP["Explainability\nreasons • positive/negative factors •\nmodel_version • data_freshness"]

    classDef req fill:#e3f2fd,stroke:#1565c0;
    classDef eng fill:#fff3e0,stroke:#ef6c00;
    classDef out fill:#e8f5e9,stroke:#2e7d32;
    class REQ req;
    class REC,COMPAT,CONG,ETA,DEM,VOY,SUIT,FB,MP,RISK,SVC,FW,LC eng;
    class RES,EXP out;
```

---

## 4. Request lifecycle (any endpoint)

Every API call follows the same envelope-based path, with safe retry for idempotent GETs only.

```mermaid
flowchart TB
    A["React component\ncalls endpoint fn"] --> B["api/endpoints/*.ts"]
    B --> C["client.ts: get/post/patch/del"]
    C --> D{"GET &\ntransient error?"}
    D -- yes --> E["retry w/ backoff\n(max 2)"] --> C
    D -- no --> F["fetch() → Django"]
    F --> G["API v1 router\nresolves /api/v1/<domain>/"]
    G --> H["DRF View + Serializer\n(validate)"]
    H --> I["Domain engine / ORM query"]
    I --> J["Renderer wraps\n{success,data,errors,pagination}"]
    J --> K["client unwraps envelope\n→ ApiError on failure"]
    K --> A

    classDef fe fill:#e3f2fd,stroke:#1565c0;
    classDef be fill:#e8f5e9,stroke:#2e7d32;
    class A,B,C,D,E,K fe;
    class F,G,H,I,J be;
```

---

## 5. Data ingestion pipeline

External providers are pulled through a common, resilient pipeline. Each run is tracked as an `IngestionRun` (status, counters, per-record errors) so data freshness and quality are observable.

```mermaid
flowchart LR
    subgraph Sources["Registered sources (by key)"]
        S1["aisstream"]
        S2["open_meteo"]
        S3["imd / incois"]
        S4["comtrade / world_bank /\nindia_open_data"]
    end

    Sources --> F["fetch()\n(retry + backoff)"]
    F --> D["in-batch dedup\n(natural key)"]
    D --> N["normalize\n(per record)"]
    N --> V["validate\n(per record)"]
    V --> P["persist()\n(source-owned upsert)"]
    P --> DB[("catalog + operations tables")]

    F -.-> RUN["IngestionRun\nstatus • fetched/valid/invalid/\nwritten/duplicate • errors"]
    N -.-> RUN
    V -.-> RUN
    P -.-> RUN

    classDef src fill:#e3f2fd,stroke:#1565c0;
    classDef pipe fill:#fff3e0,stroke:#ef6c00;
    classDef store fill:#f3e5f5,stroke:#6a1b9a;
    class S1,S2,S3,S4 src;
    class F,D,N,V,P pipe;
    class DB,RUN store;
```

Run states: `RUNNING → SUCCESS | PARTIAL | SOURCE_UNAVAILABLE | FAILED`. A missing file or unavailable provider is reported distinctly rather than as a hard adapter failure, and validation failures downgrade a run to `PARTIAL` without losing the good records.

---

## 6. Core data model (ERD)

The `catalog` app holds reference/master data; `operations` holds observed and derived data. Simplified relationships:

```mermaid
erDiagram
    COMMODITY ||--o{ CARGO_REQUIREMENT : "for"
    COMMODITY }o--o{ BERTH : "handled at"
    PORT ||--o{ BERTH : "has"
    PORT ||--o{ ROUTE : "destination"
    PORT ||--o{ CARGO_REQUIREMENT : "delivered to"
    ORIGIN ||--o{ ROUTE : "from"
    ORIGIN ||--o| PORT : "load port"
    ROUTE ||--o{ FREIGHT_OBSERVATION : "priced by"
    ROUTE ||--o{ FREIGHT_FORECAST : "forecast for"
    VESSEL ||--o{ AIS_POSITION : "reports"

    COMMODITY {
        string name
        string category
        string hs_code
    }
    PORT {
        string name
        string country
        string coast
        decimal latitude
        decimal longitude
    }
    BERTH {
        decimal max_loa
        decimal max_beam
        decimal max_draft
        decimal handling_rate
    }
    VESSEL {
        string imo
        string mmsi
        string vessel_type
        decimal dwt
        decimal draft
        string availability_status
    }
    ROUTE {
        decimal distance_nm
        decimal typical_transit_days
    }
    CARGO_REQUIREMENT {
        decimal quantity_tonnes
        date laycan_start
        date laycan_end
        string status
    }
    FREIGHT_OBSERVATION {
        date observed_on
        decimal rate_per_tonne
        string rate_type
        bool is_estimated
    }
```

`operations` adds observed series (AIS positions, port congestion, weather, marine/cyclone warnings, prices, trade, bunkers) and derived outputs (`FreightForecast`, ETA forecasts, risk scores, recommendations). Geo models carry portable lat/lon plus an optional PostGIS `geom` point.

---

## 7. Frontend page → API map

Each page is backed by domain endpoint modules that all sit on top of the single `client.ts`.

```mermaid
flowchart LR
    subgraph Pages
        P1["DecisionPage"]
        P2["FreightForecastPage"]
        P3["MarketIntelligencePage"]
        P4["RiskPage"]
        P5["OptimizerPage"]
        P6["IdleVesselsPage"]
        P7["VesselsPage / CargoPage / PortsPage"]
        P8["AlertsPage"]
        P9["ChatbotPage"]
        P10["ScenariosPage"]
    end

    P1 --> E1["/decision/"]
    P2 --> E2["/forecasts/ /freight/"]
    P3 --> E3["/market-pressure/ /congestion/"]
    P4 --> E4["/risk/"]
    P5 --> E5["/optimization/"]
    P6 --> E6["/idle-vessel/"]
    P7 --> E7["/vessels/ /cargo/ /ports/ /routes/"]
    P8 --> E8["/alerts/"]
    P9 --> E9["/chat/"]
    P10 --> E1

    classDef pg fill:#e3f2fd,stroke:#1565c0;
    classDef ep fill:#e8f5e9,stroke:#2e7d32;
    class P1,P2,P3,P4,P5,P6,P7,P8,P9,P10 pg;
    class E1,E2,E3,E4,E5,E6,E7,E8,E9 ep;
```

---

## 8. Deployment topology

Frontend and backend build into **separate images** and deploy independently. Local orchestration adds PostGIS.

```mermaid
flowchart LR
    Browser["Browser"] --> FE["Frontend image\n(static SPA, :8080)"]
    Browser --> BE["Backend image\n(Django + DRF, :8000)"]
    FE -. "VITE_API_BASE_URL" .-> BE
    BE --> PG[("PostgreSQL + PostGIS")]
    BE -. "startup" .-> MIG["migrate + seed ports"]

    classDef box fill:#e8f5e9,stroke:#2e7d32;
    class FE,BE,PG,MIG box;
```

---

## 9. End-to-end story (one line per hop)

1. External providers → **ingestion** pulls, dedups, validates, and persists REAL data.
2. **ML layer** produces FORECAST rows (freight/ETA/demurrage) into the DB.
3. User opens a page in the **React SPA** and submits a chartering requirement.
4. `client.ts` sends a JSON request through the **DRF router** to the matching view.
5. The view validates input and calls a **domain engine** (or `evaluate_decision` for the unified flow).
6. Engines read modelled data, compose forecast + vessel + cost + contract + risk + timing.
7. The response is wrapped in the standard envelope, unwrapped client-side, and rendered with **explainability** (reasons, factors, model versions, data freshness).

---

## Related docs

- [Docs index](../docs/README.md) · [Architecture](../docs/ARCHITECTURE.md) · [API conventions](../docs/API_CONVENTIONS.md)
- [Data sources](../docs/DATA_SOURCES.md) · [Ingestion architecture](../docs/DATA_INGESTION_ARCHITECTURE.md) · [Explainability](../docs/EXPLAINABILITY.md)
- [Frontend architecture](../docs/FRONTEND_ARCHITECTURE.md) · [Workflows](../docs/WORKFLOWS)
