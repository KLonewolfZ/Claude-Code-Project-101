"""Corrections for multiple testing.

This module addresses what is arguably the roadmap's most serious omission
(finding 4). The roadmap describes an iterative research loop - try features,
try models, tune hyperparameters, compare to a benchmark - and then reports a
Sharpe ratio. But if you try N strategies and report the best one, that Sharpe
is **biased upward by construction**. Even with no real edge whatsoever, the
maximum of N sample Sharpe ratios grows roughly like ``sqrt(2 * log N)`` times
their standard error.

Concretely: try 50 variants on 5 years of daily data with zero true edge, and
the best one shows a Sharpe near 0.9 - which most people would trade.

The tools here quantify that. ``deflated_sharpe_ratio`` returns the probability
that the observed Sharpe exceeds what the *best of N trials* would produce by
luck alone, given the return distribution's skew and kurtosis. Below ~0.95, the
result is not distinguishable from selection bias.

References: Bailey and Lopez de Prado, "The Deflated Sharpe Ratio" (2014);
"The Probability of Backtest Overfitting" (2016).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "deflated_sharpe_ratio",
    "expected_max_sharpe",
    "minimum_track_record_length",
    "probability_of_backtest_overfitting",
]

EULER_MASCHERONI = 0.5772156649015329


def expected_max_sharpe(n_trials: int, sharpe_std: float = 1.0) -> float:
    """Expected maximum Sharpe across ``n_trials`` strategies with *no* edge.

    The benchmark an observed Sharpe must clear to be interesting. Uses the
    standard extreme-value approximation for the maximum of N independent
    standard normals.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    if n_trials == 1:
        return 0.0

    n = float(n_trials)
    # E[max of N standard normals], via the Gumbel approximation.
    term = (1.0 - EULER_MASCHERONI) * stats.norm.ppf(1.0 - 1.0 / n) + (
        EULER_MASCHERONI * stats.norm.ppf(1.0 - 1.0 / (n * np.e))
    )
    return float(sharpe_std * term)


def deflated_sharpe_ratio(
    returns: pd.Series,
    n_trials: int = 1,
    periods_per_year: int = 252,
    benchmark_sharpe: float | None = None,
) -> float:
    """Probability the observed Sharpe reflects skill rather than selection.

    Returns a probability in ``[0, 1]``. Values below ~0.95 mean the result is
    not statistically distinguishable from the best of ``n_trials`` lucky draws.

    The test accounts for non-normality: negative skew and fat tails - both
    typical of trading strategies, especially anything that sells optionality -
    make a given Sharpe *less* impressive, because they widen its sampling
    error.
    """
    r = pd.Series(returns).astype("float64").replace([np.inf, -np.inf], np.nan).dropna()
    n = len(r)
    if n < 3:
        return float("nan")

    sd = float(r.std(ddof=1))
    if not np.isfinite(sd) or sd <= 1e-15:
        return float("nan")

    # Work in per-period units; annualize only at the end for reporting.
    sharpe_per_period = float(r.mean() / sd)
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))  # non-excess kurtosis

    if benchmark_sharpe is None:
        # Deflate against the expected best of n_trials, in per-period units.
        benchmark_per_period = expected_max_sharpe(n_trials) / np.sqrt(periods_per_year)
    else:
        benchmark_per_period = benchmark_sharpe / np.sqrt(periods_per_year)

    # Standard error of the Sharpe estimator under non-normal returns
    # (Bailey & Lopez de Prado 2014, eq. 1).
    variance = (1.0 - skew * sharpe_per_period + (kurt - 1.0) / 4.0 * sharpe_per_period**2) / (
        n - 1
    )
    if variance <= 0.0:
        return float("nan")

    z = (sharpe_per_period - benchmark_per_period) / np.sqrt(variance)
    return float(stats.norm.cdf(z))


def minimum_track_record_length(
    returns: pd.Series,
    target_sharpe: float = 0.0,
    confidence: float = 0.95,
    periods_per_year: int = 252,
) -> float:
    """Periods of track record needed to call the Sharpe significant.

    Answers "how long must this run before I can distinguish it from noise?"
    The answer is routinely years, which is worth knowing before committing
    capital on a two-year backtest.
    """
    r = pd.Series(returns).astype("float64").replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 3:
        return float("nan")

    sd = float(r.std(ddof=1))
    if not np.isfinite(sd) or sd <= 1e-15:
        return float("nan")

    sharpe = float(r.mean() / sd)
    target = target_sharpe / np.sqrt(periods_per_year)
    if sharpe <= target:
        return float("inf")  # no track record length can rescue it

    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))
    z = stats.norm.ppf(confidence)

    numerator = 1.0 - skew * sharpe + (kurt - 1.0) / 4.0 * sharpe**2
    return float(1.0 + numerator * (z / (sharpe - target)) ** 2)


def probability_of_backtest_overfitting(
    trial_returns: pd.DataFrame, n_partitions: int = 8
) -> float:
    """Combinatorially-symmetric PBO across a set of strategy variants.

    Splits the return history into ``n_partitions`` blocks, and over every
    balanced in-sample/out-of-sample recombination asks: does the variant that
    ranked best in-sample land in the bottom half out-of-sample?

    The resulting probability is a direct measure of how much of the selection
    is noise-fitting. Above ~0.5 the selection procedure is worse than random.

    Parameters
    ----------
    trial_returns:
        One column per strategy variant, indexed by date.
    """
    from itertools import combinations

    if trial_returns.shape[1] < 2:
        raise ValueError("PBO needs at least 2 strategy variants to compare")
    if n_partitions % 2 != 0:
        raise ValueError(f"n_partitions must be even, got {n_partitions}")

    frame = trial_returns.dropna()
    n_rows = len(frame)
    if n_rows < n_partitions * 2:
        raise ValueError(
            f"{n_rows} rows is too few for {n_partitions} partitions; need at least "
            f"{n_partitions * 2}"
        )

    blocks = np.array_split(np.arange(n_rows), n_partitions)
    half = n_partitions // 2
    logits = []

    for in_sample_blocks in combinations(range(n_partitions), half):
        oos_blocks = [b for b in range(n_partitions) if b not in in_sample_blocks]
        is_idx = np.concatenate([blocks[b] for b in in_sample_blocks])
        oos_idx = np.concatenate([blocks[b] for b in oos_blocks])

        is_perf = frame.iloc[is_idx].mean()
        oos_perf = frame.iloc[oos_idx].mean()

        best = is_perf.idxmax()
        # Relative rank of the in-sample winner, out of sample.
        rank = float(oos_perf.rank(pct=True)[best])
        rank = min(max(rank, 1e-6), 1.0 - 1e-6)  # keep the logit finite
        logits.append(np.log(rank / (1.0 - rank)))

    return float(np.mean(np.array(logits) <= 0.0))
