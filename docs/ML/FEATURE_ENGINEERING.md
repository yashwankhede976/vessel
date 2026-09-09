# Feature Engineering

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Model / Methodology note
**Status:** v1.0

The leakage-safe feature pipeline for freight forecasting. Implemented in
`ml/features/` (`pipeline.py`, `transforms.py`, `indicators.py`,
`validation.py`). Pure pandas — no Django, no training.

---

## 1. Entry point

`build_features(df, *, value_column="freight_rate", lags=[1,2,3,7],
roll_windows=[3,7,14], pct_periods=[1,7], validate=True)` returns the engineered
frame. `engineered_feature_columns(df)` returns the columns safe to use as model
inputs (excludes grain keys, `freight_rate`, and all future/target columns).

Grain: `["date", "origin", "destination", "vessel_type"]`. Lane:
`["origin", "destination", "vessel_type"]`.

## 2. Engineered features

| Group | Features | Source |
|---|---|---|
| Historical freight | lags 1/2/3/7 of `freight_rate` | `add_lags` |
| Rolling averages | rolling mean over 3/7/14 days | `add_rolling_mean` |
| Volatility | rolling std over 3/7/14 days | `add_rolling_volatility` |
| Momentum | pct-change over 1/7 days | `add_pct_change` |
| Seasonality | day_of_year, week_of_year, quarter, is_monsoon | `add_seasonal_features` |
| Vessel supply | availability trend, supply tightness | `add_vessel_supply_indicators` |
| Demand / ton-mile | import volume, ton-mile proxy | `add_demand_indicators` |
| Port congestion | congestion level, waiting time, congestion pressure | `add_port_congestion_indicators` |
| Weather risk | weather risk, weather_risk_elevated | `add_weather_risk_indicators` |
| Commodity price | `commodity_price` (passthrough from dataset) | dataset |
| Bunker | `bunker_indicator` (passthrough) | dataset |
| Route distance | `route_distance_nm` (passthrough) | dataset |

Each indicator group is tolerant of missing base columns: if a source column is
absent, that indicator is simply not produced (never fabricated).

## 3. Preventing future-data leakage

Leakage is blocked in **three independent ways**:

1. **Target isolation.** `LEAKAGE_PRONE_COLUMNS =
   {future_7d_freight, future_14d_freight, future_30d_freight}`.
   `engineered_feature_columns` excludes these and `freight_rate`. `build_features`
   raises if asked to build features from a future/target column.
2. **Past-only transforms.** Every windowed transform is computed **per lane**
   and **shifted by 1** before rolling, so a row's feature can only ever see data
   strictly before its own `date`. Lags reject `lag < 1`.
3. **Temporal-order validation.** `validate_temporal_order` asserts each lane is
   strictly increasing in time with no duplicate timestamps before any windowed
   operation runs; `time_split` (in `ml/models/splits.py`) splits by global date
   quantiles so the test set is strictly in the future of the train set.

These are exercised by `ml/features/test_leakage.py` (11 tests, all passing).

## 4. Data provenance

The pipeline consumes whatever the dataset builder assembled. In the demo path
(`ml/datasets/example.py` → `build_demo`) all inputs are **SYNTHETIC** generated
series; no real provider data is used. Real ingestion (`apps/ingestion/`) writes
raw observations into the operations models, but the current forecasting demo
runs on synthetic inputs and every downstream forecast is labelled accordingly.
