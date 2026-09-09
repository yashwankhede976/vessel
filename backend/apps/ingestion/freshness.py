"""Data-freshness classification and external-service health.

Provides two read-only views over the ingestion state, computed on demand from
the latest observation rows and the IngestionRun history — no extra stored
table is needed.

1) Data freshness per source+dataset:
     FRESH / STALE / VERY_STALE / UNKNOWN
   based on the age of the most recent observation for each dataset against
   documented per-dataset thresholds (different datasets refresh at different
   cadences — AIS is minutes, trade statistics are months).

2) External-service health per provider:
     configured / reachable / last_success / last_failure / data_freshness
   API keys are NEVER included — only a boolean `configured`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from apps.ingestion.models import IngestionRun


# --- Freshness levels ------------------------------------------------------
FRESH = "FRESH"
STALE = "STALE"
VERY_STALE = "VERY_STALE"
UNKNOWN = "UNKNOWN"


# --- Per-dataset freshness thresholds (documented) -------------------------
# (fresh_within_hours, stale_within_hours). Older than stale_within => VERY_STALE.
# Chosen to match each dataset's natural cadence.
DATASET_THRESHOLDS = {
    # dataset key -> (fresh_h, stale_h)
    "ais_positions": (6, 24),          # AIS should be near-real-time
    "weather": (12, 48),               # forecasts refreshed a few times/day
    "marine": (24, 96),                # marine/ocean-state bulletins
    "cyclone": (12, 48),               # cyclone advisories (when active)
    "port_congestion": (48, 168),      # congestion snapshots
    "port_traffic": (24 * 30, 24 * 120),   # monthly port statistics
    "trade": (24 * 60, 24 * 180),      # trade stats are months-lagged
    "commodity_price": (24 * 7, 24 * 45),  # weekly-ish indices
    "bunker_price": (24 * 3, 24 * 14),
}
DEFAULT_THRESHOLD = (24, 72)


@dataclass
class FreshnessEntry:
    dataset: str
    latest_at: Optional[str]        # ISO timestamp of the most recent record
    age_hours: Optional[float]
    level: str                      # FRESH/STALE/VERY_STALE/UNKNOWN
    fresh_within_hours: int
    stale_within_hours: int
    record_count: int

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "latest_at": self.latest_at,
            "age_hours": self.age_hours,
            "level": self.level,
            "fresh_within_hours": self.fresh_within_hours,
            "stale_within_hours": self.stale_within_hours,
            "record_count": self.record_count,
        }


def classify_age(age_hours: Optional[float], thresholds) -> str:
    """Map an age (hours) to a freshness level using (fresh_h, stale_h)."""
    if age_hours is None:
        return UNKNOWN
    fresh_h, stale_h = thresholds
    if age_hours <= fresh_h:
        return FRESH
    if age_hours <= stale_h:
        return STALE
    return VERY_STALE


def _dataset_latest():
    """Return {dataset: (latest_datetime_or_None, count)} for each tracked dataset.

    Imported lazily so this module has no import-time dependency on the models
    graph beyond IngestionRun.
    """
    from apps.operations.models import (
        AISPosition,
        BunkerPriceObservation,
        CommodityPriceObservation,
        CycloneObservation,
        MarineObservation,
        PortCongestionObservation,
        PortTraffic,
        TradeObservation,
        WeatherObservation,
    )

    specs = {
        "ais_positions": (AISPosition, "timestamp"),
        "weather": (WeatherObservation, "timestamp"),
        "marine": (MarineObservation, "timestamp"),
        "cyclone": (CycloneObservation, "timestamp"),
        "port_congestion": (PortCongestionObservation, "observed_at"),
        "port_traffic": (PortTraffic, "period"),
        "trade": (TradeObservation, "period"),
        "commodity_price": (CommodityPriceObservation, "observed_on"),
        "bunker_price": (BunkerPriceObservation, "observed_on"),
    }
    out = {}
    for dataset, (model, field) in specs.items():
        agg = model.objects.aggregate(latest=Max(field))
        out[dataset] = (agg["latest"], model.objects.count())
    return out


def _to_datetime(value):
    """Coerce a date or datetime to an aware datetime (UTC midnight for dates)."""
    if value is None:
        return None
    from datetime import date, datetime, timezone as _tz

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=_tz.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=_tz.utc)
    return None


def data_freshness(now=None) -> list[FreshnessEntry]:
    """Compute freshness for every tracked dataset."""
    now = now or timezone.now()
    entries: list[FreshnessEntry] = []
    for dataset, (latest, count) in _dataset_latest().items():
        thresholds = DATASET_THRESHOLDS.get(dataset, DEFAULT_THRESHOLD)
        dt = _to_datetime(latest)
        if dt is None:
            entries.append(
                FreshnessEntry(dataset, None, None, UNKNOWN, thresholds[0],
                               thresholds[1], count)
            )
            continue
        age_hours = round((now - dt).total_seconds() / 3600.0, 2)
        entries.append(
            FreshnessEntry(
                dataset=dataset,
                latest_at=dt.isoformat(),
                age_hours=age_hours,
                level=classify_age(age_hours, thresholds),
                fresh_within_hours=thresholds[0],
                stale_within_hours=thresholds[1],
                record_count=count,
            )
        )
    return entries


# ---------------------------------------------------------------------------
# External-service health
# ---------------------------------------------------------------------------

# Map each provider to: the settings key(s) that make it "configured", whether it
# needs a key at all, and the ingestion source key + datasets it feeds. A
# provider with `needs_key=False` is always configured (keyless).
PROVIDERS = {
    "aisstream": {
        "settings_keys": ["AISSTREAM_API_KEY"],
        "needs_key": True,
        "source_key": "aisstream",
        "datasets": ["ais_positions"],
    },
    "un_comtrade": {
        "settings_keys": ["COMTRADE_API_KEY"],
        "needs_key": False,  # free public tier works without a key
        "source_key": "un_comtrade",
        "datasets": ["trade"],
    },
    "data_gov_in": {
        "settings_keys": ["DATA_GOV_API_KEY"],
        "needs_key": True,
        "source_key": "data_gov_in",
        "datasets": ["port_traffic", "trade", "commodity_price"],
    },
    "ministry_of_coal": {
        "settings_keys": [],
        "needs_key": False,  # file-download mode
        "source_key": "ministry_of_coal",
        "datasets": ["port_traffic"],
    },
    "open_meteo": {
        "settings_keys": [],
        "needs_key": False,  # keyless
        "source_key": "open_meteo",
        "datasets": ["weather"],
    },
    "imd": {
        "settings_keys": ["IMD_BASE_URL"],
        "needs_key": False,  # config-driven URLs; no key
        "source_key": "imd",
        "datasets": ["marine", "cyclone"],
    },
    "incois": {
        "settings_keys": [],
        "needs_key": False,  # public ocean-state products
        "source_key": "incois",
        "datasets": ["marine"],
    },
    "world_bank": {
        "settings_keys": [],
        "needs_key": False,  # keyless
        "source_key": "world_bank",
        "datasets": ["commodity_price"],
    },
}


@dataclass
class ServiceHealth:
    provider: str
    configured: bool
    needs_key: bool
    reachable: Optional[bool]         # None => not checked live (default)
    last_success: Optional[str]
    last_failure: Optional[str]
    data_freshness: list             # freshness entries for this provider's datasets

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "configured": self.configured,
            "needs_key": self.needs_key,
            "reachable": self.reachable,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "data_freshness": self.data_freshness,
        }


def _is_configured(spec: dict) -> bool:
    if not spec["needs_key"]:
        return True
    ext = getattr(settings, "EXTERNAL_APIS", {})
    return any(bool(ext.get(k)) for k in spec["settings_keys"])


def _last_run_times(source_key: str):
    """Return (last_success_iso, last_failure_iso) from IngestionRun history."""
    success = (
        IngestionRun.objects.filter(
            source_key=source_key,
            status__in=[IngestionRun.Status.SUCCESS, IngestionRun.Status.PARTIAL],
        )
        .order_by("-finished_at")
        .values_list("finished_at", flat=True)
        .first()
    )
    failure = (
        IngestionRun.objects.filter(
            source_key=source_key,
            status__in=[
                IngestionRun.Status.FAILED,
                IngestionRun.Status.SOURCE_UNAVAILABLE,
            ],
        )
        .order_by("-finished_at")
        .values_list("finished_at", flat=True)
        .first()
    )
    return (
        success.isoformat() if success else None,
        failure.isoformat() if failure else None,
    )


def external_services(now=None) -> list[ServiceHealth]:
    """Per-provider health. NEVER includes API keys — only a configured flag.

    `reachable` is None by default (we do not make live calls from a status
    endpoint); the last_success/last_failure from IngestionRun history is the
    real signal of whether the integration is working.
    """
    freshness_by_dataset = {e.dataset: e.to_dict() for e in data_freshness(now=now)}
    out: list[ServiceHealth] = []
    for provider, spec in PROVIDERS.items():
        last_success, last_failure = _last_run_times(spec["source_key"])
        out.append(
            ServiceHealth(
                provider=provider,
                configured=_is_configured(spec),
                needs_key=spec["needs_key"],
                reachable=None,
                last_success=last_success,
                last_failure=last_failure,
                data_freshness=[
                    freshness_by_dataset[d]
                    for d in spec["datasets"]
                    if d in freshness_by_dataset
                ],
            )
        )
    return out
