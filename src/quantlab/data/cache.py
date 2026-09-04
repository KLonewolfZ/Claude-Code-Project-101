"""On-disk parquet cache for fetched bars.

Keyed by ``(provider, symbol, start, end)`` so a cache entry can never be served
for a different window than it was fetched for - a subtle way to end up
backtesting on the wrong date range.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from quantlab.data.providers import PriceProvider, validate_ohlcv

__all__ = ["CachedProvider", "cache_key"]


def cache_key(provider: str, symbol: str, start: str, end: str) -> str:
    """Stable filename-safe key for one fetch request."""
    digest = hashlib.sha256(f"{provider}|{symbol}|{start}|{end}".encode()).hexdigest()[:12]
    safe_symbol = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in symbol)
    return f"{provider}__{safe_symbol}__{digest}"


class CachedProvider:
    """Wrap a provider with a parquet read-through cache."""

    def __init__(self, inner: PriceProvider, cache_dir: str | Path) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", "unknown")
        self.cache_dir = Path(cache_dir)

    def _path(self, symbol: str, start: str, end: str) -> Path:
        return self.cache_dir / f"{cache_key(self.name, symbol, start, end)}.parquet"

    def fetch(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        path = self._path(symbol, start, end)
        if path.exists():
            return validate_ohlcv(pd.read_parquet(path), symbol)

        frame = self.inner.fetch(symbol, start, end)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then rename, so an interrupted run cannot leave a
        # truncated parquet that later reads as valid-but-short.
        tmp = path.with_suffix(".parquet.tmp")
        frame.to_parquet(tmp)
        tmp.replace(path)
        return frame
