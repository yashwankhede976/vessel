# Vessel Selection

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Decision-support note
**Status:** v1.0

How the platform selects and ranks vessels for a cargo. Implemented in
`apps/decisions/services/recommendations.py` (orchestration),
`apps/decisions/services/vessel_suitability.py` (scoring),
`apps/catalog/services/` (compatibility), and exposed at
`POST /api/v1/recommendations/vessels/`.

---

## 1. Approach

Vessel selection is a **transparent, deterministic ranking** — not a solver and
not ML. For a chartering request (origin, destination, cargo tonnes, commodity,
laycan) it composes the existing engines per candidate vessel:

1. **Compatibility** (`evaluate_compatibility`) — a hard gate. Incompatible
   vessels (draft/LOA/beam/DWT/cargo failures) are **excluded automatically** and
   reported under `excluded_vessels`.
2. **Port congestion** (`score_port_congestion`) — destination congestion score.
3. **ETA** (`predict_vessel_eta`) — ETA, P50/P80/P95, delay probability, reasons.
4. **Voyage economics** (`compute_voyage_economics`) — estimated freight,
   demurrage, total cost.
5. **Suitability** (`score_vessel_suitability`) — the 0–100 ranking key.

## 2. Suitability score (0–100)

`vessel_suitability.py` scores each factor to 0..1 (higher = better) and combines
them as a weighted average, **renormalizing weights over available factors** so
missing data neither inflates nor deflates the score. Factors: port
compatibility, cargo capacity, draft/LOA/beam suitability, estimated freight,
ETA reliability, congestion, weather, expected demurrage, fuel efficiency (where
data exists). Every result carries a full factor breakdown (raw value,
normalized, weight, contribution, availability), so the score is explainable.

## 3. Output

`ranked_vessels` (suitability desc), `ranked_vessel_types` (roll-up),
`excluded_vessels` (with reasons), and `notes` for graceful degradation
(missing route/port). Each candidate carries compatibility, estimated freight,
ETA, demurrage, risk, suitability score and estimated total cost.

## 4. What this is NOT

This ranks candidates; it does not *solve* a fleet allocation. Selecting the
cheapest feasible set of voyages across a requirement is the job of the
multi-voyage optimizer (`CONTRACT_OPTIMIZATION.md`).
