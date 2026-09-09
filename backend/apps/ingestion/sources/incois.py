"""INCOIS (Indian National Centre for Ocean Information Services) adapter.

INCOIS publishes ocean-state information for Indian waters — significant wave
height, wave period, swell, surface currents, sea-surface temperature — and
high-wave / swell-surge bulletins. Like IMD, INCOIS does not expose one stable,
uniformly-documented public JSON API for all products, so this adapter is:

- **Config-driven** — each ingestion supplies a product URL and an explicit
  field_map (canonical -> source key). Only declared fields are read; nothing a
  product does not provide is invented.
- **Defensive** — missing fields become null; a missing/unreachable product is
  reported as SOURCE_UNAVAILABLE, never a hard crash.
- **Keyless by default** — INCOIS ocean-state products are publicly served; no
  API key is required. HTTP is injectable for tests.

Normalization target: MarineObservation with warning_type = OBSERVATION
(ocean-state) or a bulletin type, mapped to the supported East Coast ports where
a port/area is given. It writes the ocean-state fields (wave/swell/current/SST)
that the congestion & risk layers can consume.

Reference: INCOIS (incois.gov.in) ocean-state/forecast products; endpoints and
shapes are provider-specific and must be confirmed at integration
(see docs/DATA_SOURCES.md). No scraping — documented product URLs / injected
payloads only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone as _tz
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.catalog.models import Port
from apps.ingestion.base import BaseIngestionSource
from apps.ingestion.exceptions import SourceConfigError, SourceUnavailableError
from apps.ingestion.models import IngestionRun
from apps.operations.models import (
    MarineObservation,
    MarineWarningType,
    WarningSeverity,
)

logger = logging.getLogger("vessel.ingestion.incois")

Record = dict[str, Any]

# Product types this adapter understands (all map to MarineObservation).
PRODUCT_OCEAN_STATE = "ocean_state"        # wave/swell/current/SST observation
PRODUCT_HIGH_WAVE_ALERT = "high_wave_alert"  # high-wave / swell-surge bulletin

PRODUCT_WARNING_TYPE = {
    PRODUCT_OCEAN_STATE: MarineWarningType.OBSERVATION,
    PRODUCT_HIGH_WAVE_ALERT: MarineWarningType.SEA_AREA_BULLETIN,
}

# Free-text severity -> normalized level. Unknown text -> UNKNOWN (not guessed).
SEVERITY_MAP = {
    "": WarningSeverity.NONE,
    "none": WarningSeverity.NONE,
    "no warning": WarningSeverity.NONE,
    "green": WarningSeverity.NONE,
    "low": WarningSeverity.LOW,
    "yellow": WarningSeverity.LOW,
    "moderate": WarningSeverity.MODERATE,
    "orange": WarningSeverity.MODERATE,
    "high": WarningSeverity.HIGH,
    "red": WarningSeverity.SEVERE,
    "severe": WarningSeverity.SEVERE,
}


def _dec(value: Any) -> Optional[Decimal]:
    if value in (None, "", "NA", "N/A"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    dt = value if isinstance(value, datetime) else parse_datetime(str(value))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, _tz.utc)
    return dt


def _severity(value: Any) -> str:
    return SEVERITY_MAP.get(str(value or "").strip().lower(), WarningSeverity.UNKNOWN)


@dataclass
class INCOISProductConfig:
    """Config for one INCOIS product ingestion.

    field_map maps canonical fields to source keys. Canonical fields:
      timestamp (opt), issue_time (opt), valid_from (opt), valid_to (opt),
      area_name (opt), port_name (opt), latitude (opt), longitude (opt),
      severity (opt), headline (opt),
      significant_wave_height_m (opt), wave_period_s (opt),
      swell_direction_deg (opt), current_speed_kn (opt), sea_surface_temp_c (opt)
    """

    product: str
    url: str
    field_map: dict[str, str]
    records_key: str = ""
    source_ref: str = ""

    def __post_init__(self):
        if self.product not in PRODUCT_WARNING_TYPE:
            raise SourceConfigError(f"Unknown INCOIS product '{self.product}'.")
        if not self.field_map:
            raise SourceConfigError("INCOISProductConfig requires a non-empty field_map.")


class INCOISSource(BaseIngestionSource):
    """Config-driven INCOIS ocean-state / high-wave product adapter (keyless)."""

    key = "incois"
    source_kind = IngestionRun.SourceKind.REST
    timeout_seconds: float = 20.0

    def __init__(
        self,
        config: INCOISProductConfig,
        *,
        http_get_json: Optional[Callable[[str], Any]] = None,
        **context: Any,
    ):
        self.config = config
        self._injected_http = http_get_json
        self._retrieved_at = None
        super().__init__(**context)

    # --- HTTP (injectable) ---
    def _http_get_json(self, url: str) -> Any:
        try:
            import requests  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SourceConfigError(
                "The 'requests' package is required for live INCOIS ingestion "
                "(or inject http_get_json in tests)."
            ) from exc
        try:  # pragma: no cover - network
            resp = requests.get(url, timeout=self.timeout_seconds)
        except Exception as exc:  # pragma: no cover - network
            raise SourceUnavailableError(f"INCOIS product unreachable: {exc}") from exc
        if resp.status_code == 404 or resp.status_code >= 500:  # pragma: no cover
            raise SourceUnavailableError(
                f"INCOIS product returned HTTP {resp.status_code}."
            )
        resp.raise_for_status()
        return resp.json()

    def fetch(self) -> Iterable[Record]:
        if not self.config.url:
            raise SourceConfigError("INCOIS product config has no url.")
        self._retrieved_at = timezone.now()
        getter = self._injected_http or self._http_get_json
        payload = getter(self.config.url)

        if self.config.records_key:
            if not isinstance(payload, dict):
                raise SourceUnavailableError(
                    "INCOIS payload is not an object; cannot read records_key."
                )
            records = payload.get(self.config.records_key)
            if isinstance(records, dict):
                records = [records]
        else:
            records = payload

        if records is None:
            raise SourceUnavailableError(
                "INCOIS product returned no records (unavailable or empty)."
            )
        if not isinstance(records, list):
            raise SourceUnavailableError(
                "INCOIS product records are not a list (payload may be an error "
                "envelope or records_key is misconfigured)."
            )
        return [self._map(r) for r in records]

    def _map(self, raw: Record) -> Record:
        out: Record = {"_raw": raw}
        for canonical, source_key in self.config.field_map.items():
            out[canonical] = raw.get(source_key)
        return out

    def persist(self, records: list[Record]) -> tuple[int, int]:
        warning_type = PRODUCT_WARNING_TYPE[self.config.product]
        written = duplicate = 0
        for rec in records:
            issue_time = _dt(rec.get("issue_time"))
            ts = _dt(rec.get("timestamp")) or issue_time or _dt(rec.get("valid_from")) \
                or timezone.now()
            port = self._resolve_port(rec.get("port_name"))
            area = str(rec.get("area_name") or "").strip()

            # Need at least a port, an area, or a coordinate to be meaningful.
            lat = _dec(rec.get("latitude"))
            lon = _dec(rec.get("longitude"))
            if not area and port is None and lat is None and lon is None:
                logger.debug("incois skip: no area/port/coordinate in record")
                continue

            _, created = MarineObservation.objects.update_or_create(
                source=self.key,
                warning_type=warning_type,
                area_name=area,
                port=port,
                timestamp=ts,
                defaults={
                    "latitude": lat,
                    "longitude": lon,
                    "severity": _severity(rec.get("severity")),
                    "headline": str(rec.get("headline") or "")[:500],
                    "issue_time": issue_time,
                    "valid_from": _dt(rec.get("valid_from")),
                    "valid_to": _dt(rec.get("valid_to")),
                    "significant_wave_height_m": _dec(rec.get("significant_wave_height_m")),
                    "wave_period_s": _dec(rec.get("wave_period_s")),
                    "swell_direction_deg": _dec(rec.get("swell_direction_deg")),
                    "current_speed_kn": _dec(rec.get("current_speed_kn")),
                    "sea_surface_temp_c": _dec(rec.get("sea_surface_temp_c")),
                    "is_forecast": self.config.product == PRODUCT_OCEAN_STATE,
                    "source_ref": self.config.source_ref or self.config.url,
                    "raw": rec.get("_raw") or {},
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate

    def _resolve_port(self, name: Optional[str]) -> Optional[Port]:
        if not name:
            return None
        return Port.objects.filter(name__iexact=str(name).strip()).first()
