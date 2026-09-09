# Data Quality

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Data-quality note
**Status:** v1.0

How bad data is kept out of the analytical tables while the ingestion error is
preserved for diagnosis. Rules live in `apps/ingestion/validators.py`; they are
composed per source via `chain(...)` and run in the pipeline's validate stage
(`apps/ingestion/base.py`).

## What happens to a bad record

When a validator raises `ValidationError`, the base pipeline:
1. increments `IngestionRun.records_invalid`,
2. appends `{index, type, field, detail}` to `IngestionRun.errors`,
3. drops the record so it never reaches the sink model.

So the analytical tables stay clean, and the diagnostic trail is retained on the
run record. Model-level validators (`LAT`/`LON`/`NON_NEGATIVE`/`SCORE`) provide a
second line of defence at write time.

## Generic validators

| Validator | Rejects |
|---|---|
| `require_fields(*f)` | missing/empty required fields |
| `numeric_range(f, minimum, maximum)` | non-numeric / out-of-range values |
| `one_of(f, allowed)` | values outside an allowed set |
| `valid_coordinates(lat, lon)` | impossible coordinates (lat∉[-90,90], lon∉[-180,180]) |
| `non_negative(*f)` | negative cargo quantities / distances / prices |
| `no_future_timestamp(*f, skew_seconds)` | timestamps implausibly in the future |
| `valid_date_order(a, b)` | a start after its end |
| `valid_vessel_dimensions(...)` | zero/negative or absurd LOA/beam/draft/DWT |
| `valid_freight_rate(f, min, max)` | negative or absurd freight rates |

### Documented bounds

- Coordinates: latitude [-90, 90], longitude [-180, 180].
- Vessel dimensions (generous physical bounds for the largest bulk carriers):
  LOA (1, 400] m, beam (1, 70] m, draft [0.5, 30] m, DWT (1, 500000] t.
- Freight rate: [0, 1000] currency/tonne by default (a generous dry-bulk sanity
  ceiling; override per source).
- Future-timestamp tolerance: 3600s (1h) clock-skew allowance. **Forecast rows**
  with far-future target dates must NOT use `no_future_timestamp` on the target
  field.

## Duplicates

- **In-batch** duplicates are removed by the pipeline when a source sets a
  `dedup_key` (first occurrence wins).
- **Cross-run** duplicates are prevented by each source's `persist()` upserting
  on the sink model's natural-key unique constraint (e.g. AISPosition on
  `(mmsi, timestamp)`, TradeObservation on its lane/period/flow/source key), so
  re-running a source updates rather than duplicates.

## Provenance retained

Sinks store provenance so a value can always be traced: `source` on every model;
`source_url` / `source_date` / `retrieved_at` on Trade, PortTraffic and
CommodityPrice; and a verbatim `raw` payload on Weather/Marine/Cyclone/Trade.
`is_estimated` flags ESTIMATED values where applicable.
