"""Build a demo dataset from SYNTHETIC inputs to validate the schema end-to-end.

This uses generated placeholder data only — no real provider data, no model
training. Run it to sanity-check the assembler and inspect the output shape:

    python -m ml.datasets.example        # (from repo root, with ml venv)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .builder import build_dataset


def synthetic_inputs(seed: int = 7) -> dict:
    """Generate synthetic source frames for two lanes over a date range."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=60, freq="D")
    lanes = [
        ("Australia", "Paradip", "capesize"),
        ("Indonesia", "Visakhapatnam", "panamax"),
    ]

    freight_rows = []
    for origin, dest, vtype in lanes:
        base = 18.0 if vtype == "capesize" else 14.0
        walk = np.cumsum(rng.normal(0, 0.3, len(dates)))
        for d, w in zip(dates, walk):
            freight_rows.append(
                {"date": d, "origin": origin, "destination": dest,
                 "vessel_type": vtype, "freight_rate": round(base + w, 2)}
            )
    freight = pd.DataFrame(freight_rows)

    routes = pd.DataFrame([
        {"origin": "Australia", "destination": "Paradip", "route_distance_nm": 5200},
        {"origin": "Indonesia", "destination": "Visakhapatnam", "route_distance_nm": 2100},
    ])

    congestion = pd.DataFrame([
        {"date": d, "destination": dest,
         "port_congestion": int(rng.integers(0, 12)),
         "port_waiting_time": round(float(rng.uniform(0, 5)), 2)}
        for d in dates for dest in ("Paradip", "Visakhapatnam")
    ])

    commodity_price = pd.DataFrame([
        {"date": d, "commodity_price": round(120 + float(rng.normal(0, 4)), 2)}
        for d in dates
    ])

    bunker = pd.DataFrame([
        {"date": d, "bunker_indicator": round(600 + float(rng.normal(0, 15)), 2)}
        for d in dates
    ])

    commodity_volume = pd.DataFrame([
        {"date": d, "destination": dest, "commodity_import_volume": float(rng.integers(50_000, 200_000))}
        for d in dates for dest in ("Paradip", "Visakhapatnam")
    ])

    vessel_availability = pd.DataFrame([
        {"date": d, "origin": origin, "vessel_type": vtype,
         "vessel_availability": int(rng.integers(0, 8))}
        for d in dates for (origin, _, vtype) in lanes
    ])

    weather_risk = pd.DataFrame([
        {"date": d, "destination": dest, "weather_risk": round(float(rng.uniform(0, 1)), 3)}
        for d in dates for dest in ("Paradip", "Visakhapatnam")
    ])

    trade_volume = pd.DataFrame([
        {"date": d, "origin": origin, "destination": dest,
         "trade_volume": float(rng.integers(100_000, 500_000))}
        for d in dates for (origin, dest, _) in lanes
    ])

    return {
        "freight": freight,
        "routes": routes,
        "congestion": congestion,
        "commodity_price": commodity_price,
        "bunker": bunker,
        "commodity_volume": commodity_volume,
        "vessel_availability": vessel_availability,
        "weather_risk": weather_risk,
        "trade_volume": trade_volume,
    }


def build_demo() -> pd.DataFrame:
    return build_dataset(**synthetic_inputs())


if __name__ == "__main__":  # pragma: no cover
    df = build_demo()
    print(f"Rows: {len(df)}  Columns: {len(df.columns)}")
    print(df.dtypes)
    print(df.head(3).to_string())
