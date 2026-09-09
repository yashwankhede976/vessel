# ML

Machine-learning layer for the Vessel platform (freight forecasting, ETA, demurrage-risk models).

This package is **pure computation**: given features, it returns predictions with uncertainty and driver attributions. It contains no Django imports, no business rules, and is never called by the API or client directly. See [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §7 and §12 for the boundary contract.

Planned structure (created as models are implemented):

```
ml/
├── features/       # feature engineering (Pandas / NumPy)
├── models/         # forecasting / ETA / demurrage models (scikit-learn, XGBoost/LightGBM, statsmodels)
├── registry/       # model versioning / metadata
└── experiments/    # experiment logs (metrics, params) — see docs/DEVELOPMENT_WORKFLOW.md §10
```

No business features or model code are implemented yet.
