"""CLI and reporting smoke tests.

These paths are what a user actually touches, so they get exercised end to end
rather than left to a manual check.
"""

from __future__ import annotations

import pandas as pd
import pytest
import yaml

from quantlab.cli import main
from quantlab.config import ModelConfig
from quantlab.models.sklearn_models import build_model
from quantlab.reporting.tearsheet import build_tearsheet, format_metrics_table


@pytest.fixture
def config_file(tmp_path, config) -> str:
    """Write the test config to disk so the CLI can load it."""
    payload = {
        "name": config.name,
        "seed": config.seed,
        "data": {
            "provider": "synthetic",
            "symbols": ["TEST"],
            "start": "2016-01-01",
            "end": "2023-12-31",
            "cache_dir": str(tmp_path / "cache"),
        },
        "validation": {"n_splits": 3, "purge": 5, "embargo": 5, "min_train": 200},
        "model": {"kind": "random_forest", "params": {"n_estimators": 10, "max_depth": 3}},
    }
    path = tmp_path / "strategy.yaml"
    path.write_text(yaml.safe_dump(payload))
    return str(path)


def test_cli_data_command(config_file, capsys):
    assert main(["data", "--config", config_file]) == 0
    assert "bars" in capsys.readouterr().out


def test_cli_features_command(config_file, capsys):
    assert main(["features", "--config", config_file]) == 0
    out = capsys.readouterr().out
    assert "usable rows" in out
    assert "feat_rsi_14" in out


def test_cli_run_command_writes_artifacts(config_file, tmp_path, capsys):
    exit_code = main(["run", "--config", config_file, "--output-dir", str(tmp_path / "out")])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Sharpe ratio" in out
    assert "Deflated Sharpe" in out

    assert (tmp_path / "out" / "test_strategy_tearsheet.png").exists()
    assert (tmp_path / "out" / "test_strategy_backtest.csv").exists()


def test_cli_run_can_skip_artifacts(config_file, tmp_path):
    assert main(["run", "--config", config_file, "--no-tearsheet"]) == 0
    assert not (tmp_path / "out").exists()


def test_cli_symbol_override(config_file, capsys):
    assert main(["data", "--config", config_file, "--symbol", "OTHER"]) == 0
    assert "OTHER" in capsys.readouterr().out


def test_format_metrics_table_renders_percentages_and_ratios():
    text = format_metrics_table(
        {"annualized_return": 0.1234, "sharpe_ratio": 1.5, "n_periods": 2500}
    )
    assert "12.34%" in text
    assert "1.500" in text
    assert "2,500" in text


def test_build_tearsheet_writes_a_png(tmp_path, bars):
    from quantlab.backtest.costs import CostModel
    from quantlab.backtest.engine import run_backtest
    from quantlab.metrics.performance import summarize

    positions = pd.Series(0.5, index=bars.index)
    result = run_backtest(bars, positions, CostModel())
    metrics = summarize(result.net_returns, positions=positions)

    path = build_tearsheet(result, metrics, tmp_path / "sheet.png", title="Test")
    assert path.exists() and path.stat().st_size > 5_000


def test_logistic_model_is_a_scaled_pipeline():
    """The logistic branch must scale features before regularising them."""
    model = build_model(ModelConfig(kind="logistic"))
    assert "scale" in dict(model.named_steps)


def test_unknown_model_kind_is_rejected():
    with pytest.raises(ValueError, match="unknown model kind"):
        build_model(ModelConfig(kind="transformer"))


def test_logistic_model_trains_and_predicts(bars):
    """Exercise the alternative model end to end on real feature data."""
    import numpy as np

    from quantlab.config import FeatureConfig, LabelConfig
    from quantlab.features.pipeline import build_features, feature_columns
    from quantlab.labeling.targets import make_label

    frame = make_label(build_features(bars, FeatureConfig()), LabelConfig(horizon=5))
    frame = frame.dropna(subset=[*feature_columns(frame), "label"])

    model = build_model(ModelConfig(kind="logistic"))
    cols = feature_columns(frame)
    model.fit(frame[cols].iloc[:500], frame["label"].iloc[:500].astype(int))

    proba = model.predict_proba(frame[cols].iloc[500:600])
    assert proba.shape == (100, 2)
    assert np.isfinite(proba).all()
    assert proba.sum(axis=1) == pytest.approx(1.0)
