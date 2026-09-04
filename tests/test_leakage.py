"""Look-ahead bias tests.

The load-bearing tests in this repo. Leakage is not prevented by a convention or
a code review; it is prevented by a test that mechanically corrupts the future
and checks nothing downstream noticed.

Each test here maps to a finding in docs/ROADMAP_ANALYSIS.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.config import FeatureConfig, LabelConfig
from quantlab.features.pipeline import build_features, feature_columns
from quantlab.features.technical import atr, macd, realized_vol, rsi
from quantlab.labeling.targets import forward_return, make_label
from quantlab.validation.leakage import LeakageError, assert_no_future_columns


def test_features_ignore_all_future_data(bars):
    """THE leakage test.

    Corrupt every bar strictly after a cut-off, rebuild features, and assert the
    values at and before the cut-off are bit-identical. Any feature that peeks
    forward - by a stray negative shift, a centred rolling window, a global
    normalisation - changes and fails here.
    """
    cfg = FeatureConfig()
    cut = len(bars) // 2

    clean = build_features(bars, cfg)

    corrupted_bars = bars.copy()
    # Not noise: a violent, structural change, so any dependence shows up.
    corrupted_bars.iloc[cut + 1 :] *= 3.7
    corrupted = build_features(corrupted_bars, cfg)

    for col in feature_columns(clean):
        pd.testing.assert_series_equal(
            clean[col].iloc[: cut + 1],
            corrupted[col].iloc[: cut + 1],
            check_names=False,
            obj=f"feature '{col}' changed when only FUTURE bars were altered",
        )


@pytest.mark.parametrize(
    "fn",
    [
        lambda b: rsi(b["close"], 14),
        lambda b: macd(b["close"])["macd"],
        lambda b: atr(b["high"], b["low"], b["close"], 14),
        lambda b: realized_vol(b["close"], 21),
    ],
    ids=["rsi", "macd", "atr", "realized_vol"],
)
def test_each_indicator_is_causal(bars, fn):
    """Every indicator individually must depend only on the past."""
    cut = len(bars) // 2
    corrupted = bars.copy()
    corrupted.iloc[cut + 1 :] *= 2.5

    pd.testing.assert_series_equal(
        fn(bars).iloc[: cut + 1],
        fn(corrupted).iloc[: cut + 1],
        check_names=False,
    )


def test_forward_return_is_actually_forward(bars):
    """The label must describe the future, and be NaN where that future is unknown."""
    horizon = 5
    fwd = forward_return(bars["close"], horizon)

    assert fwd.iloc[-horizon:].isna().all(), "final rows must have no known forward return"

    close = bars["close"]
    expected = close.iloc[10 + horizon] / close.iloc[10] - 1.0
    assert fwd.iloc[10] == pytest.approx(expected)


def test_label_is_a_return_not_a_price_level(bars):
    """Finding 2: the target must be a return, never a price level."""
    labelled = make_label(bars, LabelConfig(kind="forward_return", horizon=5))
    fwd = labelled["fwd_return"].dropna()

    # A return series is centred near zero and small; a price level is not.
    assert abs(fwd.mean()) < 0.05
    assert fwd.abs().max() < 1.0
    # And it must not track the price level, which is the tautology to avoid.
    assert abs(fwd.corr(bars["close"].loc[fwd.index])) < 0.5


def test_roadmap_price_level_formulation_is_caught(bars):
    """Reconstruct the roadmap's example and assert the guard rejects it.

    The roadmap trains on ``X = Close.shift(1)`` against ``y = Close``. That is a
    near-tautology, and the leakage guard exists to refuse it.
    """
    frame = bars.copy()
    frame["feat_lag1"] = frame["close"].shift(1)  # the roadmap's only feature

    with pytest.raises(LeakageError, match="tautology|correlates"):
        assert_no_future_columns(frame, ["feat_lag1"])


def test_legitimate_features_pass_the_guard(bars):
    """The guard must not fire on ordinary return-based features."""
    built = build_features(bars, FeatureConfig())
    assert_no_future_columns(built, feature_columns(built))  # must not raise


def test_no_feature_is_near_perfectly_correlated_with_the_target(bars):
    """A feature that predicts the label almost perfectly is a leak, not alpha."""
    cfg = FeatureConfig()
    frame = make_label(build_features(bars, cfg), LabelConfig(horizon=5))
    frame = frame.dropna(subset=[*feature_columns(frame), "fwd_return"])

    for col in feature_columns(frame):
        corr = abs(float(frame[col].corr(frame["fwd_return"])))
        assert corr < 0.5, f"feature '{col}' correlates {corr:.3f} with the forward return"


def test_vol_scaled_threshold_uses_only_trailing_volatility(bars):
    """The label threshold itself must not contain future information."""
    cut = len(bars) // 2
    cfg = LabelConfig(kind="forward_return", horizon=5, vol_scaled=True)

    clean = make_label(bars, cfg)
    corrupted_bars = bars.copy()
    corrupted_bars.iloc[cut + 1 :] *= 3.0
    corrupted = make_label(corrupted_bars, cfg)

    # Labels within `horizon` bars of the cut legitimately depend on the future
    # that was altered; everything before that must be untouched.
    safe = cut - cfg.horizon
    pd.testing.assert_series_equal(
        clean["label"].iloc[:safe], corrupted["label"].iloc[:safe], check_names=False
    )


def test_pipeline_predictions_are_out_of_sample(config):
    """Predictions must come from models that never saw their own test fold."""
    from quantlab.pipeline import run_strategy

    run = run_strategy(config)

    assert run.n_folds >= 2
    # The earliest block is never in a test fold, so it must carry no position.
    first_test_row = int(np.argmax(run.signal.to_numpy() != 0.0))
    assert first_test_row > 0, "the initial training block should not be traded"


def test_synthetic_null_strategy_earns_no_real_edge(config):
    """A sanity check on the whole pipeline.

    The synthetic series has no predictable structure, so an honest pipeline must
    report roughly zero. A high Sharpe here would mean the plumbing leaks - this
    is the canary for the entire system.
    """
    from quantlab.pipeline import run_strategy

    run = run_strategy(config)
    sharpe = run.metrics["sharpe_ratio"]

    assert abs(sharpe) < 1.5, (
        f"Sharpe {sharpe:.2f} on structureless synthetic data suggests leakage"
    )
    assert run.metrics["deflated_sharpe"] < 0.95, (
        "a null strategy must not clear the multiple-testing hurdle"
    )
