"""The model interface the pipeline depends on.

Kept to ``fit`` / ``predict_proba`` so a scikit-learn estimator satisfies it as
is, while leaving room for a hand-rolled or deep-learning model later without
touching the pipeline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

__all__ = ["Model"]


@runtime_checkable
class Model(Protocol):
    def fit(self, X, y):  # noqa: N803
        """Fit on a feature matrix and target vector."""
        ...

    def predict_proba(self, X) -> np.ndarray:  # noqa: N803
        """Return class probabilities with shape ``(n_samples, n_classes)``."""
        ...
