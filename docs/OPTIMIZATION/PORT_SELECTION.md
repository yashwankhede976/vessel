# Port Selection

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Decision-support note
**Status:** v1.0

Choosing a destination port when the requested East Coast India port is congested
or infeasible. Implemented in `apps/decisions/services/alternative_port.py` and
exposed at `POST /api/v1/alternative-port/`.

---

## 1. Approach

A **deterministic comparator** (not a solver). Given an origin, requested
destination, cargo and (optionally) a vessel, it compares the East Coast India
ports on the factors that drive delivered cost and schedule:

- **Compatibility** — a feasibility gate; incompatible ports are marked
  infeasible and never recommended.
- **Congestion + expected waiting** (`score_port_congestion`, then a documented
  score→waiting-days mapping).
- **Route distance + delivered cost + time** (`compute_voyage_economics`,
  including waiting time as port days).

## 2. Output

`recommended_port` (lowest delivered-cost **feasible** port), the ranked
`alternative_ports` (each with feasibility, congestion, waiting, distance, total
cost, estimated days, notes), and `cost_difference` / `time_difference` of the
recommendation vs the requested port, with a plain-language `reason`. The
requested port is always included so the delta is explicit.

## 3. Missing data

Where a route/distance or congestion signal is absent, the port's cost/time is
left unknown (reported in `notes`) rather than fabricated; such ports cannot be
recommended.
