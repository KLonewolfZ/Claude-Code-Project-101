"""End-to-end research pipeline.

One function, :func:`run_strategy`, wires the whole thing together: fetch ->
features -> labels -> purged walk-forward -> out-of-sample signal -> sizing ->
backtest -> metrics.

The key structural property is that **out-of-sample predictions are assembled
fold by fold and never overlap the training data for their own fold**. The
resulting signal series is what the backtest trades, so the reported Sharpe is
an out-of-sample number rather than an in-sample fit statistic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from quantlab.backtest.costs import CostModel
from quantlab.backtest.engine import BacktestResult, run_backtest
from quantlab.backtest.sizing import vol_target_position
from quantlab.config import Config
from quantlab.data.cache import CachedProvider
from quantlab.data.providers import get_provider
from quantlab.features.pipeline import build_features, feature_columns
from quantlab.labeling.targets import LABEL_COLUMN, RAW_RETURN_COLUMN, make_label
from quantlab.metrics.deflated import deflated_sharpe_ratio
from quantlab.metrics.performance import summarize
from quantlab.models.sklearn_models import build_model
from quantlab.validation.leakage import (
    assert_no_label_columns_in_features,
    assert_split_is_purged,
)
from quantlab.validation.splits import PurgedWalkForwardSplit

__all__ = ["StrategyRun", "load_dataset", "run_strategy"]


@dataclass
class StrategyRun:
    """Everything one strategy run produced."""

    config: Config
    dataset: pd.DataFrame
    signal: pd.Series
    positions: pd.Series
    result: BacktestResult
    metrics: dict[str, float]
    n_folds: int


def load_dataset(cfg: Config, symbol: str | None = None) -> pd.DataFrame:
    """Fetch bars and build the aligned feature/label frame.

    Warm-up NaNs and unrealisable tail labels are dropped **once**, here, so
    features and labels cannot drift out of alignment.
    """
    symbol = symbol or cfg.data.symbols[0]

    provider = get_provider(cfg.data.provider, seed=cfg.seed)
    provider = CachedProvider(provider, cfg.data.cache_dir)
    bars = provider.fetch(symbol, cfg.data.start, cfg.data.end)

    frame = build_features(bars, cfg.features)
    frame = make_label(frame, cfg.label)

    required = feature_columns(frame) + [LABEL_COLUMN, RAW_RETURN_COLUMN]
    return frame.dropna(subset=required).copy()


def run_strategy(cfg: Config, symbol: str | None = None) -> StrategyRun:
    """Run the full pipeline and return the out-of-sample result."""
    dataset = load_dataset(cfg, symbol)
    feat_cols = feature_columns(dataset)
    if not feat_cols:
        raise ValueError("no feature columns were produced")

    assert_no_label_columns_in_features(feat_cols, [LABEL_COLUMN, RAW_RETURN_COLUMN])

    X = dataset[feat_cols]
    y = dataset[LABEL_COLUMN].astype(int)

    splitter = PurgedWalkForwardSplit(
        n_splits=cfg.validation.n_splits,
        purge=max(cfg.validation.purge, cfg.label.horizon),
        embargo=cfg.validation.embargo,
        min_train=cfg.validation.min_train,
    )

    # Out-of-sample probabilities, assembled fold by fold. NaN wherever a bar was
    # never part of any test fold - those bars are simply not traded.
    oos_proba = pd.Series(np.nan, index=dataset.index, name="proba")
    n_folds = 0

    for train_idx, test_idx in splitter.split(X):
        # Belt and braces: the splitter is unit-tested, and the invariant is
        # re-checked here so a future change to either cannot silently leak.
        assert_split_is_purged(train_idx, test_idx, cfg.label.horizon)

        y_train = y.iloc[train_idx]
        if y_train.nunique() < 2:
            # A fold with one class teaches the model nothing and makes
            # predict_proba's column layout ambiguous.
            continue

        model = build_model(cfg.model, seed=cfg.seed)
        model.fit(X.iloc[train_idx], y_train)

        proba = model.predict_proba(X.iloc[test_idx])
        classes = list(getattr(model, "classes_", [0, 1]))
        positive_col = classes.index(1) if 1 in classes else proba.shape[1] - 1

        oos_proba.iloc[test_idx] = proba[:, positive_col]
        n_folds += 1

    if n_folds == 0:
        raise ValueError(
            "no usable folds; try more data, fewer splits, or a lower validation.min_train"
        )

    # Map probability to a signal in [-1, 1]. 0.5 is neutral, so a model with no
    # view takes no position rather than defaulting long.
    signal = ((oos_proba - 0.5) * 2.0).clip(-1.0, 1.0).fillna(0.0).rename("signal")

    vol_col = f"feat_realized_vol_{cfg.features.vol_window}"
    positions = vol_target_position(
        signal,
        dataset[vol_col],
        target_vol_annual=cfg.sizing.target_vol_annual,
        max_leverage=cfg.sizing.max_leverage,
    )

    cost_model = CostModel.from_config(cfg.costs, cfg.backtest.periods_per_year)
    result = run_backtest(dataset, positions, cost_model, execution=cfg.backtest.execution)

    metrics = summarize(
        result.net_returns, cfg.backtest.periods_per_year, positions=result.positions
    )
    # Report the deflated Sharpe alongside the raw one. n_trials is the number of
    # model fits; a real research programme should pass its true trial count.
    metrics["deflated_sharpe"] = deflated_sharpe_ratio(
        result.net_returns, n_trials=max(n_folds, 1), periods_per_year=cfg.backtest.periods_per_year
    )

    return StrategyRun(
        config=cfg,
        dataset=dataset,
        signal=signal,
        positions=positions,
        result=result,
        metrics=metrics,
        n_folds=n_folds,
    )


def save_run(run: StrategyRun, output_dir: str | Path) -> dict[str, Path]:
    """Persist per-bar output and the tearsheet."""
    from quantlab.reporting.tearsheet import build_tearsheet

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = run.config.name

    csv_path = output_dir / f"{name}_backtest.csv"
    run.result.to_frame().to_csv(csv_path)

    png_path = build_tearsheet(
        run.result,
        run.metrics,
        output_dir / f"{name}_tearsheet.png",
        title=f"{name} - out-of-sample, net of costs",
    )
    return {"csv": csv_path, "tearsheet": png_path}
