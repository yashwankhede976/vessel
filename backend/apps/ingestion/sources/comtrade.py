"""UN Comtrade ingestion adapter.

Ingests international merchandise trade statistics from the official UN Comtrade
API, focused initially on **coal imports into India** from the project origin
countries. Maps each Comtrade record to a TradeObservation, storing both the
raw provider record and the normalized fields.

Scope defaults
--------------
- Reporter: India (imports reported by India).
- Partners: Australia, Indonesia, Mozambique, USA, Russia.
- Commodities: coal HS codes (2701 coal, 2702 lignite, 2704 coke).
- Flow: imports (M = import).

Credentials
-----------
The subscription key is read ONLY from settings.EXTERNAL_APIS["COMTRADE_API_KEY"]
(env COMTRADE_API_KEY) and sent as the `subscription-key` query parameter. It is
never hard-coded and never exposed to the frontend.

Rate limits
-----------
The Comtrade free tier is limited (roughly a few hundred calls/day). HTTP 429
(and 5xx) responses are retried with exponential backoff a few times; if the
limit is still hit, the run is reported as SOURCE_UNAVAILABLE rather than a hard
failure, so a desk can distinguish "quota exhausted" from "adapter broken".

Reference: UN Comtrade Plus API (comtradeapi.un.org), consulted 2026-09-08.
No scraping — the documented REST API only. HTTP is injectable for tests.
"""
from __future__ import annotations

import logging
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Commodity, Origin
from apps.ingestion.base import BaseIngestionSource
from apps.ingestion.exceptions import SourceConfigError, SourceUnavailableError
from apps.ingestion.models import IngestionRun
from apps.operations.models import TradeObservation

logger = logging.getLogger("vessel.ingestion.comtrade")

Record = dict[str, Any]

COMTRADE_BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

# M49 country codes used by Comtrade.
INDIA_M49 = "699"
ORIGIN_M49 = {
    "Australia": "36",
    "Indonesia": "360",
    "Mozambique": "508",
    "USA": "842",
    "Russia": "643",
}
M49_TO_NAME = {code: name for name, code in ORIGIN_M49.items()}
M49_TO_NAME[INDIA_M49] = "India"

# Coal-related HS codes.
COAL_HS_CODES = ["2701", "2702", "2704"]

# Comtrade flow codes -> our Flow choices.
FLOW_MAP = {
    "M": TradeObservation.Flow.IMPORT,
    "X": TradeObservation.Flow.EXPORT,
    "RM": TradeObservation.Flow.RE_IMPORT,
    "RX": TradeObservation.Flow.RE_EXPORT,
}


def _dec(value: Any) -> Optional[Decimal]:
    if value in (None, "", "NULL"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _period_to_date(period: Any) -> Optional[date]:
    """Comtrade period is 'YYYY' (annual) or 'YYYYMM' (monthly)."""
    s = str(period).strip()
    try:
        if len(s) == 4:
            return date(int(s), 1, 1)
        if len(s) == 6:
            return date(int(s[:4]), int(s[4:6]), 1)
    except (ValueError, TypeError):
        return None
    return None


class ComtradeSource(BaseIngestionSource):
    """Adapter for the UN Comtrade API (coal imports into India by default)."""

    key = "un_comtrade"
    source_kind = IngestionRun.SourceKind.REST

    base_url = COMTRADE_BASE_URL
    timeout_seconds: float = 30.0

    # Rate-limit retry policy.
    max_attempts = 4
    backoff_seconds = 1.0

    def __init__(
        self,
        *,
        reporter_m49: str = INDIA_M49,
        partner_m49: Optional[list[str]] = None,
        hs_codes: Optional[list[str]] = None,
        period: str = "2024",
        flow_code: str = "M",
        api_key: Optional[str] = None,
        http_get: Optional[Callable[[str, dict], Any]] = None,
        **context: Any,
    ):
        self.reporter_m49 = reporter_m49
        self.partner_m49 = partner_m49 or list(ORIGIN_M49.values())
        self.hs_codes = hs_codes or COAL_HS_CODES
        self.period = period
        self.flow_code = flow_code
        self.api_key = api_key or settings.EXTERNAL_APIS.get("COMTRADE_API_KEY", "")
        # Injected HTTP for tests: (url, params) -> (status_code, json).
        self._injected_http = http_get
        self._retrieved_at = None
        super().__init__(**context)

    # ------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------
    def _query_params(self) -> dict:
        return {
            "reporterCode": self.reporter_m49,
            "partnerCode": ",".join(self.partner_m49),
            "period": self.period,
            "cmdCode": ",".join(self.hs_codes),
            "flowCode": self.flow_code,
            "subscription-key": self.api_key,
        }

    def _source_url(self) -> str:
        # For provenance: the base endpoint (key omitted).
        return f"{self.base_url}?reporterCode={self.reporter_m49}&period={self.period}"

    # ------------------------------------------------------------------
    # HTTP (isolated, injectable). Returns (status_code, json_body).
    # ------------------------------------------------------------------
    def _http_get(self, url: str, params: dict) -> tuple[int, Any]:
        try:
            import requests  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SourceConfigError(
                "The 'requests' package is required for live Comtrade ingestion "
                "(or inject http_get in tests)."
            ) from exc
        try:  # pragma: no cover - network
            resp = requests.get(url, params=params, timeout=self.timeout_seconds)
            return resp.status_code, (resp.json() if resp.content else {})
        except Exception as exc:  # pragma: no cover - network
            raise SourceUnavailableError(f"Comtrade unreachable: {exc}") from exc

    def _fetch_page(self) -> Any:
        """One API call with rate-limit-aware retry.

        Retries on HTTP 429 (rate limit) and 5xx with exponential backoff. If
        the limit persists after max_attempts, raises SourceUnavailableError.
        """
        if not self.api_key:
            raise SourceConfigError(
                "COMTRADE_API_KEY is not set; cannot query the UN Comtrade API."
            )
        getter = self._injected_http or self._http_get
        url = self.base_url
        params = self._query_params()

        attempt = 0
        while True:
            attempt += 1
            status, body = getter(url, params)

            if status == 200:
                return body
            if status == 429:
                if attempt >= self.max_attempts:
                    raise SourceUnavailableError(
                        "UN Comtrade rate limit hit (HTTP 429) and retries "
                        "exhausted; try again later."
                    )
                backoff = self.backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "comtrade.rate_limit 429 attempt=%d backoff=%.1fs", attempt, backoff
                )
                time.sleep(backoff)
                continue
            if status in (401, 403):
                raise SourceConfigError(
                    f"UN Comtrade auth failed (HTTP {status}); check COMTRADE_API_KEY."
                )
            if status == 404 or status >= 500:
                if status >= 500 and attempt < self.max_attempts:
                    backoff = self.backoff_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "comtrade.server_error %d attempt=%d backoff=%.1fs",
                        status, attempt, backoff,
                    )
                    time.sleep(backoff)
                    continue
                raise SourceUnavailableError(
                    f"UN Comtrade returned HTTP {status}; source unavailable."
                )
            # Any other status: treat as unavailable.
            raise SourceUnavailableError(f"UN Comtrade unexpected HTTP {status}.")

    # ------------------------------------------------------------------
    # Framework hooks
    # ------------------------------------------------------------------
    def fetch(self) -> Iterable[Record]:
        self._retrieved_at = timezone.now()
        body = self._fetch_page()
        if not isinstance(body, dict):
            raise SourceUnavailableError("Comtrade returned an unexpected payload.")
        data = body.get("data")
        if data is None:
            # Comtrade signals problems in the body; treat as unavailable.
            raise SourceUnavailableError(
                "Comtrade response had no 'data' (quota, invalid query, or "
                "temporary unavailability)."
            )
        return data

    def persist(self, records: list[Record]) -> tuple[int, int]:
        written = duplicate = 0
        source_url = self._source_url()
        source_date = timezone.now().date()

        for raw in records:
            mapped = self._map(raw)
            if mapped is None:
                continue  # unresolvable/unusable record — skipped, not fabricated
            _, created = TradeObservation.objects.update_or_create(
                commodity=mapped["commodity"],
                period=mapped["period"],
                reporter_country=mapped["reporter_country"],
                partner_country=mapped["partner_country"],
                hs_code=mapped["hs_code"],
                flow=mapped["flow"],
                source=self.key,
                defaults={
                    "origin": mapped["origin"],
                    "quantity_tonnes": mapped["quantity_tonnes"],
                    "net_weight_kg": mapped["net_weight_kg"],
                    "qty_unit": mapped["qty_unit"],
                    "trade_value": mapped["trade_value"],
                    "currency": "USD",  # Comtrade primaryValue is USD
                    "source_url": source_url,
                    "source_date": source_date,
                    "retrieved_at": self._retrieved_at,
                    "raw": raw,
                },
            )
            written += int(created)
            duplicate += int(not created)
        return written, duplicate

    # ------------------------------------------------------------------
    # Mapping (only fields Comtrade actually provides)
    # ------------------------------------------------------------------
    def _map(self, raw: Record) -> Optional[dict]:
        period = _period_to_date(raw.get("period"))
        hs_code = str(raw.get("cmdCode") or "").strip()
        if period is None or not hs_code:
            return None

        # Resolve/attach a Commodity for the HS code (coal-focused).
        commodity = self._commodity_for_hs(hs_code)
        if commodity is None:
            return None

        reporter = raw.get("reporterDesc") or M49_TO_NAME.get(
            str(raw.get("reporterCode") or ""), ""
        )
        partner_code = str(raw.get("partnerCode") or "")
        partner = raw.get("partnerDesc") or M49_TO_NAME.get(partner_code, "")

        # Link to a known Origin when the partner matches one of our origins.
        origin = None
        origin_name = M49_TO_NAME.get(partner_code)
        if origin_name and origin_name != "India":
            origin = Origin.objects.filter(name__icontains=origin_name).first()

        # Net weight (kg) -> tonnes when present; qty is the reported quantity.
        net_wgt = _dec(raw.get("netWgt"))
        qty = _dec(raw.get("qty"))
        quantity_tonnes = None
        if net_wgt is not None:
            quantity_tonnes = net_wgt / Decimal("1000")
        elif qty is not None and str(raw.get("qtyUnitAbbr") or "").lower() in ("kg", "kilogram"):
            quantity_tonnes = qty / Decimal("1000")

        return {
            "commodity": commodity,
            "origin": origin,
            "period": period,
            "hs_code": hs_code,
            "flow": FLOW_MAP.get(str(raw.get("flowCode") or ""), TradeObservation.Flow.IMPORT),
            "reporter_country": str(reporter)[:80],
            "partner_country": str(partner)[:80],
            "quantity_tonnes": quantity_tonnes,
            "net_weight_kg": net_wgt,
            "qty_unit": str(raw.get("qtyUnitAbbr") or "")[:32],
            "trade_value": _dec(raw.get("primaryValue")),
        }

    def _commodity_for_hs(self, hs_code: str) -> Optional[Commodity]:
        """Map a coal HS code to a Commodity, creating a coal commodity if needed.

        Only coal-family HS codes are handled; other codes are ignored (return
        None) so we never mis-file non-coal trade under a coal commodity.
        """
        hs4 = hs_code[:4]
        mapping = {
            "2701": ("Thermal Coal", Commodity.Category.COAL_THERMAL),
            "2702": ("Lignite", Commodity.Category.COAL_THERMAL),
            "2704": ("Coke", Commodity.Category.COAL_COKING),
        }
        entry = mapping.get(hs4)
        if entry is None:
            return None
        name, category = entry
        commodity, _ = Commodity.objects.get_or_create(
            name=name, defaults={"category": category, "hs_code": hs4}
        )
        return commodity
