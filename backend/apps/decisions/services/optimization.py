"""Multi-voyage procurement optimization (OR-Tools MILP).

Selects a set of candidate voyages to satisfy a cargo requirement at MINIMUM
expected procurement cost, using a mixed-integer linear program solved with
Google OR-Tools (CBC). This is genuine mathematical optimization — the only
module in the platform that solves rather than scores/ranks.

Decision variables
-------------------
For each candidate voyage v (an origin -> destination lane served by a vessel
type under a contract strategy):
    x[v] : integer number of voyages of type v to run (0..max_voyages[v])

Objective
---------
    minimize  sum_v  cost_per_voyage[v] * x[v]
where cost_per_voyage[v] is the delivered cost of one full voyage on v (freight
+ bunker + port + demurrage + ... — supplied by the caller, typically from the
landed-cost / voyage-economics engines).

Constraints
-----------
  * cargo requirement : sum_v capacity[v]*x[v] >= required_tonnes (within a
    tolerance band [required*(1-tol), required*(1+tol)] when a tolerance is given)
  * voyage capacity   : each x[v] <= max_voyages[v] (fleet/berth availability)
  * vessel-port compatibility : incompatible candidates are dropped before the
    solve (their x is fixed to 0) — infeasible pairings never enter the model
  * laycan constraints : candidates whose earliest delivery misses the laycan are
    dropped (feasible_in_laycan flag)
  * contract constraints : optional per-strategy min/max voyage counts
  * destination capacity : optional cap on total tonnes into a destination
  * origin constraints : optional per-origin min/max tonnes

Returns the selected voyages, origin/destination allocation, vessel types,
contract strategy mix, total cost, and estimated savings vs a single-source
baseline. OR-Tools is imported LAZILY so the rest of the app never requires it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

MONEY_QUANT = Decimal("0.01")
DEFAULT_CURRENCY = "USD"


class OptimizationError(ValueError):
    """Raised for invalid optimization inputs or an infeasible/failed solve."""


def _dec(v) -> Optional[Decimal]:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _money(v: Decimal) -> Decimal:
    return v.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class CandidateVoyage:
    """One candidate voyage option the solver may pick (0..max_voyages times).

    cost_per_voyage : delivered cost of ONE full voyage (currency).
    capacity_tonnes : tonnes delivered per voyage.
    """

    id: str
    origin: str
    destination: str
    vessel_type: str
    contract_strategy: str
    cost_per_voyage: Decimal
    capacity_tonnes: Decimal
    max_voyages: int = 1
    feasible_in_laycan: bool = True
    is_compatible: bool = True

    def __post_init__(self):
        self.cost_per_voyage = _dec(self.cost_per_voyage)
        self.capacity_tonnes = _dec(self.capacity_tonnes)


@dataclass
class OptimizationInput:
    required_tonnes: Decimal
    candidates: list[CandidateVoyage]
    tolerance_pct: Decimal = Decimal("0")          # +/- band on required tonnes
    currency: str = DEFAULT_CURRENCY
    # Optional constraints (all keyed by the relevant dimension).
    destination_capacity: dict = field(default_factory=dict)   # dest -> max tonnes
    origin_min_tonnes: dict = field(default_factory=dict)      # origin -> min tonnes
    origin_max_tonnes: dict = field(default_factory=dict)      # origin -> max tonnes
    contract_min_voyages: dict = field(default_factory=dict)   # strategy -> min count
    contract_max_voyages: dict = field(default_factory=dict)   # strategy -> max count
    # Solver time limit (ms).
    time_limit_ms: int = 5000

    def __post_init__(self):
        self.required_tonnes = _dec(self.required_tonnes)
        self.tolerance_pct = _dec(self.tolerance_pct) or Decimal("0")


@dataclass
class SelectedVoyage:
    candidate_id: str
    origin: str
    destination: str
    vessel_type: str
    contract_strategy: str
    voyages: int
    tonnes: Decimal
    cost: Decimal

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "origin": self.origin,
            "destination": self.destination,
            "vessel_type": self.vessel_type,
            "contract_strategy": self.contract_strategy,
            "voyages": self.voyages,
            "tonnes": str(self.tonnes),
            "cost": str(self.cost),
        }


@dataclass
class OptimizationResultDTO:
    status: str                        # "optimal" | "feasible"
    selected_voyages: list[SelectedVoyage]
    origin_allocation: dict            # origin -> tonnes
    destination_allocation: dict       # destination -> tonnes
    vessel_type_allocation: dict       # vessel_type -> tonnes
    contract_strategy_mix: dict        # strategy -> voyages
    total_cost: Decimal
    total_tonnes: Decimal
    estimated_savings: Decimal         # vs single-cheapest-source baseline
    currency: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "selected_voyages": [v.to_dict() for v in self.selected_voyages],
            "origin_allocation": {k: str(v) for k, v in self.origin_allocation.items()},
            "destination_allocation": {
                k: str(v) for k, v in self.destination_allocation.items()
            },
            "vessel_type_allocation": {
                k: str(v) for k, v in self.vessel_type_allocation.items()
            },
            "contract_strategy_mix": self.contract_strategy_mix,
            "total_cost": str(self.total_cost),
            "total_tonnes": str(self.total_tonnes),
            "estimated_savings": str(self.estimated_savings),
            "currency": self.currency,
            "notes": self.notes,
        }


def _baseline_single_source_cost(
    inp: OptimizationInput, feasible: list[CandidateVoyage]
) -> Optional[Decimal]:
    """Cost of meeting the requirement from the SINGLE cheapest-per-tonne feasible
    candidate alone (ignoring multi-source blending), for a savings comparison.
    Returns None if no single candidate can cover the requirement within its
    max_voyages."""
    best: Optional[Decimal] = None
    for c in feasible:
        if c.capacity_tonnes <= 0:
            continue
        # Voyages needed to cover the requirement using only this candidate.
        import math

        needed = math.ceil(float(inp.required_tonnes) / float(c.capacity_tonnes))
        if needed <= c.max_voyages:
            total = _money(c.cost_per_voyage * Decimal(needed))
            if best is None or total < best:
                best = total
    return best


def optimize_multi_voyage(inp: OptimizationInput) -> OptimizationResultDTO:
    """Solve the multi-voyage procurement MILP and return the plan.

    OR-Tools is imported here (lazily) so importing this module — or running the
    rest of the app — never requires the solver to be installed.
    """
    if inp.required_tonnes is None or inp.required_tonnes <= 0:
        raise OptimizationError("required_tonnes must be positive.")

    # Drop infeasible candidates up front (compatibility + laycan) — these never
    # enter the model, so an infeasible pairing can't be selected.
    feasible = [
        c for c in inp.candidates
        if c.is_compatible and c.feasible_in_laycan
        and c.capacity_tonnes and c.capacity_tonnes > 0
        and c.cost_per_voyage is not None and c.cost_per_voyage >= 0
    ]
    if not feasible:
        raise OptimizationError(
            "No feasible candidate voyages (all incompatible, outside laycan, or "
            "missing capacity/cost)."
        )

    try:
        from ortools.linear_solver import pywraplp
    except ImportError as exc:  # pragma: no cover - environment guard
        raise OptimizationError(
            "OR-Tools is not installed; multi-voyage optimization is unavailable. "
            "Install 'ortools' to enable it."
        ) from exc

    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:  # pragma: no cover
        raise OptimizationError("Could not create the CBC solver.")

    # --- decision variables: integer voyage counts per candidate ---
    x = {
        c.id: solver.IntVar(0, int(c.max_voyages), f"x_{c.id}")
        for c in feasible
    }

    # --- cargo requirement (tolerance band) ---
    tol = inp.tolerance_pct / Decimal("100")
    lower = float(inp.required_tonnes * (Decimal("1") - tol))
    upper = float(inp.required_tonnes * (Decimal("1") + tol))
    delivered = solver.Sum(
        float(c.capacity_tonnes) * x[c.id] for c in feasible
    )
    solver.Add(delivered >= lower)
    if tol > 0:
        solver.Add(delivered <= upper)

    # --- destination capacity caps ---
    for dest, cap in inp.destination_capacity.items():
        terms = [
            float(c.capacity_tonnes) * x[c.id] for c in feasible if c.destination == dest
        ]
        if terms:
            solver.Add(solver.Sum(terms) <= float(cap))

    # --- origin min/max tonnes ---
    for origin, mn in inp.origin_min_tonnes.items():
        terms = [float(c.capacity_tonnes) * x[c.id] for c in feasible if c.origin == origin]
        if terms:
            solver.Add(solver.Sum(terms) >= float(mn))
    for origin, mx in inp.origin_max_tonnes.items():
        terms = [float(c.capacity_tonnes) * x[c.id] for c in feasible if c.origin == origin]
        if terms:
            solver.Add(solver.Sum(terms) <= float(mx))

    # --- contract strategy min/max voyage counts ---
    for strat, mn in inp.contract_min_voyages.items():
        terms = [x[c.id] for c in feasible if c.contract_strategy == strat]
        if terms:
            solver.Add(solver.Sum(terms) >= int(mn))
    for strat, mx in inp.contract_max_voyages.items():
        terms = [x[c.id] for c in feasible if c.contract_strategy == strat]
        if terms:
            solver.Add(solver.Sum(terms) <= int(mx))

    # --- objective: minimize total delivered cost ---
    solver.Minimize(
        solver.Sum(float(c.cost_per_voyage) * x[c.id] for c in feasible)
    )

    solver.SetTimeLimit(int(inp.time_limit_ms))
    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL:
        status_str = "optimal"
    elif status == pywraplp.Solver.FEASIBLE:
        status_str = "feasible"
    else:
        raise OptimizationError(
            "No feasible allocation satisfies the constraints (requirement may "
            "exceed available capacity, or constraints conflict)."
        )

    # --- extract the solution ---
    selected: list[SelectedVoyage] = []
    origin_alloc: dict[str, Decimal] = {}
    dest_alloc: dict[str, Decimal] = {}
    vtype_alloc: dict[str, Decimal] = {}
    contract_mix: dict[str, int] = {}
    total_cost = Decimal("0")
    total_tonnes = Decimal("0")

    for c in feasible:
        n = int(round(x[c.id].solution_value()))
        if n <= 0:
            continue
        tonnes = _money(c.capacity_tonnes * Decimal(n))
        cost = _money(c.cost_per_voyage * Decimal(n))
        selected.append(
            SelectedVoyage(
                candidate_id=c.id,
                origin=c.origin,
                destination=c.destination,
                vessel_type=c.vessel_type,
                contract_strategy=c.contract_strategy,
                voyages=n,
                tonnes=tonnes,
                cost=cost,
            )
        )
        origin_alloc[c.origin] = origin_alloc.get(c.origin, Decimal("0")) + tonnes
        dest_alloc[c.destination] = dest_alloc.get(c.destination, Decimal("0")) + tonnes
        vtype_alloc[c.vessel_type] = vtype_alloc.get(c.vessel_type, Decimal("0")) + tonnes
        contract_mix[c.contract_strategy] = contract_mix.get(c.contract_strategy, 0) + n
        total_cost += cost
        total_tonnes += tonnes

    total_cost = _money(total_cost)
    total_tonnes = _money(total_tonnes)

    # --- savings vs single-cheapest-source baseline ---
    baseline = _baseline_single_source_cost(inp, feasible)
    savings = _money(baseline - total_cost) if baseline is not None else Decimal("0")

    notes = []
    if baseline is None:
        notes.append(
            "No single source could cover the requirement alone; savings vs a "
            "single-source baseline are not applicable (reported as 0)."
        )

    return OptimizationResultDTO(
        status=status_str,
        selected_voyages=sorted(selected, key=lambda s: (-s.voyages, s.candidate_id)),
        origin_allocation=origin_alloc,
        destination_allocation=dest_alloc,
        vessel_type_allocation=vtype_alloc,
        contract_strategy_mix=contract_mix,
        total_cost=total_cost,
        total_tonnes=total_tonnes,
        estimated_savings=savings,
        currency=inp.currency,
        notes=notes,
    )
