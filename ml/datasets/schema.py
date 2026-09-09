"""Feature schema for the unified freight forecasting dataset.

This module is the single source of truth for the dataset's columns. Both the
assembler (builder.py) and the documentation (docs/FREIGHT_DATASET_SCHEMA.md)
derive from these specs.

Row grain
---------
One row = (date, origin, destination, vessel_type). `date` is the observation
date; features describe conditions known AS OF that date; targets are future
freight rates for the same lane/vessel_type.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSpec:
    """Metadata for one dataset column."""

    name: str
    dtype: str            # pandas dtype family: "datetime64[ns]", "category", "float64", "Int64"
    unit: str             # human unit, or "" if none
    description: str
    nullable: bool
    source: str           # where the value originates (see docs/DATA_SOURCES.md)
    role: str             # "grain" | "feature" | "target"


# ---------------------------------------------------------------------------
# Grain (the composite key identifying a row)
# ---------------------------------------------------------------------------
GRAIN_COLUMNS: list[ColumnSpec] = [
    ColumnSpec("date", "datetime64[ns]", "date", "Observation date; features are known as of this date.", False, "derived / calendar", "grain"),
    ColumnSpec("origin", "category", "", "Origin country/region (e.g. Australia, Indonesia).", False, "catalog.Origin", "grain"),
    ColumnSpec("destination", "category", "", "Destination East Coast India port (e.g. Paradip).", False, "catalog.Port", "grain"),
    ColumnSpec("vessel_type", "category", "", "Vessel class (handysize/supramax/panamax/capesize/...).", False, "catalog.Vessel.vessel_type", "grain"),
]


# ---------------------------------------------------------------------------
# Features (all describe state known as of `date` — no future leakage)
# ---------------------------------------------------------------------------
FEATURE_COLUMNS: list[ColumnSpec] = [
    ColumnSpec("route_distance_nm", "float64", "nautical miles", "Sailing distance for the origin->destination route.", True, "catalog.Route.distance_nm", "feature"),
    ColumnSpec("historical_freight_rate", "float64", "USD/tonne", "Most recent observed freight rate for the lane/vessel_type up to `date` (lagged; excludes today's realized rate to avoid leakage).", True, "operations.FreightObservation (Baltic/proxy)", "feature"),
    ColumnSpec("vessel_availability", "Int64", "count", "Number of suitable vessels open/available near the origin around `date`.", True, "catalog.Vessel.availability_status + AIS", "feature"),
    ColumnSpec("port_congestion", "float64", "count", "Vessels waiting / congestion level at the destination port on `date`.", True, "operations.PortCongestionObservation", "feature"),
    ColumnSpec("port_waiting_time", "float64", "days", "Expected/observed average waiting time at the destination port.", True, "operations.PortCongestionObservation.avg_wait_days", "feature"),
    ColumnSpec("commodity_import_volume", "float64", "tonnes", "Recent import throughput/volume of the commodity into the destination (or India).", True, "operations.PortTraffic / TradeObservation", "feature"),
    ColumnSpec("commodity_price", "float64", "USD/tonne", "Recent commodity (coal) price as of `date`.", True, "operations.CommodityPriceObservation / World Bank Pink Sheet", "feature"),
    ColumnSpec("bunker_indicator", "float64", "USD/tonne", "Recent bunker (marine fuel) price indicator as of `date`.", True, "operations.BunkerPriceObservation", "feature"),
    ColumnSpec("weather_risk", "float64", "0..1", "Normalized weather/marine risk for the lane/destination around `date` (e.g. monsoon/cyclone exposure). Derived, not a live model output.", True, "operations.WeatherObservation / MarineObservation / CycloneObservation (derived)", "feature"),
    ColumnSpec("seasonality_month", "Int64", "month", "Calendar month (1-12) of `date`.", False, "derived / calendar", "feature"),
    ColumnSpec("seasonality_sin", "float64", "", "sin(2*pi*month/12) — cyclical month encoding.", False, "derived / calendar", "feature"),
    ColumnSpec("seasonality_cos", "float64", "", "cos(2*pi*month/12) — cyclical month encoding.", False, "derived / calendar", "feature"),
    ColumnSpec("is_monsoon", "Int64", "0/1", "1 if `date` falls in the SW/NE monsoon window relevant to the Bay of Bengal (Jun-Sep, Oct-Dec heuristic), else 0.", False, "derived / calendar", "feature"),
    ColumnSpec("trade_volume", "float64", "tonnes", "Recent bilateral trade volume on the origin->destination-country lane for the commodity.", True, "operations.TradeObservation (UN Comtrade)", "feature"),
    ColumnSpec("ton_mile_proxy", "float64", "tonne-nm", "route_distance_nm * commodity_import_volume — a demand-for-shipping proxy.", True, "derived (distance x volume)", "feature"),
    ColumnSpec("vessel_supply_proxy", "float64", "", "vessel_availability normalized by recent demand — a supply-tightness proxy (higher = more available tonnage relative to demand).", True, "derived (availability / demand)", "feature"),
]


# ---------------------------------------------------------------------------
# Targets (future freight rates — the values the model predicts)
# ---------------------------------------------------------------------------
TARGET_COLUMNS: list[ColumnSpec] = [
    ColumnSpec("freight_rate", "float64", "USD/tonne", "Realized freight rate for the lane/vessel_type ON `date` (current target / label).", True, "operations.FreightObservation", "target"),
    ColumnSpec("future_7d_freight", "float64", "USD/tonne", "Realized freight rate ~7 days after `date` (short-term target).", True, "operations.FreightObservation (forward)", "target"),
    ColumnSpec("future_14d_freight", "float64", "USD/tonne", "Realized freight rate ~14 days after `date`.", True, "operations.FreightObservation (forward)", "target"),
    ColumnSpec("future_30d_freight", "float64", "USD/tonne", "Realized freight rate ~30 days after `date` (medium-term target).", True, "operations.FreightObservation (forward)", "target"),
]

# Horizons (in days) for the future_* targets, keyed by column name.
TARGET_HORIZONS: dict[str, int] = {
    "future_7d_freight": 7,
    "future_14d_freight": 14,
    "future_30d_freight": 30,
}


def all_columns() -> list[ColumnSpec]:
    """Grain + features + targets, in canonical order."""
    return GRAIN_COLUMNS + FEATURE_COLUMNS + TARGET_COLUMNS


def column_order() -> list[str]:
    return [c.name for c in all_columns()]


def dtype_map() -> dict[str, str]:
    return {c.name: c.dtype for c in all_columns()}
