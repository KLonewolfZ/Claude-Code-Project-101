"""Cost model tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.backtest.costs import BPS, CostModel


@pytest.fixture
def model() -> CostModel:
    return CostModel(commission_bps=1.0, spread_bps=2.0, slippage_bps=1.0, borrow_bps_annual=50.0)


def test_turnover_rate_charges_half_the_spread(model):
    """A round trip crosses half the spread on each side."""
    assert model.turnover_cost_rate == pytest.approx((1.0 + 1.0 + 1.0) * BPS)


def test_holding_a_constant_position_incurs_no_turnover_cost(model):
    position = pd.Series([0.5] * 10, index=pd.bdate_range("2020-01-01", periods=10))
    costs = model.turnover_costs(position)
    # Only the opening trade is charged.
    assert costs.iloc[0] == pytest.approx(0.5 * model.turnover_cost_rate)
    assert costs.iloc[1:].sum() == pytest.approx(0.0)


def test_opening_trade_is_not_free(model):
    """diff() leaves the first bar NaN; the initial trade must still be charged."""
    position = pd.Series([1.0, 1.0, 1.0], index=pd.bdate_range("2020-01-01", periods=3))
    assert model.turnover_costs(position).iloc[0] > 0.0


def test_cost_scales_with_size_of_position_change(model):
    index = pd.bdate_range("2020-01-01", periods=3)
    small = model.turnover_costs(pd.Series([0.0, 0.1, 0.1], index=index)).iloc[1]
    large = model.turnover_costs(pd.Series([0.0, 1.0, 1.0], index=index)).iloc[1]
    assert large == pytest.approx(10.0 * small)


def test_flipping_long_to_short_costs_two_units_of_turnover(model):
    index = pd.bdate_range("2020-01-01", periods=2)
    costs = model.turnover_costs(pd.Series([1.0, -1.0], index=index))
    assert costs.iloc[1] == pytest.approx(2.0 * model.turnover_cost_rate)


def test_borrow_is_charged_on_shorts_only(model):
    index = pd.bdate_range("2020-01-01", periods=5)

    short = model.holding_costs(pd.Series([-1.0] * 5, index=index))
    long = model.holding_costs(pd.Series([1.0] * 5, index=index))

    assert (long == 0.0).all(), "a long position pays no borrow"
    expected_daily = 50.0 * BPS / 252
    assert short.iloc[0] == pytest.approx(expected_daily)


def test_annual_borrow_cost_accumulates_to_the_quoted_rate(model):
    """A year fully short should cost about the annual rate."""
    index = pd.bdate_range("2020-01-01", periods=252)
    total = model.holding_costs(pd.Series([-1.0] * 252, index=index)).sum()
    assert total == pytest.approx(50.0 * BPS, rel=1e-9)


def test_flat_position_is_free(model):
    index = pd.bdate_range("2020-01-01", periods=10)
    assert model.total_costs(pd.Series([0.0] * 10, index=index)).sum() == pytest.approx(0.0)


def test_square_root_impact_is_concave():
    """Impact must grow sublinearly in trade size."""
    model = CostModel(
        commission_bps=0.0,
        spread_bps=0.0,
        slippage_bps=0.0,
        borrow_bps_annual=0.0,
        impact_coefficient=0.01,
    )
    index = pd.bdate_range("2020-01-01", periods=2)
    one = model.turnover_costs(pd.Series([0.0, 1.0], index=index)).iloc[1]
    four = model.turnover_costs(pd.Series([0.0, 4.0], index=index)).iloc[1]
    # sqrt(4) / sqrt(1) == 2, not 4.
    assert four == pytest.approx(2.0 * one)


def test_from_config_round_trips(config):
    model = CostModel.from_config(config.costs, config.backtest.periods_per_year)
    assert model.commission_bps == config.costs.commission_bps
    assert model.periods_per_year == config.backtest.periods_per_year


def test_costs_are_never_negative(model):
    rng = np.random.default_rng(0)
    index = pd.bdate_range("2020-01-01", periods=200)
    position = pd.Series(rng.uniform(-1.0, 1.0, 200), index=index)
    assert (model.total_costs(position) >= 0.0).all()
