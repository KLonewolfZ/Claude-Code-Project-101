"""Provider, cache and universe tests."""

from __future__ import annotations

import pandas as pd
import pytest

from quantlab.data.cache import CachedProvider, cache_key
from quantlab.data.providers import (
    OHLCV_COLUMNS,
    CSVProvider,
    DataUnavailableError,
    PriceProvider,
    SyntheticProvider,
    validate_ohlcv,
)
from quantlab.data.universe import PointInTimeUniverse, StaticUniverse


def test_synthetic_provider_satisfies_the_protocol(provider):
    assert isinstance(provider, PriceProvider)


def test_bars_obey_the_shared_schema(bars):
    assert list(bars.columns) == OHLCV_COLUMNS
    assert isinstance(bars.index, pd.DatetimeIndex)
    assert bars.index.name == "date"
    assert bars.index.is_monotonic_increasing
    assert not bars.index.has_duplicates
    assert bars.notna().all().all()


def test_ohlc_invariant_holds(bars):
    assert (bars["high"] >= bars["low"]).all()
    assert (bars["close"] <= bars["high"]).all()
    assert (bars["close"] >= bars["low"]).all()
    assert (bars["open"] <= bars["high"]).all()
    assert (bars["open"] >= bars["low"]).all()
    assert (bars["volume"] > 0).all()


def test_same_seed_and_symbol_reproduce_exactly():
    a = SyntheticProvider(seed=99).fetch("AAA", "2020-01-01", "2021-01-01")
    b = SyntheticProvider(seed=99).fetch("AAA", "2020-01-01", "2021-01-01")
    pd.testing.assert_frame_equal(a, b)


def test_seed_is_stable_across_processes():
    """Regression test.

    An earlier implementation seeded from the builtin ``hash()`` of the symbol
    string, which Python salts per process. The "deterministic" provider then
    returned different data on every run. The seed must be derived from a stable
    digest instead.
    """
    import subprocess
    import sys

    code = (
        "from quantlab.data.providers import SyntheticProvider;"
        "print(SyntheticProvider(seed=99).fetch('AAA','2020-01-01','2021-01-01')"
        "['close'].iloc[-1])"
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        ).stdout.strip()
        # PYTHONHASHSEED differs between these two child processes.
        for _ in range(2)
    }
    local = str(
        SyntheticProvider(seed=99).fetch("AAA", "2020-01-01", "2021-01-01")["close"].iloc[-1]
    )
    assert len(runs) == 1 and runs.pop() == local


def test_different_symbols_produce_different_series():
    a = SyntheticProvider(seed=99).fetch("AAA", "2020-01-01", "2021-01-01")
    b = SyntheticProvider(seed=99).fetch("BBB", "2020-01-01", "2021-01-01")
    assert not a["close"].equals(b["close"])


def test_empty_range_is_an_error(provider):
    with pytest.raises(DataUnavailableError, match="empty date range"):
        provider.fetch("AAA", "2021-01-05", "2021-01-01")


def test_validate_rejects_a_missing_column():
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0]},
        index=pd.DatetimeIndex(["2020-01-01"]),
    )
    with pytest.raises(DataUnavailableError, match="close"):
        validate_ohlcv(frame, "AAA")


def test_validate_rejects_an_empty_frame():
    """An empty frame must raise, not flow into a zero-trade backtest."""
    frame = pd.DataFrame({c: [] for c in OHLCV_COLUMNS}, index=pd.DatetimeIndex([]))
    with pytest.raises(DataUnavailableError, match="zero rows"):
        validate_ohlcv(frame, "AAA")


def test_validate_rejects_an_impossible_bar():
    frame = pd.DataFrame(
        {"open": [10.0], "high": [9.0], "low": [11.0], "close": [10.0], "volume": [1.0]},
        index=pd.DatetimeIndex(["2020-01-01"]),
    )
    with pytest.raises(DataUnavailableError, match="low <= close <= high"):
        validate_ohlcv(frame, "AAA")


# --- cache -------------------------------------------------------------------


def test_cache_key_distinguishes_every_field():
    base = cache_key("synthetic", "AAA", "2020-01-01", "2021-01-01")
    assert base != cache_key("yfinance", "AAA", "2020-01-01", "2021-01-01")
    assert base != cache_key("synthetic", "BBB", "2020-01-01", "2021-01-01")
    assert base != cache_key("synthetic", "AAA", "2020-01-02", "2021-01-01")
    assert base != cache_key("synthetic", "AAA", "2020-01-01", "2021-01-02")


def test_cache_key_is_filename_safe():
    assert "/" not in cache_key("synthetic", "BRK/B", "2020-01-01", "2021-01-01")


def test_cache_round_trips(tmp_path, provider):
    cached = CachedProvider(provider, tmp_path / "cache")

    first = cached.fetch("AAA", "2020-01-01", "2021-01-01")
    assert list((tmp_path / "cache").glob("*.parquet"))

    second = cached.fetch("AAA", "2020-01-01", "2021-01-01")
    pd.testing.assert_frame_equal(first, second)


def test_cache_does_not_serve_a_different_window(tmp_path, provider):
    cached = CachedProvider(provider, tmp_path / "cache")
    one = cached.fetch("AAA", "2020-01-01", "2020-06-01")
    two = cached.fetch("AAA", "2020-01-01", "2021-01-01")
    assert len(two) > len(one)


# --- CSV provider ------------------------------------------------------------


def test_csv_provider_round_trips(tmp_path, bars):
    bars.to_csv(tmp_path / "AAA.csv")
    loaded = CSVProvider(tmp_path).fetch("AAA", "2015-01-01", "2024-12-31")
    pd.testing.assert_frame_equal(loaded, bars)


def test_csv_provider_reports_a_missing_file(tmp_path):
    with pytest.raises(DataUnavailableError, match="no CSV"):
        CSVProvider(tmp_path).fetch("NOPE", "2020-01-01", "2021-01-01")


# --- universe ----------------------------------------------------------------


def test_static_universe_is_flagged_as_not_point_in_time():
    """The survivorship guard: a static list must admit what it is."""
    universe = StaticUniverse(symbols=["AAA", "BBB"])
    assert universe.is_point_in_time is False
    assert universe.members_on(pd.Timestamp("2020-01-01")) == ["AAA", "BBB"]


def test_point_in_time_universe_excludes_a_delisted_member():
    membership = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "start": pd.to_datetime(["2010-01-01", "2010-01-01", "2018-01-01"]),
            "end": pd.to_datetime([None, "2015-06-30", None]),
        }
    )
    universe = PointInTimeUniverse(membership)

    # BBB was still a member in 2012 and must be tradable then - the whole point
    # of point-in-time membership.
    assert universe.members_on(pd.Timestamp("2012-01-01")) == ["AAA", "BBB"]
    # By 2020 it is gone and CCC has joined.
    assert universe.members_on(pd.Timestamp("2020-01-01")) == ["AAA", "CCC"]
    assert universe.is_point_in_time is True


def test_point_in_time_universe_requires_the_right_columns():
    with pytest.raises(ValueError, match="missing column"):
        PointInTimeUniverse(pd.DataFrame({"symbol": ["AAA"]}))
