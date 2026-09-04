"""Universe construction with an explicit survivorship-bias guard.

The roadmap's worked example - "predict daily closing prices for S&P 500 stocks"
- is the canonical survivorship trap: backtesting on *today's* index members
bakes in the fact that they survived and outperformed. Firms that blew up or got
delisted are silently absent, so the backtest measures a portfolio nobody could
have selected at the time.

The honest fix is a point-in-time membership table: for each date, the symbols
that were actually in the index *that day*. This module holds that structure and
refuses to pretend a static list is point-in-time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

__all__ = ["StaticUniverse", "PointInTimeUniverse", "load_membership"]


@dataclass(frozen=True)
class StaticUniverse:
    """A fixed symbol list.

    Fine for a single-asset study or a universe that genuinely does not change.
    Its :attr:`is_point_in_time` flag is ``False`` so callers can refuse it for
    an index-membership study rather than discovering the bias in the results.
    """

    symbols: list[str]
    is_point_in_time: bool = False

    def members_on(self, date: pd.Timestamp) -> list[str]:  # noqa: ARG002 - fixed by design
        return list(self.symbols)

    def all_symbols(self) -> list[str]:
        return list(self.symbols)


@dataclass(frozen=True)
class PointInTimeUniverse:
    """Membership intervals: one row per ``(symbol, start, end)``.

    ``end`` may be ``NaT`` for a symbol that is still a member. A symbol that
    was removed keeps its historical interval, so a backtest over that period
    still trades it - which is the entire point.
    """

    membership: pd.DataFrame
    is_point_in_time: bool = True

    def __post_init__(self) -> None:
        required = {"symbol", "start", "end"}
        missing = required - set(self.membership.columns)
        if missing:
            raise ValueError(f"membership table is missing column(s): {sorted(missing)}")

    def members_on(self, date: pd.Timestamp) -> list[str]:
        date = pd.Timestamp(date)
        frame = self.membership
        started = frame["start"] <= date
        not_ended = frame["end"].isna() | (frame["end"] >= date)
        return sorted(frame.loc[started & not_ended, "symbol"].unique().tolist())

    def all_symbols(self) -> list[str]:
        return sorted(self.membership["symbol"].unique().tolist())


def load_membership(path: str | Path) -> PointInTimeUniverse:
    """Load a point-in-time membership CSV with ``symbol,start,end`` columns."""
    frame = pd.read_csv(path, parse_dates=["start", "end"])
    return PointInTimeUniverse(membership=frame)
