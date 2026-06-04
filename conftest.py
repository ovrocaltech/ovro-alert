"""Make lwa-fasttransients importable when running ovro-alert tests."""
from __future__ import annotations

import sys
from pathlib import Path

_lwa_src = Path(__file__).resolve().parent.parent / "lwa-fasttransients" / "src"
if _lwa_src.is_dir() and str(_lwa_src) not in sys.path:
    sys.path.insert(0, str(_lwa_src))
