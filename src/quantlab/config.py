"""Configuration loading.

Configs are plain YAML with a single ``extends`` key for one level of
inheritance, which is all this project needs. Everything is resolved into
frozen dataclasses so a typo in a YAML key fails loudly at load time rather
than silently defaulting deep inside the pipeline.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "BacktestConfig",
    "Config",
    "CostConfig",
    "DataConfig",
    "FeatureConfig",
    "LabelConfig",
    "ModelConfig",
    "SizingConfig",
    "ValidationConfig",
    "load_config",
]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base`` without mutating either."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _build(cls: type, payload: dict[str, Any], where: str):
    """Instantiate a dataclass, rejecting unknown keys with a useful message."""
    known = {f.name for f in fields(cls)}
    unknown = set(payload) - known
    if unknown:
        raise ValueError(
            f"unknown key(s) {sorted(unknown)} under '{where}'; expected any of {sorted(known)}"
        )
    return cls(**payload)


@dataclass(frozen=True)
class DataConfig:
    provider: str = "synthetic"
    symbols: list[str] = field(default_factory=lambda: ["SYNTH_A"])
    start: str = "2015-01-02"
    end: str = "2024-12-31"
    cache_dir: str = "data/cache"


@dataclass(frozen=True)
class FeatureConfig:
    ma_windows: list[int] = field(default_factory=lambda: [10, 20, 50, 100])
    extreme_windows: list[int] = field(default_factory=lambda: [10, 20, 50])
    momentum_windows: list[int] = field(default_factory=lambda: [5, 10, 21, 63])
    rsi_window: int = 14
    atr_window: int = 14
    vol_window: int = 21


@dataclass(frozen=True)
class LabelConfig:
    kind: str = "forward_return"
    horizon: int = 5
    vol_scaled: bool = True
    # The hurdle the forward return must clear, in multiples of the forward
    # return's own ex-ante standard deviation. 0.0 predicts pure direction and
    # gives a roughly balanced target; raising it asks for a move large enough to
    # be worth trading, at the cost of a rarer positive class. A full 1.0 leaves
    # only ~16% positives, which is too imbalanced to learn from on daily bars.
    threshold_vol_multiple: float = 0.0
    # Triple-barrier only; multiples of realized vol.
    upper_barrier: float = 2.0
    lower_barrier: float = 2.0


@dataclass(frozen=True)
class ValidationConfig:
    n_splits: int = 5
    purge: int = 5
    embargo: int = 5
    min_train: int = 500


@dataclass(frozen=True)
class ModelConfig:
    kind: str = "random_forest"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CostConfig:
    commission_bps: float = 1.0
    spread_bps: float = 2.0
    slippage_bps: float = 1.0
    borrow_bps_annual: float = 50.0


@dataclass(frozen=True)
class SizingConfig:
    kind: str = "vol_target"
    target_vol_annual: float = 0.10
    max_leverage: float = 1.0
    kelly_fraction: float = 0.25


@dataclass(frozen=True)
class BacktestConfig:
    execution: str = "next_open"
    periods_per_year: int = 252


@dataclass(frozen=True)
class Config:
    name: str = "unnamed"
    seed: int = 42
    data: DataConfig = field(default_factory=DataConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    label: LabelConfig = field(default_factory=LabelConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Config:
        payload = copy.deepcopy(payload)
        payload.pop("extends", None)
        sections = {
            "data": DataConfig,
            "features": FeatureConfig,
            "label": LabelConfig,
            "validation": ValidationConfig,
            "model": ModelConfig,
            "costs": CostConfig,
            "sizing": SizingConfig,
            "backtest": BacktestConfig,
        }
        kwargs: dict[str, Any] = {}
        for key, section_cls in sections.items():
            kwargs[key] = _build(section_cls, payload.pop(key, {}) or {}, key)
        for scalar in ("name", "seed"):
            if scalar in payload:
                kwargs[scalar] = payload.pop(scalar)
        if payload:
            raise ValueError(f"unknown top-level config key(s): {sorted(payload)}")
        return cls(**kwargs)


def load_config(path: str | Path) -> Config:
    """Load a YAML config, resolving a single ``extends`` parent relative to it."""
    path = Path(path)
    with path.open() as fh:
        payload = yaml.safe_load(fh) or {}

    parent_ref = payload.get("extends")
    if parent_ref:
        parent_path = (path.parent / parent_ref).resolve()
        with parent_path.open() as fh:
            parent = yaml.safe_load(fh) or {}
        parent.pop("extends", None)
        payload = _deep_merge(parent, payload)

    return Config.from_dict(payload)
