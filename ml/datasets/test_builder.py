"""Tests for the freight dataset assembler (no Django, no model training).

Run from the ml/ directory with the ml venv:
    .venv/bin/python -m pytest datasets/test_builder.py
or simply execute this file: .venv/bin/python datasets/test_builder.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from datasets.builder import build_dataset
from datasets.schema import column_order, TARGET_HORIZONS
from datasets.example import build_demo


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_output_has_exact_schema_columns():
    df = build_demo()
    _assert(list(df.columns) == column_order(), "columns must match schema order exactly")


def test_grain_is_unique():
    df = build_demo()
    dup = df.duplicated(subset=["date", "origin", "destination", "vessel_type"]).sum()
    _assert(dup == 0, "each (date,origin,destination,vessel_type) must be unique")


def test_seasonality_and_monsoon():
    df = build_demo()
    # month in 1..12, sin/cos in [-1,1], is_monsoon in {0,1}
    _assert(df["seasonality_month"].between(1, 12).all(), "month out of range")
    _assert(df["seasonality_sin"].between(-1, 1).all(), "sin out of range")
    _assert(set(df["is_monsoon"].dropna().unique()).issubset({0, 1}), "is_monsoon must be 0/1")


def test_historical_rate_is_lagged_not_leaking():
    # A single lane with a strictly increasing rate: historical (lag-1) must be
    # strictly less than the current freight_rate, and the first row is NaN.
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    freight = pd.DataFrame({
        "date": dates,
        "origin": "Australia", "destination": "Paradip", "vessel_type": "capesize",
        "freight_rate": [10.0, 11.0, 12.0, 13.0, 14.0],
    })
    df = build_dataset(freight).sort_values("date").reset_index(drop=True)
    _assert(pd.isna(df.loc[0, "historical_freight_rate"]), "first lagged rate must be NaN")
    later = df.iloc[1:]
    _assert((later["historical_freight_rate"] < later["freight_rate"]).all(),
            "lagged historical rate must precede (be less than) current on rising series")


def test_future_targets_look_forward():
    # Daily series 100,101,...; future_7d at day0 should be ~107.
    dates = pd.date_range("2026-01-01", periods=40, freq="D")
    freight = pd.DataFrame({
        "date": dates,
        "origin": "Indonesia", "destination": "Visakhapatnam", "vessel_type": "panamax",
        "freight_rate": [100.0 + i for i in range(40)],
    })
    df = build_dataset(freight).sort_values("date").reset_index(drop=True)
    row0 = df.iloc[0]
    _assert(abs(row0["future_7d_freight"] - 107.0) < 1e-6, f"7d target wrong: {row0['future_7d_freight']}")
    _assert(abs(row0["future_14d_freight"] - 114.0) < 1e-6, f"14d target wrong: {row0['future_14d_freight']}")
    _assert(abs(row0["future_30d_freight"] - 130.0) < 1e-6, f"30d target wrong: {row0['future_30d_freight']}")
    # Near the end, the 30d-ahead target has no future observation -> NaN.
    _assert(pd.isna(df.iloc[-1]["future_30d_freight"]), "end-of-series 30d target must be NaN")


def test_derived_proxies_present():
    df = build_demo()
    _assert("ton_mile_proxy" in df.columns and df["ton_mile_proxy"].notna().any(),
            "ton_mile_proxy must be computed where inputs exist")
    _assert("vessel_supply_proxy" in df.columns, "vessel_supply_proxy must exist")


def test_empty_input_returns_empty_schema():
    df = build_dataset(pd.DataFrame(columns=["date", "origin", "destination", "vessel_type", "freight_rate"]))
    _assert(list(df.columns) == column_order(), "empty output must still have schema columns")
    _assert(len(df) == 0, "empty input -> empty output")


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"  ok: {t.__name__}")
    print(f"{passed}/{len(tests)} dataset tests passed")


if __name__ == "__main__":
    _run_all()
