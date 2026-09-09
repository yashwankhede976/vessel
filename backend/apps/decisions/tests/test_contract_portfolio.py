"""Unit tests for the contract-portfolio engine."""
from decimal import Decimal

import pytest

from apps.decisions.services.contract_portfolio import (
    ContractPortfolioError,
    ContractPortfolioInput,
    build_portfolio,
)


def test_regime_from_market_pressure():
    loose = build_portfolio(ContractPortfolioInput(total_tonnes="100000", spot_freight_per_tonne="20", market_pressure_index=30))
    tight = build_portfolio(ContractPortfolioInput(total_tonnes="100000", spot_freight_per_tonne="20", market_pressure_index=80))
    assert loose.regime == "loose"
    assert tight.regime == "tight"


def test_allocations_sum_to_total():
    r = build_portfolio(ContractPortfolioInput(total_tonnes="600000", spot_freight_per_tonne="22", market_pressure_index=67))
    total = sum(a.tonnes for a in r.allocations)
    assert total == Decimal("600000.00")


def test_portfolio_cheaper_and_less_risky_than_all_spot():
    r = build_portfolio(ContractPortfolioInput(total_tonnes="600000", spot_freight_per_tonne="22", market_pressure_index=67))
    assert r.expected_cost <= r.all_spot_cost
    assert r.estimated_savings >= Decimal("0")
    assert 0.0 < r.risk_reduction < 1.0   # committed tranches reduce exposure


def test_tight_market_commits_more_than_loose():
    loose = build_portfolio(ContractPortfolioInput(total_tonnes="100000", spot_freight_per_tonne="20", market_pressure_index=30))
    tight = build_portfolio(ContractPortfolioInput(total_tonnes="100000", spot_freight_per_tonne="20", market_pressure_index=80))
    spot_loose = next(a for a in loose.allocations if a.strategy == "SPOT")
    spot_tight = next(a for a in tight.allocations if a.strategy == "SPOT")
    assert spot_tight.share < spot_loose.share


def test_no_mpi_defaults_neutral():
    r = build_portfolio(ContractPortfolioInput(total_tonnes="100000", spot_freight_per_tonne="20"))
    assert r.regime == "neutral"


def test_zero_tonnes_raises():
    with pytest.raises(ContractPortfolioError):
        build_portfolio(ContractPortfolioInput(total_tonnes="0", spot_freight_per_tonne="20"))
