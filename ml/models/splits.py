"""Time-based train/validation/test splitting.

Freight forecasting is a temporal problem: splits MUST respect time so the model
is only ever validated/tested on dates AFTER those it trained on. Random splits
would leak future information. We split by global date quantiles (not row count)
so every lane contributes its early history to train and its later history to
test, and no test date precedes a train date globally.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class TimeSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    train_end: pd.Timestamp
    val_end: pd.Timestamp


def time_split(
    df: pd.DataFrame,
    *,
    train_frac: float = 0.6,
    val_frac: float = 0.2,
    date_col: str = "date",
) -> TimeSplit:
    """Split chronologically by global date quantiles.

    Rows with date <= train_end -> train; (train_end, val_end] -> val;
    > val_end -> test. Boundaries are the `train_frac` and `train_frac+val_frac`
    quantiles of the distinct dates, so the cut is time-based, not row-based.
    """
    if not (0 < train_frac < 1 and 0 < val_frac < 1 and train_frac + val_frac < 1):
        raise ValueError("Require 0 < train_frac, val_frac and train_frac+val_frac < 1.")

    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col])
    work = work.sort_values(date_col)

    dates = work[date_col]
    train_end = dates.quantile(train_frac)
    val_end = dates.quantile(train_frac + val_frac)

    train = work[work[date_col] <= train_end]
    val = work[(work[date_col] > train_end) & (work[date_col] <= val_end)]
    test = work[work[date_col] > val_end]

    return TimeSplit(
        train=train.reset_index(drop=True),
        val=val.reset_index(drop=True),
        test=test.reset_index(drop=True),
        train_end=pd.Timestamp(train_end),
        val_end=pd.Timestamp(val_end),
    )
