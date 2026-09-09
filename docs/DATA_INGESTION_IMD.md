# Weather/Marine Warnings Ingestion — IMD Adapter

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Ingestion Adapter Guide
**Status:** Draft v1.0

How the platform ingests **India Meteorological Department (IMD)** marine and
cyclone products, normalizing them to `MarineObservation` and
`CycloneObservation`. Built on the ingestion framework (`apps.ingestion`).
Implementation: `backend/apps/ingestion/sources/imd.py`.

---

## 1. Provider & important caveat

- **Provider:** India Meteorological Department (`mausam.imd.gov.in`).
- **Caveat:** IMD does **not** publish a single, stable, uniformly-documented public JSON API. Products (port warnings, sea-area / coastal bulletins, cyclone tracks, wind warnings) are offered in varying forms — some as structured feeds, much as text/PDF — and their endpoints and shapes change over time (see [DATA_SOURCES.md](./DATA_SOURCES.md) §5: IMD endpoints are marked *unverified — confirm at integration*).
- Consequently this adapter is **config-driven**: each ingestion is configured with a product URL, a product type, and an explicit `field_map`. It reads **only** the declared fields and never invents data a product does not provide.
- **No scraping:** the adapter consumes documented structured product URLs (or injected payloads in tests). It does not parse HTML/PDF. Where IMD offers only human-readable bulletins, curation into a structured feed is a separate concern, not done here.

## 2. Products supported

| Product type | Normalized to |
| --- | --- |
| `port_warning` | `MarineObservation` (warning_type = port_warning) |
| `sea_area_bulletin` | `MarineObservation` (warning_type = sea_area_bulletin) |
| `coastal_bulletin` | `MarineObservation` (warning_type = coastal_bulletin) |
| `cyclone_track` | `CycloneObservation` (bulletin_kind = track) |
| `cyclone_wind_warning` | `CycloneObservation` (bulletin_kind = wind_warning) |

## 3. Captured & stored fields

Common to both targets: **issue time**, **valid time** (`valid_from` / `valid_to`), **port/location** (a linked `Port` and/or an `area_name`), **warning type**, **severity** (normalized), and a **raw source reference** (`source_ref`) plus the full `raw` record.

- **MarineObservation** additionally: `headline`, optional coordinates, optional `significant_wave_height_m`.
- **CycloneObservation** additionally: `system_name`, `advisory_no`, track `latitude`/`longitude`, `category`, `max_wind_kn`, `gust_kn`, `central_pressure_hpa`.

Severity is normalized from free text (e.g. yellow→low, orange→moderate, red→severe); unrecognized values map to `unknown` rather than being guessed. Coordinates are nullable so an area-level bulletin or a wind warning can be stored without fabricating a point.

## 4. Missing-data handling

- A declared field absent from a record → that field is null (never fabricated).
- A marine record with neither an `area_name` nor a resolvable `port` is skipped (nothing to anchor it to).
- A cyclone record missing `system_name` or `timestamp` is skipped.
- If the product is unreachable, returns 404/5xx, has no records, or returns an ambiguous non-list payload, the run is reported as `SOURCE_UNAVAILABLE` (not a hard failure).

## 5. Dedup & run tracking

- `MarineObservation` upserts on `(source, warning_type, area_name, port, timestamp)`.
- `CycloneObservation` upserts on `(system_name, timestamp, bulletin_kind, source)`.

Each run records an `IngestionRun` with status and counters.

## 6. Configuration example

```python
from apps.ingestion.sources.imd import IMDSource, IMDProductConfig, PRODUCT_PORT_WARNING

config = IMDProductConfig(
    product=PRODUCT_PORT_WARNING,
    url="https://mausam.imd.gov.in/<documented-product-endpoint>",
    field_map={
        "issue_time": "issued",
        "valid_from": "from",
        "valid_to": "to",
        "port_name": "port",
        "severity": "warning_level",
        "headline": "text",
    },
    source_ref="IMD-PORT-BULLETIN",
)
IMDSource(config).run()
```

The exact `url` and `field_map` must be set to match the specific IMD product's
real structure at integration time — the adapter makes no assumptions about it.

## 7. Limitations & licensing

- IMD is Government of India data; confirm reuse and attribution terms for the specific product before production. Treat this as guidance, not a legal determination (NFR-CMP).
- Machine-readable access is uneven; some products may require a curated feed. This adapter handles structured JSON products and degrades gracefully where a product is unavailable.
- `requests` is an optional dependency (lazy import) needed only for live use; tests inject the HTTP call.

## 8. Testing

`backend/apps/ingestion/tests/test_imd.py` uses mocked IMD product responses:
port warning (with severity + issue/valid times + raw retention), unknown
severity → `unknown`, sea-area and coastal bulletins (area-level, no port),
record-without-area-or-port skipped, cyclone track points, cyclone wind warning
(no track point, gust), cyclone missing name/time skipped, `SOURCE_UNAVAILABLE`
(no records / HTTP error), invalid product config, and idempotent re-ingest.

## Related documents

- [DATA_SOURCES.md](./DATA_SOURCES.md)
- [DATA_INGESTION_WEATHER.md](./DATA_INGESTION_WEATHER.md)
- [DATA_INGESTION_AIS.md](./DATA_INGESTION_AIS.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
