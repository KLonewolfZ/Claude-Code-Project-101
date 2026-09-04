"""Vectorized backtest with explicit execution timing.

**The timing convention, stated once and enforced in code.** A signal formed
from the close of bar ``t`` cannot be filled at that same close - the close has
already happened when you observe it. Under ``next_open`` the fill is the open
of bar ``t+1``, and the position earns the open-to-open return from ``t+1`` to
``t+2``.

The roadmap's backtesting phase never states an execution assumption. That
omission is where a large share of phantom alpha hides: filling at the same
close that generated the signal is a one-bar look-ahead that can turn a losing
strategy into a spectacular one, especially for mean-reversion signals, which
are precisely predicting the move you are pretending to trade at.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quantlab.backtest.costs import CostModel

__all__ = ["BacktestResult", "run_backtest"]


@dataclass(frozen=True)
class BacktestResult:
    """Per-bar backtest output.

    ``net_returns`` is the series every performance metric is computed from.
    """

    positions: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    net_returns: pd.Series
    equity_curve: pd.Series
    execution: str

    @property
    def turnover(self) -> float:
        """Average absolute position change per bar."""
        return float(self.positions.diff().abs().mean())

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "position": self.positions,
                "gross_return": self.gross_returns,
                "cost": self.costs,
                "net_return": self.net_returns,
                "equity": self.equity_curve,
            }
        )


def _execution_returns(bars: pd.DataFrame, execution: str) -> pd.Series:
    """The return series a position actually earns, given the fill convention."""
    if execution == "next_open":
        # Filled at the open of t+1, so the position earns open(t+1) -> open(t+2).
        open_ = bars["open"]
        return (open_.shift(-2) / open_.shift(-1) - 1.0).rename("exec_return")

    if execution == "next_close":
        close = bars["close"]
        return (close.shift(-2) / close.shift(-1) - 1.0).rename("exec_return")

    if execution == "same_close":
        # Deliberately available, and deliberately documented as wrong: it is the
        # implicit assumption in most naive backtests. Useful only to quantify
        # how much a one-bar look-ahead inflates a result.
        close = bars["close"]
        return (close.shift(-1) / close - 1.0).rename("exec_return")

    raise ValueError(
        f"unknown execution '{execution}'; expected 'next_open', 'next_close' or 'same_close'"
    )


def run_backtest(
    bars: pd.DataFrame,
    positions: pd.Series,
    cost_model: CostModel,
    execution: str = "next_open",
) -> BacktestResult:
    """Run a vectorized backtest.

    Parameters
    ----------
    bars:
        OHLCV indexed by date.
    positions:
        Target position per bar, indexed like ``bars``, in units of NAV. The
        position on bar ``t`` is *decided* on bar ``t`` and *filled* per
        ``execution``.
    cost_model:
        Turnover and holding costs.
    execution:
        Fill convention. See :func:`_execution_returns`.
    """
    positions = positions.reindex(bars.index).fillna(0.0).astype("float64")

    exec_returns = _execution_returns(bars, execution)
    gross = (positions * exec_returns).rename("gross_return")

    costs = cost_model.total_costs(positions)
    net = (gross - costs).rename("net_return")

    # Trailing NaNs come from shifting the execution window past the end of the
    # data; those bars have no realised outcome, so they contribute nothing.
    net_filled = net.fillna(0.0)
    equity = (1.0 + net_filled).cumprod().rename("equity")

    return BacktestResult(
        positions=positions,
        gross_returns=gross,
        costs=costs,
        net_returns=net_filled,
        equity_curve=equity,
        execution=execution,
    )
