"""Shared fixtures.

Everything is synthetic and seeded. No test touches the network, so the suite is
deterministic and runs in CI with no credentials.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.config import Config
from quantlab.data.providers import SyntheticProvider


@pytest.fixture
def provider() -> SyntheticProvider:
    return SyntheticProvider(seed=7)


@pytest.fixture
def bars(provider: SyntheticProvider) -> pd.DataFrame:
    """Ten years of daily synthetic OHLCV."""
    return provider.fetch("TEST", "2015-01-01", "2024-12-31")


@pytest.fixture
def short_bars(provider: SyntheticProvider) -> pd.DataFrame:
    """Two years, for tests that do not need a long history."""
    return provider.fetch("TEST", "2022-01-01", "2023-12-31")


@pytest.fixture
def config(tmp_path) -> Config:
    """A config whose cache is redirected into a temp dir."""
    return Config.from_dict(
        {
            "name": "test_strategy",
            "seed": 7,
            "data": {
                "provider": "synthetic",
                "symbols": ["TEST"],
                "start": "2015-01-01",
                "end": "2024-12-31",
                "cache_dir": str(tmp_path / "cache"),
            },
            "validation": {"n_splits": 4, "purge": 5, "embargo": 5, "min_train": 200},
            "label": {"kind": "forward_return", "horizon": 5, "vol_scaled": True},
            "model": {
                "kind": "random_forest",
                "params": {"n_estimators": 25, "max_depth": 3, "random_state": 7},
            },
        }
    )


@pytest.fixture
def flat_returns() -> pd.Series:
    """A constant-return series: zero volatility, so Sharpe is undefined."""
    index = pd.bdate_range("2020-01-01", periods=252)
    return pd.Series(0.001, index=index)


@pytest.fixture
def known_returns() -> pd.Series:
    """Returns with an analytically known Sharpe ratio.

    Mean and standard deviation are set exactly, so the annualized Sharpe is
    ``0.0005 / 0.01 * sqrt(252)`` and can be asserted to tight tolerance.
    """
    rng = np.random.default_rng(0)
    index = pd.bdate_range("2020-01-01", periods=1000)
    raw = rng.normal(0.0, 1.0, len(index))
    # Standardise exactly, then rescale.
    raw = (raw - raw.mean()) / raw.std(ddof=1)
    return pd.Series(raw * 0.01 + 0.0005, index=index)
