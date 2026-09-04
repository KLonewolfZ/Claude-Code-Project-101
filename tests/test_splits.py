"""Purged walk-forward splitter.

These tests encode the correction to the roadmap's central error: k-fold CV on
time series leaks the future. See docs/ROADMAP_ANALYSIS.md finding 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.validation.leakage import LeakageError, assert_split_is_purged
from quantlab.validation.splits import PurgedWalkForwardSplit


@pytest.fixture
def X() -> pd.DataFrame:  # noqa: N802
    return pd.DataFrame({"a": np.arange(1000, dtype=float)})


def test_train_always_precedes_test(X):  # noqa: N803
    """No training index may come from after the test window opens."""
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=0, embargo=0)
    for train_idx, test_idx in splitter.split(X):
        assert train_idx.max() < test_idx.min()


def test_train_and_test_never_overlap(X):  # noqa: N803
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=5, embargo=5)
    for train_idx, test_idx in splitter.split(X):
        assert np.intersect1d(train_idx, test_idx).size == 0


def test_purge_gap_is_respected(X):  # noqa: N803
    """The gap between train and test must be at least `purge` bars."""
    purge = 10
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=purge, embargo=0)
    for train_idx, test_idx in splitter.split(X):
        gap = test_idx.min() - train_idx.max() - 1
        assert gap >= purge, f"gap {gap} < purge {purge}"


def test_zero_purge_leaves_labels_overlapping(X):  # noqa: N803
    """Without purging, a 5-bar label overlaps the test window.

    This is the failure the splitter exists to prevent, asserted directly so the
    guard cannot be silently weakened.
    """
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=0, embargo=0)
    train_idx, test_idx = next(iter(splitter.split(X)))
    with pytest.raises(LeakageError, match="purge"):
        assert_split_is_purged(train_idx, test_idx, horizon=5)


def test_purged_split_passes_the_guard(X):  # noqa: N803
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=5, embargo=5)
    for train_idx, test_idx in splitter.split(X):
        assert_split_is_purged(train_idx, test_idx, horizon=5)  # must not raise


def test_training_window_expands(X):  # noqa: N803
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=5, embargo=0)
    sizes = [len(train) for train, _ in splitter.split(X)]
    assert sizes == sorted(sizes)
    assert len(set(sizes)) > 1, "expanding window should grow between folds"


def test_test_folds_tile_the_tail_without_gaps(X):  # noqa: N803
    """Test folds must be contiguous and cover the data through the final row."""
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=5, embargo=0)
    folds = [test for _, test in splitter.split(X)]
    for earlier, later in zip(folds[:-1], folds[1:], strict=True):
        assert later.min() == earlier.max() + 1
    assert folds[-1].max() == len(X) - 1


def test_min_train_skips_undersized_folds(X):  # noqa: N803
    splitter = PurgedWalkForwardSplit(n_splits=5, purge=0, embargo=0, min_train=400)
    for train_idx, _ in splitter.split(X):
        assert len(train_idx) >= 400


def test_embargo_removes_rows_after_the_test_window():
    """On a rolling window the embargo must exclude post-test rows."""
    frame = pd.DataFrame({"a": np.arange(100, dtype=float)})
    splitter = PurgedWalkForwardSplit(n_splits=3, purge=2, embargo=5)
    for train_idx, test_idx in splitter.split(frame):
        embargo_zone = set(range(test_idx.max() + 1, test_idx.max() + 6))
        assert not (set(train_idx.tolist()) & embargo_zone)


def test_rejects_empty_and_impossible_inputs():
    with pytest.raises(ValueError, match="empty"):
        list(PurgedWalkForwardSplit().split(pd.DataFrame({"a": []})))
    with pytest.raises(ValueError, match="too few"):
        list(PurgedWalkForwardSplit(n_splits=50).split(pd.DataFrame({"a": np.arange(10.0)})))
    with pytest.raises(ValueError, match="n_splits"):
        PurgedWalkForwardSplit(n_splits=0)
    with pytest.raises(ValueError, match="non-negative"):
        PurgedWalkForwardSplit(purge=-1)
