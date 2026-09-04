"""Assemble the feature matrix.

Two conventions carry weight here:

* Every feature column is prefixed ``feat_``. Model code selects by that prefix,
  so a raw price column can never be handed to a model by accident - which is
  exactly how the roadmap's example ends up regressing close on lagged close.
* Features are computed from data up to and including bar ``t`` and are used to
  predict a return realised *after* ``t``. The temporal offset lives entirely in
  the label (see :mod:`quantlab.labeling.targets`), so there is one place to
  reason about it instead of two.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.config import FeatureConfig
from quantlab.features.technical import atr, macd, realized_vol, rsi

__all__ = ["FEATURE_PREFIX", "build_features", "feature_columns"]

FEATURE_PREFIX = "feat_"


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Every model-visible column, in stable order."""
    return sorted(c for c in frame.columns if c.startswith(FEATURE_PREFIX))


def build_features(bars: pd.DataFrame, cfg: FeatureConfig) -> pd.DataFrame:
    """Build the feature matrix from OHLCV bars.

    Returns the original bars plus ``feat_*`` columns. Rows are not dropped
    here; warm-up NaNs are removed once, alongside the label, so features and
    labels can never fall out of alignment.
    """
    close, high, low = bars["close"], bars["high"], bars["low"]
    out = bars.copy()

    # Distance from trailing moving averages: a scale-free trend measure.
    for window in cfg.ma_windows:
        ma = close.rolling(window, min_periods=window).mean()
        out[f"{FEATURE_PREFIX}dist_from_ma_{window}"] = close / ma - 1.0

    # Distance from trailing extremes: where in its recent range is price.
    for window in cfg.extreme_windows:
        out[f"{FEATURE_PREFIX}dist_from_max_{window}"] = (
            close / high.rolling(window, min_periods=window).max() - 1.0
        )
        out[f"{FEATURE_PREFIX}dist_from_min_{window}"] = (
            close / low.rolling(window, min_periods=window).min() - 1.0
        )

    # Trailing momentum over several horizons - a return, so already stationary.
    for window in cfg.momentum_windows:
        out[f"{FEATURE_PREFIX}momentum_{window}"] = close.pct_change(window)

    out[f"{FEATURE_PREFIX}rsi_{cfg.rsi_window}"] = rsi(close, cfg.rsi_window)

    macd_frame = macd(close)
    # Normalise MACD by price: the raw level is in currency units and so is not
    # comparable across assets or across time as the price level drifts.
    out[f"{FEATURE_PREFIX}macd_norm"] = macd_frame["macd"] / close
    out[f"{FEATURE_PREFIX}macd_hist_norm"] = macd_frame["macd_hist"] / close

    # ATR as a fraction of price, for the same reason.
    out[f"{FEATURE_PREFIX}atr_norm_{cfg.atr_window}"] = (
        atr(high, low, close, cfg.atr_window) / close
    )

    out[f"{FEATURE_PREFIX}realized_vol_{cfg.vol_window}"] = realized_vol(close, cfg.vol_window)

    # Volume relative to its own trailing average; raw volume trends over years.
    vol_ma = bars["volume"].rolling(cfg.vol_window, min_periods=cfg.vol_window).mean()
    out[f"{FEATURE_PREFIX}volume_ratio"] = bars["volume"] / vol_ma.replace(0.0, np.nan)

    return out
