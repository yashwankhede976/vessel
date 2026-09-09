# Data Freshness

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Observability note
**Status:** v1.0

How the platform reports whether each dataset is up to date. Implemented in
`apps/ingestion/freshness.py`; exposed at `GET /api/v1/system/data-freshness/`.

## Levels

- **FRESH** — most recent record is within the dataset's fresh window.
- **STALE** — older than fresh but within the stale window.
- **VERY_STALE** — older than the stale window.
- **UNKNOWN** — no records for the dataset (nothing ingested yet).

Freshness is computed on demand from the age of the latest observation per
dataset — no extra stored table. Different datasets refresh at different
cadences, so each has its own documented thresholds `(fresh_within_hours,
stale_within_hours)`:

| Dataset | fresh ≤ | stale ≤ | Rationale |
|---|---|---|---|
| `ais_positions` | 6 h | 24 h | near-real-time positions |
| `weather` | 12 h | 48 h | forecasts refreshed a few times/day |
| `marine` | 24 h | 96 h | marine/ocean-state bulletins |
| `cyclone` | 12 h | 48 h | cyclone advisories (when active) |
| `port_congestion` | 48 h | 168 h | congestion snapshots |
| `port_traffic` | 30 d | 120 d | monthly port statistics |
| `trade` | 60 d | 180 d | trade stats are months-lagged |
| `commodity_price` | 7 d | 45 d | weekly-ish indices |
| `bunker_price` | 3 d | 14 d | bunker quotes |

Datasets not listed use a default of (24 h, 72 h).

## Response shape

```json
{
  "generated_at": "2026-09-09T00:00:00Z",
  "datasets": [
    {
      "dataset": "ais_positions",
      "latest_at": "2026-09-08T22:00:00Z",
      "age_hours": 2.0,
      "level": "FRESH",
      "fresh_within_hours": 6,
      "stale_within_hours": 24,
      "record_count": 1234
    }
  ]
}
```

Freshness is also embedded per provider in the external-services endpoint (see
`DATA_INGESTION_ARCHITECTURE.md`). It reflects **stored** data — the platform
does not claim real-time freshness beyond what has actually been ingested.
