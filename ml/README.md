# ML

Machine-learning layer for the Vessel platform (freight forecasting, ETA, demurrage-risk models).

This package is **pure computation**: given features, it returns predictions with uncertainty and driver attributions. It contains no Django imports, no business rules, and is never called by the API or client directly. See [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §7 and §12 for the boundary contract.

Structure:

```
ml/
├── datasets/       # unified analytical dataset assembly (IMPLEMENTED)
│   ├── schema.py       # feature/target schema — single source of truth
│   ├── builder.py      # pure-pandas assembler (joins + derived features + targets)
│   ├── example.py      # synthetic-data demo (validation only; trains nothing)
│   └── test_builder.py # dataset tests
├── features/       # leakage-safe feature engineering (IMPLEMENTED)
│   ├── validation.py   # temporal-order + leakage guards
│   ├── transforms.py   # rolling mean/vol, lags, pct-change, seasonal (past-only)
│   ├── indicators.py   # vessel supply / demand / congestion / weather indicators
│   ├── pipeline.py     # build_features() entrypoint
│   └── test_leakage.py # leakage-prevention tests
├── models/         # forecasting models (baseline + GBM IMPLEMENTED)
│   ├── metrics.py            # MAE / RMSE / MAPE
│   ├── baseline_freight.py   # naive-previous + moving-average benchmarks
│   ├── splits.py             # time-based train/val/test split
│   ├── freight_gbm.py        # XGBoost gradient-boosted forecaster (7/14/30d)
│   ├── test_baseline.py      # benchmark tests
│   ├── test_freight_gbm.py   # GBM + split tests
│   ├── results/              # stored baseline evaluation results (JSON)
│   └── artifacts/            # saved GBM bundle (models git-ignored; reports tracked)
├── registry/       # (planned) model versioning / metadata
└── experiments/    # (planned) experiment logs — see docs/DEVELOPMENT_WORKFLOW.md §10
```

## Datasets

The `datasets` package builds the unified freight forecasting feature matrix
(grain: date × origin × destination × vessel_type). See
[../docs/FREIGHT_DATASET_SCHEMA.md](../docs/FREIGHT_DATASET_SCHEMA.md).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m datasets.example       # build a synthetic demo dataset
.venv/bin/python -m datasets.test_builder  # run dataset tests
```

## Feature engineering

The `features` package adds leakage-safe features (rolling stats, lags,
pct-change, seasonal, domain indicators) on top of the dataset. All transforms
are per-lane and past-only; see [../docs/FREIGHT_DATASET_SCHEMA.md](../docs/FREIGHT_DATASET_SCHEMA.md) §6.

```bash
.venv/bin/python -m features.test_leakage  # run leakage-prevention tests
```

## Baseline benchmark

The `models` package provides deterministic baseline forecasters (naive
previous value, moving average) for the 7/14/30-day horizons, evaluated with
MAE/RMSE/MAPE per lane and overall. These are the benchmark advanced models must
beat. Results are stored in `models/results/baseline_freight_results.json`.

```bash
.venv/bin/python -m models.baseline_freight  # evaluate + store results
.venv/bin/python -m models.test_baseline     # run benchmark tests
```

## Gradient-boosted model (XGBoost)

`models/freight_gbm.py` trains one XGBoost regressor per horizon (7/14/30d) on
the validated feature pipeline, using a **time-based** train/val/test split, and
compares against the baseline. It saves a versioned artifact bundle (per-horizon
models, feature list, metrics, training timestamp, dataset version) to
`models/artifacts/`. Not exposed to the frontend.

```bash
.venv/bin/python -m models.freight_gbm       # train, evaluate vs baseline, save bundle
.venv/bin/python -m models.test_freight_gbm  # run GBM + split tests
```

> Environment note: the ML layer runs on **Python 3.13** with a numpy-2
> scientific stack (see `requirements.txt`). Python 3.14 is not supported —
> stable numpy/scipy/pandas wheels are unavailable for it and mixing builds
> caused native segfaults.

XGBoost is a gradient-boosted tree ensemble — **no deep learning**. The model is
not yet exposed via the API/React.
