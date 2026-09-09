"""Domain indicator features (vessel supply, demand, congestion, weather).

Each indicator is derived only from as-of feature columns (state known on
`date`) — never from the future target columns. Rolling context uses the
leakage-safe transforms (shifted per lane), so indicators for a row reflect only
past-and-present information.

Missing base columns are tolerated: an indicator that needs an absent column is
skipped rather than fabricated.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .transforms import add_rolling_mean

LANE = ["origin", "destination", "vessel_type"]


def _has(df: pd.DataFrame, *cols: str) -> bool:
    return all(c in df.columns for c in cols)


def add_vessel_supply_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Vessel supply signals from availability and the supply proxy.

    - supply_availability_trend_3: rolling mean of vessel_availability over the
      last 3 PAST rows (per lane) — recent tonnage availability.
    - supply_tightness: inverse of vessel_supply_proxy (higher => tighter),
      guarded against divide-by-zero.
    """
    out = df.copy()
    if _has(out, "vessel_availability"):
        out = add_rolling_mean(
            out, "vessel_availability", [3], prefix="supply_availability_trend"
        )
    if _has(out, "vessel_supply_proxy"):
        proxy = pd.to_numeric(out["vessel_supply_proxy"], errors="coerce")
        out["supply_tightness"] = 1.0 / proxy.replace(0, np.nan)
        out["supply_tightness"] = out["supply_tightness"].replace(
            [np.inf, -np.inf], np.nan
        )
    return out


def add_demand_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Demand signals from trade/import volume and the ton-mile proxy.

    - demand_volume_trend_3: rolling mean of commodity_import_volume (past).
    - demand_tonmile_trend_3: rolling mean of ton_mile_proxy (past).
    """
    out = df.copy()
    if _has(out, "commodity_import_volume"):
        out = add_rolling_mean(
            out, "commodity_import_volume", [3], prefix="demand_volume_trend"
        )
    if _has(out, "ton_mile_proxy"):
        out = add_rolling_mean(
            out, "ton_mile_proxy", [3], prefix="demand_tonmile_trend"
        )
    return out


def add_port_congestion_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Port congestion signals from congestion count and waiting time.

    - congestion_trend_3 / waiting_trend_3: rolling means (past) per lane.
    - congestion_pressure: current congestion relative to its recent past mean
      (>1 means worse than recent norm). Uses the shifted rolling mean so the
      current row's own value is not in the baseline.
    """
    out = df.copy()
    if _has(out, "port_congestion"):
        out = add_rolling_mean(out, "port_congestion", [3], prefix="congestion_trend")
        base = out.get("congestion_trend_rollmean_3")
        if base is not None:
            cur = pd.to_numeric(out["port_congestion"], errors="coerce")
            out["congestion_pressure"] = (
                cur / pd.to_numeric(base, errors="coerce").replace(0, np.nan)
            ).replace([np.inf, -np.inf], np.nan)
    if _has(out, "port_waiting_time"):
        out = add_rolling_mean(out, "port_waiting_time", [3], prefix="waiting_trend")
    return out


def add_weather_risk_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Weather-risk signals from the (as-of) weather_risk feature.

    - weather_risk_trend_3: rolling mean of weather_risk (past) per lane.
    - weather_risk_elevated: 1 if current weather_risk exceeds its recent past
      mean, else 0 (Int64, null where undefined).
    """
    out = df.copy()
    if _has(out, "weather_risk"):
        out = add_rolling_mean(out, "weather_risk", [3], prefix="weather_risk_trend")
        base = out.get("weather_risk_trend_rollmean_3")
        if base is not None:
            cur = pd.to_numeric(out["weather_risk"], errors="coerce")
            baseline = pd.to_numeric(base, errors="coerce")
            elevated = (cur > baseline)
            # Preserve NaN where baseline is unknown.
            elevated = elevated.where(baseline.notna() & cur.notna(), other=pd.NA)
            out["weather_risk_elevated"] = elevated.astype("Int64")
    return out
