from __future__ import annotations

import math
from numbers import Real
from pathlib import Path
from typing import Any


def sanitize_filename(text: Any, fallback: str = "plot") -> str:
    cleaned = "".join("_" if ch in '<>:"/\\|?*' else ch for ch in str(text)).strip()
    return cleaned or fallback


def format_filename_param_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        num = float(value)
        if num.is_integer():
            return str(int(num))
        return f"{num:.6f}".rstrip("0").rstrip(".")
    return str(value)


def format_legend_param_value(value: Any, decimals: int = 2) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            return str(value)
        rounded = round(number, int(decimals))
        if rounded == 0:
            rounded = 0.0
        text = f"{rounded:.{int(decimals)}f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(value)


def normalize_export_mode(
    mode: str | None,
    *,
    default_mode: str,
    allow_1d_alias: bool = False,
) -> str:
    value = str(mode or "").strip().lower()
    if allow_1d_alias and value == "1d":
        value = "single"
    if value in {"single", "multi", "3d"}:
        return value
    return default_mode


def resolve_metrics_output_path(target: str | Path, source_file_path: str | None) -> Path:
    resolved = Path(target)
    if source_file_path:
        return resolved.with_name(f"{Path(source_file_path).stem}.xlsx")
    if resolved.suffix.lower() != ".xlsx":
        return resolved.with_suffix(".xlsx")
    return resolved


def round_export_metric_value(value: Any, decimals: int = 3) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            return value
        return round(number, int(decimals))
    return value


def round_export_metric_row(row: dict[str, Any], decimals: int = 3) -> dict[str, Any]:
    return {
        key: round_export_metric_value(value, decimals=decimals)
        for key, value in row.items()
    }
