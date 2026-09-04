"""Performance metrics, including corrections for multiple testing."""

from quantlab.metrics.deflated import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    minimum_track_record_length,
    probability_of_backtest_overfitting,
)
from quantlab.metrics.performance import (
    annualized_return,
    annualized_volatility,
    calmar_ratio,
    hit_rate,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    summarize,
)

__all__ = [
    "annualized_return",
    "annualized_volatility",
    "calmar_ratio",
    "deflated_sharpe_ratio",
    "expected_max_sharpe",
    "hit_rate",
    "max_drawdown",
    "minimum_track_record_length",
    "probability_of_backtest_overfitting",
    "sharpe_ratio",
    "sortino_ratio",
    "summarize",
]
