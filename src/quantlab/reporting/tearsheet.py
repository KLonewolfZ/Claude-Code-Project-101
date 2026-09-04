"""Tearsheet rendering.

Deliberately plain matplotlib rather than a reporting library: the output is a
committed artifact reviewed in a PR, so it needs to render identically in CI
with no browser, no JS runtime and no network.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; must precede the pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from quantlab.backtest.engine import BacktestResult  # noqa: E402

__all__ = ["build_tearsheet", "format_metrics_table"]

_LABELS = {
    "annualized_return": "Annualized return",
    "annualized_volatility": "Annualized volatility",
    "sharpe_ratio": "Sharpe ratio",
    "sortino_ratio": "Sortino ratio",
    "max_drawdown": "Max drawdown",
    "calmar_ratio": "Calmar ratio",
    "hit_rate": "Hit rate",
    "avg_turnover": "Avg daily turnover",
    "avg_abs_position": "Avg absolute position",
    "deflated_sharpe": "Deflated Sharpe (prob. of skill)",
    "n_periods": "Periods",
}
_PERCENT_KEYS = {
    "annualized_return",
    "annualized_volatility",
    "max_drawdown",
    "hit_rate",
}


def format_metrics_table(metrics: dict[str, float]) -> str:
    """Render metrics as an aligned plain-text table."""
    rows = []
    for key, value in metrics.items():
        label = _LABELS.get(key, key.replace("_", " ").capitalize())
        if key in _PERCENT_KEYS:
            rendered = f"{value:>10.2%}"
        elif key == "n_periods":
            rendered = f"{value:>10,.0f}"
        else:
            rendered = f"{value:>10.3f}"
        rows.append(f"  {label:<34}{rendered}")
    return "\n".join(rows)


def build_tearsheet(
    result: BacktestResult,
    metrics: dict[str, float],
    output_path: str | Path,
    title: str = "Strategy tearsheet",
) -> Path:
    """Write an equity-curve / drawdown / position tearsheet to PNG."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    equity = result.equity_curve
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0

    fig, axes = plt.subplots(
        3, 1, figsize=(11, 10), sharex=True, gridspec_kw={"height_ratios": [3, 2, 2]}
    )

    axes[0].plot(equity.index, equity.to_numpy(), linewidth=1.3, color="#1f4e79")
    axes[0].axhline(1.0, color="#999999", linewidth=0.8, linestyle="--")
    axes[0].set_ylabel("Growth of 1.0")
    axes[0].set_title(title, fontsize=13, fontweight="bold", loc="left")
    axes[0].grid(alpha=0.25)

    axes[1].fill_between(drawdown.index, drawdown.to_numpy(), 0.0, color="#b03030", alpha=0.35)
    axes[1].set_ylabel("Drawdown")
    axes[1].grid(alpha=0.25)

    axes[2].plot(
        result.positions.index, result.positions.to_numpy(), linewidth=0.9, color="#2c6e49"
    )
    axes[2].axhline(0.0, color="#999999", linewidth=0.8, linestyle="--")
    axes[2].set_ylabel("Position (NAV)")
    axes[2].set_xlabel("Date")
    axes[2].grid(alpha=0.25)

    summary = "   ".join(
        f"{_LABELS.get(k, k)}: "
        + (f"{metrics[k]:.2%}" if k in _PERCENT_KEYS else f"{metrics[k]:.2f}")
        for k in ("annualized_return", "sharpe_ratio", "max_drawdown")
        if k in metrics and pd.notna(metrics[k])
    )
    fig.text(0.01, 0.005, summary, fontsize=9, color="#333333")
    fig.text(
        0.99,
        0.005,
        f"execution: {result.execution}",
        fontsize=9,
        color="#666666",
        ha="right",
    )

    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(output_path, dpi=130)
    plt.close(fig)
    return output_path
