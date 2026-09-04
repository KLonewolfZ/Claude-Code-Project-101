#!/usr/bin/env python3
"""Reproduce the roadmap's example model and measure what it actually learns.

The roadmap's closing code snippet trains ``LinearRegression`` on
``X = Close.shift(1)`` against ``y = Close``. This script runs exactly that,
then runs the corrected returns-based formulation on the same data, and prints
both. The numbers it produces are quoted in ``docs/ROADMAP_ANALYSIS.md`` so the
critique rests on evidence rather than assertion.

Run:  python scripts/demonstrate_tautology.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.linear_model import LinearRegression  # noqa: E402
from sklearn.metrics import r2_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from quantlab.data.providers import SyntheticProvider  # noqa: E402


def roadmap_formulation(data: pd.DataFrame) -> dict[str, float]:
    """The roadmap's snippet, transcribed as written."""
    frame = pd.DataFrame(index=data.index)
    frame["Close"] = data["close"]
    frame["Lag1"] = data["close"].shift(1)
    frame = frame.dropna()

    X = frame[["Lag1"]]
    y = frame["Close"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = LinearRegression().fit(X_train, y_train)
    predictions = model.predict(X_test)

    # The naive read of this result: "R-squared of 0.99, the model works."
    r2 = r2_score(y_test, predictions)

    # What it actually learned: y = x. A coefficient of ~1.0 and an intercept of
    # ~0 means the model reproduces its own input.
    coefficient = float(model.coef_[0])
    intercept = float(model.intercept_)

    # The honest comparison: a model that simply repeats yesterday's price,
    # learning nothing at all. If it scores the same, the fit added nothing.
    naive_r2 = r2_score(y_test, X_test["Lag1"])

    # And the question that actually matters for trading: does it predict the
    # DIRECTION of the next move? Convert the price forecast into a predicted
    # return and check its sign against the realised one.
    predicted_change = predictions - X_test["Lag1"].to_numpy()
    actual_change = y_test.to_numpy() - X_test["Lag1"].to_numpy()
    directional_accuracy = float(np.mean(np.sign(predicted_change) == np.sign(actual_change)))

    return {
        "r2": float(r2),
        "naive_repeat_r2": float(naive_r2),
        "coefficient": coefficient,
        "intercept": intercept,
        "directional_accuracy": directional_accuracy,
    }


def corrected_formulation(data: pd.DataFrame) -> dict[str, float]:
    """The same idea expressed on returns, which is the honest version."""
    frame = pd.DataFrame(index=data.index)
    frame["ret"] = data["close"].pct_change()
    frame["lag_ret"] = frame["ret"].shift(1)
    frame = frame.dropna()

    X = frame[["lag_ret"]]
    y = frame["ret"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = LinearRegression().fit(X_train, y_train)
    predictions = model.predict(X_test)

    directional_accuracy = float(np.mean(np.sign(predictions) == np.sign(y_test.to_numpy())))

    return {
        "r2": float(r2_score(y_test, predictions)),
        "directional_accuracy": directional_accuracy,
    }


def main() -> int:
    # Synthetic by construction: this environment has no market-data egress, and
    # the point holds for any price series, since it is about the algebra of
    # regressing a level on its own lag rather than about any particular asset.
    data = SyntheticProvider(seed=42).fetch("DEMO", "2015-01-01", "2024-12-31")

    roadmap = roadmap_formulation(data)
    corrected = corrected_formulation(data)

    print("=" * 74)
    print("The roadmap's example:  X = Close.shift(1)   ->   y = Close")
    print("=" * 74)
    print(f"  R-squared                        {roadmap['r2']:.6f}   <- looks excellent")
    print(f"  Fitted coefficient               {roadmap['coefficient']:.6f}")
    print(f"  Fitted intercept                 {roadmap['intercept']:.6f}")
    print(f"  R-squared of just repeating x    {roadmap['naive_repeat_r2']:.6f}   <- same score,")
    print("                                                zero model needed")
    print(
        f"  Directional accuracy             {roadmap['directional_accuracy']:.4f}   <- a coin flip"
    )
    print()
    print("  The model learned y = x. It reproduces its own input, scores the")
    print("  same as doing nothing, and cannot call the direction of the move.")
    print()
    print("=" * 74)
    print("Corrected:  X = lagged RETURN   ->   y = RETURN")
    print("=" * 74)
    print(f"  R-squared                        {corrected['r2']:.6f}   <- honest, and near zero")
    print(f"  Directional accuracy             {corrected['directional_accuracy']:.4f}")
    print()
    print("  A far worse-looking R-squared that is a far more useful number: it")
    print("  correctly reports that one lagged return barely predicts the next.")
    print("=" * 74)

    out = ROOT / "docs" / "tautology_evidence.json"
    out.write_text(json.dumps({"roadmap": roadmap, "corrected": corrected}, indent=2) + "\n")
    print(f"\nWrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
