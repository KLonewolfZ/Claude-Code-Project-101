"""Backtest engine tests, centred on execution timing.

Roadmap finding 8: a signal formed on the close of bar t cannot be filled at
that same close. These tests pin the convention down so it cannot drift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.backtest.costs import CostModel
from quantlab.backtest.engine import run_backtest
from quantlab.backtest.sizing import fractional_kelly, vol_target_position


@pytest.fixture
def free() -> CostModel:
    """Zero-cost model, to isolate timing effects from cost effects."""
    return CostModel(commission_bps=0.0, spread_bps=0.0, slippage_bps=0.0, borrow_bps_annual=0.0)


@pytest.fixture
def ramp() -> pd.DataFrame:
    """A deterministic bar series with hand-checkable arithmetic."""
    index = pd.bdate_range("2020-01-01", periods=6)
    opens = np.array([100.0, 110.0, 121.0, 133.1, 146.41, 161.051])  # +10% each bar
    return pd.DataFrame(
        {
            "open": opens,
            "high": opens * 1.02,
            "low": opens * 0.98,
            "close": opens * 1.01,
            "volume": np.full(6, 1e6),
        },
        index=index,
    )


def test_next_open_earns_the_open_to_open_return(ramp, free):
    """Position on bar t fills at open(t+1) and earns open(t+1)->open(t+2)."""
    positions = pd.Series(0.0, index=ramp.index)
    positions.iloc[0] = 1.0

    result = run_backtest(ramp, positions, free, execution="next_open")
    # opens rise 10% per bar, so the realised return is exactly 0.10.
    assert result.gross_returns.iloc[0] == pytest.approx(0.10)


def test_same_close_execution_inflates_returns(ramp, free):
    """Quantify the look-ahead the naive convention buys.

    `same_close` fills at the very close that produced the signal. It is exposed
    only so the size of that error can be measured; it must never be the default.
    """
    positions = pd.Series(1.0, index=ramp.index)

    honest = run_backtest(ramp, positions, free, execution="next_open")
    cheating = run_backtest(ramp, positions, free, execution="same_close")

    # Both trade the same rising series, but the cheating variant captures one
    # extra bar of the move by filling in the past.
    assert cheating.net_returns.sum() > honest.net_returns.sum()


def test_zero_signal_produces_zero_pnl(bars, free):
    positions = pd.Series(0.0, index=bars.index)
    result = run_backtest(bars, positions, free)

    assert result.net_returns.abs().sum() == pytest.approx(0.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(1.0)


def test_zero_signal_costs_nothing_even_with_costs(bars):
    """Never trading must never be charged."""
    model = CostModel(commission_bps=5.0, spread_bps=10.0, slippage_bps=5.0)
    result = run_backtest(bars, pd.Series(0.0, index=bars.index), model)
    assert result.costs.sum() == pytest.approx(0.0)


def test_costs_strictly_reduce_returns(bars):
    positions = pd.Series(np.sign(np.sin(np.arange(len(bars)) / 5.0)), index=bars.index)
    expensive = CostModel(commission_bps=10.0, spread_bps=20.0, slippage_bps=10.0)
    free_model = CostModel(
        commission_bps=0.0, spread_bps=0.0, slippage_bps=0.0, borrow_bps_annual=0.0
    )

    with_costs = run_backtest(bars, positions, expensive)
    without = run_backtest(bars, positions, free_model)

    assert with_costs.net_returns.sum() < without.net_returns.sum()
    assert (with_costs.costs >= 0).all()


def test_a_high_turnover_strategy_is_destroyed_by_costs(bars):
    """Flipping every bar cannot survive realistic costs.

    Roadmap pitfall: ignoring transaction costs. A signal alternating each bar
    pays the spread constantly, and no plausible edge covers it.
    """
    alternating = pd.Series(
        [1.0 if i % 2 == 0 else -1.0 for i in range(len(bars))], index=bars.index
    )
    model = CostModel(commission_bps=1.0, spread_bps=5.0, slippage_bps=2.0)
    result = run_backtest(bars, alternating, model)

    assert result.net_returns.sum() < 0.0
    assert result.turnover == pytest.approx(2.0, abs=0.05)


def test_short_position_profits_when_price_falls(free):
    index = pd.bdate_range("2020-01-01", periods=4)
    opens = np.array([100.0, 90.0, 81.0, 72.9])  # -10% per bar
    bars = pd.DataFrame(
        {
            "open": opens,
            "high": opens * 1.01,
            "low": opens * 0.99,
            "close": opens,
            "volume": np.full(4, 1e6),
        },
        index=index,
    )
    positions = pd.Series(0.0, index=index)
    positions.iloc[0] = -1.0

    result = run_backtest(bars, positions, free, execution="next_open")
    assert result.gross_returns.iloc[0] == pytest.approx(0.10)


def test_positions_are_reindexed_and_missing_values_are_flat(bars, free):
    partial = pd.Series(1.0, index=bars.index[:10])
    result = run_backtest(bars, partial, free)

    assert len(result.positions) == len(bars)
    assert result.positions.iloc[10:].abs().sum() == pytest.approx(0.0)


def test_unknown_execution_is_rejected(bars, free):
    with pytest.raises(ValueError, match="unknown execution"):
        run_backtest(bars, pd.Series(0.0, index=bars.index), free, execution="teleport")


def test_equity_curve_compounds_net_returns(bars, free):
    rng = np.random.default_rng(11)
    positions = pd.Series(rng.uniform(-1, 1, len(bars)), index=bars.index)
    result = run_backtest(bars, positions, free)

    expected = float((1.0 + result.net_returns).prod())
    assert result.equity_curve.iloc[-1] == pytest.approx(expected)


# --- sizing ------------------------------------------------------------------


def test_vol_targeting_shrinks_positions_when_vol_rises():
    index = pd.bdate_range("2020-01-01", periods=4)
    signal = pd.Series(1.0, index=index)
    vol = pd.Series([0.10, 0.20, 0.40, 0.80], index=index)

    positions = vol_target_position(signal, vol, target_vol_annual=0.10, max_leverage=1.0)
    assert positions.is_monotonic_decreasing
    assert positions.iloc[0] == pytest.approx(1.0)
    assert positions.iloc[2] == pytest.approx(0.25)


def test_vol_targeting_respects_the_leverage_cap():
    index = pd.bdate_range("2020-01-01", periods=3)
    signal = pd.Series(1.0, index=index)
    vol = pd.Series(0.001, index=index)  # near-zero vol would imply huge leverage
    positions = vol_target_position(signal, vol, target_vol_annual=0.10, max_leverage=1.0)
    assert (positions.abs() <= 1.0).all()


def test_vol_targeting_handles_zero_and_missing_vol():
    index = pd.bdate_range("2020-01-01", periods=3)
    signal = pd.Series(1.0, index=index)
    vol = pd.Series([0.0, np.nan, 0.2], index=index)
    positions = vol_target_position(signal, vol)
    assert positions.notna().all()
    assert positions.iloc[0] == 0.0 and positions.iloc[1] == 0.0


def test_fractional_kelly_is_a_fraction_of_full_kelly():
    index = pd.bdate_range("2020-01-01", periods=3)
    win_prob = pd.Series([0.6, 0.5, 0.4], index=index)

    quarter = fractional_kelly(win_prob, payoff_ratio=1.0, fraction=0.25)
    full = fractional_kelly(win_prob, payoff_ratio=1.0, fraction=1.0)

    assert quarter.iloc[0] == pytest.approx(0.25 * full.iloc[0])
    # p = 0.5 is no edge, so no position.
    assert quarter.iloc[1] == pytest.approx(0.0)
    # p < 0.5 flips the bet short.
    assert quarter.iloc[2] < 0.0


def test_fractional_kelly_rejects_bad_parameters():
    win_prob = pd.Series([0.6], index=pd.bdate_range("2020-01-01", periods=1))
    with pytest.raises(ValueError, match="fraction"):
        fractional_kelly(win_prob, fraction=0.0)
    with pytest.raises(ValueError, match="payoff_ratio"):
        fractional_kelly(win_prob, payoff_ratio=-1.0)
