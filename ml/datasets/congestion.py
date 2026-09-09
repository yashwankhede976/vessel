"""Unified port-congestion dataset for the congestion forecasting model.

Row grain: (date, port). Features describe conditions known AS OF `date`;
targets are the future congestion level at +1/+3/+7/+14 days for the same port.

Pure pandas/numpy — no Django, no model training here. Mirrors the freight
dataset's leakage discipline (see ml/datasets/builder.py and
docs/FREIGHT_DATASET_SCHEMA.md §4): historical congestion is lagged, and future
targets are looked up FORWARD per port via merge_asof, so nothing from the
future leaks into a feature.
"""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings(
    "ignore", category=FutureWarning, message=".*ChainedAssignmentError.*"
)
try:
    warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
except AttributeError:  # pragma: no cover
    pass

GRAIN = ["date", "port"]

# Forecast horizons (days) -> target column names.
CONGESTION_HORIZONS = {
    1: "future_1d_congestion",
    3: "future_3d_congestion",
    7: "future_7d_congestion",
    14: "future_14d_congestion",
}

# Feature columns (all as-of `date`).
FEATURE_COLUMNS = [
    "current_congestion",       # congestion level today (the value we forecast)
    "vessel_arrival_density",   # arrivals per day around the port
    "historical_traffic",       # trailing baseline traffic
    "cargo_demand",             # inbound cargo demand signal
    "weather_risk",             # 0..1 weather/marine risk
    "cyclone_warning",          # 0/1 active cyclone warning
    "berth_capacity_indicator", # 0..1 utilization of berth capacity
    "historical_congestion_lag1",  # yesterday's congestion (lagged; leakage-safe)
    "seasonality_month",
    "seasonality_sin",
    "seasonality_cos",
    "is_monsoon",
]

MONSOON_MONTHS = {6, 7, 8, 9, 10, 11, 12}
TARGET_TOLERANCE_DAYS = 2

COLUMN_ORDER = GRAIN + FEATURE_COLUMNS + list(CONGESTION_HORIZONS.values())


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMN_ORDER)


def build_congestion_dataset(
    congestion: pd.DataFrame,
    *,
    arrivals: Optional[pd.DataFrame] = None,
    traffic: Optional[pd.DataFrame] = None,
    cargo_demand: Optional[pd.DataFrame] = None,
    weather: Optional[pd.DataFrame] = None,
    cyclone: Optional[pd.DataFrame] = None,
    berth_capacity: Optional[pd.DataFrame] = None,
    target_tolerance_days: int = TARGET_TOLERANCE_DAYS,
) -> pd.DataFrame:
    """Assemble the (date, port) congestion dataset.

    `congestion` is the spine: columns [date, port, current_congestion]. All
    other frames are optional and left-joined on the keys they share. Missing
    sources leave their feature columns null (never fabricated).
    """
    if congestion is None or len(congestion) == 0:
        return _empty()

    df = congestion.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["port", "date"]).drop_duplicates(GRAIN, keep="last")
    df = df.reset_index(drop=True)

    # Lagged historical congestion (previous obs per port) — leakage-safe.
    df["historical_congestion_lag1"] = (
        df.groupby("port", observed=True)["current_congestion"].shift(1)
    )

    # Forward targets per port.
    df = _attach_future_targets(df, target_tolerance_days)

    # Calendar / seasonality.
    month = df["date"].dt.month
    df["seasonality_month"] = month.astype("Int64")
    df["seasonality_sin"] = np.sin(2 * np.pi * month / 12.0)
    df["seasonality_cos"] = np.cos(2 * np.pi * month / 12.0)
    df["is_monsoon"] = month.isin(MONSOON_MONTHS).astype("Int64")

    # Optional feature joins.
    df = _join(df, arrivals, ["date", "port"])
    df = _join(df, traffic, ["date", "port"])
    df = _join(df, cargo_demand, ["date", "port"])
    df = _join(df, weather, ["date", "port"])
    df = _join(df, cyclone, ["date", "port"])
    df = _join(df, berth_capacity, ["date", "port"])

    # Ensure all columns exist, order + return.
    df = df.copy()
    for col in COLUMN_ORDER:
        if col not in df.columns:
            df[col] = np.nan
    df["port"] = df["port"].astype("category")
    for c in ("seasonality_month", "is_monsoon", "cyclone_warning"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df[COLUMN_ORDER].sort_values(GRAIN).reset_index(drop=True)


def _attach_future_targets(df: pd.DataFrame, tolerance_days: int) -> pd.DataFrame:
    tol = pd.Timedelta(days=tolerance_days)
    out = df.copy()
    for col in CONGESTION_HORIZONS.values():
        out[col] = np.nan

    for _, port_df in df.groupby("port", observed=True):
        series = port_df[["date", "current_congestion"]].sort_values("date")
        for horizon, col in CONGESTION_HORIZONS.items():
            targets = port_df[["date"]].copy()
            targets["target_date"] = targets["date"] + pd.Timedelta(days=horizon)
            targets = targets.sort_values("target_date")
            merged = pd.merge_asof(
                targets,
                series.rename(columns={"date": "obs_date"}),
                left_on="target_date", right_on="obs_date",
                direction="nearest", tolerance=tol,
            )
            mapped = merged.set_index("date")["current_congestion"]
            out.loc[port_df.index, col] = port_df["date"].map(mapped).to_numpy()
    return out


def _join(df: pd.DataFrame, other: Optional[pd.DataFrame], on: list[str]) -> pd.DataFrame:
    if other is None or len(other) == 0:
        return df
    other = other.copy()
    if "date" in other.columns:
        other["date"] = pd.to_datetime(other["date"])
    keys = [k for k in on if k in df.columns and k in other.columns]
    if not keys:
        return df
    other = other.drop_duplicates(subset=keys, keep="last")
    return df.merge(other, on=keys, how="left")


# ---------------------------------------------------------------------------
# Synthetic demo (validation only — no real data, trains nothing)
# ---------------------------------------------------------------------------
def synthetic_congestion(seed: int = 11) -> dict:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=160, freq="D")
    ports = ["Paradip", "Visakhapatnam"]

    cong_rows, arr_rows, traf_rows, cargo_rows, wx_rows, cyc_rows, cap_rows = (
        [], [], [], [], [], [], []
    )
    for port in ports:
        level = 5.0
        for d in dates:
            level = max(0.0, level + rng.normal(0, 0.6))
            cong_rows.append({"date": d, "port": port, "current_congestion": round(level, 2)})
            arr_rows.append({"date": d, "port": port, "vessel_arrival_density": float(rng.integers(0, 10))})
            traf_rows.append({"date": d, "port": port, "historical_traffic": float(rng.integers(20, 60))})
            cargo_rows.append({"date": d, "port": port, "cargo_demand": float(rng.integers(50_000, 200_000))})
            wx_rows.append({"date": d, "port": port, "weather_risk": round(float(rng.uniform(0, 1)), 3)})
            cyc_rows.append({"date": d, "port": port, "cyclone_warning": int(rng.random() < 0.05)})
            cap_rows.append({"date": d, "port": port, "berth_capacity_indicator": round(float(rng.uniform(0.2, 1.0)), 3)})

    return {
        "congestion": pd.DataFrame(cong_rows),
        "arrivals": pd.DataFrame(arr_rows),
        "traffic": pd.DataFrame(traf_rows),
        "cargo_demand": pd.DataFrame(cargo_rows),
        "weather": pd.DataFrame(wx_rows),
        "cyclone": pd.DataFrame(cyc_rows),
        "berth_capacity": pd.DataFrame(cap_rows),
    }


def build_demo() -> pd.DataFrame:
    return build_congestion_dataset(**synthetic_congestion())


if __name__ == "__main__":  # pragma: no cover
    d = build_demo()
    print("rows", len(d), "cols", len(d.columns))
    print(d.dtypes)
    print(d.head(3).to_string())
