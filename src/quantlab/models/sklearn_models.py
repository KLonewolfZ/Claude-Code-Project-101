"""Model construction from config.

Deliberately starts with a shallow random forest and a regularised logistic
regression. On daily bars with a few thousand rows and a signal-to-noise ratio
this low, a deep network has far more capacity than the data can identify - the
roadmap's own advice to "start with simpler models" is right, and the pitfalls
table's overfitting entry is the reason.

The forest is constrained hard by default (``max_depth=3``,
``min_samples_leaf=50``). Those are not arbitrary: an unconstrained forest will
memorise a price series almost perfectly in-sample and tell you nothing.
"""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from quantlab.config import ModelConfig
from quantlab.models.base import Model

__all__ = ["build_model"]


def build_model(cfg: ModelConfig, seed: int = 42) -> Model:
    """Instantiate the configured model."""
    params: dict[str, Any] = dict(cfg.params or {})
    kind = cfg.kind.strip().lower()

    if kind == "random_forest":
        params.setdefault("n_estimators", 200)
        params.setdefault("max_depth", 3)
        params.setdefault("min_samples_leaf", 50)
        params.setdefault("class_weight", "balanced")
        params.setdefault("random_state", seed)
        params.setdefault("n_jobs", 1)  # deterministic ordering over raw speed
        return RandomForestClassifier(**params)

    if kind in {"logistic", "logistic_regression"}:
        params.setdefault("C", 0.1)  # strong shrinkage; the features are collinear
        params.setdefault("max_iter", 2000)
        params.setdefault("class_weight", "balanced")
        params.setdefault("random_state", seed)
        # Scaling is required, not cosmetic: regularisation penalises raw
        # coefficients, so unscaled features get penalised by their units.
        return Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(**params))])

    raise ValueError(f"unknown model kind '{cfg.kind}'; expected 'random_forest' or 'logistic'")
