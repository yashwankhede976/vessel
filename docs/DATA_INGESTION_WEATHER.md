# Weather Ingestion — Open-Meteo Adapter

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Ingestion Adapter Guide
**Status:** Draft v1.0

How the platform ingests weather **forecasts** for the East Coast India ports
using **Open-Meteo** as the default prototype provider, mapping each hourly step
to a `WeatherObservation`. Built on the ingestion framework (`apps.ingestion`).
Implementation: `backend/apps/ingestion/sources/open_meteo.py`.

---

## 1. Provider

- **Provider:** Open-Meteo (`open-meteo.com`) — free, open weather forecast API.
- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Auth:** **none** on the free tier — Open-Meteo is keyless. There is no credential to store for the default prototype configuration. (If a commercial/self-hosted Open-Meteo endpoint is used later, `OPEN_METEO_BASE_URL` / `OPEN_METEO_API_KEY` env variables are reserved for it — backend-only.)

## 2. Locations

Hourly forecasts are fetched for the seven East Coast India locations, at
coordinates matching the seeded ports so observations link to the `Port` rows:

Paradip, Dhamra, Gopalpur, Visakhapatnam, Gangavaram, Haldia, Sagar/Sandheads.

## 3. Captured fields

Per hourly step the adapter requests and stores:

| Field | Open-Meteo variable | Stored on WeatherObservation |
| --- | --- | --- |
| Temperature (°C) | `temperature_2m` | `temperature_c` |
| Wind speed (kn) | `windspeed_10m` (requested in knots) | `wind_speed_kn` |
| Wind direction (°) | `winddirection_10m` | `wind_dir_deg` |
| Precipitation (mm) | `precipitation` | `precipitation_mm` |
| Weather condition | `weathercode` (WMO) → label | `weather_code` + `weather_condition` |
| Forecast timestamp (UTC) | `hourly.time` | `timestamp` |

All rows are marked `is_forecast=True` and `source="open_meteo"`. The raw
per-hour values are also stored in `raw` for audit/reprocessing. A variable
absent from a response leaves that field null (never fabricated). Wind speed is
requested from Open-Meteo directly in knots (`windspeed_unit=kn`) to avoid a
lossy client-side conversion.

WMO weather codes are mapped to human-readable conditions (e.g. 0 → "Clear sky",
61 → "Slight rain", 95 → "Thunderstorm").

## 4. Caching

To avoid repeatedly requesting the same external forecast, each location's raw
response is cached in Django's cache (`django.core.cache`) keyed by
location + forecast window, with a TTL (default 1 hour, `cache_ttl_seconds`).
A run within the TTL reuses the cached forecast instead of calling Open-Meteo
again. Caching can be disabled per run (`use_cache=False`). This bounds outbound
calls and respects the provider's fair-use expectations (see §6).

> Note: the default Django cache backend is in-process/local memory. For a
> multi-process deployment, configure a shared cache (e.g. Redis) so the cache
> is effective across workers — see [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md).

## 5. Dedup & run tracking

Observations are upserted on `(latitude, longitude, timestamp, source)`, so
re-running for the same window updates rather than duplicates. Each run records
an `IngestionRun`; if Open-Meteo is unreachable or returns an invalid payload,
the run is reported as `SOURCE_UNAVAILABLE` (not a hard failure).

## 6. Provider limitations & licensing considerations

**Limitations**
- **Forecast, not observation:** Open-Meteo provides model *forecasts*. These are estimates, not measured conditions, and carry inherent uncertainty (flagged via `is_forecast=True`).
- **Model resolution:** values are interpolated to the requested coordinates from an underlying weather model grid; they are not point measurements at the berth.
- **Marine specifics:** the standard forecast API covers meteorological variables (temperature, wind, precipitation). It does **not** provide wave height, swell, or currents — those marine parameters come from INCOIS/NOAA (see [DATA_SOURCES.md](./DATA_SOURCES.md)), mapped to `MarineObservation`, not here.
- **Free-tier fair use:** the free tier is intended for non-commercial / reasonable use with rate limits; heavy or commercial use should move to Open-Meteo's paid tier or a self-hosted instance. The caching layer (§4) is the first line of defence against excessive calls.
- **Availability:** as a free service, availability is best-effort; the adapter degrades to `SOURCE_UNAVAILABLE` when the API is down.

**Licensing**
- Open-Meteo data is offered under a permissive open licence (Open-Meteo publishes its data under CC BY 4.0, with the underlying national weather-service models under their own open terms). **Attribution to Open-Meteo is required** wherever the data is displayed.
- Confirm the current terms at open-meteo.com before production use, and attribute appropriately. Content and terms may change; treat this note as guidance, not a legal determination (see [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md) NFR-CMP).
- For production, evaluate a commercial plan or self-hosting to obtain an SLA and clear commercial-use rights; the adapter's `OPEN_METEO_BASE_URL` setting supports pointing at such an endpoint.

## 7. Running it

Open-Meteo is keyless, so no credentials are needed for the prototype:

```python
from apps.ingestion.sources.open_meteo import OpenMeteoSource

OpenMeteoSource().run()   # fetches all seven ports (cached per location)
```

`requests` is an optional dependency, imported lazily — only needed for live
use; tests inject the HTTP call.

## 8. Testing

`backend/apps/ingestion/tests/test_open_meteo.py` uses mocked Open-Meteo
responses (no network): hourly expansion into observations, WMO condition
mapping, port linkage, caching (a second run makes no external call),
cache-disabled behaviour, dedup on re-ingest, missing-variable → null, and
graceful `SOURCE_UNAVAILABLE`.

## Related documents

- [DATA_SOURCES.md](./DATA_SOURCES.md)
- [DATA_INGESTION_AIS.md](./DATA_INGESTION_AIS.md)
- [ENVIRONMENT.md](./ENVIRONMENT.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
