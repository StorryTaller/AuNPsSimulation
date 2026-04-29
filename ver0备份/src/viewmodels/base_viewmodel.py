from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject

from src.utils.i18n import I18NManager


class BaseViewModel(QObject):
    def __init__(self, i18n: I18NManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n

    def _t(self, key: str, fallback: str = "") -> str:
        return self.i18n.t(self.__class__.__name__, self.tr(key), fallback)

    def _emit_info(self, level: str, title_key: str, content: str) -> None:
        title = self._t(title_key, title_key)
        self.message.emit(level, title, content)  # type: ignore[attr-defined]

    @staticmethod
    def _log(log_callback: Callable[[str], None] | None, text: str) -> None:
        if log_callback is not None:
            log_callback(str(text))


class BasePlotViewModel(BaseViewModel):
    METRIC_KEYS = ("lambda", "fwhm", "q", "ris", "fom")

    def __init__(self, i18n: I18NManager, parent: QObject | None = None) -> None:
        super().__init__(i18n, parent)
        self.custom_plot_title = ""
        self.custom_y_label = ""
        self.wavelength_window: tuple[float, float] | None = None

    @staticmethod
    def _clip_by_wavelength_window(
        wavelengths: np.ndarray,
        spectra: np.ndarray,
        window: tuple[float, float] | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if window is None:
            return wavelengths, spectra

        start, end = window
        lo = min(float(start), float(end))
        hi = max(float(start), float(end))
        mask = (wavelengths >= lo) & (wavelengths <= hi)
        if not np.any(mask):
            raise ValueError("empty-window")

        if spectra.ndim == 1:
            return wavelengths[mask], spectra[mask]
        return wavelengths[mask], spectra[:, mask]

    @staticmethod
    def _text_or_fallback(value: str, fallback: str) -> str:
        text = str(value or "").strip()
        return text if text else fallback

    def _effective_title(self, fallback: str) -> str:
        return self._text_or_fallback(self.custom_plot_title, fallback)

    def _effective_y_label(self, fallback: str) -> str:
        return self._text_or_fallback(self.custom_y_label, fallback)

    def set_custom_plot_title(self, title: str) -> None:
        self.custom_plot_title = str(title or "")
        self._on_plot_edit_state_changed()

    def set_custom_y_label(self, y_label: str) -> None:
        self.custom_y_label = str(y_label or "")
        self._on_plot_edit_state_changed()

    def set_wavelength_window(self, start_nm: float | None, end_nm: float | None) -> None:
        if start_nm is None or end_nm is None:
            self.wavelength_window = None
        else:
            self.wavelength_window = (float(start_nm), float(end_nm))
        self._on_plot_edit_state_changed()

    def reset_plot_edit_state(self) -> None:
        self.custom_plot_title = ""
        self.custom_y_label = ""
        self.wavelength_window = None

    def _on_plot_edit_state_changed(self) -> None:
        """Hook for subclasses to refresh current plot state."""

    @classmethod
    def _blank_metrics(cls) -> dict[str, str]:
        return {key: "-" for key in cls.METRIC_KEYS}

    @classmethod
    def _summary_metrics_payload(cls, summary: dict[str, Any] | None) -> dict[str, str]:
        values = cls._blank_metrics()
        if not summary:
            return values
        values["lambda"] = f"{summary.get('resonance_wavelength_nm', 0.0):.4f}"
        values["fwhm"] = f"{summary.get('fwhm_nm', 0.0):.4f}"
        values["q"] = f"{summary.get('q_factor', 0.0):.4f}"
        values["ris"] = f"{summary.get('ris_nm_per_riu', 0.0):.4f}"
        values["fom"] = f"{summary.get('fom_inv_riu', 0.0):.4f}"
        return values

    @staticmethod
    def _collect_batch_paths(csv_paths: list[str]) -> list[str]:
        return [str(Path(path)) for path in csv_paths if str(path).strip()]

    @classmethod
    def _prepare_batch_export(
        cls,
        csv_paths: list[str],
        output_dir: str,
        *,
        output_dir_error: str,
    ) -> tuple[list[str], Path]:
        paths = cls._collect_batch_paths(csv_paths)
        if not paths:
            raise ValueError("请先选择CSV文件")
        if not output_dir:
            raise ValueError(output_dir_error)

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return paths, out_dir
