"""Economic performance metrics.

The roadmap evaluates models with MSE, R-squared, accuracy and F1. Those measure
*classification* quality, not *money*. A strategy can be right 70% of the time
and lose steadily if the 30% of losses are larger - payoffs in markets are
asymmetric, and directional accuracy is blind to magnitude.

Model selection in this project therefore runs against the metrics in this
module, computed on the net-of-cost return series from the backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "annualized_return",
    "annualized_volatility",
    "calmar_ratio",
    "hit_rate",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
    "summarize",
]


# A return series whose dispersion is below this is constant to within floating
# point error, and its Sharpe ratio is undefined rather than enormous. The std of
# a literally constant pandas Series lands around 1e-19 from summation error, so
# an `== 0.0` test misses it and reports a Sharpe of ~1e16.
_ZERO_VOL_TOL = 1e-15


def _clean(returns: pd.Series) -> pd.Series:
    return pd.Series(returns).astype("float64").replace([np.inf, -np.inf], np.nan).dropna()


def _is_degenerate(dispersion: float) -> bool:
    """True when a dispersion measure is zero to within floating point error."""
    return not np.isfinite(dispersion) or abs(dispersion) <= _ZERO_VOL_TOL


def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Geometric annualized return. Compounding matters; the arithmetic mean overstates."""
    r = _clean(returns)
    if r.empty:
        return float("nan")
    total_growth = float((1.0 + r).prod())
    if total_growth <= 0.0:
        return -1.0  # the account was wiped out
    return total_growth ** (periods_per_year / len(r)) - 1.0


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    r = _clean(returns)
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series, periods_per_year: int = 252, risk_free_rate: float = 0.0
) -> float:
    """Annualized Sharpe ratio, net of a per-period risk-free rate.

    Reported as-is here. See :mod:`quantlab.metrics.deflated` before believing
    it: a Sharpe selected as the best of many trials is biased upward.
    """
    r = _clean(returns)
    if len(r) < 2:
        return float("nan")
    excess = r - risk_free_rate / periods_per_year
    sd = float(excess.std(ddof=1))
    if _is_degenerate(sd):
        return float("nan")
    return float(excess.mean() / sd * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series, periods_per_year: int = 252, target: float = 0.0) -> float:
    """Like Sharpe but penalising only downside deviation."""
    r = _clean(returns)
    if len(r) < 2:
        return float("nan")
    downside = (r - target).clip(upper=0.0)
    dd = float(np.sqrt((downside**2).mean()))
    if _is_degenerate(dd):
        return float("nan")
    return float((r.mean() - target) / dd * np.sqrt(periods_per_year))


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline of the compounded equity curve.

    Returned as a negative number.
    """
    r = _clean(returns)
    if r.empty:
        return float("nan")
    equity = (1.0 + r).cumprod()
    running_peak = equity.cummax()
    return float((equity / running_peak - 1.0).min())


def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized return divided by the absolute max drawdown."""
    mdd = max_drawdown(returns)
    if not np.isfinite(mdd) or mdd == 0.0:
        return float("nan")
    return annualized_return(returns, periods_per_year) / abs(mdd)


def hit_rate(returns: pd.Series) -> float:
    """Fraction of non-zero periods that were positive."""
    r = _clean(returns)
    active = r[r != 0.0]
    if active.empty:
        return float("nan")
    return float((active > 0).mean())


def summarize(
    returns: pd.Series,
    periods_per_year: int = 252,
    positions: pd.Series | None = None,
) -> dict[str, float]:
    """The standard metric block for a return series."""
    out = {
        "annualized_return": annualized_return(returns, periods_per_year),
        "annualized_volatility": annualized_volatility(returns, periods_per_year),
        "sharpe_ratio": sharpe_ratio(returns, periods_per_year),
        "sortino_ratio": sortino_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(returns),
        "calmar_ratio": calmar_ratio(returns, periods_per_year),
        "hit_rate": hit_rate(returns),
        "n_periods": float(len(_clean(returns))),
    }
    if positions is not None:
        out["avg_turnover"] = float(pd.Series(positions).diff().abs().mean())
        out["avg_abs_position"] = float(pd.Series(positions).abs().mean())
    return out
