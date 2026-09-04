"""Technical indicators, vectorized in pandas.

Implemented directly rather than via TA-Lib on purpose. TA-Lib needs a C library
built and on the linker path, which is a recurring install failure and a poor
dependency for a reproducible research repo (see ``docs/ROADMAP_ANALYSIS.md``
finding 11). These are a few lines each and are unit-tested against known
values.

**Every function here uses only information available at or before each bar.**
Rolling windows are trailing and no function calls ``.shift(-n)``. That is the
invariant the leakage test enforces mechanically.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["atr", "macd", "realized_vol", "rolling_max_distance", "rsi", "true_range"]


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index over a trailing window.

    Uses Wilder's smoothing (an EWM with ``alpha = 1/window``), which is what
    charting packages report; a simple moving average of gains and losses gives
    visibly different values.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # All-gain window: RS is infinite, RSI is 100 by definition.
    out = out.where(avg_loss != 0.0, 100.0)
    out = out.where(~(avg_gain == 0.0) | (avg_loss == 0.0), 0.0)
    return out.rename(f"rsi_{window}")


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    ema_fast = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Wilder's true range: the widest of the three standard spans."""
    prev_close = close.shift(1)
    spans = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    )
    return spans.max(axis=1).rename("true_range")


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range, Wilder-smoothed."""
    tr = true_range(high, low, close)
    return (
        tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean().rename(f"atr_{window}")
    )


def realized_vol(close: pd.Series, window: int = 21, periods_per_year: int = 252) -> pd.Series:
    """Annualized trailing realized volatility of log returns."""
    log_ret = np.log(close).diff()
    return (
        log_ret.rolling(window, min_periods=window).std(ddof=1) * np.sqrt(periods_per_year)
    ).rename(f"realized_vol_{window}")


def rolling_max_distance(close: pd.Series, high: pd.Series, window: int) -> pd.Series:
    """Fractional distance from the trailing ``window``-bar high."""
    return (close / high.rolling(window, min_periods=window).max() - 1.0).rename(
        f"dist_from_max_{window}"
    )
