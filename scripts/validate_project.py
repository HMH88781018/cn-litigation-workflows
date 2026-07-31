#!/usr/bin/env python3
"""Repository-local wrapper for the validator CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_litigation_workflows.cli import validate_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(validate_main())
