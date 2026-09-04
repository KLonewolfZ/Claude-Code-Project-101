# quantlab

A machine-learning quantitative trading research system in Python, built as a
working answer to
[*Comprehensive Roadmap for Building a Python ML Quantitative Hedge Fund Investment Strategy*](docs/source/Quantitative_Trading_Strategy_Roadmap.md).

Two deliverables:

1. **[`docs/ROADMAP_ANALYSIS.md`](docs/ROADMAP_ANALYSIS.md)** — a critical analysis of that roadmap: 11 findings, 2 of them critical, each with a measured demonstration and the module that addresses it. Also rendered as [a PDF](docs/pdf/Roadmap_Analysis.pdf).
2. **This package** — the corrected implementation.

## The short version

The roadmap's phase ordering is sound, and it is better than most introductory
material for naming look-ahead bias and transaction costs at all. But its
cross-validation advice contradicts itself, its only complete code example is a
tautology, and it has no correction for multiple testing — the omission most
likely to turn a promising backtest into a losing live strategy.

**Measured, not asserted.** The roadmap's example predicts today's close from
yesterday's close and scores R² = 0.985. Repeating the input verbatim, with no
model at all, scores **0.985008**. Fitting the model adds **0.000013** of R², and
its directional accuracy is **0.5115** — a coin flip. Reproduce it:

```bash
python scripts/demonstrate_tautology.py
```

## Quickstart

```bash
make setup     # uv venv + editable install
make test      # 123 tests, fully offline
make run       # end-to-end: data -> features -> purged CV -> backtest -> tearsheet
make report    # regenerate the analysis PDF
```

Or via the CLI:

```bash
quantlab data     --config configs/strategies/momentum_rf.yaml
quantlab features --config configs/strategies/momentum_rf.yaml
quantlab run      --config configs/strategies/momentum_rf.yaml
```

## What `make run` prints

```
Strategy: momentum_rf
Provider: synthetic   Execution: next_open
Folds:    4 purged walk-forward (purge=5, embargo=5)

Out-of-sample performance, net of costs:
  Sharpe ratio                          -0.613
  Max drawdown                         -18.72%
  Deflated Sharpe (prob. of skill)       0.000

  Deflated Sharpe 0.000 -> NOT distinguishable from selection bias.
```

**That result is the correct one.** The default provider generates a series with
no predictable structure, so an honest pipeline must earn roughly nothing on it.
A Sharpe of 2.0 here would mean the plumbing leaks. This doubles as the system's
canary — `test_synthetic_null_strategy_earns_no_real_edge` asserts it.

## The four invariants

| Invariant | Enforced by |
|---|---|
| No feature sees the future | `test_features_ignore_all_future_data` — corrupts all bars after a cut-off, asserts earlier feature values are bit-identical |
| Targets are returns, never price levels | `labeling/targets.py`; `assert_no_future_columns` raises on the roadmap's formulation |
| Training is purged and embargoed around every test fold | `PurgedWalkForwardSplit`, re-asserted per fold in the pipeline |
| A signal is filled *after* it is observed | `backtest/engine.py` — close(*t*) → open(*t+1*) |

## Layout

```
src/quantlab/
├── config.py            frozen dataclasses; unknown YAML keys raise
├── data/                providers (synthetic | csv | yfinance), parquet cache,
│                        point-in-time universe
├── features/            vectorized indicators, shift-safe feature matrix
├── labeling/            forward returns, vol-scaled thresholds, triple-barrier
├── validation/          purged walk-forward CV, leakage assertions
├── models/              RF and logistic behind a narrow protocol
├── backtest/            next-open engine, cost model, vol targeting / Kelly
├── metrics/             Sharpe/Sortino/maxDD + deflated Sharpe, PBO, min TRL
└── reporting/           matplotlib tearsheet
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the data flow and the
reasoning behind each boundary.

## Offline by default

The default data provider is a **seeded synthetic generator**, not a vendor API.
This was originally forced by an environment whose egress policy blocks Yahoo
Finance, but it is the better default regardless: tests are deterministic and
need no credentials, leakage tests become possible at all (they require
controlling the data generating process), and there is a null result to measure
against.

For real data on a machine with open egress:

```bash
pip install -e ".[data]"
# then set data.provider: yfinance in your config
```

`CSVProvider` is the bridge for locked-down environments — fetch once where
egress is open, commit the CSVs, stay reproducible.

## Not implemented

Roadmap Phase 7 (paper trading, live execution, scheduled retraining) needs a
broker connection and continuous operation, neither of which can be verified
here. Those are left out rather than shipped as untested scaffolding that looks
functional. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#what-is-deliberately-not-implemented).

## Status

123 tests, 94% coverage, ruff clean, CI on Python 3.11 and 3.12.

---

**This is research tooling, not investment advice.** The synthetic default
produces no real edge by design. Nothing here has been validated against live
markets, and a backtest — however carefully purged — is not evidence that a
strategy will make money.
