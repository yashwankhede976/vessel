# Decision Engine

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Workflow note
**Status:** v1.0

The unified decision layer. One endpoint turns a cargo requirement into a single,
explainable recommendation by **composing the existing engines** — it writes no
new business logic. Implemented in
`backend/apps/decisions/services/decision_engine.py` and exposed at
`POST /api/v1/decision/`.

---

## 1. Endpoint

```
POST /api/v1/decision/
{
  "commodity": "Coal",
  "cargo_quantity": "75000",
  "origin": "Australia",
  "destination": "Paradip",
  "laycan_start": "2026-10-01",
  "laycan_end": "2026-10-10",
  "required_arrival": "2026-10-20",
  "scenario": { "freight_change_pct": 10 }   // optional
}
```

Returns (envelope `data`): `market`, `freight_forecast`, `recommended_vessel`,
`compatibility`, `congestion`, `eta`, `demurrage`, `total_landed_cost`,
`recommended_contract`, `risk`, `timing_decision`
(FIX_NOW / WAIT / PARTIAL_FIX / MONITOR), `expected_savings`, `confidence`,
`ranked_vessels`, `excluded_vessels`, `explainability`, and `notes`.

## 2. Composition (which engine produces what)

```
cargo requirement
   │
   ├─ recommend_vessels (decisions.services.recommendations, OPEN vessels)
   │     ├─ evaluate_compatibility (catalog)        → compatibility + hard filter
   │     ├─ score_port_congestion (operations)      → congestion
   │     ├─ predict_vessel_eta (operations)         → ETA + P50/P80/P95 + delay prob
   │     ├─ compute_voyage_economics (decisions)    → freight, demurrage, total cost
   │     └─ score_vessel_suitability (decisions)    → 0–100 ranking (top = recommended vessel)
   │
   ├─ FreightForecast rows + _market_freight_band   → freight forecast band + model version
   ├─ compute_market_pressure (decisions)           → market pressure index
   ├─ score_risk (decisions.services.risk_engine)   → unified risk score
   ├─ compare_strategies (decisions.spot_vs_contract)→ recommended contract + expected savings
   └─ decide_fix_wait (decisions.services.fix_wait) → FIX_NOW / WAIT / PARTIAL_FIX / MONITOR
```

The top-ranked vessel supplies the vessel/compatibility/ETA/demurrage/cost
sections; the market/risk/contract/timing layers are computed from that context
plus the stored freight forecast. `confidence` is the fix/wait effective
confidence, falling back to the top vessel's suitability fraction.

## 3. Scenarios (stateless what-if)

`scenario` overrides are applied only to the downstream timing/contract/risk
inputs — **stored data is never mutated**:

- `freight_change_pct` — scales the working freight rate and the forecast points
  fed to fix/wait and contract strategy (e.g. +10 → +10%).
- `congestion_score` — an absolute 0–100 override feeding market pressure, risk,
  fix/wait and the reported congestion.
- `vessel_availability` — 0–1 override feeding market pressure and fix/wait.

Every scenario run is a fresh computation from the same real base, so it is safe
to explore repeatedly.

## 4. No invented data

- Freight rate uses the stored `FreightForecast` for the lane; if none exists, a
  clearly-labelled documented planning spot rate is used and a note is added.
- Congestion/weather/ETA/demurrage come from the real per-vessel engine outputs.
- Missing signals stay missing (risk factors go UNKNOWN, ETA is null when there
  is no route distance) — nothing is fabricated.

## 5. Verification

`backend/apps/api/v1/decision/tests.py` exercises the full flow (cargo → forecast
→ vessel → port → cost → contract → recommendation), the presence of every
explainability field, scenario overrides changing the output, and validation.
The frontend Decision page (`/decision`) consumes this endpoint directly.
