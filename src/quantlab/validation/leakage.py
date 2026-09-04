"""Runtime leakage assertions.

Look-ahead bias is not something a convention prevents; it is something a test
prevents. These helpers are called from the pipeline and from the test suite so
a violation fails a run rather than quietly inflating a Sharpe ratio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "LeakageError",
    "assert_no_future_columns",
    "assert_split_is_purged",
    "assert_no_label_columns_in_features",
]


class LeakageError(AssertionError):
    """Raised when future information reaches a place it must not."""


def assert_no_future_columns(
    frame: pd.DataFrame, columns: list[str], *, max_abs_corr: float = 0.99
) -> None:
    """Flag a feature that is a near-perfect image of a same-bar price level.

    Catches the roadmap's example directly: a feature equal to ``close.shift(1)``
    is a tautology against a price-level target, not a signal.

    The threshold is a heuristic, but the two populations separate cleanly. On
    this project's synthetic series the roadmap's ``close.shift(1)`` feature
    correlates **0.998** with the contemporaneous close, while the most
    price-coupled legitimate feature (normalised ATR) reaches only **0.65**. On
    a strongly trending real series the tautology climbs above 0.9999. A default
    of 0.99 sits in the wide gap between them.
    """
    if "close" not in frame.columns:
        return
    close = frame["close"]
    for col in columns:
        series = frame[col]
        if not np.issubdtype(series.dtype, np.number):
            continue
        aligned = pd.concat([series, close], axis=1).dropna()
        if len(aligned) < 3 or aligned.iloc[:, 0].std(ddof=0) == 0:
            continue
        corr = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
        if np.isfinite(corr) and abs(corr) >= max_abs_corr:
            raise LeakageError(
                f"feature '{col}' correlates {corr:.6f} with the contemporaneous close. "
                "This is the price-level tautology described in docs/ROADMAP_ANALYSIS.md "
                "(finding 2): predict returns, not levels."
            )


def assert_no_label_columns_in_features(feature_cols: list[str], label_cols: list[str]) -> None:
    """Refuse to train on a feature matrix that contains the label."""
    overlap = sorted(set(feature_cols) & set(label_cols))
    if overlap:
        raise LeakageError(f"label column(s) {overlap} present in the feature matrix")


def assert_split_is_purged(train_idx: np.ndarray, test_idx: np.ndarray, horizon: int) -> None:
    """Assert a train/test split leaves at least ``horizon`` bars of purge.

    With a label spanning ``horizon`` bars, a training row within ``horizon``
    bars of the test window has a label computed from prices inside that window.
    """
    if len(train_idx) == 0 or len(test_idx) == 0:
        return

    overlap = np.intersect1d(train_idx, test_idx)
    if overlap.size:
        raise LeakageError(f"{overlap.size} index/indices appear in both train and test")

    test_start = int(np.min(test_idx))
    before = train_idx[train_idx < test_start]
    if before.size:
        gap = test_start - int(np.max(before)) - 1
        if gap < horizon:
            raise LeakageError(
                f"only {gap} bar(s) of purge before the test fold, need >= {horizon}: "
                f"training labels overlap the test window"
            )
