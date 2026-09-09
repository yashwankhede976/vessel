"""Forecasting models for the freight forecasting system.

Currently contains only the deterministic BASELINE benchmark (naive + moving
average). No deep learning. Advanced models will be compared against these
baselines. Pure pandas/numpy — no Django, and no model is "trained" beyond the
trivial baselines.
"""
from .metrics import mae, rmse, mape, evaluate_metrics
from .baseline_freight import (
    HORIZONS,
    BaselineResult,
    evaluate_baselines,
    moving_average_forecast,
    naive_previous_forecast,
    run_and_store,
)

__all__ = [
    "mae",
    "rmse",
    "mape",
    "evaluate_metrics",
    "HORIZONS",
    "BaselineResult",
    "evaluate_baselines",
    "moving_average_forecast",
    "naive_previous_forecast",
    "run_and_store",
]
