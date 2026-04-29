from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SpectrumMetrics:
    resonance_wavelength: float
    fwhm: float
    q_factor: float
    max_absorption: float


def _to_float_array(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    return arr


def normalize_rows(spectra: np.ndarray) -> np.ndarray:
    data = np.asarray(spectra, dtype=float)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    mins = data.min(axis=1, keepdims=True)
    maxs = data.max(axis=1, keepdims=True)
    span = maxs - mins
    span[span == 0] = 1.0
    return (data - mins) / span


def _interp_x(x: np.ndarray, y: np.ndarray, i1: int, i2: int, target: float) -> float:
    if y[i2] == y[i1]:
        return float(x[i1])
    return float(x[i1] + (target - y[i1]) * (x[i2] - x[i1]) / (y[i2] - y[i1]))


def calculate_spectrum_metrics(wavelengths_nm: Any, spectrum: Any) -> SpectrumMetrics | None:
    x = _to_float_array(wavelengths_nm)
    y = _to_float_array(spectrum)
    if len(x) != len(y) or len(x) < 3:
        return None

    peak_idx = int(np.argmax(y))
    resonance = float(x[peak_idx])
    peak_value = float(y[peak_idx])
    half = peak_value / 2.0

    idx = np.where(y >= half)[0]
    if len(idx) < 2:
        return None

    left_i = int(idx[0])
    right_i = int(idx[-1])

    left = _interp_x(x, y, left_i - 1, left_i, half) if left_i > 0 else float(x[left_i])
    right = _interp_x(x, y, right_i, right_i + 1, half) if right_i < len(x) - 1 else float(x[right_i])

    fwhm = abs(right - left)
    q_factor = resonance / fwhm if fwhm > 0 else 0.0
    return SpectrumMetrics(
        resonance_wavelength=resonance,
        fwhm=fwhm,
        q_factor=q_factor,
        max_absorption=peak_value,
    )


def calculate_batch_metrics(
    wavelengths_nm: Any,
    spectra: Any,
    param_values: list[Any] | None = None,
    param_name: str = "",
) -> dict[str, Any]:
    data = np.asarray(spectra, dtype=float)
    if data.ndim == 1:
        data = data.reshape(1, -1)

    items = [calculate_spectrum_metrics(wavelengths_nm, data[i]) for i in range(len(data))]
    valid = [m for m in items if m is not None]

    ris = 0.0
    delta_lambda = 0.0
    delta_n = 0.0

    if (
        str(param_name).strip().lower() == "index"
        and param_values is not None
        and len(param_values) >= 2
        and len(valid) >= 2
    ):
        try:
            first = float(param_values[0])
            last = float(param_values[-1])
            delta_n = last - first
            delta_lambda = valid[-1].resonance_wavelength - valid[0].resonance_wavelength
            if delta_n != 0:
                ris = delta_lambda / delta_n
        except Exception:
            ris = 0.0
            delta_lambda = 0.0
            delta_n = 0.0

    return {
        "single_metrics": items,
        "valid_metrics": valid,
        "ris": ris,
        "delta_lambda_res": delta_lambda,
        "delta_n": delta_n,
    }


def build_summary_row(batch_metrics: dict[str, Any]) -> dict[str, float]:
    valid = batch_metrics.get("valid_metrics", [])
    if not valid:
        return {}

    center = valid[len(valid) // 2]
    ris = float(batch_metrics.get("ris", 0.0) or 0.0)
    fom = abs(ris) / center.fwhm if center.fwhm > 0 else 0.0
    return {
        "resonance_wavelength_nm": center.resonance_wavelength,
        "fwhm_nm": center.fwhm,
        "q_factor": center.q_factor,
        "ris_nm_per_riu": ris,
        "fom_inv_riu": fom,
    }
