"""Position sizing.

The roadmap suggests the Kelly criterion. Full Kelly is optimal only if the edge
is *known*; applied to an **estimated** edge it is famously unstable, because
the optimal fraction is roughly linear in an estimate whose error is large. A
modest overestimate of edge produces a large overbet, and Kelly's drawdowns are
brutal even when the edge is real.

Practitioners therefore use fractional Kelly (a quarter to a half) or size to a
volatility target instead. Both are here; vol targeting is the default.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["fractional_kelly", "vol_target_position"]


def vol_target_position(
    signal: pd.Series,
    realized_vol: pd.Series,
    target_vol_annual: float = 0.10,
    max_leverage: float = 1.0,
) -> pd.Series:
    """Scale a signal in ``[-1, 1]`` to a constant volatility target.

    ``realized_vol`` must be the *trailing* annualized volatility known at the
    signal's own timestamp. Using contemporaneous or forward volatility here is
    a subtle and very effective way to leak the future into position sizes.
    """
    vol = realized_vol.replace(0.0, np.nan)
    scale = (target_vol_annual / vol).clip(upper=max_leverage)
    position = (signal * scale).clip(lower=-max_leverage, upper=max_leverage)
    return position.fillna(0.0).rename("position")


def fractional_kelly(
    win_prob: pd.Series,
    payoff_ratio: float = 1.0,
    fraction: float = 0.25,
    max_leverage: float = 1.0,
) -> pd.Series:
    """Fractional Kelly sizing from a predicted win probability.

    For a binary bet the Kelly fraction is ``p - (1 - p) / b``. Multiplying by
    ``fraction`` (0.25 by default) trades a modest amount of long-run growth for
    a large reduction in drawdown and in sensitivity to a mis-estimated ``p``.
    """
    if not 0.0 < fraction <= 1.0:
        raise ValueError(f"fraction must be in (0, 1], got {fraction}")
    if payoff_ratio <= 0.0:
        raise ValueError(f"payoff_ratio must be positive, got {payoff_ratio}")

    kelly = win_prob - (1.0 - win_prob) / payoff_ratio
    position = (fraction * kelly).clip(lower=-max_leverage, upper=max_leverage)
    return position.fillna(0.0).rename("position")
