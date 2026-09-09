# Data Sources

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Integration reference
**Status:** v1.0

Every external data source, its adapter, credential requirement, and data
classification. Adapters live in `apps/ingestion/sources/` and are built on the
ingestion framework (`apps/ingestion/base.py`); see
`DATA_INGESTION_ARCHITECTURE.md`.

## Data classification

- **REAL** — actual published/observed provider data.
- **SYNTHETIC** — generated/demo data (used for pipeline validation only).
- **ESTIMATED** — inferred where a direct measurement was unavailable (flagged
  `is_estimated` on the model where applicable).
- **FORECAST** — a model/provider prediction for a future time.

## Adapters

| Provider | Source key | Credential | Kind | Sink model | Data | Status |
|---|---|---|---|---|---|---|
| AISStream | `aisstream` | **API key required** (`AISSTREAM_API_KEY`) | WebSocket stream | `AISPosition` | REAL | Complete (needs key + `websockets`) |
| UN Comtrade | `un_comtrade` | Keyless (free tier); key raises limits (`COMTRADE_API_KEY`) | REST | `TradeObservation` | REAL | Complete |
| data.gov.in | `data_gov_in` | **API key required** (`DATA_GOV_API_KEY`) + resource id | REST | `PortTraffic`/`TradeObservation`/`CommodityPriceObservation` | REAL | Complete (per-dataset config) |
| Ministry of Coal | `ministry_of_coal` | None (download/file mode) | File | `PortTraffic` | REAL | Complete (file supplied; no public API) |
| Open-Meteo | `open_meteo` | **Keyless** | REST | `WeatherObservation` | FORECAST | Complete |
| IMD | `imd` | **Keyless** (config-driven product URLs) | REST | `MarineObservation`/`CycloneObservation` | REAL/FORECAST | Framework complete; product URLs/field maps set at integration |
| INCOIS | `incois` | **Keyless** (public ocean-state products) | REST | `MarineObservation` (ocean-state) | REAL/FORECAST | Framework complete; product URLs/field maps set at integration |
| World Bank | `world_bank` | **Keyless** | REST | `CommodityPriceObservation` | REAL | Complete |

### Keyless vs key-required (summary)

- **Keyless:** Open-Meteo, INCOIS, World Bank, IMD (config-driven URLs),
  Ministry of Coal (file mode), UN Comtrade (free tier — a key only raises the
  rate limit).
- **Key-required:** AISStream (`AISSTREAM_API_KEY`), data.gov.in
  (`DATA_GOV_API_KEY`).

All keys are read only from `settings.EXTERNAL_APIS` (env vars) on the backend
and are **never** returned by any API or exposed to the browser (see
`/api/v1/system/external-services/`, which returns only a `configured` boolean).

## Rate limits & provider terms

- UN Comtrade free tier is limited; the adapter retries HTTP 429/5xx with
  exponential backoff and reports `SOURCE_UNAVAILABLE` when exhausted (it does
  not hammer the API).
- Baltic Exchange freight data is **licensed/commercial** — there is no adapter;
  its key slot exists but is unused. Do not ingest or redistribute licensed data
  without a licence.
- Config-driven providers (IMD/INCOIS) read only documented product URLs passed
  in configuration — no scraping.

## Running a source

```bash
python manage.py list_ingestion_sources          # discover registered sources
python manage.py run_ingestion open_meteo         # keyless, self-configuring
python manage.py run_ingestion world_bank --indicator EG.USE.PCAP.KG.OE
python manage.py run_ingestion un_comtrade --period 2024
```

Config-driven sources (imd, incois, data_gov_in, ministry_of_coal) require a
config object and are invoked programmatically, not via `run_ingestion`.
