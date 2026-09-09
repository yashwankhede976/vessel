"""Analytical dataset assembly for the freight forecasting system.

Pure computation (pandas/numpy) — no Django imports. This package builds the
unified feature matrix consumed by the forecasting models; it does not train
any model.
"""
from .schema import (
    FEATURE_COLUMNS,
    GRAIN_COLUMNS,
    TARGET_COLUMNS,
    ColumnSpec,
    all_columns,
)
from .builder import build_dataset

__all__ = [
    "FEATURE_COLUMNS",
    "GRAIN_COLUMNS",
    "TARGET_COLUMNS",
    "ColumnSpec",
    "all_columns",
    "build_dataset",
]
