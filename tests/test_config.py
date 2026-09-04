"""Config loading and validation."""

from __future__ import annotations

import pytest
import yaml

from quantlab.config import Config, load_config


def test_repository_configs_load():
    """The shipped configs must parse, including the extends chain."""
    cfg = load_config("configs/strategies/momentum_rf.yaml")
    assert cfg.name == "momentum_rf"
    assert cfg.data.provider == "synthetic"
    assert cfg.backtest.execution == "next_open"


def test_extends_inherits_parent_values():
    """Keys absent from the child come from the parent."""
    cfg = load_config("configs/strategies/momentum_rf.yaml")
    # Defined only in base.yaml.
    assert cfg.costs.commission_bps == 1.0
    assert cfg.validation.n_splits == 5


def test_child_overrides_parent(tmp_path):
    (tmp_path / "base.yaml").write_text(
        yaml.safe_dump({"seed": 1, "costs": {"commission_bps": 9.0, "spread_bps": 3.0}})
    )
    (tmp_path / "child.yaml").write_text(
        yaml.safe_dump({"extends": "base.yaml", "seed": 2, "costs": {"commission_bps": 0.5}})
    )
    cfg = load_config(tmp_path / "child.yaml")

    assert cfg.seed == 2
    assert cfg.costs.commission_bps == 0.5  # overridden
    assert cfg.costs.spread_bps == 3.0  # merged from parent, not clobbered


def test_unknown_key_fails_loudly():
    """A typo must not silently fall back to a default."""
    with pytest.raises(ValueError, match="unknown key"):
        Config.from_dict({"costs": {"comission_bps": 1.0}})  # misspelled


def test_unknown_top_level_key_fails_loudly():
    with pytest.raises(ValueError, match="unknown top-level"):
        Config.from_dict({"strategy_name": "oops"})


def test_defaults_are_sane():
    cfg = Config.from_dict({})
    assert cfg.backtest.execution == "next_open", "the safe execution convention must be default"
    assert cfg.data.provider == "synthetic", "the offline provider must be default"
    assert cfg.label.kind == "forward_return", "the target must be a return by default"


def test_purge_defaults_cover_the_label_horizon():
    """The shipped config must not ship a leaky purge setting."""
    cfg = load_config("configs/strategies/momentum_rf.yaml")
    assert cfg.validation.purge >= cfg.label.horizon
