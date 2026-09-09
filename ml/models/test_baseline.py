"""Tests for the baseline freight forecasting benchmark.

Run from ml/ with the ml venv:
    .venv/bin/python -m models.test_baseline
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from models.baseline_freight import (
    HORIZONS,
    evaluate_baselines,
    moving_average_forecast,
    naive_previous_forecast,
    run_and_store,
    store_results,
)
from models.metrics import mae, rmse, mape, evaluate_metrics


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _frame(rates, targets=None, origin="Australia", dest="Paradip", vtype="capesize"):
    dates = pd.date_range("2026-01-01", periods=len(rates), freq="D")
    df = pd.DataFrame({
        "date": dates, "origin": origin, "destination": dest,
        "vessel_type": vtype, "freight_rate": rates,
    })
    for col in HORIZONS.values():
        df[col] = np.nan
    if targets:
        for col, vals in targets.items():
            df[col] = vals
    return df


# --- metrics ---
def test_metrics_known_values():
    yt = [10.0, 20.0, 30.0]
    yp = [12.0, 18.0, 33.0]
    _assert(abs(mae(yt, yp) - (2 + 2 + 3) / 3) < 1e-9, "MAE wrong")
    _assert(abs(rmse(yt, yp) - np.sqrt((4 + 4 + 9) / 3)) < 1e-9, "RMSE wrong")
    # MAPE: (2/10 + 2/20 + 3/30)/3 * 100 = (0.2+0.1+0.1)/3*100 = 13.333%
    _assert(abs(mape(yt, yp) - (0.4 / 3 * 100)) < 1e-6, "MAPE wrong")


def test_mape_excludes_zero_actuals():
    yt = [0.0, 10.0]
    yp = [5.0, 11.0]
    # Only the second pair counts: |10-11|/10 = 0.1 -> 10%
    _assert(abs(mape(yt, yp) - 10.0) < 1e-6, "MAPE must skip zero actuals")


def test_metrics_all_nan_returns_none():
    r = evaluate_metrics([np.nan, np.nan], [1.0, 2.0])
    _assert(r["n"] == 0 and r["mae"] is None, "all-NaN -> None metrics")


# --- forecasters ---
def test_naive_previous_is_current_rate():
    df = _frame([10.0, 11.0, 12.0])
    fc = naive_previous_forecast(df)
    _assert(list(fc) == [10.0, 11.0, 12.0], "naive forecast must equal current rate")


def test_moving_average_is_past_only():
    # Rising series; MA(3) at each row must be < current (uses only past rates).
    rates = [float(i) for i in range(1, 11)]
    df = _frame(rates)
    ma = moving_average_forecast(df, window=3).reset_index(drop=True)
    _assert(pd.isna(ma.iloc[0]), "first MA has no past -> NaN")
    later = pd.Series(rates[1:], index=range(1, 10))
    _assert((ma.iloc[1:] < later).all(), "MA must use only past rates (below current on rising)")


def test_moving_average_no_future_leakage():
    # A huge spike on the LAST day must not change any earlier MA forecast.
    rates = [10.0] * 9 + [1000.0]
    df = _frame(rates)
    ma = moving_average_forecast(df, window=5).reset_index(drop=True)
    _assert((ma.iloc[:9].dropna() < 50).all(), "future spike leaked into earlier MA")


# --- evaluation ---
def test_evaluate_produces_all_models_and_horizons():
    # Build a frame where the future targets are known so metrics are computable.
    rates = [100.0 + i for i in range(40)]
    df = _frame(rates, targets={
        "future_7d_freight": [r + 7 for r in rates],
        "future_14d_freight": [r + 14 for r in rates],
        "future_30d_freight": [r + 30 for r in rates],
    })
    results = evaluate_baselines(df, ma_window=7)
    models = {r.model for r in results}
    _assert(models == {"naive_previous", "moving_average"}, "both baselines must be evaluated")
    for r in results:
        for h in ("7", "14", "30"):
            _assert(h in r.horizons, f"{r.model} missing horizon {h}")
            _assert(r.horizons[h]["mae"] is not None, f"{r.model} h{h} MAE should compute")


def test_naive_error_matches_horizon_offset():
    # Targets = current + h. Naive predicts current, so MAE for horizon h ≈ h.
    rates = [100.0 + i for i in range(40)]
    df = _frame(rates, targets={
        "future_7d_freight": [r + 7 for r in rates],
        "future_14d_freight": [r + 14 for r in rates],
        "future_30d_freight": [r + 30 for r in rates],
    })
    results = evaluate_baselines(df)
    naive = next(r for r in results if r.model == "naive_previous")
    _assert(abs(naive.horizons["7"]["mae"] - 7.0) < 1e-6, "naive 7d MAE should be ~7")
    _assert(abs(naive.horizons["30"]["mae"] - 30.0) < 1e-6, "naive 30d MAE should be ~30")


def test_empty_input():
    _assert(evaluate_baselines(pd.DataFrame(columns=["date", "origin", "destination", "vessel_type", "freight_rate"])) == [], "empty -> no results")


# --- persistence ---
def test_store_and_run_writes_json():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "res.json"
        out = run_and_store(path=path)  # uses synthetic demo dataset
        _assert(out.exists(), "results file not written")
        payload = json.loads(out.read_text())
        _assert(payload["benchmark"] == "baseline_freight", "benchmark tag missing")
        _assert(len(payload["results"]) == 2, "expected two baseline results")
        _assert("7" in payload["results"][0]["horizons"], "horizon 7 missing in stored results")


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok: {t.__name__}")
    print(f"{len(tests)}/{len(tests)} baseline tests passed")


if __name__ == "__main__":
    _run_all()
