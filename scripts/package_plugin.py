#!/usr/bin/env python3
"""Repository-local wrapper for deterministic release packaging."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_litigation_workflows.cli import package_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(package_main())
