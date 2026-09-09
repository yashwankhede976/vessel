# Contract & Multi-Voyage Optimization

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Optimization note
**Status:** v1.0

Mathematical optimization for procurement, plus the contract-strategy and
portfolio decision engines.

- Multi-voyage MILP: `apps/decisions/services/optimization.py` →
  `POST /api/v1/optimization/multi-voyage/`
- Spot vs contract: `apps/decisions/services/spot_vs_contract.py` →
  `POST /api/v1/contract-strategy/compare/`
- Contract portfolio: `apps/decisions/services/contract_portfolio.py` →
  `POST /api/v1/contract-strategy/portfolio/`

---

## 1. Multi-voyage optimization (OR-Tools MILP)

The only true **solver** in the platform. A mixed-integer linear program solved
with Google OR-Tools (CBC). OR-Tools is a pinned dependency
(`ortools==9.15.6755`) imported **lazily** inside the service, so the rest of the
app never requires it.

**Decision variables:** `x[v]` = integer number of voyages of candidate `v`
(an origin × vessel-type × contract-strategy lane), `0 ≤ x[v] ≤ max_voyages[v]`.

**Objective:** minimize `Σ cost_per_voyage[v] · x[v]`.

**Constraints:**
- cargo requirement: `Σ capacity[v]·x[v] ≥ required` (within a `± tolerance_pct`
  band when a tolerance is given);
- voyage capacity: `x[v] ≤ max_voyages[v]`;
- vessel–port compatibility: incompatible candidates are dropped before the solve
  (fixed to 0) so an infeasible pairing can never be selected;
- laycan: candidates outside the laycan (`feasible_in_laycan=false`) are dropped;
- contract: optional per-strategy min/max voyage counts;
- destination capacity: optional cap on tonnes into a destination;
- origin: optional per-origin min/max tonnes.

**Output:** `status`, `selected_voyages`, `origin_allocation`,
`destination_allocation`, `vessel_type_allocation`, `contract_strategy_mix`,
`total_cost`, `total_tonnes`, and `estimated_savings` vs a single-cheapest-source
baseline (reported as 0 when no single source can cover the requirement alone).

If the constraints cannot be satisfied (requirement exceeds available capacity,
or conflicting constraints) the service raises and the endpoint returns HTTP 400.

## 2. Spot vs contract

`compare_strategies` evaluates SPOT / SHORT_TERM / MEDIUM_TERM / MULTI_VOYAGE on
expected freight, volatility exposure, flexibility, volume commitment, expected
demurrage, a **risk score** (from the unified risk engine) and total cost. It
recommends the **lowest risk-adjusted cost** strategy
(`cost · (1 + RISK_AVERSION · risk/100)`) and reports `expected_savings` vs the
most expensive alternative with a plain-language reason. All planning assumptions
(period discounts, volatility exposure, flexibility, demurrage multipliers,
risk aversion) are documented constants — no market data is fabricated.

## 3. Contract portfolio

`build_portfolio` recommends a diversified mix across the four strategies for a
multi-month requirement. The blend is chosen by **market regime** (loose /
neutral / tight, from the Market Pressure Index): tighter markets commit more
volume to term contracts; looser markets keep more on spot. It returns the
per-strategy allocation, expected blended cost, `estimated_savings` vs an
all-spot book, and `risk_reduction` (the drop in freight-volatility exposure vs
all-spot). Blend weights and regime thresholds are documented constants.
