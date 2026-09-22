# Vessel — Total Project Flow

Visual, end-to-end map of the **Vessel** platform: an intelligent freight-forecasting and vessel-chartering decision-support system for bulk cargo procurement into India's East Coast ports (SIH 2026).

This document is diagram-first. Every diagram below is a [Mermaid](https://mermaid.js.org/) block that renders on GitHub and in most Markdown viewers. For prose specs see [`../docs/`](../docs/README.md); this file traces *how data and requests flow* through the whole stack.

> **Data labelling.** Values are tagged by nature: **REAL** (observed/stored), **FORECAST** (model output), **ESTIMATED** (derived/heuristic), **SYNTHETIC** (seed/demo). The decision engine never fabricates numbers — every value traces back to a source or a labelled planning default.

### Contents

1. [System context (bird's-eye)](#1-system-context-birds-eye)
2. [Layered architecture](#2-layered-architecture)
3. [The core flow — unified decision](#3-the-core-flow--unified-decision-post-apiv1decision)
4. [Request lifecycle (any endpoint)](#4-request-lifecycle-any-endpoint)
5. [Data ingestion pipeline](#5-data-ingestion-pipeline)
6. [Core data model (ERD)](#6-core-data-model-erd)
7. [Frontend page → API map](#7-frontend-page--api-map)
8. [Deployment topology](#8-deployment-topology)
9. [End-to-end story](#9-end-to-end-story-one-line-per-hop)
10. [Domain engine catalogue](#10-domain-engine-catalogue)
11. [Fix / Wait timing decision tree](#11-fix--wait-timing-decision-tree)
12. [Unified risk scoring](#12-unified-risk-scoring)
13. [Spot-vs-contract comparison](#13-spot-vs-contract-comparison)
14. [Scenario what-if flow](#14-scenario-what-if-flow-stateless)
15. [Alerts pipeline](#15-alerts-pipeline)
16. [Chatbot flow](#16-chatbot-flow-grounded--graceful-fallback)

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

## 10. Domain engine catalogue

Every engine is **rule-based, deterministic, and explainable** — not ML, not a black-box solver. Each lives in `apps/decisions/services/` (or the paired `catalog`/`operations` service) and returns a structured breakdown alongside its headline number. The ML layer is the only statistical component, and it only produces stored `FreightForecast` / ETA rows that engines read.

| Engine | Module | Input (key signals) | Output |
| --- | --- | --- | --- |
| Vessel recommendation | `recommendations.py` | origin, destination, cargo, commodity, laycan | ranked + excluded vessels |
| Berth compatibility | `catalog.services` | vessel draft/LOA/beam vs berth limits, commodity | COMPATIBLE / CONDITIONAL / INCOMPATIBLE |
| Port congestion | `operations.services.congestion` | AIS positions, port calls | congestion score 0–100 |
| ETA | `operations.services.eta` | route distance, speed, weather risk | ETA + P50/P80/P95 + delay causes |
| Voyage economics | `voyage_economics.py` | distance, speed, tonnes, freight, bunker | freight cost, demurrage, total voyage cost |
| Vessel suitability | `vessel_suitability.py` | dimension fits, freight vs band, ETA, congestion | suitability score 0–100 (the ranking key) |
| Market pressure | `market_pressure.py` | vessel supply, volatility, congestion | index + BALANCED…EXTREMELY_TIGHT |
| Unified risk | `risk_engine.py` | 8 factors (freight/port/weather/eta/demurrage/…) | risk 0–100 + LOW/MED/HIGH + breakdown |
| Spot vs contract | `spot_vs_contract.py` | spot rate, tonnes, volatility, demurrage | recommended strategy + savings |
| Fix / Wait timing | `fix_wait.py` | current rate, 7/14/30d forecast, deadline | FIX_NOW / WAIT / PARTIAL_FIX / MONITOR |
| Landed cost | `landed_cost.py` | freight, duties, port, inland | total delivered cost/tonne |
| Idle-vessel detection | `idle_vessel.py` | AIS dwell, availability | idle candidates |
| Alternative port | `alternative_port.py` | congestion, distance, cost | ranked substitute ports |
| Optimization | `optimization.py` | cargo demands, vessel supply | cargo↔vessel matching |
| Contract portfolio | `contract_portfolio.py` | multiple cargoes, strategies | portfolio-level mix |
| Chatbot | `chatbot.py` | question + inferred lane | grounded NL answer |

```mermaid
flowchart TB
    subgraph read["Read stored data"]
        DB[("catalog + operations")]
    end
    subgraph compose["Composition engines"]
        DEC["decision_engine\n(evaluate_decision)"]
        REC["recommendations"]
        OPT["optimization"]
        PORT2["contract_portfolio"]
    end
    subgraph leaf["Leaf engines (single concern)"]
        COMPAT["compatibility"]
        CONG["congestion"]
        ETA["eta"]
        VOY["voyage_economics"]
        SUIT["vessel_suitability"]
        MP["market_pressure"]
        RISK["risk_engine"]
        SVC["spot_vs_contract"]
        FW["fix_wait"]
        LC["landed_cost"]
    end

    DB --> COMPAT & CONG & ETA & VOY & MP & RISK & LC
    REC --> COMPAT & CONG & ETA & VOY & SUIT
    DEC --> REC & MP & RISK & SVC & FW & LC
    SVC --> RISK
    OPT --> REC
    PORT2 --> SVC

    classDef d fill:#f3e5f5,stroke:#6a1b9a;
    classDef c fill:#fff3e0,stroke:#ef6c00;
    classDef l fill:#e8f5e9,stroke:#2e7d32;
    class DB d;
    class DEC,REC,OPT,PORT2 c;
    class COMPAT,CONG,ETA,VOY,SUIT,MP,RISK,SVC,FW,LC l;
```

Note the layering: `spot_vs_contract` reuses `risk_engine`; `recommendations` reuses the five leaf engines per candidate; and `decision_engine` sits on top of everything. No engine duplicates another's logic.

---

## 11. Fix / Wait timing decision tree

The timing engine is fully auditable — every branch is a **named, documented threshold** (e.g. `STRONG_MOVE_PCT = 0.05`, `DEADLINE_URGENT_DAYS = 7`). It blends 7/14/30-day forecasts into a confidence-weighted expected move, then walks a deterministic tree.

```mermaid
flowchart TD
    START(["current rate + 7/14/30d forecasts\n+ deadline + availability + volatility"])
    START --> HASFC{"any forecast\navailable?"}
    HASFC -- no --> MON1["MONITOR\n(no directional signal)"]
    HASFC -- yes --> BLEND["blend → expected_move_pct\n+ effective_confidence"]

    BLEND --> URGENT{"deadline ≤ 7d?"}
    URGENT -- yes --> FIX1["FIX_NOW\n(no time to wait)"]
    URGENT -- no --> RISE{"rates rising\n≥ +2%?"}

    RISE -- yes --> FIX2["FIX_NOW\n(avoid paying more)"]
    RISE -- no --> TIGHT{"tonnage tight\n≤ 0.35?"}
    TIGHT -- yes --> FIX3["FIX_NOW\n(supply tightening)"]
    TIGHT -- no --> FALL{"rates falling\n≤ -2%?"}

    FALL -- no --> MON2["MONITOR\n(flat / no edge)"]
    FALL -- yes --> STRONG{"strong fall ≤ -5%\n+ high conf ≥ 0.70\n+ deadline > 14d\n+ low volatility?"}
    STRONG -- yes --> WAIT["WAIT\n(waiting pays off)"]
    STRONG -- no --> CONF{"confident ≥ 0.55\n+ low volatility\n+ time left?"}
    CONF -- yes --> PART1["PARTIAL_FIX\n(hedge mixed signal)"]
    CONF -- no --> VOL{"high volatility\n≥ 0.6?"}
    VOL -- yes --> PART2["PARTIAL_FIX\n(unreliable forecast)"]
    VOL -- no --> MON3["MONITOR\n(low conviction)"]

    classDef fix fill:#ffebee,stroke:#c62828;
    classDef wait fill:#e8f5e9,stroke:#2e7d32;
    classDef part fill:#fff8e1,stroke:#f9a825;
    classDef mon fill:#eceff1,stroke:#546e7a;
    class FIX1,FIX2,FIX3 fix;
    class WAIT wait;
    class PART1,PART2 part;
    class MON1,MON2,MON3 mon;
```

---

## 12. Unified risk scoring

Risk blends up to eight independent factors into one 0–100 score. **Unknown factors are never invented** — a factor with no data stays UNKNOWN, is excluded from the weighting, and its weight is redistributed across the factors that do have data. This is the platform's core honesty rule in action.

```mermaid
flowchart LR
    subgraph factors["Factors (raw → normalized 0..1)"]
        F1["freight vol · 0.20"]
        F2["port congestion · 0.16"]
        F3["weather · 0.14"]
        F4["eta delay · 0.14"]
        F5["demurrage · 0.12"]
        F6["commodity · 0.10"]
        F7["fx · 0.08"]
        F8["geopolitical · 0.06"]
    end
    factors --> KNOWN{"has data?"}
    KNOWN -- no --> UNK["stays UNKNOWN\n(weight redistributed)"]
    KNOWN -- yes --> W["renormalize weights\nover known factors"]
    W --> SUM["Σ weight × normalized × 100"]
    SUM --> SCORE["overall_score 0–100"]
    SCORE --> LVL{"level"}
    LVL --> L1["LOW < 33"]
    LVL --> L2["MEDIUM 33–66"]
    LVL --> L3["HIGH ≥ 66"]

    classDef f fill:#e3f2fd,stroke:#1565c0;
    classDef o fill:#fff3e0,stroke:#ef6c00;
    class F1,F2,F3,F4,F5,F6,F7,F8 f;
    class SCORE,L1,L2,L3 o;
```

---

## 13. Spot-vs-contract comparison

Four strategies are each costed with documented planning assumptions (freight multiplier, volatility exposure, flexibility, demurrage multiplier), risk-scored via the risk engine, then ranked by **risk-adjusted cost** = `total × (1 + 0.25 × risk/100)`.

```mermaid
flowchart TB
    IN["spot rate · tonnes · volatility ·\ndemurrage · congestion"]
    IN --> S1["SPOT ×1.00\nexposure 1.00 · flex 1.00"]
    IN --> S2["SHORT_TERM ×0.98\nexposure 0.60 · flex 0.70"]
    IN --> S3["MEDIUM_TERM ×0.95\nexposure 0.30 · flex 0.40"]
    IN --> S4["MULTI_VOYAGE ×0.93\nexposure 0.15 · flex 0.20"]

    S1 & S2 & S3 & S4 --> RS["score_risk(residual volatility,\ncongestion, demurrage)"]
    RS --> RA["risk-adjusted cost\n= total × (1 + 0.25 × risk/100)"]
    RA --> SORT["sort ascending\n(tie-break by strategy order)"]
    SORT --> BEST["recommended strategy\n+ savings vs most expensive"]

    classDef in fill:#e3f2fd,stroke:#1565c0;
    classDef st fill:#fff3e0,stroke:#ef6c00;
    classDef out fill:#e8f5e9,stroke:#2e7d32;
    class IN in;
    class S1,S2,S3,S4 st;
    class BEST out;
```

---

## 14. Scenario what-if flow (stateless)

Scenarios are **stateless overrides** — they adjust the downstream timing/contract/risk inputs for a single computation and never mutate stored data. The same real base data drives both the baseline and every what-if.

```mermaid
flowchart LR
    BASE["stored REAL/FORECAST data"] --> EVAL["evaluate_decision"]
    SCEN["ScenarioOverrides\nfreight_change_pct ·\ncongestion_score ·\nvessel_availability"] --> EVAL
    EVAL --> R1["baseline result"]
    EVAL --> R2["what-if result"]
    R1 & R2 --> CMP["side-by-side compare\n(ScenariosPage)"]
    note["stored data unchanged —\neach scenario recomputed from base"]
    EVAL -.-> note

    classDef b fill:#f3e5f5,stroke:#6a1b9a;
    classDef s fill:#fff3e0,stroke:#ef6c00;
    class BASE b;
    class SCEN s;
```

---

## 15. Alerts pipeline

Detectors consume already-computed signals (freight moves, congestion, warnings, market pressure, ETA delay, availability) and raise deduped `Alert` records with documented thresholds, then dispatch notifications.

```mermaid
flowchart LR
    subgraph signals["Computed signals"]
        A1["freight move ≥ 5% / 12%"]
        A2["congestion ≥ 55 / 75"]
        A3["marine warning\nmoderate/high/severe"]
        A4["market pressure\n≥ 75 / ≤ 25"]
        A5["ETA delay prob ≥ 0.6"]
        A6["availability ≤ 0.30"]
    end
    signals --> DET["detectors\n(threshold check)"]
    DET --> DEDUP["dedup on fingerprint"]
    DEDUP --> ALERT[("Alert\ntype · severity · action")]
    ALERT --> DISP["dispatch notifications"]
    ALERT --> API["/api/v1/alerts/ → AlertsPage"]

    classDef s fill:#e3f2fd,stroke:#1565c0;
    classDef p fill:#fff3e0,stroke:#ef6c00;
    class A1,A2,A3,A4,A5,A6 s;
    class DET,DEDUP,DISP p;
```

---

## 16. Chatbot flow (grounded + graceful fallback)

The chatbot is **strictly scoped** to East Coast India bulk-cargo chartering and **grounded** only in the platform's own `evaluate_decision` output. The OpenAI key is backend-only; if it's missing or the call fails, the service returns a deterministic answer composed from the same grounded data — so the endpoint always responds honestly.

```mermaid
sequenceDiagram
    autonumber
    participant U as ChatbotPage
    participant C as /api/v1/chat/
    participant P as intent parser
    participant D as evaluate_decision
    participant O as OpenAI (optional)

    U->>C: question + conversation_id
    C->>P: parse lane / intent
    alt out of scope
        P-->>U: scope message (no external call)
    else in scope
        P->>D: build DecisionRequest for lane
        D-->>C: grounded decision data
        alt OPENAI_API_KEY set
            C->>O: prompt + grounded data only
            O-->>C: natural-language answer
        else no key / error / timeout
            C->>C: deterministic answer from grounded data
        end
        C-->>U: grounded answer (never invents numbers)
    end
```

---

## Related docs

- [Docs index](../docs/README.md) · [Architecture](../docs/ARCHITECTURE.md) · [API conventions](../docs/API_CONVENTIONS.md)
- [Data sources](../docs/DATA_SOURCES.md) · [Ingestion architecture](../docs/DATA_INGESTION_ARCHITECTURE.md) · [Explainability](../docs/EXPLAINABILITY.md)
- [Frontend architecture](../docs/FRONTEND_ARCHITECTURE.md) · [Workflows](../docs/WORKFLOWS)
