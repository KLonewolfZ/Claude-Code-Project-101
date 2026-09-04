"""Feature and indicator correctness."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.config import FeatureConfig, LabelConfig
from quantlab.features.pipeline import FEATURE_PREFIX, build_features, feature_columns
from quantlab.features.technical import atr, macd, realized_vol, rsi, true_range
from quantlab.labeling.targets import make_label, triple_barrier


def test_rsi_is_100_when_price_only_rises():
    close = pd.Series(np.arange(1, 60, dtype=float))
    assert rsi(close, 14).iloc[-1] == pytest.approx(100.0)


def test_rsi_is_0_when_price_only_falls():
    close = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert rsi(close, 14).iloc[-1] == pytest.approx(0.0)


def test_rsi_stays_within_bounds(bars):
    values = rsi(bars["close"], 14).dropna()
    assert values.between(0.0, 100.0).all()


def test_macd_is_zero_for_a_constant_series():
    close = pd.Series([100.0] * 100)
    assert macd(close)["macd"].iloc[-1] == pytest.approx(0.0)


def test_macd_is_positive_in_an_uptrend():
    close = pd.Series(np.linspace(100, 200, 200))
    assert macd(close)["macd"].iloc[-1] > 0.0


def test_true_range_uses_the_widest_span():
    """A gap down makes |low - prev_close| the widest of the three spans."""
    high = pd.Series([10.0, 8.0])
    low = pd.Series([9.0, 7.0])
    close = pd.Series([10.0, 7.5])
    # bar 1: high-low = 1.0; |high-prev| = 2.0; |low-prev| = 3.0
    assert true_range(high, low, close).iloc[1] == pytest.approx(3.0)


def test_atr_is_positive(bars):
    assert (atr(bars["high"], bars["low"], bars["close"], 14).dropna() > 0).all()


def test_realized_vol_recovers_a_known_volatility():
    """A series with known daily sigma must annualize to sigma*sqrt(252)."""
    rng = np.random.default_rng(3)
    daily_sigma = 0.01
    log_returns = rng.normal(0.0, daily_sigma, 5000)
    close = pd.Series(100.0 * np.exp(np.cumsum(log_returns)))

    estimate = realized_vol(close, window=250).dropna().mean()
    assert estimate == pytest.approx(daily_sigma * np.sqrt(252), rel=0.1)


def test_every_feature_is_prefixed(bars):
    built = build_features(bars, FeatureConfig())
    assert all(c.startswith(FEATURE_PREFIX) for c in feature_columns(built))
    # Raw price columns must not be model-visible.
    assert "close" not in feature_columns(built)


def test_features_are_finite_after_warmup(bars):
    built = build_features(bars, FeatureConfig())
    cols = feature_columns(built)
    tail = built[cols].iloc[200:]
    assert np.isfinite(tail.to_numpy()).all()


def test_features_are_scale_invariant(bars):
    """Doubling every price must not change a scale-free feature.

    Guards against a raw-level feature sneaking in: those are not comparable
    across assets or across a long sample as the price level drifts.
    """
    cfg = FeatureConfig()
    base = build_features(bars, cfg)
    scaled = build_features(bars * 2.0, cfg)

    for col in feature_columns(base):
        if col.endswith("volume_ratio"):
            continue  # volume is scaled too, so the ratio is unchanged anyway
        pd.testing.assert_series_equal(
            base[col],
            scaled[col],
            check_names=False,
            rtol=1e-9,
            obj=f"feature '{col}' is not scale-invariant",
        )


def test_triple_barrier_labels_are_in_range(bars):
    labels = triple_barrier(bars["close"], horizon=10).dropna()
    assert set(labels.unique()) <= {-1.0, 0.0, 1.0}


def test_triple_barrier_detects_an_upward_breakout():
    """A series that only rises must hit the upper barrier."""
    close = pd.Series(
        100.0
        * np.exp(
            np.cumsum(
                np.concatenate([np.random.default_rng(1).normal(0, 0.01, 100), np.full(20, 0.05)])
            )
        )
    )
    labels = triple_barrier(close, horizon=10).dropna()
    assert labels.iloc[-5:].eq(1.0).all()


def test_label_horizon_must_be_positive(bars):
    with pytest.raises(ValueError, match="horizon"):
        make_label(bars, LabelConfig(horizon=0))


def test_unknown_label_kind_is_rejected(bars):
    with pytest.raises(ValueError, match="unknown label kind"):
        make_label(bars, LabelConfig(kind="crystal_ball"))


def test_labels_are_reasonably_balanced(bars):
    """A vol-scaled threshold should not produce a degenerate all-one-class target."""
    labelled = make_label(bars, LabelConfig(horizon=5, vol_scaled=True))
    rate = labelled["label"].dropna().mean()
    assert 0.2 < rate < 0.8, f"label base rate {rate:.2f} is too imbalanced to learn from"
