"""Ingestion adapters for public Indian open datasets.

Covers two providers:
- data.gov.in — the Open Government Data platform (REST resource API with an
  API key, and downloadable CSV/XLSX resources).
- Ministry of Coal — published statistics offered as downloadable files.

Design principles (important):
- **No assumed schema.** data.gov.in datasets are heterogeneous; there is no
  single fixed set of columns. Each adapter instance is configured with an
  explicit `field_map` (canonical_field -> source_column). The adapter reads
  ONLY the declared columns and never invents a field a dataset does not
  provide. A declared column that is missing from a given row leaves that
  canonical field null.
- **Graceful unavailability.** If the endpoint/file is unreachable or returns
  an error/404, the adapter raises SourceUnavailableError, which the runner
  records as SOURCE_UNAVAILABLE (not a hard failure).
- **No scraping.** Only the documented REST resource API and direct file
  downloads/paths are used — never HTML parsing.
- **Provenance.** Every persisted row records source, source_url, source_date,
  and retrieved_at.

Target models: PortTraffic, TradeObservation, CommodityPriceObservation
(apps.operations). Which target a config writes to is set by `target`.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field as dc_field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.catalog.models import Commodity, Port
from apps.ingestion.base import BaseIngestionSource
from apps.ingestion.exceptions import (
    SourceConfigError,
    SourceUnavailableError,
)
from apps.ingestion.models import IngestionRun
from apps.operations.models import (
    CommodityPriceObservation,
    PortTraffic,
    TradeObservation,
)

logger = logging.getLogger("vessel.ingestion.india")

Record = dict[str, Any]

# Canonical targets this module can write to.
TARGET_PORT_TRAFFIC = "port_traffic"
TARGET_TRADE = "trade_observation"
TARGET_COMMODITY_PRICE = "commodity_price"


@dataclass
class DatasetConfig:
    """Declarative configuration for one dataset ingestion.

    field_map maps canonical field names to the EXACT source column/key names.
    Only these columns are read. Canonical fields understood per target:

      port_traffic:     period, port_name, commodity_name (opt), direction (opt),
                        throughput_tonnes (opt), vessel_count (opt)
      trade_observation: period, commodity_name, reporter_country (opt),
                        partner_country (opt), quantity_tonnes (opt),
                        trade_value (opt), currency (opt)
      commodity_price:  observed_on, commodity_name, price, currency (opt),
                        unit (opt)
    """

    target: str
    field_map: dict[str, str]
    source: str
    source_url: str
    source_date: Optional[str] = None  # ISO date the dataset was published/consulted
    # Optional constants applied to every row (e.g. a fixed commodity or currency).
    constants: dict[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self):
        valid = {TARGET_PORT_TRAFFIC, TARGET_TRADE, TARGET_COMMODITY_PRICE}
        if self.target not in valid:
            raise SourceConfigError(f"Unknown ingestion target '{self.target}'.")
        if not self.field_map:
            raise SourceConfigError("DatasetConfig requires a non-empty field_map.")


# ---------------------------------------------------------------------------
# Value coercion helpers (return None rather than guessing)
# ---------------------------------------------------------------------------
def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    d = _dec(value)
    return int(d) if d is not None else None


def _date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return parse_date(str(value).strip())


class _IndiaOpenDataBase(BaseIngestionSource):
    """Shared pipeline for config-driven Indian open-data ingestion.

    Subclasses provide the raw-record iterable via `_read_raw()`; this base maps
    each raw record through the DatasetConfig's field_map (declared fields only),
    then persists to the configured target with provenance.
    """

    def __init__(self, config: DatasetConfig, **context: Any):
        self.config = config
        self._retrieved_at = None
        # Count rows skipped in persist because they could not be resolved
        # (e.g. unknown port/commodity) — not fatal, not fabricated.
        self._skipped = 0
        super().__init__(**context)

    # --- raw source (implemented by REST/file subclasses) ---
    def _read_raw(self) -> Iterable[Record]:  # pragma: no cover - abstract-ish
        raise NotImplementedError

    def fetch(self) -> Iterable[Record]:
        self._retrieved_at = timezone.now()
        raw = list(self._read_raw())
        # Map each raw record using ONLY the declared field_map columns.
        mapped = [self._map_record(r) for r in raw]
        return mapped

    def _map_record(self, raw: Record) -> Record:
        """Project a raw record onto canonical fields declared in field_map.

        A declared source column absent from this row yields None for that
        canonical field — never a fabricated value. Undeclared columns are
        dropped.
        """
        out: Record = {}
        for canonical, source_col in self.config.field_map.items():
            out[canonical] = raw.get(source_col)
        # Apply constants (do not override an explicitly mapped, present value).
        for k, v in self.config.constants.items():
            out.setdefault(k, v)
            if out.get(k) in (None, ""):
                out[k] = v
        return out

    # --- persistence per target, with provenance ---
    def persist(self, records: list[Record]) -> tuple[int, int]:
        handler: Callable[[list[Record]], tuple[int, int]] = {
            TARGET_PORT_TRAFFIC: self._persist_port_traffic,
            TARGET_TRADE: self._persist_trade,
            TARGET_COMMODITY_PRICE: self._persist_commodity_price,
        }[self.config.target]
        return handler(records)

    def _provenance(self) -> dict:
        return {
            "source": self.config.source[:120],
            "source_url": self.config.source_url[:500],
            "source_date": _date(self.config.source_date),
            "retrieved_at": self._retrieved_at,
        }

    def _resolve_port(self, name: Optional[str]) -> Optional[Port]:
        if not name:
            return None
        return Port.objects.filter(name__iexact=str(name).strip()).first()

    def _resolve_commodity(self, name: Optional[str]) -> Optional[Commodity]:
        if not name:
            return None
        return Commodity.objects.filter(name__iexact=str(name).strip()).first()

    def _persist_port_traffic(self, records: list[Record]) -> tuple[int, int]:
        written = duplicate = 0
        prov = self._provenance()
        for rec in records:
            period = _date(rec.get("period"))
            port = self._resolve_port(rec.get("port_name"))
            if period is None or port is None:
                # Cannot key the row without a resolvable port + period. Skip it
                # rather than aborting the batch or fabricating values.
                self._skipped += 1
                logger.debug(
                    "india.port_traffic skip: unresolved port=%r period=%r",
                    rec.get("port_name"), rec.get("period"),
                )
                continue
            commodity = self._resolve_commodity(rec.get("commodity_name"))
            direction = rec.get("direction") or PortTraffic.Direction.TOTAL
            _, created = PortTraffic.objects.update_or_create(
                port=port,
                commodity=commodity,
                period=period,
                direction=direction,
                source=prov["source"],
                defaults={
                    "throughput_tonnes": _dec(rec.get("throughput_tonnes")),
                    "vessel_count": _int(rec.get("vessel_count")),
                    "source_url": prov["source_url"],
                    "source_date": prov["source_date"],
                    "retrieved_at": prov["retrieved_at"],
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate

    def _persist_trade(self, records: list[Record]) -> tuple[int, int]:
        written = duplicate = 0
        prov = self._provenance()
        for rec in records:
            period = _date(rec.get("period"))
            commodity = self._resolve_commodity(rec.get("commodity_name"))
            if period is None or commodity is None:
                self._skipped += 1
                logger.debug(
                    "india.trade skip: unresolved commodity=%r period=%r",
                    rec.get("commodity_name"), rec.get("period"),
                )
                continue
            obj, created = TradeObservation.objects.update_or_create(
                commodity=commodity,
                period=period,
                reporter_country=(rec.get("reporter_country") or ""),
                partner_country=(rec.get("partner_country") or ""),
                source=prov["source"],
                defaults={
                    "quantity_tonnes": _dec(rec.get("quantity_tonnes")),
                    "trade_value": _dec(rec.get("trade_value")),
                    "currency": (rec.get("currency") or "USD")[:3],
                    "source_url": prov["source_url"],
                    "source_date": prov["source_date"],
                    "retrieved_at": prov["retrieved_at"],
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate

    def _persist_commodity_price(self, records: list[Record]) -> tuple[int, int]:
        written = duplicate = 0
        prov = self._provenance()
        for rec in records:
            observed_on = _date(rec.get("observed_on"))
            commodity = self._resolve_commodity(rec.get("commodity_name"))
            price = _dec(rec.get("price"))
            if observed_on is None or commodity is None or price is None:
                self._skipped += 1
                logger.debug(
                    "india.commodity_price skip: unresolved commodity=%r date=%r price=%r",
                    rec.get("commodity_name"), rec.get("observed_on"), rec.get("price"),
                )
                continue
            _, created = CommodityPriceObservation.objects.update_or_create(
                commodity=commodity,
                observed_on=observed_on,
                source=prov["source"],
                defaults={
                    "price": price,
                    "currency": (rec.get("currency") or "INR")[:3],
                    "unit": (rec.get("unit") or "tonne")[:16],
                    "source_url": prov["source_url"],
                    "source_date": prov["source_date"],
                    "retrieved_at": prov["retrieved_at"],
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate


# ---------------------------------------------------------------------------
# data.gov.in — REST resource API
# ---------------------------------------------------------------------------
class DataGovInApiSource(_IndiaOpenDataBase):
    """Ingest a data.gov.in resource via its REST API.

    The resource API returns JSON with a top-level "records" array. The API key
    comes from settings/env (DATA_GOV_API_KEY); it is never hard-coded.

    HTTP is isolated in `_http_get_json` so it can be injected in tests and so
    the framework carries no hard HTTP dependency.
    """

    source_kind = IngestionRun.SourceKind.REST
    base_url = "https://api.data.gov.in/resource"

    def __init__(
        self,
        config: DatasetConfig,
        *,
        resource_id: str,
        api_key: Optional[str] = None,
        params: Optional[dict] = None,
        http_get_json: Optional[Callable[[str, dict], Any]] = None,
        **context: Any,
    ):
        self.resource_id = resource_id
        self.params = params or {}
        # Injected HTTP function for tests; None => real HTTP via requests.
        self._injected_http = http_get_json
        from django.conf import settings

        self.api_key = api_key or settings.EXTERNAL_APIS.get("DATA_GOV_API_KEY", "")
        super().__init__(config, **context)

    key = "data_gov_in"

    def _http_get_json(self, url: str, params: dict) -> Any:
        """Real HTTP GET returning parsed JSON. Uses requests if available."""
        try:
            import requests  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SourceConfigError(
                "The 'requests' package is required for live data.gov.in "
                "ingestion (or inject http_get_json in tests)."
            ) from exc
        try:  # pragma: no cover - network
            resp = requests.get(url, params=params, timeout=self.timeout_seconds)
        except Exception as exc:  # pragma: no cover - network
            raise SourceUnavailableError(
                f"data.gov.in unreachable for resource {self.resource_id}: {exc}"
            ) from exc
        if resp.status_code == 404:  # pragma: no cover - network
            raise SourceUnavailableError(
                f"data.gov.in resource {self.resource_id} not found (404)."
            )
        if resp.status_code >= 500:  # pragma: no cover - network
            raise SourceUnavailableError(
                f"data.gov.in server error {resp.status_code} for {self.resource_id}."
            )
        resp.raise_for_status()
        return resp.json()

    timeout_seconds: float = 20.0

    def _read_raw(self) -> Iterable[Record]:
        if not self.resource_id:
            raise SourceConfigError("data.gov.in source needs a resource_id.")
        if not self.api_key:
            raise SourceConfigError(
                "DATA_GOV_API_KEY is not set; cannot query the data.gov.in API."
            )
        url = f"{self.base_url}/{self.resource_id}"
        params = {"api-key": self.api_key, "format": "json", **self.params}
        getter = self._injected_http or self._http_get_json
        payload = getter(url, params)
        if not isinstance(payload, dict):
            raise SourceUnavailableError("data.gov.in returned an unexpected payload.")
        records = payload.get("records")
        if records is None:
            # Some resources signal errors in the body rather than HTTP status.
            raise SourceUnavailableError(
                "data.gov.in response contained no 'records' (resource may be "
                "unavailable or the query invalid)."
            )
        return records


# ---------------------------------------------------------------------------
# Downloadable CSV — data.gov.in resource downloads and Ministry of Coal files
# ---------------------------------------------------------------------------
class CsvDownloadSource(_IndiaOpenDataBase):
    """Ingest a downloadable CSV (a local path or an in-memory injected text).

    Supports two inputs, in priority order:
      1. `csv_text` — CSV content injected directly (used in tests / when the
         caller already downloaded the file).
      2. `path` — a local filesystem path to a CSV file.

    A remote URL download is intentionally left to a caller-provided
    `download()` (or `csv_text`) so this class needs no HTTP dependency and does
    no scraping. If the file/path is missing, raises SourceUnavailableError.
    """

    source_kind = IngestionRun.SourceKind.FILE
    key = "india_csv_download"

    def __init__(
        self,
        config: DatasetConfig,
        *,
        path: Optional[str] = None,
        csv_text: Optional[str] = None,
        **context: Any,
    ):
        self.path = path
        self.csv_text = csv_text
        super().__init__(config, **context)

    def _read_raw(self) -> Iterable[Record]:
        if self.csv_text is None and not self.path:
            raise SourceConfigError("CsvDownloadSource needs csv_text or path.")

        if self.csv_text is not None:
            text = self.csv_text
        else:
            try:
                with open(self.path, "r", encoding="utf-8-sig", newline="") as fh:
                    text = fh.read()
            except FileNotFoundError as exc:
                raise SourceUnavailableError(
                    f"Download file not found: {self.path}"
                ) from exc
            except OSError as exc:
                raise SourceUnavailableError(
                    f"Could not read download file {self.path}: {exc}"
                ) from exc

        reader = csv.DictReader(io.StringIO(text))
        return list(reader)


class MinistryOfCoalSource(CsvDownloadSource):
    """Ministry of Coal published statistics (downloadable file mode).

    The Ministry of Coal publishes statistics as downloadable documents rather
    than a stable machine API; this adapter ingests a downloaded CSV export
    using an explicit field_map (no assumed schema, no scraping).
    """

    key = "ministry_of_coal"
