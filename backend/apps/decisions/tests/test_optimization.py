"""Unit tests for the multi-voyage procurement optimization (OR-Tools MILP)."""
from decimal import Decimal

import pytest

from apps.decisions.services.optimization import (
    CandidateVoyage,
    OptimizationError,
    OptimizationInput,
    optimize_multi_voyage,
)


def _cand(cid, origin, cost, cap, **kw):
    kw.setdefault("vessel_type", "panamax")
    return CandidateVoyage(
        id=cid, origin=origin, destination="Paradip",
        contract_strategy="SPOT", cost_per_voyage=cost, capacity_tonnes=cap, **kw
    )


def test_picks_cheapest_per_tonne_source():
    # Indonesia: 2.6M/75000 = 34.67/t ; Australia: 6.2M/160000 = 38.75/t.
    cands = [
        _cand("AUS", "Australia", "6200000", "160000", vessel_type="capesize", max_voyages=3),
        _cand("IDN", "Indonesia", "2600000", "75000", max_voyages=5),
    ]
    r = optimize_multi_voyage(OptimizationInput(required_tonnes="300000", candidates=cands, tolerance_pct="10"))
    assert r.status in ("optimal", "feasible")
    # All allocation should come from the cheaper Indonesia source.
    assert "Indonesia" in r.origin_allocation
    assert r.total_tonnes >= Decimal("270000")   # within -10% tolerance band


def test_meets_requirement():
    cands = [_cand("IDN", "Indonesia", "2600000", "75000", max_voyages=10)]
    r = optimize_multi_voyage(OptimizationInput(required_tonnes="150000", candidates=cands))
    assert r.total_tonnes >= Decimal("150000")


def test_incompatible_candidate_excluded():
    cands = [
        _cand("BAD", "Russia", "1000000", "160000", is_compatible=False, max_voyages=5),
        _cand("IDN", "Indonesia", "2600000", "75000", max_voyages=5),
    ]
    r = optimize_multi_voyage(OptimizationInput(required_tonnes="150000", candidates=cands))
    assert "Russia" not in r.origin_allocation


def test_laycan_infeasible_excluded():
    cands = [
        _cand("LATE", "Australia", "1000000", "160000", feasible_in_laycan=False, max_voyages=5),
        _cand("IDN", "Indonesia", "2600000", "75000", max_voyages=5),
    ]
    r = optimize_multi_voyage(OptimizationInput(required_tonnes="150000", candidates=cands))
    assert "Australia" not in r.origin_allocation


def test_destination_capacity_constraint():
    cands = [
        CandidateVoyage(id="A", origin="Australia", destination="Paradip",
                        vessel_type="capesize", contract_strategy="SPOT",
                        cost_per_voyage="2000000", capacity_tonnes="80000", max_voyages=5),
        CandidateVoyage(id="B", origin="Indonesia", destination="Haldia",
                        vessel_type="panamax", contract_strategy="SPOT",
                        cost_per_voyage="2600000", capacity_tonnes="75000", max_voyages=5),
    ]
    r = optimize_multi_voyage(OptimizationInput(
        required_tonnes="200000", candidates=cands, tolerance_pct="20",
        destination_capacity={"Paradip": 80000},
    ))
    assert Decimal(str(r.destination_allocation.get("Paradip", "0"))) <= Decimal("80000")


def test_infeasible_all_incompatible_raises():
    cands = [_cand("BAD", "Russia", "1000000", "160000", is_compatible=False)]
    with pytest.raises(OptimizationError):
        optimize_multi_voyage(OptimizationInput(required_tonnes="150000", candidates=cands))


def test_requirement_exceeds_capacity_raises():
    cands = [_cand("IDN", "Indonesia", "2600000", "75000", max_voyages=1)]
    with pytest.raises(OptimizationError):
        optimize_multi_voyage(OptimizationInput(required_tonnes="1000000", candidates=cands))


def test_zero_requirement_raises():
    cands = [_cand("IDN", "Indonesia", "2600000", "75000")]
    with pytest.raises(OptimizationError):
        optimize_multi_voyage(OptimizationInput(required_tonnes="0", candidates=cands))
