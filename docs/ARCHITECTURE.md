# Architecture

## Design principle

Every structural decision here traces to a specific failure mode documented in
[`ROADMAP_ANALYSIS.md`](ROADMAP_ANALYSIS.md). The organising idea is that the
errors which destroy quant research are **silent** — a leaky backtest does not
crash, it reports a great Sharpe ratio. So wherever a mistake can be caught
mechanically, it is caught by a test rather than left to reviewer discipline.

## Data flow

```
                 configs/*.yaml
                       │
                       ▼
              ┌─────────────────┐
              │   config.py     │  frozen dataclasses; unknown keys raise
              └────────┬────────┘
                       ▼
   ┌───────────────────────────────────────┐
   │ data/providers.py   PriceProvider      │  Synthetic (default) │ CSV │ YFinance
   │ data/cache.py       parquet cache      │  keyed by provider+symbol+window
   │ data/universe.py    point-in-time      │  survivorship guard
   └───────────────────┬───────────────────┘
                       │  OHLCV, validated: low <= close <= high, no dupes
                       ▼
   ┌───────────────────────────────────────┐
   │ features/technical.py  indicators      │  trailing windows only
   │ features/pipeline.py   feat_* matrix   │  every column backward-looking
   └───────────────────┬───────────────────┘
                       ▼
   ┌───────────────────────────────────────┐
   │ labeling/targets.py                    │  forward RETURNS, never levels
   └───────────────────┬───────────────────┘
                       ▼
   ┌───────────────────────────────────────┐
   │ validation/splits.py  PurgedWalkForward│  purge + embargo
   │ validation/leakage.py assertions       │  raises on future contamination
   └───────────────────┬───────────────────┘
                       ▼
   ┌───────────────────────────────────────┐
   │ models/  fit per fold, predict its own │  out-of-sample probabilities only
   └───────────────────┬───────────────────┘
                       ▼
   ┌───────────────────────────────────────┐
   │ backtest/sizing.py   vol target        │  trailing vol, known at signal time
   │ backtest/engine.py   next-open fill    │  signal close(t) -> fill open(t+1)
   │ backtest/costs.py    turnover+holding  │  commission, spread, slippage, borrow
   └───────────────────┬───────────────────┘
                       ▼
   ┌───────────────────────────────────────┐
   │ metrics/performance.py  economic       │  Sharpe, Sortino, maxDD, Calmar
   │ metrics/deflated.py     multiple-test  │  deflated Sharpe, PBO, min TRL
   │ reporting/tearsheet.py  PNG            │
   └───────────────────────────────────────┘
```

## The four invariants

Everything else is detail. These are the properties the system exists to hold.

### 1. No feature sees the future

Every indicator uses trailing windows. Enforced by
`tests/test_leakage.py::test_features_ignore_all_future_data`, which corrupts
every bar after a cut-off, rebuilds the features, and asserts the values at and
before the cut-off are bit-identical. Any negative shift, centred window or
global normalisation fails it.

### 2. Targets are returns, never price levels

`labeling/targets.py` only produces return-based targets.
`validation/leakage.py::assert_no_future_columns` additionally raises on any
feature that tracks the contemporaneous close too closely — the check that
catches the roadmap's `Lag1` example.

### 3. Training data is purged and embargoed around every test fold

`PurgedWalkForwardSplit` drops training rows whose label horizon overlaps the
test window, plus rows immediately after it. The pipeline re-asserts this per
fold via `assert_split_is_purged`, so a change to either the splitter or the
pipeline cannot silently reintroduce overlap.

### 4. A signal is filled after it is observed

Signal at close *t* → fill at open *t+1*. Encoded in
`backtest/engine.py::_execution_returns` and asserted in `tests/test_backtest.py`.

## Why the default data provider is synthetic

This project was built in an environment whose egress policy blocks Yahoo
Finance (403 on CONNECT to `query2.finance.yahoo.com`). Rather than treat that
as an obstacle, the data layer was put behind a protocol with a seeded synthetic
generator as the default. That turns out to be the better design regardless:

- **Tests are deterministic and offline.** No network, no API keys, no flakiness, no rate limits in CI.
- **The leakage tests become possible.** Testing for look-ahead requires *controlling* the data generating process — you have to be able to corrupt the future and see whether anything downstream notices.
- **There is a null to measure against.** The synthetic series has no predictable structure beyond volatility clustering, so an honest pipeline must earn roughly zero on it. It currently reports a Sharpe of −0.61 with a deflated Sharpe of 0.000. A high Sharpe here would mean the plumbing leaks, which makes this the canary for the whole system (`test_synthetic_null_strategy_earns_no_real_edge`).

`YFinanceProvider` is implemented and works wherever egress is open; it is
simply never exercised by the test suite, because a test that depends on a live
vendor is flaky by construction.

## What is deliberately not implemented

Roadmap Phase 7 needs a broker connection and continuous operation, neither of
which can be built or verified here. Rather than ship untested scaffolding that
looks functional:

| Component | Status |
|---|---|
| Paper trading adapter | Not implemented |
| Live execution / order management | Not implemented |
| Scheduled retraining | Not implemented |
| Real-time monitoring | Not implemented |

The pieces these would build on — a single signal-generation path shared by
research and execution, and a strict cost model — are in place, so adding them
does not require restructuring.

## Extending the system

**A new data source:** implement `fetch(symbol, start, end) -> DataFrame`
satisfying the OHLCV contract, register it in `get_provider`. Nothing downstream
changes.

**A new feature:** add it to `features/pipeline.py` with the `feat_` prefix. The
leakage test picks it up automatically — it iterates over every `feat_*` column,
so a new feature is covered the moment it exists.

**A new model:** anything with `fit` / `predict_proba` satisfies the `Model`
protocol.

**A new strategy:** a YAML file in `configs/strategies/` with `extends: ../base.yaml`.

## Known limitations

- **Single-asset.** The backtest handles one instrument at a time. Cross-sectional strategies need a portfolio layer over the top.
- **Daily bars.** No intraday or tick support; the cost model assumes daily rebalancing.
- **No slippage model tied to volume.** Square-root impact is supported but its coefficient must be calibrated per market; it defaults to zero.
- **`n_trials` in the deflated Sharpe defaults to the fold count.** A real research programme tries far more variants than that and should pass its true trial count, which will lower the reported probability.
