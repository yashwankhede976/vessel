"""World Bank indicators ingestion adapter.

Ingests time-series indicator values from the **public, keyless** World Bank
Indicators API v2 and stores them as CommodityPriceObservation rows (with full
provenance). The World Bank publishes energy/commodity-relevant indicators (for
example energy or fuel price indices) at country/global scope; the exact
indicator is configurable so this adapter is not tied to one series.

Data provenance
---------------
World Bank indicator values are REAL published statistics (annual, often lagged).
They are stored as-is with `source="world_bank"`, `source_url`, `source_date`
and `retrieved_at`. Nothing is fabricated — a year with no reported value is
skipped, not interpolated.

Credentials
-----------
NONE. The World Bank Indicators API is open and requires no key. This adapter is
therefore always "configured".

Reference: World Bank Indicators API v2 (api.worldbank.org/v2), JSON format.
HTTP is injectable for tests; no scraping.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

from django.utils import timezone

from apps.catalog.models import Commodity
from apps.ingestion.base import BaseIngestionSource
from apps.ingestion.exceptions import SourceConfigError, SourceUnavailableError
from apps.ingestion.models import IngestionRun
from apps.operations.models import CommodityPriceObservation

logger = logging.getLogger("vessel.ingestion.world_bank")

Record = dict[str, Any]

WORLD_BANK_BASE_URL = "https://api.worldbank.org/v2"


def _dec(value: Any) -> Optional[Decimal]:
    if value in (None, "", "NULL"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class WorldBankSource(BaseIngestionSource):
    """Adapter for the World Bank Indicators API (keyless).

    Fetches one indicator for one country (default: world aggregate) and stores
    each yearly value as a CommodityPriceObservation for the configured
    commodity. The indicator, country and commodity are all configurable.
    """

    key = "world_bank"
    source_kind = IngestionRun.SourceKind.REST

    base_url = WORLD_BANK_BASE_URL
    timeout_seconds: float = 30.0
    max_attempts = 3
    backoff_seconds = 1.0

    def __init__(
        self,
        *,
        indicator: str = "EG.USE.PCAP.KG.OE",  # energy use per capita (demo default)
        country: str = "WLD",                   # world aggregate
        commodity_name: str = "Thermal Coal",
        commodity_category: Optional[str] = None,
        unit: str = "index",
        per_page: int = 100,
        date_range: Optional[str] = None,       # e.g. "2015:2024"
        http_get: Optional[Callable[[str, dict], Any]] = None,
        **context: Any,
    ):
        self.indicator = indicator
        self.country = country
        self.commodity_name = commodity_name
        self.commodity_category = commodity_category or Commodity.Category.COAL_THERMAL
        self.unit = unit
        self.per_page = per_page
        self.date_range = date_range
        self._injected_http = http_get
        self._retrieved_at = None
        super().__init__(**context)

    # ------------------------------------------------------------------
    def _query_params(self) -> dict:
        params = {"format": "json", "per_page": str(self.per_page)}
        if self.date_range:
            params["date"] = self.date_range
        return params

    def _url(self) -> str:
        return f"{self.base_url}/country/{self.country}/indicator/{self.indicator}"

    def _http_get(self, url: str, params: dict) -> tuple[int, Any]:
        try:
            import requests  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SourceConfigError(
                "The 'requests' package is required for live World Bank ingestion "
                "(or inject http_get in tests)."
            ) from exc
        try:  # pragma: no cover - network
            resp = requests.get(url, params=params, timeout=self.timeout_seconds)
            return resp.status_code, (resp.json() if resp.content else None)
        except Exception as exc:  # pragma: no cover - network
            raise SourceUnavailableError(f"World Bank unreachable: {exc}") from exc

    # ------------------------------------------------------------------
    def fetch(self) -> Iterable[Record]:
        self._retrieved_at = timezone.now()
        getter = self._injected_http or self._http_get
        status, body = getter(self._url(), self._query_params())

        if status == 429:
            raise SourceUnavailableError("World Bank rate limit hit (HTTP 429).")
        if status >= 500:
            raise SourceUnavailableError(f"World Bank returned HTTP {status}.")
        if status != 200:
            raise SourceUnavailableError(f"World Bank unexpected HTTP {status}.")

        # The v2 JSON response is a 2-element array: [metadata, [records...]].
        if not isinstance(body, list) or len(body) < 2:
            # A World Bank error is returned as [{"message": [...]}].
            raise SourceUnavailableError(
                "World Bank response was not in the expected [meta, data] shape "
                "(invalid indicator/country, or temporary unavailability)."
            )
        data = body[1]
        if not isinstance(data, list):
            raise SourceUnavailableError("World Bank response had no data array.")
        return data

    def persist(self, records: list[Record]) -> tuple[int, int]:
        written = duplicate = 0
        commodity = self._commodity()
        source_url = self._url()
        source_date = timezone.now().date()

        for raw in records:
            mapped = self._map(raw)
            if mapped is None:
                continue  # missing value/year — skipped, never interpolated
            _, created = CommodityPriceObservation.objects.update_or_create(
                commodity=commodity,
                observed_on=mapped["observed_on"],
                source=self.key,
                defaults={
                    "price": mapped["price"],
                    "currency": "USD",
                    "unit": self.unit,
                    "source_url": source_url,
                    "source_date": source_date,
                    "retrieved_at": self._retrieved_at,
                    # World Bank indicator values are real published statistics,
                    # not our estimates.
                    "is_estimated": False,
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate

    # ------------------------------------------------------------------
    def _map(self, raw: Record) -> Optional[dict]:
        value = _dec(raw.get("value"))
        year = raw.get("date")
        if value is None or not year:
            return None
        try:
            observed_on = date(int(str(year)[:4]), 1, 1)
        except (ValueError, TypeError):
            return None
        return {"observed_on": observed_on, "price": value}

    def _commodity(self) -> Commodity:
        commodity, _ = Commodity.objects.get_or_create(
            name=self.commodity_name,
            defaults={"category": self.commodity_category},
        )
        return commodity
