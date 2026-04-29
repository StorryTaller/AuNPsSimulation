from __future__ import annotations

import contextlib
import importlib
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStackedLayout, QWidget

_FONT_FAMILIES = ["Arial", "DengXian", "等线"]
_PLOT_COLORS = [
    "#2A2A2A",
    "#E32B2B",
    "#1E67D3",
    "#1A9B57",
    "#A66AD8",
    "#C99200",
    "#0FA5C7",
]
_FIGURE_BG = "#FFFFFF"
_GRID_COLOR = "#8B8F97"
_GRID_CLIP_INSET_AXES = 0.001
_CANVAS_FIGSIZE = (6.4, 6.0)
_CANVAS_DPI = 100


def _try_import_pyqtgraph():
    try:
        return importlib.import_module("pyqtgraph")
    except Exception:
        return None


def _apply_matplotlib_font_policy() -> None:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = list(_FONT_FAMILIES)
    plt.rcParams["axes.unicode_minus"] = False


def _style_context(style_name: str):
    try:
        import scienceplots  # noqa: F401

        style = (style_name or "origin").lower()
        if style == "nature":
            return plt.style.context(["science", "nature", "no-latex"])
        return plt.style.context(["science", "grid", "no-latex"])
    except Exception:
        return contextlib.nullcontext()


def _safe_dpi(dpi: int) -> int:
    try:
        value = int(dpi)
    except Exception:
        value = 400
    return max(72, value)


def _normalize_payload_mode(mode: str) -> str:
    lowered = str(mode or "").lower()
    if lowered in {"2d", "single", "multi"}:
        return "2d"
    if lowered == "3d":
        return "3d"
    return ""


def _clip_gridlines_inside_axes(ax, inset: float = _GRID_CLIP_INSET_AXES) -> None:
    inset = float(inset)
    if inset <= 0.0:
        return
    inset = min(inset, 0.25)

    clip_rect = Rectangle((0.0, 0.0), 1.0 - inset, 1.0 - inset, transform=ax.transAxes)
    clip_path = clip_rect.get_path()
    clip_transform = clip_rect.get_transform()

    ticks = (
        ax.xaxis.get_major_ticks()
        + ax.xaxis.get_minor_ticks()
        + ax.yaxis.get_major_ticks()
        + ax.yaxis.get_minor_ticks()
    )
    for tick in ticks:
        gridline = getattr(tick, "gridline", None)
        if gridline is None:
            continue
        gridline.set_clip_on(True)
        gridline.set_clip_path(clip_path, clip_transform)


def _apply_2d_axis_style(ax, x_label: str, y_label: str, title: str, has_labels: bool) -> None:
    ax.set_facecolor("none")
    ax.patch.set_edgecolor("none")
    ax.patch.set_linewidth(0.0)
    ax.set_xlabel(x_label, fontsize=14, labelpad=6)
    ax.set_ylabel(y_label, fontsize=15, labelpad=8)
    ax.set_title(title, fontsize=13, pad=8)
    ax.tick_params(axis="both", which="major", labelsize=11, width=1.6, length=6, direction="out")
    ax.tick_params(axis="both", which="minor", width=1.0, length=3, direction="out")
    ax.tick_params(axis="both", which="both", top=False, right=False, labeltop=False, labelright=False)
    ax.minorticks_on()
    ax.grid(True, which="major", color=_GRID_COLOR, alpha=0.28, linewidth=0.6)
    ax.grid(True, which="minor", color=_GRID_COLOR, alpha=0.16, linewidth=0.4)
    _clip_gridlines_inside_axes(ax)
    ax.margins(x=0.01, y=0.05)

    ax.spines["left"].set_linewidth(1.8)
    ax.spines["left"].set_color("#111111")
    ax.spines["bottom"].set_linewidth(1.8)
    ax.spines["bottom"].set_color("#111111")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if hasattr(ax, "set_box_aspect"):
        ax.set_box_aspect(0.95)  # x 轴略长，接近 1:1

    if has_labels:
        legend = ax.legend(
            loc="upper right",
            fontsize=10,
            frameon=True,
            borderpad=0.3,
            handlelength=1.8,
            handletextpad=0.35,
            fancybox=False,
        )
        frame = legend.get_frame()
        frame.set_alpha(1.0)
        frame.set_linewidth(1.0)
        frame.set_edgecolor("#222222")
        frame.set_facecolor((1.0, 1.0, 1.0, 0.0))


def export_plot_payload_png(
    payload: dict[str, Any],
    save_path: str | Path,
    dpi: int = 400,
    style_name: str = "origin",
) -> str:
    if not payload:
        raise ValueError("当前没有可导出的图像")

    target = Path(save_path)
    if target.suffix.lower() != ".png":
        target = target.with_suffix(".png")
    target.parent.mkdir(parents=True, exist_ok=True)
    export_dpi = _safe_dpi(dpi)

    payload_dict = dict(payload)
    mode = _normalize_payload_mode(str(payload_dict.get("mode", "")))
    if mode not in {"2d", "3d"}:
        raise ValueError("unsupported-export-mode")

    with _style_context(style_name):
        # scienceplots style may override font settings; enforce the same
        # matplotlib font policy as the on-screen chart for export.
        _apply_matplotlib_font_policy()
        fig = Figure(figsize=_CANVAS_FIGSIZE, dpi=export_dpi, facecolor=_FIGURE_BG)
        fig.patch.set_alpha(0.0)
        try:
            if mode == "2d":
                x = np.asarray(payload_dict.get("wavelengths"), dtype=float).reshape(-1)
                spectra = np.asarray(payload_dict.get("spectra"), dtype=float)
                if spectra.ndim == 1:
                    spectra = spectra.reshape(1, -1)

                labels = payload_dict.get("labels") or []
                if not isinstance(labels, list):
                    labels = [str(labels)]

                ax = fig.add_subplot(111)
                for idx, line in enumerate(spectra):
                    name = labels[idx] if idx < len(labels) else f"line_{idx + 1}"
                    ax.plot(
                        x,
                        line,
                        color=_PLOT_COLORS[idx % len(_PLOT_COLORS)],
                        linewidth=1.9,
                        label=str(name),
                    )
                _apply_2d_axis_style(
                    ax,
                    x_label=str(payload_dict.get("x_label", "Wavelength (nm)")),
                    y_label=str(payload_dict.get("y_label", "Absorption (a.u.)")),
                    title=str(payload_dict.get("title", "")),
                    has_labels=len(labels) > 0,
                )
            else:
                x = np.asarray(payload_dict.get("wavelengths"), dtype=float).reshape(-1)
                param_values = np.asarray(payload_dict.get("param_values"), dtype=float).reshape(-1)
                spectra = np.asarray(payload_dict.get("spectra"), dtype=float)
                if spectra.ndim == 1:
                    spectra = spectra.reshape(1, -1)

                ax = fig.add_subplot(111, projection="3d")
                cmap = plt.get_cmap("viridis")
                for idx, line in enumerate(spectra):
                    y_axis = np.full_like(x, param_values[idx], dtype=float)
                    color = cmap(idx / max(1, len(spectra) - 1))
                    ax.plot(x, y_axis, line, linewidth=1.5, color=color)

                ax.set_xlabel("Wavelength (nm)")
                ax.set_ylabel(str(payload_dict.get("param_name", "param")))
                ax.set_zlabel(str(payload_dict.get("y_label", "Absorption (a.u.)")))
                ax.set_title(str(payload_dict.get("title", "")))
                fixed_text = str(payload_dict.get("fixed_text", "") or "")
                if fixed_text:
                    ax.text2D(0.02, 0.98, fixed_text, transform=ax.transAxes, fontsize=9, va="top")

            fig.tight_layout()
            fig.savefig(str(target), dpi=export_dpi, format="png", transparent=True)
        finally:
            plt.close(fig)
    return str(target)


class SpectrumChartWidget(QWidget):
    """光谱图组件：2D/3D 默认使用 matplotlib 渲染。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _apply_matplotlib_font_policy()
        self._last_payload: dict[str, Any] = {}
        self.setObjectName("SpectrumChartWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self._pg_widget: QWidget | None = None
        self._pg_plot = None
        self._pg = _try_import_pyqtgraph()

        if self._pg is not None:
            self._pg.setConfigOptions(antialias=True, foreground="#1F2D3D", background="#FFFFFF")
            self._pg_widget = self._pg.PlotWidget()
            self._pg_widget.setStyleSheet("background: transparent;")
            self._pg_plot = self._pg_widget.getPlotItem()
            self._pg_plot.showGrid(x=True, y=True, alpha=0.15)
            self._stack.addWidget(self._pg_widget)
        else:
            self._pg_widget = QWidget()
            self._pg_widget.setStyleSheet("background: transparent;")
            self._stack.addWidget(self._pg_widget)

        self._figure = Figure(figsize=_CANVAS_FIGSIZE, dpi=_CANVAS_DPI, facecolor=_FIGURE_BG)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setStyleSheet("background: transparent;")
        self._canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._canvas.setAutoFillBackground(False)
        self._stack.addWidget(self._canvas)
        self._stack.setCurrentWidget(self._canvas)

    @property
    def last_payload(self) -> dict[str, Any]:
        return dict(self._last_payload)

    def clear(self) -> None:
        if self._pg is not None and self._pg_plot is not None:
            self._pg_plot.clear()
        self._figure.clear()
        self._canvas.draw_idle()
        self._last_payload = {}

    def plot_2d(
        self,
        wavelengths: Any,
        spectra: Any,
        labels: list[str] | None = None,
        y_label: str = "Absorption (a.u.)",
        title: str = "",
        x_label: str = "Wavelength (nm)",
    ) -> None:
        x = np.asarray(wavelengths, dtype=float).reshape(-1)
        y = np.asarray(spectra, dtype=float)
        if y.ndim == 1:
            y = y.reshape(1, -1)

        labels = labels or [f"line_{i + 1}" for i in range(len(y))]
        self._last_payload = {
            "mode": "2d",
            "wavelengths": x,
            "spectra": y,
            "labels": labels,
            "x_label": x_label,
            "y_label": y_label,
            "title": title,
        }

        self._draw_matplotlib_2d(x, y, labels, x_label, y_label, title)

    @staticmethod
    def _apply_2d_axis_style(ax, x_label: str, y_label: str, title: str, has_labels: bool) -> None:
        _apply_2d_axis_style(ax, x_label=x_label, y_label=y_label, title=title, has_labels=has_labels)

    def _draw_matplotlib_2d(
        self,
        wavelengths: np.ndarray,
        spectra: np.ndarray,
        labels: list[str],
        x_label: str,
        y_label: str,
        title: str,
    ) -> None:
        _apply_matplotlib_font_policy()
        self._stack.setCurrentWidget(self._canvas)
        self._figure.clear()
        self._figure.set_facecolor(_FIGURE_BG)
        self._figure.patch.set_alpha(0.0)
        ax = self._figure.add_subplot(111)
        for idx, line in enumerate(spectra):
            name = labels[idx] if idx < len(labels) else f"line_{idx + 1}"
            ax.plot(wavelengths, line, color=_PLOT_COLORS[idx % len(_PLOT_COLORS)], linewidth=1.9, label=name)
        self._apply_2d_axis_style(ax, x_label=x_label, y_label=y_label, title=title, has_labels=bool(labels))
        self._figure.tight_layout()
        self._canvas.draw_idle()

    def plot_3d(
        self,
        wavelengths: Any,
        param_values: Any,
        spectra: Any,
        y_label: str,
        param_name: str,
        title: str = "",
        fixed_text: str = "",
    ) -> None:
        _apply_matplotlib_font_policy()
        x = np.asarray(wavelengths, dtype=float).reshape(-1)
        y_values = np.asarray(param_values, dtype=float).reshape(-1)
        z = np.asarray(spectra, dtype=float)
        if z.ndim == 1:
            z = z.reshape(1, -1)

        self._last_payload = {
            "mode": "3d",
            "wavelengths": x,
            "param_values": y_values,
            "spectra": z,
            "y_label": y_label,
            "param_name": param_name,
            "title": title,
            "fixed_text": fixed_text,
        }

        self._stack.setCurrentWidget(self._canvas)
        self._figure.clear()
        ax = self._figure.add_subplot(111, projection="3d")

        cmap = plt.get_cmap("viridis")
        for idx, line in enumerate(z):
            color = cmap(idx / max(1, len(z) - 1))
            y_axis = np.full_like(x, y_values[idx], dtype=float)
            ax.plot(x, y_axis, line, linewidth=1.5, color=color)

        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel(param_name)
        ax.set_zlabel(y_label)
        ax.set_title(title)
        if fixed_text:
            ax.text2D(0.02, 0.98, fixed_text, transform=ax.transAxes, fontsize=9, va="top")
        self._figure.tight_layout()
        self._canvas.draw_idle()

    @staticmethod
    def _safe_dpi(dpi: int) -> int:
        return _safe_dpi(dpi)

    def _export_with_matplotlib(self, target: Path, dpi: int, style_name: str) -> str:
        return export_plot_payload_png(dict(self._last_payload), target, dpi=dpi, style_name=style_name)

    def export_current(self, save_path: str, dpi: int = 400, style_name: str = "origin") -> str:
        if not self._last_payload:
            raise ValueError("当前没有可导出的图像")

        target = Path(save_path)
        export_dpi = self._safe_dpi(dpi)
        return self._export_with_matplotlib(target, export_dpi, style_name)

    def export_visible(self, save_path: str, image_format: str = "PNG", dpi: int = 400) -> str:
        """Export exactly what is currently visible in the chart widget."""
        if not self._last_payload:
            raise ValueError("当前没有可导出的图像")

        target = Path(save_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        fmt = (image_format or "PNG").upper()
        export_dpi = self._safe_dpi(dpi)

        source = self._stack.currentWidget() or self
        width = max(1, source.width())
        height = max(1, source.height())
        logical_dpi = float(self.logicalDpiX() or 96.0)
        scale = max(1.0, float(export_dpi) / logical_dpi)

        image = QImage(
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale))),
            QImage.Format.Format_ARGB32,
        )
        image.fill(Qt.GlobalColor.white)

        dots_per_meter = int(round(export_dpi / 0.0254))
        image.setDotsPerMeterX(dots_per_meter)
        image.setDotsPerMeterY(dots_per_meter)

        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.scale(scale, scale)
            source.render(painter)
        finally:
            painter.end()

        if not image.save(str(target), fmt):
            raise ValueError(f"图像导出失败：不支持格式 {fmt}")
        return str(target)
