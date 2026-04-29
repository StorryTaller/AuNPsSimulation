from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, Signal

from src.models.spectrum_model import SpectrumDataset
from src.utils.export_helpers import (
    format_filename_param_value,
    format_legend_param_value,
    normalize_export_mode,
    resolve_metrics_output_path,
    sanitize_filename,
)
from src.utils.i18n import I18NManager
from src.viewmodels.base_viewmodel import BasePlotViewModel
from src.views.components.charts import export_plot_payload_png


class VizViewModel(BasePlotViewModel):
    data_loaded = Signal(dict)
    plot_data_changed = Signal(dict)
    metrics_changed = Signal(dict)
    index_range_changed = Signal(int)
    message = Signal(str, str, str)
    busy_changed = Signal(bool)

    def __init__(self, i18n: I18NManager, parent: QObject | None = None) -> None:
        super().__init__(i18n, parent)
        self.dataset = SpectrumDataset()
        self.current_index = 0
        self.current_mode = "single"

    def _build_line_labels(self, dataset: SpectrumDataset) -> list[str]:
        labels: list[str] = []
        if dataset.spectra_data is None:
            return labels

        pname = str(dataset.param_name or "param")
        unit = f" {dataset.param_unit}" if dataset.param_unit else ""
        for i in range(len(dataset.spectra_data)):
            value = dataset.get_param_value(i)
            if isinstance(value, (int, float, np.floating)):
                value_text = format_legend_param_value(value, decimals=2)
                labels.append(f"{pname}={value_text}{unit}")
            else:
                labels.append(f"{pname}={value}")
        return labels

    def _save_batch_plot(
        self,
        dataset: SpectrumDataset,
        output_path: str,
        mode: str,
        y_label: str,
        single_index: int | None = None,
        title: str = "",
        window: tuple[float, float] | None = None,
    ) -> None:
        if dataset.wavelengths_nm is None or dataset.spectra_data is None:
            raise ValueError("暂无光谱数据")

        wl = np.asarray(dataset.wavelengths_nm, dtype=float)
        spectra = np.asarray(dataset.spectra_data, dtype=float)
        single_idx: int | None = None
        if mode == "single":
            single_idx = 0 if single_index is None else max(0, int(single_index))
            if single_idx >= len(spectra):
                raise ValueError("单线模式索引超出范围")
            spectra = np.asarray([spectra[single_idx]], dtype=float)

        wl, spectra = self._clip_by_wavelength_window(wl, spectra, window)

        if mode == "3d":
            if dataset.param_values_scaled is None:
                raise ValueError("3D 模式需要数值型参数")

            params = np.asarray(dataset.param_values_scaled, dtype=float)
            payload = {
                "mode": "3d",
                "wavelengths": wl,
                "spectra": spectra,
                "param_values": params,
                "param_name": str(dataset.param_name or "param"),
                "y_label": y_label,
                "title": title,
            }
            export_plot_payload_png(payload, output_path, dpi=400, style_name="origin")
            return

        labels = self._build_line_labels(dataset)
        if single_idx is not None:
            labels = [labels[single_idx] if single_idx < len(labels) else f"line_{single_idx + 1}"]

        payload = {
            "mode": "2d",
            "wavelengths": wl,
            "spectra": spectra,
            "labels": labels,
            "x_label": "Wavelength (nm)",
            "y_label": y_label,
            "title": title,
        }
        export_plot_payload_png(payload, output_path, dpi=400, style_name="origin")

    def _has_data(self) -> bool:
        return self.dataset.spectra_data is not None and self.dataset.wavelengths_nm is not None

    def _effective_title(self) -> str:
        return super()._effective_title(self._t("viz.title"))

    def _effective_y_label(self) -> str:
        return super()._effective_y_label(self._t("viz.ylabel.extinction", "Absorption (a.u.)"))

    def _on_plot_edit_state_changed(self) -> None:
        if self._has_data():
            self.refresh_plot()

    def _export_metrics_for_dataset(
        self,
        dataset: SpectrumDataset,
        output_path: str | None,
        mode: str,
        index: int | None,
    ) -> tuple[bool, str]:
        idx = 0 if index is None else max(0, int(index))
        return dataset.export_metrics_table(output_path, mode=mode, index=idx)

    def _export_metrics_once(
        self,
        dataset: SpectrumDataset,
        source_file_path: str | None,
        output_target: str | Path | None,
        mode: str,
        index: int | None,
    ) -> tuple[bool, str]:
        target_path: str | None = None
        if output_target is not None:
            target_path = str(resolve_metrics_output_path(output_target, source_file_path))
        return self._export_metrics_for_dataset(dataset, target_path, mode, index)

    def _export_plots_for_dataset(
        self,
        dataset: SpectrumDataset,
        source_file_path: str,
        output_dir: str | Path,
        mode: str,
        y_label: str,
        title: str,
        window: tuple[float, float] | None,
    ) -> list[str]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        source = Path(source_file_path)
        base_name = source.stem
        run_mode = normalize_export_mode(mode, default_mode="multi", allow_1d_alias=True)
        param_name = (dataset.param_name or "param").strip() or "param"
        saved_paths: list[str] = []

        if run_mode == "single":
            if dataset.spectra_data is None:
                raise ValueError("暂无光谱数据")

            for idx in range(int(len(dataset.spectra_data))):
                value = dataset.get_param_value(idx)
                value_text = format_filename_param_value(value)
                suffix = f"{param_name}={value_text}"
                file_name = f"{base_name}_{sanitize_filename(suffix)}.png"
                img_path = out_dir / file_name
                self._save_batch_plot(
                    dataset,
                    str(img_path),
                    "single",
                    y_label=y_label,
                    single_index=idx,
                    title=title,
                    window=window,
                )
                saved_paths.append(str(img_path))
            return saved_paths

        dim_suffix = "2d" if run_mode == "multi" else "3d"
        suffix = f"{param_name}-{dim_suffix}"
        file_name = f"{base_name}_{sanitize_filename(suffix)}.png"
        img_path = out_dir / file_name
        self._save_batch_plot(dataset, str(img_path), run_mode, y_label=y_label, title=title, window=window)
        saved_paths.append(str(img_path))
        return saved_paths

    def export_current_plots(
        self,
        output_dir: str,
        mode: str | None = None,
    ) -> tuple[bool, list[str] | str]:
        if self.dataset.spectra_data is None or self.dataset.file_path is None:
            return False, "暂无光谱数据"
        if not output_dir:
            return False, "请选择图片输出位置"

        run_mode = normalize_export_mode(mode, default_mode=self.current_mode, allow_1d_alias=True)
        try:
            saved_paths = self._export_plots_for_dataset(
                self.dataset,
                self.dataset.file_path,
                output_dir,
                run_mode,
                self._effective_y_label(),
                self._effective_title(),
                self.wavelength_window,
            )
        except Exception as exc:
            return False, str(exc)
        return True, saved_paths

    def run_batch_export_plots(
        self,
        csv_paths: list[str],
        output_dir: str,
        mode: str = "multi",
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        paths, out_dir = self._prepare_batch_export(
            csv_paths,
            output_dir,
            output_dir_error="请选择图片输出位置",
        )

        run_mode = normalize_export_mode(mode, default_mode="multi", allow_1d_alias=True)
        total = len(paths)
        mode_text = {"single": "单线", "multi": "多线", "3d": "3D"}[run_mode]
        self._log(log_callback, f"开始批量导出图片 {total} 个文件 (模式: {mode_text})...")

        success = 0
        failed = 0
        saved_images = 0
        y_label = self._effective_y_label()
        title = self._effective_title()
        window = self.wavelength_window

        for i, file_path in enumerate(paths):
            try:
                source = Path(file_path)
                fname = source.name

                self._log(log_callback, f"[{i + 1}/{total}] 处理: {fname}")
                ds = SpectrumDataset()
                ds.load_csv_data(file_path)
                saved_paths = self._export_plots_for_dataset(
                    ds,
                    file_path,
                    out_dir,
                    run_mode,
                    y_label,
                    title,
                    window,
                )
                success += 1
                saved_images += len(saved_paths)
                self._log(log_callback, f"  - 图片成功: {len(saved_paths)} 张")
            except Exception as exc:
                failed += 1
                self._log(log_callback, f"  - 错误: {exc}")

        self._log(log_callback, "批量图片导出完成!")
        return {
            "action": "plots",
            "success_count": success,
            "failed_count": failed,
            "total_count": total,
            "saved_images": saved_images,
            "mode": run_mode,
        }

    def run_batch_export_metrics(
        self,
        csv_paths: list[str],
        output_dir: str,
        mode: str = "multi",
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        paths, out_dir = self._prepare_batch_export(
            csv_paths,
            output_dir,
            output_dir_error="请选择输出位置",
        )
        excel_dir = out_dir / "Excel"
        excel_dir.mkdir(parents=True, exist_ok=True)

        run_mode = normalize_export_mode(mode, default_mode="multi", allow_1d_alias=True)
        total = len(paths)
        self._log(log_callback, f"开始批量导出指标 {total} 个文件...")

        success = 0
        failed = 0
        excel_paths: list[str] = []

        for i, file_path in enumerate(paths):
            try:
                source = Path(file_path)
                fname = source.name
                base_name = source.stem

                self._log(log_callback, f"[{i + 1}/{total}] 处理: {fname}")
                ds = SpectrumDataset()
                ds.load_csv_data(file_path)
                ok, result = self._export_metrics_once(
                    ds,
                    source_file_path=file_path,
                    output_target=excel_dir / f"{base_name}.xlsx",
                    mode=run_mode,
                    index=0,
                )
                if not ok:
                    raise ValueError(result)
                excel_paths.append(result)
                success += 1
                self._log(log_callback, f"  - 指标成功: {Path(result).name}")
            except Exception as exc:
                failed += 1
                self._log(log_callback, f"  - 错误: {exc}")

        excel_path = ""
        if excel_paths:
            excel_path = excel_paths[0] if len(excel_paths) == 1 else str(excel_dir)
            self._log(log_callback, f"表格已保存: {excel_path}")

        self._log(log_callback, "批量指标导出完成!")
        return {
            "action": "metrics",
            "success_count": success,
            "failed_count": failed,
            "total_count": total,
            "excel_path": excel_path,
            "saved_excels": len(excel_paths),
            "mode": run_mode,
        }

    def run_batch_analysis(
        self,
        csv_paths: list[str],
        output_dir: str,
        mode: str = "multi",
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        # 兼容旧接口：依次执行“导出图片 + 导出指标”。
        plot_result = self.run_batch_export_plots(
            csv_paths=csv_paths,
            output_dir=output_dir,
            mode=mode,
            log_callback=log_callback,
        )
        metrics_result = self.run_batch_export_metrics(
            csv_paths=csv_paths,
            output_dir=output_dir,
            mode=mode,
            log_callback=log_callback,
        )
        self._log(log_callback, "批量分析全部完成!")
        return {
            "action": "all",
            "success_count": plot_result.get("success_count", 0),
            "failed_count": plot_result.get("failed_count", 0),
            "total_count": plot_result.get("total_count", 0),
            "saved_images": plot_result.get("saved_images", 0),
            "excel_path": metrics_result.get("excel_path", ""),
            "mode": normalize_export_mode(mode, default_mode="multi", allow_1d_alias=True),
        }

    def load_csv(self, file_path: str) -> None:
        self.busy_changed.emit(True)
        try:
            self.dataset.load_csv_data(file_path)
            self.current_index = 0
            self.reset_plot_edit_state()

            info = {
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "param_name": self.dataset.param_name,
                "count": int(len(self.dataset.spectra_data)) if self.dataset.spectra_data is not None else 0,
            }
            self.data_loaded.emit(info)
            self.index_range_changed.emit(max(0, info["count"] - 1))
            self.refresh_plot()
            self._emit_info("success", "common.success", self._t("viz.message.loaded"))
        except Exception as exc:
            self._emit_info("error", "common.error", f"{self._t('msg.read_error')}: {exc}")
        finally:
            self.busy_changed.emit(False)

    def set_mode(self, mode: str) -> None:
        if mode not in {"single", "multi", "3d"}:
            return
        self.current_mode = mode
        self.refresh_plot()

    def set_index(self, index: int) -> None:
        self.current_index = max(0, int(index))
        if self.current_mode == "single":
            self.refresh_plot()

    def refresh_plot(self) -> None:
        if self.dataset.spectra_data is None or self.dataset.wavelengths_nm is None:
            self._emit_info("warning", "common.warning", self._t("viz.message.no_data"))
            return

        spectra = np.asarray(self.dataset.spectra_data, dtype=float)
        wl = np.asarray(self.dataset.wavelengths_nm, dtype=float)
        param_name = self.dataset.param_name

        if self.current_mode == "single":
            idx = min(self.current_index, len(spectra) - 1)
            value = self.dataset.get_param_value(idx)
            if isinstance(value, (int, float, np.floating)):
                unit = f" {self.dataset.param_unit}" if self.dataset.param_unit else ""
                value_text = format_legend_param_value(value, decimals=2)
                label = f"{param_name}={value_text}{unit}"
            else:
                label = f"{param_name}={value}"

            try:
                wl_view, spectrum_view = self._clip_by_wavelength_window(
                    wl,
                    np.asarray(spectra[idx], dtype=float),
                    self.wavelength_window,
                )
            except ValueError:
                self._emit_info("warning", "common.warning", self._t("viz.message.empty_range", "当前波段范围内无可显示数据"))
                return

            payload = {
                "mode": "single",
                "wavelengths": wl_view,
                "spectra": spectrum_view,
                "labels": [label],
                "y_label": self._effective_y_label(),
                "title": self._effective_title(),
            }
            self.plot_data_changed.emit(payload)
            self._update_metrics_single(idx)
            return

        if self.current_mode == "multi":
            labels: list[str] = []
            for i in range(len(spectra)):
                value = self.dataset.get_param_value(i)
                if isinstance(value, (int, float, np.floating)):
                    unit = f" {self.dataset.param_unit}" if self.dataset.param_unit else ""
                    value_text = format_legend_param_value(value, decimals=2)
                    labels.append(f"{param_name}={value_text}{unit}")
                else:
                    labels.append(f"{param_name}={value}")

            try:
                wl_view, spectra_view = self._clip_by_wavelength_window(
                    wl,
                    spectra,
                    self.wavelength_window,
                )
            except ValueError:
                self._emit_info("warning", "common.warning", self._t("viz.message.empty_range", "当前波段范围内无可显示数据"))
                return

            payload = {
                "mode": "multi",
                "wavelengths": wl_view,
                "spectra": spectra_view,
                "labels": labels,
                "y_label": self._effective_y_label(),
                "title": self._effective_title(),
            }
            self.plot_data_changed.emit(payload)
            self._update_metrics_summary()
            return

        params = self.dataset.param_values_scaled
        if params is None:
            self.current_mode = "multi"
            self._emit_info("warning", "common.warning", self._t("viz.message.no_data"))
            self.refresh_plot()
            return

        try:
            wl_view, spectra_view = self._clip_by_wavelength_window(
                wl,
                spectra,
                self.wavelength_window,
            )
        except ValueError:
            self._emit_info("warning", "common.warning", self._t("viz.message.empty_range", "当前波段范围内无可显示数据"))
            return

        payload = {
            "mode": "3d",
            "wavelengths": wl_view,
            "spectra": spectra_view,
            "param_values": params,
            "param_name": param_name,
            "y_label": self._effective_y_label(),
            "title": self._effective_title(),
        }
        self.plot_data_changed.emit(payload)
        self._update_metrics_summary()

    def _update_metrics_single(self, index: int) -> None:
        metric = self.dataset.calculate_spectrum_metrics(index)
        batch = self.dataset.calculate_all_metrics()
        ris = float(batch.get("ris", 0.0) or 0.0)

        values = self._blank_metrics()
        if metric is not None:
            values["lambda"] = f"{metric.resonance_wavelength:.4f}"
            values["fwhm"] = f"{metric.fwhm:.4f}"
            values["q"] = f"{metric.q_factor:.4f}"
            if str(self.dataset.param_name or "").lower() == "index":
                values["ris"] = f"{ris:.4f}"
                fom = abs(ris) / metric.fwhm if metric.fwhm > 0 else 0.0
                values["fom"] = f"{fom:.4f}"

        self.metrics_changed.emit(values)

    def _update_metrics_summary(self) -> None:
        summary = self.dataset.get_batch_summary()
        values = self._summary_metrics_payload(summary)
        self.metrics_changed.emit(values)

    def save_normalized_csv(self, output_path: str | None = None) -> tuple[bool, str]:
        ok, result = self.dataset.save_normalized_csv(output_path)
        if ok:
            self._emit_info("success", "common.success", self._t("viz.message.normalized_saved"))
        else:
            self._emit_info("error", "common.error", result)
        return ok, result

    def export_metrics_excel(
        self,
        output_path: str | None = None,
        mode: str | None = None,
        index: int | None = None,
    ) -> tuple[bool, str]:
        run_mode = normalize_export_mode(mode, default_mode=self.current_mode, allow_1d_alias=True)
        run_index = self.current_index if index is None else int(index)
        ok, result = self._export_metrics_once(
            self.dataset,
            source_file_path=self.dataset.file_path,
            output_target=output_path,
            mode=run_mode,
            index=run_index,
        )
        if ok:
            self._emit_info("success", "common.success", self._t("viz.message.metrics_exported"))
        else:
            self._emit_info("error", "common.error", result)
        return ok, result

    def export_metrics_csv(
        self,
        output_path: str | None = None,
        mode: str | None = None,
        index: int | None = None,
    ) -> tuple[bool, str]:
        return self.export_metrics_excel(output_path, mode=mode, index=index)
