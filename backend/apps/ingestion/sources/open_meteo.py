"""Open-Meteo weather ingestion adapter (default prototype weather provider).

Fetches hourly forecasts for the project's East Coast India ports and maps each
hourly step to a WeatherObservation. Open-Meteo is keyless on its free tier, so
there is no credential to manage; requests are made server-side.

Captured per hour: temperature (C), wind speed (kn), wind direction (deg),
precipitation (mm), weather condition (from the WMO weather code), and the
forecast timestamp.

Caching
-------
To avoid repeatedly requesting the same external forecast, each location's raw
response is cached in Django's cache for a TTL (default 1 hour). A run within
the TTL reuses the cached forecast instead of calling Open-Meteo again.

Provider limitations & licensing: see docs/DATA_INGESTION_WEATHER.md.

HTTP is isolated in `_http_get_json` and injectable for tests; `requests` is an
optional lazy import (only needed for live use). No scraping.
"""
from __future__ import annotations

import hashlib
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.catalog.models import Port
from apps.ingestion.base import BaseIngestionSource
from apps.ingestion.exceptions import SourceUnavailableError
from apps.ingestion.models import IngestionRun
from apps.operations.models import WeatherObservation

logger = logging.getLogger("vessel.ingestion.weather")

Record = dict[str, Any]

# The seven East Coast India locations, with coordinates matching the seeded
# ports (see catalog seed data). Names must match Port.name for FK linkage.
EAST_COAST_LOCATIONS = [
    ("Paradip", Decimal("20.264000"), Decimal("86.670000")),
    ("Dhamra", Decimal("20.780000"), Decimal("86.980000")),
    ("Gopalpur", Decimal("19.290000"), Decimal("84.960000")),
    ("Visakhapatnam", Decimal("17.686000"), Decimal("83.218000")),
    ("Gangavaram", Decimal("17.630000"), Decimal("83.230000")),
    ("Haldia", Decimal("22.030000"), Decimal("88.060000")),
    ("Sagar/Sandheads", Decimal("21.650000"), Decimal("88.050000")),
]

# WMO weather interpretation codes -> human-readable condition.
# https://open-meteo.com/en/docs (WMO Weather interpretation codes)
WMO_CONDITIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hour


def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class OpenMeteoSource(BaseIngestionSource):
    """Ingest hourly forecasts from Open-Meteo for the East Coast ports."""

    key = "open_meteo"
    source_kind = IngestionRun.SourceKind.REST

    timeout_seconds: float = 20.0
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
    # Open-Meteo hourly variables we request.
    hourly_vars = [
        "temperature_2m",
        "precipitation",
        "weathercode",
        "windspeed_10m",
        "winddirection_10m",
    ]

    def __init__(
        self,
        *,
        locations: Optional[list[tuple[str, Decimal, Decimal]]] = None,
        forecast_days: int = 3,
        http_get_json: Optional[Callable[[str, dict], Any]] = None,
        use_cache: bool = True,
        **context: Any,
    ):
        self.locations = locations or EAST_COAST_LOCATIONS
        self.forecast_days = forecast_days
        self._injected_http = http_get_json
        self.use_cache = use_cache
        self.base_url = settings.EXTERNAL_APIS.get(
            "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1"
        )
        self._retrieved_at = None
        self._cache_hits = 0
        super().__init__(**context)

    # ------------------------------------------------------------------
    # HTTP (injectable) + caching
    # ------------------------------------------------------------------
    def _http_get_json(self, url: str, params: dict) -> Any:
        try:
            import requests  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            from apps.ingestion.exceptions import SourceConfigError

            raise SourceConfigError(
                "The 'requests' package is required for live Open-Meteo "
                "ingestion (or inject http_get_json in tests)."
            ) from exc
        try:  # pragma: no cover - network
            resp = requests.get(url, params=params, timeout=self.timeout_seconds)
        except Exception as exc:  # pragma: no cover - network
            raise SourceUnavailableError(f"Open-Meteo unreachable: {exc}") from exc
        if resp.status_code == 429:  # pragma: no cover - network
            raise SourceUnavailableError("Open-Meteo rate limit hit (HTTP 429).")
        if resp.status_code >= 500 or resp.status_code == 404:  # pragma: no cover
            raise SourceUnavailableError(
                f"Open-Meteo returned HTTP {resp.status_code}."
            )
        resp.raise_for_status()
        return resp.json()

    def _cache_key(self, lat: Decimal, lon: Decimal) -> str:
        raw = f"{self.base_url}|{lat}|{lon}|{self.forecast_days}|{','.join(self.hourly_vars)}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return f"openmeteo:forecast:{digest}"

    def _get_forecast(self, lat: Decimal, lon: Decimal) -> dict:
        """Return the forecast payload for a location, using the cache."""
        cache_key = self._cache_key(lat, lon)
        if self.use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                logger.debug("open_meteo.cache hit lat=%s lon=%s", lat, lon)
                return cached

        url = f"{self.base_url.rstrip('/')}/forecast"
        params = {
            "latitude": str(lat),
            "longitude": str(lon),
            "hourly": ",".join(self.hourly_vars),
            "windspeed_unit": "kn",  # ask Open-Meteo for knots directly
            "timezone": "UTC",
            "forecast_days": self.forecast_days,
        }
        getter = self._injected_http or self._http_get_json
        payload = getter(url, params)
        if not isinstance(payload, dict) or "hourly" not in payload:
            raise SourceUnavailableError(
                "Open-Meteo response missing 'hourly' block (unavailable or invalid)."
            )
        if self.use_cache:
            cache.set(cache_key, payload, self.cache_ttl_seconds)
        return payload

    # ------------------------------------------------------------------
    # Framework hooks
    # ------------------------------------------------------------------
    def fetch(self) -> Iterable[Record]:
        self._retrieved_at = timezone.now()
        records: list[Record] = []
        for name, lat, lon in self.locations:
            payload = self._get_forecast(lat, lon)
            records.extend(self._expand_hourly(name, lat, lon, payload))
        return records

    def _expand_hourly(
        self, name: str, lat: Decimal, lon: Decimal, payload: dict
    ) -> list[Record]:
        """Flatten Open-Meteo's parallel hourly arrays into per-hour records.

        Reads ONLY the arrays we requested; a variable absent from the response
        yields None for that field (never fabricated).
        """
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        precip = hourly.get("precipitation") or []
        codes = hourly.get("weathercode") or []
        wspd = hourly.get("windspeed_10m") or []
        wdir = hourly.get("winddirection_10m") or []

        def at(arr: list, i: int):
            return arr[i] if i < len(arr) else None

        out: list[Record] = []
        for i, t in enumerate(times):
            out.append(
                {
                    "location_name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "timestamp": t,
                    "temperature_c": at(temps, i),
                    "precipitation_mm": at(precip, i),
                    "weather_code": at(codes, i),
                    "wind_speed_kn": at(wspd, i),
                    "wind_dir_deg": at(wdir, i),
                }
            )
        return out

    def persist(self, records: list[Record]) -> tuple[int, int]:
        written = duplicate = 0
        # Resolve ports once by name.
        port_by_name = {
            p.name: p
            for p in Port.objects.filter(
                name__in=[loc[0] for loc in self.locations]
            )
        }
        for rec in records:
            ts = parse_datetime(str(rec["timestamp"]))
            if ts is None:
                continue
            if timezone.is_naive(ts):
                from datetime import timezone as dt_timezone

                ts = timezone.make_aware(ts, dt_timezone.utc)

            code = rec.get("weather_code")
            code_int = int(code) if code is not None else None
            condition = WMO_CONDITIONS.get(code_int, "") if code_int is not None else ""

            _, created = WeatherObservation.objects.update_or_create(
                latitude=rec["latitude"],
                longitude=rec["longitude"],
                timestamp=ts,
                source=self.key,
                defaults={
                    "port": port_by_name.get(rec["location_name"]),
                    "temperature_c": _dec(rec.get("temperature_c")),
                    "precipitation_mm": _dec(rec.get("precipitation_mm")),
                    "wind_speed_kn": _dec(rec.get("wind_speed_kn")),
                    "wind_dir_deg": _dec(rec.get("wind_dir_deg")),
                    "weather_code": code_int,
                    "weather_condition": condition,
                    "is_forecast": True,
                    # JSON-safe raw record (Decimals -> str for coordinates).
                    "raw": {
                        "location_name": rec["location_name"],
                        "latitude": str(rec["latitude"]),
                        "longitude": str(rec["longitude"]),
                        "timestamp": rec["timestamp"],
                        "temperature_c": rec.get("temperature_c"),
                        "precipitation_mm": rec.get("precipitation_mm"),
                        "weather_code": rec.get("weather_code"),
                        "wind_speed_kn": rec.get("wind_speed_kn"),
                        "wind_dir_deg": rec.get("wind_dir_deg"),
                    },
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate
