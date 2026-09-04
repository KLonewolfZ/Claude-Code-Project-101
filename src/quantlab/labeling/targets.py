"""Label construction.

The single most consequential correction this project makes to the source
roadmap lives here. The roadmap's example predicts a **price level** from a
lagged price level. Two things are wrong with that:

1. It is very nearly a tautology. Today's close is within a fraction of a
   percent of yesterday's, so the fit reports R-squared around 0.99 while
   carrying no information a trader could act on.
2. Both series have a unit root. Regressing one non-stationary series on
   another produces a spurious relationship in the Granger-Newbold sense: the
   high R-squared is an artefact of the shared trend, not evidence of a link.

So labels here are always **returns realised strictly after the feature
timestamp**. ``forward_return`` at horizon ``h`` on bar ``t`` is the return from
``t`` to ``t + h``; it is unknowable at ``t``, which is the entire point of
predicting it, and it is why the validation splitter must purge ``h`` bars
around every test fold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.config import LabelConfig
from quantlab.features.technical import realized_vol

__all__ = [
    "LABEL_COLUMN",
    "RAW_RETURN_COLUMN",
    "forward_return",
    "make_label",
    "triple_barrier",
]

LABEL_COLUMN = "label"
RAW_RETURN_COLUMN = "fwd_return"


def forward_return(close: pd.Series, horizon: int) -> pd.Series:
    """Simple return from bar ``t`` to bar ``t + horizon``.

    NaN in the final ``horizon`` rows: that future does not exist yet. Those
    rows must be dropped before training, never filled.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1, got {horizon}")
    return (close.shift(-horizon) / close - 1.0).rename(RAW_RETURN_COLUMN)


def triple_barrier(
    close: pd.Series,
    horizon: int,
    upper: float = 2.0,
    lower: float = 2.0,
    vol_window: int = 21,
) -> pd.Series:
    """Triple-barrier labels: +1 / -1 / 0.

    A fixed-horizon label ignores the path: a position that would have been
    stopped out on day 2 is still scored on its day-5 return. This walks each
    path forward and returns the sign of whichever barrier is touched first, or
    0 if the horizon expires untouched.

    Barrier widths scale with trailing volatility, so a quiet market and a
    turbulent one produce comparably balanced labels rather than the quiet
    regime yielding almost all zeros.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1, got {horizon}")

    daily_vol = realized_vol(close, vol_window) / np.sqrt(252.0)
    values = close.to_numpy(dtype="float64")
    vol = daily_vol.to_numpy(dtype="float64")
    n = len(values)
    out = np.full(n, np.nan)

    for i in range(n):
        if i + horizon >= n or not np.isfinite(vol[i]) or vol[i] <= 0.0:
            continue
        entry = values[i]
        up_level = entry * (1.0 + upper * vol[i])
        dn_level = entry * (1.0 - lower * vol[i])

        label = 0.0
        for j in range(i + 1, i + horizon + 1):
            if values[j] >= up_level:
                label = 1.0
                break
            if values[j] <= dn_level:
                label = -1.0
                break
        out[i] = label

    return pd.Series(out, index=close.index, name=LABEL_COLUMN)


def make_label(bars: pd.DataFrame, cfg: LabelConfig) -> pd.DataFrame:
    """Build label columns per config.

    Always returns both:

    * ``label`` - the binary classification target the model fits;
    * ``fwd_return`` - the realised forward return, kept so the backtest scores
      the *economic* outcome rather than a classification score (finding 3).
    """
    close = bars["close"]
    fwd = forward_return(close, cfg.horizon)

    if cfg.kind == "forward_return":
        if cfg.vol_scaled:
            # The hurdle scales with the volatility that was *knowable at entry*,
            # so the same label means the same thing in a calm regime and a
            # turbulent one, and the threshold itself carries no future
            # information. With a multiple of 0.0 this reduces to predicting
            # direction, which keeps the classes balanced.
            daily_vol = realized_vol(close, 21) / np.sqrt(252.0)
            threshold = daily_vol * np.sqrt(cfg.horizon) * cfg.threshold_vol_multiple
            label = (fwd > threshold).astype("float64")
            label = label.where(fwd.notna() & daily_vol.notna())
        else:
            label = (fwd > 0.0).astype("float64").where(fwd.notna())
        label = label.rename(LABEL_COLUMN)

    elif cfg.kind == "triple_barrier":
        barrier = triple_barrier(
            close, cfg.horizon, upper=cfg.upper_barrier, lower=cfg.lower_barrier
        )
        # Fold to a binary "did the upper barrier come first" target.
        label = (barrier > 0).astype("float64").where(barrier.notna()).rename(LABEL_COLUMN)

    else:
        raise ValueError(
            f"unknown label kind '{cfg.kind}'; expected 'forward_return' or 'triple_barrier'"
        )

    out = bars.copy()
    out[LABEL_COLUMN] = label
    out[RAW_RETURN_COLUMN] = fwd
    return out
