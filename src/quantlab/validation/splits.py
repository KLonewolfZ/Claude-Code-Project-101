"""Purged, embargoed walk-forward cross-validation.

This module exists because of the roadmap's central methodological error. It
advises "apply k-fold cross-validation, ensuring no look-ahead bias" and then
recommends ``train_test_split`` and ``GridSearchCV``. Standard k-fold
*shuffles*; ``GridSearchCV`` defaults to ``KFold``. Training on shuffled
financial time series **is** look-ahead bias - the model sees the future and
reports an out-of-sample score that cannot be reproduced live.

``TimeSeriesSplit`` fixes the ordering but not the whole problem. With a label
that spans ``h`` bars, the last ``h`` training labels are computed from prices
that fall inside the test window. Two defences:

**Purge** - drop training rows whose label horizon overlaps the test window.
**Embargo** - additionally drop training rows immediately *after* the test
window, because serial correlation in features means a bar just after the test
fold still carries information about it.

Reference: Lopez de Prado, *Advances in Financial Machine Learning*, ch. 7.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np

__all__ = ["PurgedWalkForwardSplit"]


class PurgedWalkForwardSplit:
    """Expanding-window walk-forward splits with purging and embargo.

    Parameters
    ----------
    n_splits:
        Number of sequential test folds.
    purge:
        Bars dropped from the end of the training window. Must be at least the
        label horizon, or train and test labels overlap.
    embargo:
        Bars dropped from training immediately after the test window.
    min_train:
        Minimum training rows required for a fold to be emitted. Folds with less
        history are skipped rather than fitted on a handful of rows.

    Yields ``(train_idx, test_idx)`` positional index arrays, matching the
    scikit-learn splitter interface so it drops into existing code.
    """

    def __init__(
        self,
        n_splits: int = 5,
        purge: int = 0,
        embargo: int = 0,
        min_train: int = 0,
    ) -> None:
        if n_splits < 1:
            raise ValueError(f"n_splits must be >= 1, got {n_splits}")
        if purge < 0 or embargo < 0:
            raise ValueError("purge and embargo must be non-negative")
        self.n_splits = n_splits
        self.purge = purge
        self.embargo = embargo
        self.min_train = min_train

    def get_n_splits(self, X=None, y=None, groups=None) -> int:  # noqa: ARG002, N803
        return self.n_splits

    def split(self, X, y=None, groups=None) -> Iterator[tuple[np.ndarray, np.ndarray]]:  # noqa: ARG002, N803
        n_samples = len(X)
        if n_samples == 0:
            raise ValueError("cannot split an empty dataset")

        # Reserve the tail for test folds; the first block seeds the initial train set.
        fold_size = n_samples // (self.n_splits + 1)
        if fold_size < 1:
            raise ValueError(
                f"{n_samples} samples is too few for {self.n_splits} splits "
                f"(each fold would hold fewer than 1 sample)"
            )

        indices = np.arange(n_samples)

        for fold in range(self.n_splits):
            test_start = fold_size * (fold + 1)
            # The final fold absorbs the remainder so no rows are silently dropped.
            test_end = n_samples if fold == self.n_splits - 1 else fold_size * (fold + 2)

            test_idx = indices[test_start:test_end]
            if len(test_idx) == 0:
                continue

            # Purge: training stops `purge` bars before the test window opens, so
            # no training label can be computed from a price inside that window.
            train_end = max(0, test_start - self.purge)
            train_idx = indices[:train_end]

            # Embargo: on an expanding window there is nothing after the test
            # fold to include, but keep the logic explicit so it stays correct if
            # this is ever changed to a rolling window.
            if self.embargo > 0:
                embargo_end = min(n_samples, test_end + self.embargo)
                embargoed = set(range(test_end, embargo_end))
                if embargoed:
                    train_idx = np.array([i for i in train_idx if i not in embargoed], dtype=int)

            if len(train_idx) < max(1, self.min_train):
                continue

            yield train_idx, test_idx
