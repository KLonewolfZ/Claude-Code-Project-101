"""Performance metric tests, mostly known-answer.

Metrics get quoted in decisions about real money, so they are checked against
analytically derived values rather than against whatever the code happened to
produce first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.metrics.deflated import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    minimum_track_record_length,
    probability_of_backtest_overfitting,
)
from quantlab.metrics.performance import (
    annualized_return,
    annualized_volatility,
    calmar_ratio,
    hit_rate,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    summarize,
)


def test_sharpe_matches_the_analytic_value(known_returns):
    """mean 0.0005, sd 0.01 -> Sharpe = 0.0005/0.01 * sqrt(252)."""
    expected = 0.0005 / 0.01 * np.sqrt(252)
    assert sharpe_ratio(known_returns) == pytest.approx(expected, rel=1e-6)


def test_annualized_volatility_matches_the_analytic_value(known_returns):
    assert annualized_volatility(known_returns) == pytest.approx(0.01 * np.sqrt(252), rel=1e-6)


def test_annualized_return_is_geometric_not_arithmetic():
    """+50% then -50% is a 25% loss, not break-even."""
    index = pd.bdate_range("2020-01-01", periods=2)
    returns = pd.Series([0.5, -0.5], index=index)
    total = (1 + returns).prod()
    assert total == pytest.approx(0.75)
    assert annualized_return(returns, periods_per_year=2) == pytest.approx(-0.25)


def test_zero_volatility_gives_undefined_sharpe(flat_returns):
    assert np.isnan(sharpe_ratio(flat_returns))


def test_max_drawdown_known_path():
    """1.0 -> 1.2 -> 0.9: peak 1.2, trough 0.9, drawdown -25%."""
    returns = pd.Series([0.2, -0.25], index=pd.bdate_range("2020-01-01", periods=2))
    assert max_drawdown(returns) == pytest.approx(-0.25)


def test_max_drawdown_is_non_positive():
    rng = np.random.default_rng(1)
    returns = pd.Series(
        rng.normal(0.001, 0.01, 500), index=pd.bdate_range("2020-01-01", periods=500)
    )
    assert max_drawdown(returns) <= 0.0


def test_monotonic_gains_have_no_drawdown():
    returns = pd.Series([0.01] * 100, index=pd.bdate_range("2020-01-01", periods=100))
    assert max_drawdown(returns) == pytest.approx(0.0)


def test_sortino_exceeds_sharpe_when_downside_is_muted():
    """Upside volatility should not be penalised the way downside is."""
    index = pd.bdate_range("2020-01-01", periods=100)
    values = np.array([0.03] * 50 + [-0.005] * 50)
    returns = pd.Series(values, index=index)
    assert sortino_ratio(returns) > sharpe_ratio(returns)


def test_hit_rate_ignores_flat_periods():
    index = pd.bdate_range("2020-01-01", periods=4)
    returns = pd.Series([0.01, -0.01, 0.0, 0.01], index=index)
    assert hit_rate(returns) == pytest.approx(2 / 3)


def test_calmar_is_return_over_drawdown():
    rng = np.random.default_rng(2)
    returns = pd.Series(
        rng.normal(0.0005, 0.01, 756), index=pd.bdate_range("2020-01-01", periods=756)
    )
    expected = annualized_return(returns) / abs(max_drawdown(returns))
    assert calmar_ratio(returns) == pytest.approx(expected)


def test_summarize_returns_the_expected_keys(known_returns):
    out = summarize(known_returns, positions=pd.Series(0.5, index=known_returns.index))
    for key in (
        "annualized_return",
        "annualized_volatility",
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown",
        "calmar_ratio",
        "hit_rate",
        "n_periods",
        "avg_turnover",
        "avg_abs_position",
    ):
        assert key in out


def test_metrics_survive_nan_and_inf():
    index = pd.bdate_range("2020-01-01", periods=6)
    returns = pd.Series([0.01, np.nan, 0.02, np.inf, -0.01, 0.005], index=index)
    assert np.isfinite(sharpe_ratio(returns))
    assert np.isfinite(max_drawdown(returns))


# --- multiple-testing corrections (roadmap finding 4) ------------------------


def test_expected_max_sharpe_grows_with_trial_count():
    """More trials -> a higher bar, even with no real edge anywhere."""
    values = [expected_max_sharpe(n) for n in (2, 10, 100, 1000)]
    assert values == sorted(values)
    assert expected_max_sharpe(1) == 0.0


def test_deflated_sharpe_falls_as_trials_rise(known_returns):
    """The same track record is less impressive after more attempts."""
    few = deflated_sharpe_ratio(known_returns, n_trials=1)
    many = deflated_sharpe_ratio(known_returns, n_trials=500)
    assert few > many


def test_deflated_sharpe_is_a_probability(known_returns):
    for n in (1, 10, 100):
        value = deflated_sharpe_ratio(known_returns, n_trials=n)
        assert 0.0 <= value <= 1.0


def test_deflated_sharpe_rejects_a_pure_noise_strategy():
    """A zero-edge series tried many times must not clear the bar."""
    rng = np.random.default_rng(3)
    index = pd.bdate_range("2015-01-01", periods=1260)
    noise = pd.Series(rng.normal(0.0, 0.01, len(index)), index=index)
    assert deflated_sharpe_ratio(noise, n_trials=100) < 0.95


def test_minimum_track_record_length_is_longer_for_weaker_edges():
    index = pd.bdate_range("2015-01-01", periods=1260)
    rng = np.random.default_rng(4)
    base = rng.normal(0.0, 0.01, len(index))

    strong = pd.Series(base + 0.0008, index=index)
    weak = pd.Series(base + 0.0002, index=index)

    assert minimum_track_record_length(weak) > minimum_track_record_length(strong)


def test_minimum_track_record_length_is_infinite_without_an_edge():
    index = pd.bdate_range("2015-01-01", periods=500)
    losing = pd.Series(-0.0005, index=index) + pd.Series(
        np.random.default_rng(5).normal(0, 0.01, 500), index=index
    )
    assert minimum_track_record_length(losing, target_sharpe=1.0) == float("inf")


def _variant_trials(seed: int, n_variants: int = 12, edge: float = 0.0) -> pd.DataFrame:
    """Variants of a single rule applied to a single price series.

    This is the setup PBO is designed for: the variants share most of their
    return stream and differ only by a hyperparameter, so their performances are
    strongly correlated. Independent columns would instead each carry their own
    persistent spurious drift, which PBO correctly reports as real - a different
    question from the one being asked here.
    """
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2015-01-01", periods=1000)
    base = rng.normal(0.0, 0.01, len(index))
    data = {f"v{i}": base + rng.normal(0.0, 0.004, len(index)) for i in range(n_variants)}
    if edge:
        data["winner"] = base + rng.normal(edge, 0.004, len(index))
    return pd.DataFrame(data, index=index)


def test_pbo_averages_near_one_half_for_edgeless_variants():
    """With no real edge, in-sample rank should not predict out-of-sample rank.

    Averaged over datasets, PBO settles near 0.5 - a coin flip, which is exactly
    what "the winner was selected by noise" means. Any single dataset is far too
    noisy to assert on, so this averages over 20 of them.
    """
    values = [
        probability_of_backtest_overfitting(_variant_trials(seed), n_partitions=6)
        for seed in range(200, 220)
    ]
    assert 0.35 < float(np.mean(values)) < 0.65


def test_pbo_is_low_when_one_variant_is_genuinely_better():
    """A real edge persists out of sample, so PBO must collapse toward zero."""
    values = [
        probability_of_backtest_overfitting(
            _variant_trials(seed, n_variants=8, edge=0.004), n_partitions=6
        )
        for seed in range(300, 310)
    ]
    assert max(values) < 0.2


def test_pbo_separates_real_edge_from_noise():
    """The discriminating property, stated directly."""
    noise = float(
        np.mean(
            [
                probability_of_backtest_overfitting(_variant_trials(s), n_partitions=6)
                for s in range(400, 415)
            ]
        )
    )
    real = float(
        np.mean(
            [
                probability_of_backtest_overfitting(
                    _variant_trials(s, n_variants=8, edge=0.004), n_partitions=6
                )
                for s in range(400, 415)
            ]
        )
    )
    assert real < noise


def test_pbo_rejects_bad_inputs():
    index = pd.bdate_range("2015-01-01", periods=100)
    single = pd.DataFrame({"only": np.zeros(100)}, index=index)
    with pytest.raises(ValueError, match="at least 2"):
        probability_of_backtest_overfitting(single)

    pair = pd.DataFrame({"a": np.zeros(100), "b": np.zeros(100)}, index=index)
    with pytest.raises(ValueError, match="even"):
        probability_of_backtest_overfitting(pair, n_partitions=5)
