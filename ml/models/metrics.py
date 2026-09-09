"""Forecast evaluation metrics.

MAE and RMSE are always well-defined. MAPE is only appropriate when the actual
values are strictly positive and not near zero (it divides by the actual); for
freight rates in USD/tonne this generally holds, but we guard against zeros by
excluding them from the MAPE denominator and reporting the excluded count.

All functions accept array-likes, coerce to float, and drop pairs where either
value is NaN (so callers can pass aligned series with gaps).
"""
from __future__ import annotations

from typing import Optional

import numpy as np


def _clean_pairs(y_true, y_pred) -> tuple[np.ndarray, np.ndarray]:
    yt = np.asarray(y_true, dtype="float64")
    yp = np.asarray(y_pred, dtype="float64")
    mask = ~(np.isnan(yt) | np.isnan(yp))
    return yt[mask], yp[mask]


def mae(y_true, y_pred) -> Optional[float]:
    yt, yp = _clean_pairs(y_true, y_pred)
    if yt.size == 0:
        return None
    return float(np.mean(np.abs(yt - yp)))


def rmse(y_true, y_pred) -> Optional[float]:
    yt, yp = _clean_pairs(y_true, y_pred)
    if yt.size == 0:
        return None
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def mape(y_true, y_pred, *, eps: float = 1e-9) -> Optional[float]:
    """Mean Absolute Percentage Error (as a percentage).

    Only defined where the actual value is non-zero; pairs with |actual| <= eps
    are excluded from the denominator. Returns None if nothing is left.
    """
    yt, yp = _clean_pairs(y_true, y_pred)
    if yt.size == 0:
        return None
    nonzero = np.abs(yt) > eps
    if not nonzero.any():
        return None
    yt, yp = yt[nonzero], yp[nonzero]
    return float(np.mean(np.abs((yt - yp) / yt)) * 100.0)


def evaluate_metrics(y_true, y_pred) -> dict:
    """Compute MAE, RMSE, MAPE and the sample size for a set of aligned pairs."""
    yt, yp = _clean_pairs(y_true, y_pred)
    return {
        "n": int(yt.size),
        "mae": mae(yt, yp),
        "rmse": rmse(yt, yp),
        "mape_pct": mape(yt, yp),
    }
