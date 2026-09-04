"""Transaction and holding costs.

The roadmap names commissions, spreads and slippage. Two further costs matter
for anything that shorts, and both are omitted there:

* **Borrow / financing.** A short position pays a stock-loan fee daily. Over a
  year at 50bp on a fully-invested short book that is 0.5% of NAV - larger than
  the edge of many published strategies.
* **Market impact.** Slippage is not a constant; it grows with participation
  rate. The square-root law is the standard approximation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.config import CostConfig

__all__ = ["CostModel"]

BPS = 1e-4


@dataclass(frozen=True)
class CostModel:
    """Per-bar cost model applied to a position series.

    Costs split into two kinds, and conflating them is a common error:

    * **Turnover costs** are paid when the position *changes*, proportional to
      the size of the change.
    * **Holding costs** are paid every bar the position is *open*.
    """

    commission_bps: float = 1.0
    spread_bps: float = 2.0
    slippage_bps: float = 1.0
    borrow_bps_annual: float = 50.0
    periods_per_year: int = 252
    impact_coefficient: float = 0.0

    @classmethod
    def from_config(cls, cfg: CostConfig, periods_per_year: int = 252) -> CostModel:
        return cls(
            commission_bps=cfg.commission_bps,
            spread_bps=cfg.spread_bps,
            slippage_bps=cfg.slippage_bps,
            borrow_bps_annual=cfg.borrow_bps_annual,
            periods_per_year=periods_per_year,
        )

    @property
    def turnover_cost_rate(self) -> float:
        """Cost per unit of turnover.

        Half the quoted spread is paid on each side of a round trip, so a
        position change of 1.0 crosses half the spread once.
        """
        return (self.commission_bps + 0.5 * self.spread_bps + self.slippage_bps) * BPS

    def turnover_costs(self, position: pd.Series) -> pd.Series:
        """Cost charged on each change in position."""
        turnover = position.diff().abs()
        # The opening trade is a real cost; diff() leaves it NaN.
        if len(turnover) > 0:
            turnover.iloc[0] = abs(float(position.iloc[0]))

        cost = turnover * self.turnover_cost_rate

        if self.impact_coefficient > 0.0:
            # Square-root market impact: impact grows sublinearly in trade size.
            cost = cost + self.impact_coefficient * np.sqrt(turnover.clip(lower=0.0))
        return cost.rename("turnover_cost")

    def holding_costs(self, position: pd.Series) -> pd.Series:
        """Borrow cost charged daily on the short side only."""
        short_exposure = (-position).clip(lower=0.0)
        daily_rate = (self.borrow_bps_annual * BPS) / self.periods_per_year
        return (short_exposure * daily_rate).rename("holding_cost")

    def total_costs(self, position: pd.Series) -> pd.Series:
        return (self.turnover_costs(position) + self.holding_costs(position)).rename("cost")
