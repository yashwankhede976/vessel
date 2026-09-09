# Data Ingestion Architecture

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Architecture note
**Status:** v1.0

The ingestion layer turns external provider data into normalized, validated,
deduplicated rows in the operations models, with full run tracking. It lives in
`apps/ingestion/` and writes to `apps/operations/models.py` sinks.

## Pipeline

Every source runs the same pipeline (`apps/ingestion/base.py`):

```
fetch()  -> raw records          (retry with backoff on transient FetchError)
  -> in-batch dedup              (optional natural-key dedup_key)
  -> normalize (per record)      (apps/ingestion/normalizers.py hooks)
  -> validate  (per record)      (apps/ingestion/validators.py hooks)
  -> persist() -> (written, dup) (source-owned upsert on a natural key)
```

Cross-cutting concerns handled by the framework: retry + exponential backoff,
timeout (per-source `timeout_seconds`), structured logging
(`vessel.ingestion`), and run status/counters/error tracking via the
`IngestionRun` model.

## Base classes

- `BaseIngestionSource` — abstract; declares `key`, `source_kind`, optional
  `normalizer`/`validator`/`dedup_key`; implements `run()` (the orchestrator).
- `RESTIngestionSource` — REST sources; isolate the HTTP call in `_http_get`
  (injectable for tests) and implement `parse(payload)`.
- `FileIngestionSource` — CSV/XLSX/JSON file sources; implement `parse_file`.

The framework carries **no hard HTTP dependency**: concrete sources import
`requests`/`websockets` lazily and accept an injected transport, so tests run
fully offline (dependency injection, not network mocking).

## Run tracking (`IngestionRun`)

Each run records: `source_key`, `source_kind`, `status`
(pending/running/success/partial/failed/source_unavailable), `started_at`,
`finished_at`, `records_fetched/valid/invalid/written/duplicate`, `attempts`,
`error_message`, and a structured `errors` list (index/type/field/detail). A
provider being unavailable is a distinct `SOURCE_UNAVAILABLE` status, not a hard
failure — so a scheduler can tell "quota exhausted" from "adapter broken".

**Graceful degradation:** an optional provider that is unconfigured or
unreachable never crashes the app; it records a run status and moves on.

## Registry & discovery

`apps/ingestion/registry.py` maps a `key` to a source class.
`apps/ingestion/sources/__init__.py` registers every concrete source
(`register_all()`), and `IngestionConfig.ready()` imports it so the registry is
populated at startup. `apps/ingestion/tasks.py::run_source(key)` resolves and
runs a source by key (Celery-ready via `shared_task`, but Celery is optional and
degrades to a plain callable when absent).

## Scheduled ingestion

Scheduling is done by invoking the management commands from cron / a scheduler:

```
python manage.py run_ingestion <key>       # self-configuring sources
python manage.py list_ingestion_sources
```

Self-configuring sources: `open_meteo`, `world_bank`, `un_comtrade`. Each run
records an `IngestionRun`, so job status / started_at / finished_at /
records_processed / errors are all queryable, and one source failing does not
abort others (each command run is independent).

`aisstream` is a **streaming** source (WebSocket); it runs via its own
consumer/`run_session` loop, not `run_ingestion`.

## Observability endpoints

- `GET /api/v1/system/data-freshness/` — freshness per dataset (see
  `DATA_FRESHNESS.md`).
- `GET /api/v1/system/external-services/` — per-provider configured / reachable
  / last_success / last_failure / freshness. **Never returns API keys.**

## Data quality & retention

- Data-quality validators: `DATA_QUALITY.md`.
- Raw-response retention (opt-in) + `data/raw` vs `data/processed`:
  `apps/ingestion/raw_store.py` and `data/README.md`.

## PostGIS

Geo models keep portable `latitude`/`longitude` decimals always, and add a PostGIS
`geom` point only when `USE_POSTGIS` is enabled (see `apps/operations/geo.py`).
Derived AIS features (`apps/operations/services/ais_features.py`) use haversine
on the decimals, so they work with or without PostGIS.
