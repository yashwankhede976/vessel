# Multi-Voyage Procurement Workflow

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Workflow note
**Status:** v1.0

The end-to-end decision chain, and the API endpoints that back each step. Every
engine is deterministic and explainable; only the multi-voyage optimizer uses a
mathematical solver (OR-Tools). The freight forecast is the only ML component.

---

## 1. The chain

```
Cargo requirement
   │
   ▼
Freight forecast ─────────────  GET  /api/v1/forecasts/freight/        (ML, XGBoost; stored rows)
   │                            (bridge: manage.py import_freight_forecasts)
   ▼
Market pressure ──────────────  POST /api/v1/market-pressure/          (0–100 index + bands)
   │
   ▼
Vessel selection ─────────────  POST /api/v1/recommendations/vessels/  (rank; excludes incompatible)
   │   uses ETA  ────────────── POST /api/v1/eta/                       (ETA + P50/P80/P95 + delay prob)
   │   uses congestion ──────── POST /api/v1/congestion/forecast/       (1/3/7/14-day forecast)
   ▼
Port selection ───────────────  POST /api/v1/alternative-port/         (compare East Coast ports)
   │
   ▼
Voyage economics ─────────────  POST /api/v1/voyage-cost/              (total / per-tonne / per-day)
   │
   ▼
Total landed cost ────────────  POST /api/v1/landed-cost/  + /compare/  (per-origin comparison)
   │
   ▼
Contract strategy ────────────  POST /api/v1/contract-strategy/compare/ (spot vs contract)
   │                             POST /api/v1/contract-strategy/portfolio/ (multi-month mix)
   ▼
Procurement optimization ─────  POST /api/v1/optimization/multi-voyage/ (OR-Tools MILP)
   │
   ▼
Fix / Wait timing ────────────  POST /api/v1/fix-wait/                  (FIX_NOW/WAIT/PARTIAL_FIX/MONITOR)

Cross-cutting:
  Risk               ─────────  POST /api/v1/risk/                      (unified 0–100; UNKNOWN stays UNKNOWN)
  Idle-vessel        ─────────  POST /api/v1/idle-vessel/               (rank next-voyage opportunities)
```

## 2. Worked example (multi-origin coal into East Coast India)

1. **Forecast** freight for the candidate lanes (served from stored
   `FreightForecast` rows produced by the ML bridge).
2. **Market pressure** gives a 0–100 tightness index → informs contract strategy.
3. **Vessel selection** ranks feasible vessels per lane, excluding incompatible
   ones, and yields an estimated freight + total cost per candidate.
4. **Port selection** checks whether an alternative East Coast port is cheaper /
   faster if the requested one is congested.
5. **Voyage economics** and **landed cost** turn each feasible lane into a
   delivered cost; `landed-cost/compare/` ranks the five project origins
   (Australia / Indonesia / Mozambique / USA / Russia) for the destination.
6. **Optimization** takes the per-lane delivered costs as candidate voyages and
   solves for the minimum-cost set that meets the requirement subject to
   capacity, compatibility, laycan, contract, destination and origin constraints.
7. **Contract strategy / portfolio** decides how much to fix on spot vs term.
8. **Fix / Wait** decides the timing of committing, using the 7/14/30-day
   forecasts, confidence, availability, congestion, volatility and the deadline.

## 3. Data provenance

All financial figures carry currency and units. Forecasts are labelled FORECAST;
the demo dataset is SYNTHETIC (see `docs/ML/FORECASTING.md`). No real-time
inference runs in the request path — the forecast API serves stored rows, and the
decision engines are deterministic functions of their inputs.

## 4. Notes / limitations

- OR-Tools (`ortools==9.15.6755`) runs in the backend (Python 3.14); it is
  imported lazily so unrelated code and tests do not require it.
- The ML layer runs in a **separate** Python 3.13 virtualenv; Django never
  imports it. Forecasts cross the boundary as a JSON artifact.
- Real market/AIS/weather ingestion exists (`apps/ingestion/`) but the demo
  forecasting path uses synthetic inputs; production accuracy requires real data.
