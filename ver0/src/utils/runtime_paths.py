from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """Return source root in dev mode and bundled source root when frozen."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass) / "src"
        # Fallback for uncommon frozen layouts without _MEIPASS.
        return Path(sys.executable).resolve().parent / "src"
    return Path(__file__).resolve().parents[1]
