"""Price data providers.

Everything downstream depends on the :class:`PriceProvider` protocol rather than
on a vendor SDK. That buys three things:

1. **Offline determinism.** :class:`SyntheticProvider` generates reproducible
   OHLCV from a seeded generator, so the pipeline, the tests and CI run with no
   network and no API keys. This is not a toy stub - it is the default, and it
   is what makes the leakage tests meaningful, because a leakage test needs to
   control the data generating process.
2. **Vendor churn insulation.** The reference repo this project draws on had to
   carry commented-out compatibility shims when the OpenBB SDK went from v3 to
   v4. A protocol boundary keeps that churn in one file.
3. **Testability of the failure path.** A blocked or rate-limited vendor raises
   a typed error instead of silently returning an empty frame, which is what
   ``yfinance`` does by default and which quietly produces a backtest over zero
   rows.

Every provider returns the same schema: a ``DatetimeIndex`` named ``date`` and
float columns ``open``, ``high``, ``low``, ``close``, ``volume``, sorted
ascending with no duplicate timestamps.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

__all__ = [
    "CSVProvider",
    "DataUnavailableError",
    "OHLCV_COLUMNS",
    "PriceProvider",
    "SyntheticProvider",
    "YFinanceProvider",
    "get_provider",
    "validate_ohlcv",
]

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def _stable_seed(seed: int, symbol: str) -> int:
    """Process-stable seed derived from a base seed and a symbol.

    ``hash()`` on a ``str`` is salted per interpreter process, so it cannot be
    used to derive a reproducible seed. A truncated SHA-256 digest can.
    """
    digest = hashlib.sha256(f"{seed}|{symbol}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2**32)


class DataUnavailableError(RuntimeError):
    """Raised when a provider cannot supply the requested data.

    Deliberately loud. An empty DataFrame flowing into a backtest produces a
    zero-trade result that looks like a valid answer.
    """


def validate_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Enforce the shared OHLCV contract, or raise."""
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise DataUnavailableError(f"{symbol}: provider returned no {missing} column(s)")
    if df.empty:
        raise DataUnavailableError(f"{symbol}: provider returned zero rows")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise DataUnavailableError(
            f"{symbol}: index is {type(df.index).__name__}, not DatetimeIndex"
        )

    out = df.loc[:, OHLCV_COLUMNS].astype("float64").sort_index()
    out = out[~out.index.duplicated(keep="first")]
    out.index.name = "date"
    # Drop any inferred frequency. A parquet or CSV round-trip loses it, so
    # leaving it set would make a cached read compare unequal to a fresh fetch of
    # the same bars. It would also be a false claim: real bar series have holiday
    # gaps and are not a regular business-day frequency.
    out.index.freq = None

    # A high below the low, or a close outside the bar, means the vendor mangled
    # the adjustment. Catch it here rather than as a negative-cost fill later.
    bad = (out["high"] < out["low"]) | (out["close"] > out["high"]) | (out["close"] < out["low"])
    if bool(bad.any()):
        n = int(bad.sum())
        raise DataUnavailableError(f"{symbol}: {n} bar(s) violate low <= close <= high")
    return out


@runtime_checkable
class PriceProvider(Protocol):
    """Anything that can supply daily OHLCV bars for a symbol."""

    name: str

    def fetch(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Return OHLCV bars in ``[start, end]`` obeying the shared contract."""
        ...


class SyntheticProvider:
    """Deterministic synthetic OHLCV from a seeded generator.

    Prices follow geometric Brownian motion with a slow stochastic-volatility
    component, so the series has the two properties that matter for exercising
    this pipeline honestly: it is non-stationary in level (which is what makes
    the roadmap's price-level regression spurious) and it has time-varying
    volatility (which is what vol-scaled labels and vol targeting exist for).

    It has no predictable structure beyond volatility clustering. That is
    intentional: a strategy fitted on it *should* earn roughly zero after costs,
    which makes this a useful null against which a real signal is measured.
    """

    name = "synthetic"

    def __init__(
        self,
        seed: int = 42,
        annual_drift: float = 0.05,
        annual_vol: float = 0.18,
        start_price: float = 100.0,
    ) -> None:
        self.seed = seed
        self.annual_drift = annual_drift
        self.annual_vol = annual_vol
        self.start_price = start_price

    def fetch(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        # Business days only; close enough to an exchange calendar for research.
        index = pd.bdate_range(start=start, end=end, name="date")
        n = len(index)
        if n == 0:
            raise DataUnavailableError(f"{symbol}: empty date range {start}..{end}")

        # Seed per symbol so different symbols are independent but reproducible.
        # NOTE: uses a stable digest rather than the builtin hash(), whose value
        # for str is randomised per process by PYTHONHASHSEED. Using hash() here
        # made the "deterministic" provider return different data on every run.
        rng = np.random.default_rng(_stable_seed(self.seed, symbol))

        dt = 1.0 / 252.0
        # Slow-moving vol factor -> volatility clustering.
        vol_factor = np.exp(0.35 * np.cumsum(rng.normal(0.0, 0.05, n)))
        vol_factor /= vol_factor.mean()
        sigma = self.annual_vol * vol_factor

        shocks = rng.normal(0.0, 1.0, n)
        log_ret = (self.annual_drift - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks
        close = self.start_price * np.exp(np.cumsum(log_ret))

        prev_close = np.concatenate([[self.start_price], close[:-1]])
        gap = rng.normal(0.0, 0.2, n) * sigma * np.sqrt(dt)
        open_ = prev_close * np.exp(gap)

        # Build the bar around the realised open/close so the OHLC invariant holds
        # by construction rather than by clipping after the fact.
        intraday = np.abs(rng.normal(0.0, 1.0, n)) * sigma * np.sqrt(dt)
        hi_base = np.maximum(open_, close)
        lo_base = np.minimum(open_, close)
        high = hi_base * np.exp(intraday)
        low = lo_base * np.exp(-intraday)

        volume = rng.lognormal(mean=15.0, sigma=0.35, size=n)

        frame = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=index,
        )
        return validate_ohlcv(frame, symbol)


class CSVProvider:
    """Load bars from ``<root>/<symbol>.csv``.

    The bridge for real data in a locked-down environment: fetch once somewhere
    with egress, commit or mount the CSVs, and the pipeline is reproducible
    without ever touching a vendor at run time.
    """

    name = "csv"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def fetch(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        path = self.root / f"{symbol}.csv"
        if not path.exists():
            raise DataUnavailableError(f"{symbol}: no CSV at {path}")
        frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
        frame.columns = [str(c).strip().lower() for c in frame.columns]
        frame = validate_ohlcv(frame, symbol)
        return frame.loc[str(start) : str(end)]


class YFinanceProvider:
    """Yahoo Finance via ``yfinance``.

    Works on a machine with open egress. It is *not* exercised by the test suite
    or by CI, both of which run on :class:`SyntheticProvider`, because tests that
    depend on a live vendor are flaky by construction and leak the suite's
    determinism.

    Note that ``yfinance`` returns an empty frame rather than raising when a
    download fails, so the empty case is converted into
    :class:`DataUnavailableError` here.
    """

    name = "yfinance"

    def __init__(self, auto_adjust: bool = True) -> None:
        self.auto_adjust = auto_adjust

    def fetch(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise DataUnavailableError(
                "yfinance is not installed; install the optional extra with "
                "`pip install -e '.[data]'`, or use the synthetic/csv provider"
            ) from exc

        raw = yf.download(
            symbol,
            start=start,
            end=end,
            auto_adjust=self.auto_adjust,
            progress=False,
        )
        if raw is None or len(raw) == 0:
            raise DataUnavailableError(
                f"{symbol}: yfinance returned no rows for {start}..{end}. "
                "Common causes: no network egress to Yahoo, a delisted ticker, "
                "or rate limiting."
            )
        # yfinance returns a column MultiIndex when given a list of tickers, and
        # sometimes for a single ticker too. Flatten to the price field.
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
        raw.index = pd.to_datetime(raw.index)
        raw.index.name = "date"
        return validate_ohlcv(raw, symbol)


def get_provider(kind: str, *, seed: int = 42, root: str | Path | None = None) -> PriceProvider:
    """Resolve a provider by name."""
    key = kind.strip().lower()
    if key == "synthetic":
        return SyntheticProvider(seed=seed)
    if key == "csv":
        if root is None:
            raise ValueError("the csv provider requires a `root` directory")
        return CSVProvider(root)
    if key in {"yfinance", "yahoo"}:
        return YFinanceProvider()
    raise ValueError(f"unknown provider '{kind}'; expected one of: synthetic, csv, yfinance")
