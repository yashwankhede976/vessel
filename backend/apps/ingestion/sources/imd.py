"""IMD (India Meteorological Department) ingestion adapter.

IMD publishes marine and cyclone products (port warnings, sea-area and coastal
bulletins, cyclone tracks and wind warnings). IMD does not expose a single
stable, uniformly-documented public JSON API; products are offered in varying
forms and their endpoints/shapes change. This adapter is therefore:

- **Config-driven** — each ingestion is configured with a product URL, a product
  type, and an explicit field_map (canonical -> source key). It reads ONLY the
  declared fields and never invents data a product does not provide.
- **Defensive** — missing fields become null; a missing/unreachable product is
  reported as SOURCE_UNAVAILABLE (not a hard failure).
- **Format-flexible** — the JSON payload can be a list of records or an object
  with a records key (configurable). HTTP is injectable for tests.

Normalization targets:
- Port warning / sea-area bulletin / coastal bulletin -> MarineObservation
- Cyclone track / cyclone wind warning              -> CycloneObservation

No scraping (documented product URLs / injected payloads only). No risk scoring.

Reference: IMD (mausam.imd.gov.in) marine & cyclone products; endpoints/shapes
are provider-specific and must be confirmed at integration (see DATA_SOURCES.md).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.catalog.models import Port
from apps.ingestion.base import BaseIngestionSource
from apps.ingestion.exceptions import SourceConfigError, SourceUnavailableError
from apps.ingestion.models import IngestionRun
from apps.operations.models import (
    CycloneObservation,
    MarineObservation,
    MarineWarningType,
    WarningSeverity,
)

logger = logging.getLogger("vessel.ingestion.imd")

Record = dict[str, Any]

# Product types this adapter understands.
PRODUCT_PORT_WARNING = "port_warning"
PRODUCT_SEA_AREA_BULLETIN = "sea_area_bulletin"
PRODUCT_COASTAL_BULLETIN = "coastal_bulletin"
PRODUCT_CYCLONE_TRACK = "cyclone_track"
PRODUCT_CYCLONE_WIND_WARNING = "cyclone_wind_warning"

MARINE_PRODUCTS = {
    PRODUCT_PORT_WARNING: MarineWarningType.PORT_WARNING,
    PRODUCT_SEA_AREA_BULLETIN: MarineWarningType.SEA_AREA_BULLETIN,
    PRODUCT_COASTAL_BULLETIN: MarineWarningType.COASTAL_BULLETIN,
}
CYCLONE_PRODUCTS = {
    PRODUCT_CYCLONE_TRACK: CycloneObservation.BulletinKind.TRACK,
    PRODUCT_CYCLONE_WIND_WARNING: CycloneObservation.BulletinKind.WIND_WARNING,
}

# Free-text severity -> normalized level. Unknown text -> UNKNOWN (not guessed).
SEVERITY_MAP = {
    "": WarningSeverity.NONE,
    "none": WarningSeverity.NONE,
    "no warning": WarningSeverity.NONE,
    "low": WarningSeverity.LOW,
    "yellow": WarningSeverity.LOW,
    "moderate": WarningSeverity.MODERATE,
    "orange": WarningSeverity.MODERATE,
    "high": WarningSeverity.HIGH,
    "red": WarningSeverity.SEVERE,
    "severe": WarningSeverity.SEVERE,
}

# IMD cyclone category text -> CycloneObservation.Category.
CYCLONE_CATEGORY_MAP = {
    "low": CycloneObservation.Category.LOW,
    "depression": CycloneObservation.Category.DEPRESSION,
    "deep depression": CycloneObservation.Category.DEPRESSION,
    "cyclonic storm": CycloneObservation.Category.CYCLONIC_STORM,
    "severe cyclonic storm": CycloneObservation.Category.SEVERE,
    "very severe cyclonic storm": CycloneObservation.Category.VERY_SEVERE,
    "super cyclonic storm": CycloneObservation.Category.SUPER,
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
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        from datetime import timezone as _tz

        dt = timezone.make_aware(dt, _tz.utc)
    return dt


def _severity(value: Any) -> str:
    return SEVERITY_MAP.get(str(value or "").strip().lower(), WarningSeverity.UNKNOWN)


@dataclass
class IMDProductConfig:
    """Config for one IMD product ingestion.

    field_map maps canonical fields to source keys. Canonical fields per target:

    Marine (port_warning / sea_area_bulletin / coastal_bulletin):
      issue_time, valid_from, valid_to, area_name, port_name (opt),
      latitude (opt), longitude (opt), severity (opt), headline (opt),
      significant_wave_height_m (opt)

    Cyclone (cyclone_track / cyclone_wind_warning):
      system_name, advisory_no (opt), timestamp, issue_time (opt),
      valid_from (opt), valid_to (opt), latitude (opt), longitude (opt),
      category (opt), max_wind_kn (opt), gust_kn (opt),
      central_pressure_hpa (opt), severity (opt)
    """

    product: str
    url: str
    field_map: dict[str, str]
    # Where the records live in the payload: "" means the payload IS the list;
    # otherwise a key into a dict payload (e.g. "bulletins", "features").
    records_key: str = ""
    source_ref: str = ""

    def __post_init__(self):
        valid = set(MARINE_PRODUCTS) | set(CYCLONE_PRODUCTS)
        if self.product not in valid:
            raise SourceConfigError(f"Unknown IMD product '{self.product}'.")
        if not self.field_map:
            raise SourceConfigError("IMDProductConfig requires a non-empty field_map.")


class IMDSource(BaseIngestionSource):
    """Config-driven IMD product adapter."""

    key = "imd"
    source_kind = IngestionRun.SourceKind.REST
    timeout_seconds: float = 20.0

    def __init__(
        self,
        config: IMDProductConfig,
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
                "The 'requests' package is required for live IMD ingestion "
                "(or inject http_get_json in tests)."
            ) from exc
        try:  # pragma: no cover - network
            resp = requests.get(url, timeout=self.timeout_seconds)
        except Exception as exc:  # pragma: no cover - network
            raise SourceUnavailableError(f"IMD product unreachable: {exc}") from exc
        if resp.status_code == 404 or resp.status_code >= 500:  # pragma: no cover
            raise SourceUnavailableError(
                f"IMD product returned HTTP {resp.status_code}."
            )
        resp.raise_for_status()
        return resp.json()

    def fetch(self) -> Iterable[Record]:
        if not self.config.url:
            raise SourceConfigError("IMD product config has no url.")
        self._retrieved_at = timezone.now()
        getter = self._injected_http or self._http_get_json
        payload = getter(self.config.url)

        if self.config.records_key:
            # Records live under a key in a dict payload.
            if not isinstance(payload, dict):
                raise SourceUnavailableError(
                    "IMD payload is not an object; cannot read records_key."
                )
            records = payload.get(self.config.records_key)
            if isinstance(records, dict):
                records = [records]  # single record under the key
        else:
            # No records_key: the payload itself must be the list of records.
            # A dict here is ambiguous (could be an error envelope), so we do
            # NOT silently ingest it — report unavailable instead.
            records = payload

        if records is None:
            raise SourceUnavailableError(
                "IMD product returned no records (unavailable or empty)."
            )
        if not isinstance(records, list):
            raise SourceUnavailableError(
                "IMD product records are not a list (payload may be an error "
                "envelope or the records_key is misconfigured)."
            )

        # Map only declared fields; drop undeclared, missing -> None.
        return [self._map(r) for r in records]

    def _map(self, raw: Record) -> Record:
        out: Record = {"_raw": raw}
        for canonical, source_key in self.config.field_map.items():
            out[canonical] = raw.get(source_key)
        return out

    def persist(self, records: list[Record]) -> tuple[int, int]:
        if self.config.product in MARINE_PRODUCTS:
            return self._persist_marine(records)
        return self._persist_cyclone(records)

    # --- marine warnings / bulletins ---
    def _persist_marine(self, records: list[Record]) -> tuple[int, int]:
        warning_type = MARINE_PRODUCTS[self.config.product]
        written = duplicate = 0
        for rec in records:
            issue_time = _dt(rec.get("issue_time"))
            # timestamp anchors the row; use issue_time, else valid_from, else now.
            ts = issue_time or _dt(rec.get("valid_from")) or timezone.now()
            port = self._resolve_port(rec.get("port_name"))
            area = str(rec.get("area_name") or "").strip()

            # Need at least an area or a port to be meaningful; else skip.
            if not area and port is None:
                logger.debug("imd.marine skip: no area or port in record")
                continue

            _, created = MarineObservation.objects.update_or_create(
                source=self.key,
                warning_type=warning_type,
                area_name=area,
                port=port,
                timestamp=ts,
                defaults={
                    "latitude": _dec(rec.get("latitude")),
                    "longitude": _dec(rec.get("longitude")),
                    "severity": _severity(rec.get("severity")),
                    "headline": str(rec.get("headline") or "")[:500],
                    "issue_time": issue_time,
                    "valid_from": _dt(rec.get("valid_from")),
                    "valid_to": _dt(rec.get("valid_to")),
                    "significant_wave_height_m": _dec(
                        rec.get("significant_wave_height_m")
                    ),
                    "is_forecast": True,
                    "source_ref": self.config.source_ref or self.config.url,
                    "raw": rec.get("_raw") or {},
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate

    # --- cyclone track / wind warning ---
    def _persist_cyclone(self, records: list[Record]) -> tuple[int, int]:
        kind = CYCLONE_PRODUCTS[self.config.product]
        written = duplicate = 0
        for rec in records:
            system_name = str(rec.get("system_name") or "").strip()
            ts = _dt(rec.get("timestamp")) or _dt(rec.get("issue_time"))
            if not system_name or ts is None:
                logger.debug("imd.cyclone skip: missing system_name or timestamp")
                continue

            category = CYCLONE_CATEGORY_MAP.get(
                str(rec.get("category") or "").strip().lower(),
                CycloneObservation.Category.LOW,
            )
            _, created = CycloneObservation.objects.update_or_create(
                system_name=system_name,
                timestamp=ts,
                bulletin_kind=kind,
                source=self.key,
                defaults={
                    "advisory_no": str(rec.get("advisory_no") or "")[:32],
                    "latitude": _dec(rec.get("latitude")),
                    "longitude": _dec(rec.get("longitude")),
                    "category": category,
                    "max_wind_kn": _dec(rec.get("max_wind_kn")),
                    "gust_kn": _dec(rec.get("gust_kn")),
                    "central_pressure_hpa": _dec(rec.get("central_pressure_hpa")),
                    "severity": _severity(rec.get("severity")),
                    "issue_time": _dt(rec.get("issue_time")),
                    "valid_from": _dt(rec.get("valid_from")),
                    "valid_to": _dt(rec.get("valid_to")),
                    "is_forecast": kind == CycloneObservation.BulletinKind.TRACK,
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
