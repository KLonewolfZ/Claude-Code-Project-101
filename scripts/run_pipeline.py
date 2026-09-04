#!/usr/bin/env python3
"""Run the end-to-end pipeline. Thin wrapper over `quantlab run`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantlab.cli import main  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    sys.exit(main(["run", *argv]))
