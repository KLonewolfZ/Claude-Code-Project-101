"""Command-line entry point.

quantlab data     --config ...   fetch and cache bars
quantlab features --config ...   build the feature/label matrix
quantlab run      --config ...   full pipeline, metrics and tearsheet
"""

from __future__ import annotations

import argparse
import sys

from quantlab.config import load_config

__all__ = ["main"]

DEFAULT_CONFIG = "configs/strategies/momentum_rf.yaml"


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to a strategy YAML")
    parser.add_argument("--symbol", default=None, help="override the configured symbol")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quantlab", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    _add_common(sub.add_parser("data", help="fetch and cache bars"))
    _add_common(sub.add_parser("features", help="build the feature/label matrix"))

    run_parser = sub.add_parser("run", help="run the full pipeline")
    _add_common(run_parser)
    run_parser.add_argument("--output-dir", default="reports", help="where to write artifacts")
    run_parser.add_argument("--no-tearsheet", action="store_true", help="skip PNG/CSV output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "data":
        from quantlab.data.cache import CachedProvider
        from quantlab.data.providers import get_provider

        provider = CachedProvider(
            get_provider(cfg.data.provider, seed=cfg.seed), cfg.data.cache_dir
        )
        for symbol in [args.symbol] if args.symbol else cfg.data.symbols:
            bars = provider.fetch(symbol, cfg.data.start, cfg.data.end)
            print(
                f"{symbol}: {len(bars):,} bars, {bars.index[0].date()} .. {bars.index[-1].date()}"
            )
        return 0

    if args.command == "features":
        from quantlab.features.pipeline import feature_columns
        from quantlab.pipeline import load_dataset

        dataset = load_dataset(cfg, args.symbol)
        cols = feature_columns(dataset)
        print(f"{len(dataset):,} usable rows x {len(cols)} features")
        for col in cols:
            print(f"  {col}")
        return 0

    if args.command == "run":
        from quantlab.pipeline import run_strategy, save_run
        from quantlab.reporting.tearsheet import format_metrics_table

        run = run_strategy(cfg, args.symbol)

        print(f"\nStrategy: {cfg.name}")
        print(f"Provider: {cfg.data.provider}   Execution: {cfg.backtest.execution}")
        print(
            f"Folds:    {run.n_folds} purged walk-forward "
            f"(purge={max(cfg.validation.purge, cfg.label.horizon)}, "
            f"embargo={cfg.validation.embargo})"
        )
        print(f"Rows:     {len(run.dataset):,}\n")
        print("Out-of-sample performance, net of costs:")
        print(format_metrics_table(run.metrics))

        dsr = run.metrics.get("deflated_sharpe")
        if dsr is not None and dsr == dsr:  # not NaN
            verdict = (
                "clears the multiple-testing hurdle"
                if dsr >= 0.95
                else "NOT distinguishable from selection bias"
            )
            print(f"\n  Deflated Sharpe {dsr:.3f} -> {verdict}.")

        if not args.no_tearsheet:
            paths = save_run(run, args.output_dir)
            print(f"\nWrote {paths['tearsheet']}")
            print(f"Wrote {paths['csv']}")
        return 0

    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
