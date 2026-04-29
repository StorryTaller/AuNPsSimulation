from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from src.models.metrics_calc import build_summary_row, calculate_batch_metrics, calculate_spectrum_metrics
from src.models.spectrum_model import MultiDimSpectrumDataset
from src.utils.export_helpers import (
    format_filename_param_value,
    normalize_export_mode,
    round_export_metric_row,
    resolve_metrics_output_path,
    sanitize_filename,
)
from src.utils.i18n import I18NManager
from src.viewmodels.base_viewmodel import BasePlotViewModel
from src.views.components.charts import export_plot_payload_png


class MdaViewModel(BasePlotViewModel):
    data_loaded = Signal(dict)
    schema_changed = Signal(dict)
    plot_data_changed = Signal(dict)
    metrics_changed = Signal(dict)
    message = Signal(str, str, str)
    busy_changed = Signal(bool)

    def __init__(self, i18n: I18NManager, parent: QObject | None = None) -> None:
        super().__init__(i18n, parent)
        self.dataset = MultiDimSpectrumDataset()
        self.mode = "single"
        self.last_single_selection: dict[str, Any] = {}
        self.last_varying_param = ""
        self.last_fixed_params: dict[str, Any] = {}

    @staticmethod
    def _default_single_selection(dataset: MultiDimSpectrumDataset) -> dict[str, Any]:
        selection: dict[str, Any] = {}
        for name in dataset.param_names:
            values = dataset.get_param_unique_values(name)
            selection[name] = values[0] if values else None
        return selection

    @staticmethod
    def _default_sweep_selection(dataset: MultiDimSpectrumDataset) -> tuple[str, dict[str, Any]]:
        params = list(dataset.param_names)
        if not params:
            return "", {}

        varying = params[0]
        fixed: dict[str, Any] = {}
        for name in params:
            if name == varying:
                continue
            values = dataset.get_param_unique_values(name)
            fixed[name] = values[0] if values else None
        return varying, fixed

    def _has_data(self) -> bool:
        return self.dataset.spectra_data_full is not None and self.dataset.wavelengths_nm is not None

    def _effective_title(self) -> str:
        return super()._effective_title(self._t("mda.title"))

    def _effective_y_label(self) -> str:
        return super()._effective_y_label(self._t("viz.ylabel.extinction", "Absorption (a.u.)"))

    def _on_plot_edit_state_changed(self) -> None:
        self._refresh_last_plot_if_needed()

    @staticmethod
    def _normalize_selection_for_dataset(
        dataset: MultiDimSpectrumDataset,
        selection: dict[str, Any] | None,
    ) -> dict[str, Any]:
        chosen = dict(selection or {})
        normalized: dict[str, Any] = {}
        for name in dataset.param_names:
            values = dataset.get_param_unique_values(name)
            if not values:
                normalized[name] = None
                continue
            value = chosen.get(name, values[0])
            normalized[name] = value if value in values else values[0]
        return normalized

    def _resolve_sweep_selection(
        self,
        dataset: MultiDimSpectrumDataset,
        varying_param: str | None,
        fixed_params: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        default_varying, default_fixed = self._default_sweep_selection(dataset)
        picked_varying = str(varying_param or "").strip()
        if not picked_varying or picked_varying not in dataset.param_names:
            picked_varying = default_varying
        if not picked_varying:
            raise ValueError("未检测到可扫描参数")

        selected_fixed = dict(default_fixed)
        for key, value in dict(fixed_params or {}).items():
            if key in dataset.param_names and key != picked_varying:
                selected_fixed[key] = value

        normalized_fixed: dict[str, Any] = {}
        for name in dataset.param_names:
            if name == picked_varying:
                continue
            values = dataset.get_param_unique_values(name)
            if not values:
                normalized_fixed[name] = None
                continue
            value = selected_fixed.get(name, values[0])
            normalized_fixed[name] = value if value in values else values[0]
        return picked_varying, normalized_fixed

    def _export_metrics_for_dataset(
        self,
        dataset: MultiDimSpectrumDataset,
        output_path: str | None,
        mode: str,
        selection: dict[str, Any] | None = None,
        varying_param: str | None = None,
        fixed_params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        run_mode = normalize_export_mode(mode, default_mode="single")
        if run_mode == "single":
            picked_selection = self._normalize_selection_for_dataset(dataset, selection)
            rows = self._collect_metrics_rows(dataset, run_mode, selection=picked_selection)
        else:
            picked_varying, picked_fixed = self._resolve_sweep_selection(dataset, varying_param, fixed_params)
            rows = self._collect_metrics_rows(
                dataset,
                run_mode,
                varying_param=picked_varying,
                fixed_params=picked_fixed,
            )

        if not rows:
            return False, "暂无可导出的指标"

        if output_path is None:
            base = Path(dataset.file_path or "mda_metrics.xlsx")
            output_path = str(base.with_suffix(".xlsx"))

        target = Path(output_path)
        if target.suffix.lower() != ".xlsx":
            target = target.with_suffix(".xlsx")

        target.parent.mkdir(parents=True, exist_ok=True)
        formatted_rows = [round_export_metric_row(row, decimals=3) for row in rows]
        pd.DataFrame(formatted_rows).to_excel(target, index=False, sheet_name="Sheet1")
        return True, str(target)

    def _export_metrics_once(
        self,
        dataset: MultiDimSpectrumDataset,
        source_file_path: str | None,
        output_target: str | Path | None,
        mode: str,
        selection: dict[str, Any] | None = None,
        varying_param: str | None = None,
        fixed_params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        target_path: str | None = None
        if output_target is not None:
            target_path = str(resolve_metrics_output_path(output_target, source_file_path))
        return self._export_metrics_for_dataset(
            dataset,
            output_path=target_path,
            mode=mode,
            selection=selection,
            varying_param=varying_param,
            fixed_params=fixed_params,
        )

    def _export_plots_for_dataset(
        self,
        dataset: MultiDimSpectrumDataset,
        source_file_path: str,
        output_dir: str | Path,
        mode: str,
        y_label: str,
        title: str,
        window: tuple[float, float] | None,
        selection: dict[str, Any] | None = None,
        varying_param: str | None = None,
        fixed_params: dict[str, Any] | None = None,
    ) -> list[str]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        source = Path(source_file_path)
        base_name = source.stem
        run_mode = normalize_export_mode(mode, default_mode="single")
        saved_paths: list[str] = []

        if run_mode == "single":
            params = list(dataset.param_names)
            if not params:
                raise ValueError("未检测到可扫描参数")

            varying = params[0]
            picked_selection = self._normalize_selection_for_dataset(dataset, selection)
            fixed = {name: picked_selection.get(name) for name in params if name != varying}
            values_raw = dataset.get_param_unique_values(varying)
            if not values_raw:
                raise ValueError("未检测到可导出的参数取值")

            for value_raw in values_raw:
                item_selection = dict(fixed)
                item_selection[varying] = value_raw
                value = dataset.convert_param_value(varying, value_raw)
                suffix = f"{varying}={format_filename_param_value(value)}"
                file_name = f"{base_name}_{sanitize_filename(suffix)}.png"
                img_path = out_dir / file_name
                self._save_single_plot(
                    dataset,
                    item_selection,
                    str(img_path),
                    y_label=y_label,
                    title=title,
                    window=window,
                )
                saved_paths.append(str(img_path))
            return saved_paths

        picked_varying, picked_fixed = self._resolve_sweep_selection(dataset, varying_param, fixed_params)
        dim = "2d" if run_mode == "multi" else "3d"
        file_name = f"{base_name}_{sanitize_filename(picked_varying)}-{dim}.png"
        img_path = out_dir / file_name
        self._save_sweep_plot(
            dataset,
            picked_varying,
            picked_fixed,
            run_mode,
            str(img_path),
            y_label=y_label,
            title=title,
            window=window,
        )
        saved_paths.append(str(img_path))
        return saved_paths

    def export_current_plots(
        self,
        output_dir: str,
        mode: str = "single",
        selection: dict[str, Any] | None = None,
        varying_param: str | None = None,
        fixed_params: dict[str, Any] | None = None,
    ) -> tuple[bool, list[str] | str]:
        if self.dataset.spectra_data_full is None or self.dataset.file_path is None:
            return False, "暂无光谱数据"
        if not output_dir:
            return False, "请选择输出位置"

        try:
            saved_paths = self._export_plots_for_dataset(
                self.dataset,
                self.dataset.file_path,
                output_dir,
                mode,
                self._effective_y_label(),
                self._effective_title(),
                self.wavelength_window,
                selection=selection,
                varying_param=varying_param,
                fixed_params=fixed_params,
            )
        except Exception as exc:
            return False, str(exc)
        return True, saved_paths

    def _refresh_last_plot_if_needed(self) -> None:
        if not self._has_data():
            return

        if self.mode == "single":
            selection = dict(self.last_single_selection) if self.last_single_selection else self._default_single_selection(self.dataset)
            if selection:
                self.plot_single(selection)
            return

        varying = self.last_varying_param
        fixed = dict(self.last_fixed_params)
        if not varying:
            varying, defaults = self._default_sweep_selection(self.dataset)
            if not fixed:
                fixed = defaults
        if varying:
            self.plot_sweep(varying, fixed, self.mode)

    def _collect_metrics_rows(
        self,
        dataset: MultiDimSpectrumDataset,
        mode: str,
        selection: dict[str, Any] | None = None,
        varying_param: str | None = None,
        fixed_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        run_mode = normalize_export_mode(mode, default_mode="single")

        if run_mode == "single":
            picked = dict(selection or self._default_single_selection(dataset))
            wl, spectrum, _ = dataset.get_spectrum_by_selection(picked)
            metric = calculate_spectrum_metrics(wl, spectrum)

            row: dict[str, Any] = {
                name: dataset.convert_param_value(name, value)
                for name, value in picked.items()
            }
            if metric is None:
                row.update(
                    {
                        "λ(nm)": np.nan,
                        "FWHM(nm)": np.nan,
                        "Q": np.nan,
                        "RIS(nm/RIU)": np.nan,
                        "FOM(1/RIU)": np.nan,
                    }
                )
            else:
                row.update(
                    {
                        "λ(nm)": metric.resonance_wavelength,
                        "FWHM(nm)": metric.fwhm,
                        "Q": metric.q_factor,
                        "RIS(nm/RIU)": np.nan,
                        "FOM(1/RIU)": np.nan,
                    }
                )
            return [row]

        picked_vary = str(varying_param or "").strip()
        picked_fixed = dict(fixed_params or {})
        if not picked_vary:
            picked_vary, defaults = self._default_sweep_selection(dataset)
            if not picked_fixed:
                picked_fixed = defaults
        if not picked_vary:
            raise ValueError("未检测到可扫描参数")

        wl, spectra, values_raw = dataset.get_sweep(picked_vary, picked_fixed)
        converted_values = [dataset.convert_param_value(picked_vary, v) for v in values_raw]
        batch = calculate_batch_metrics(
            wl,
            spectra,
            param_values=converted_values,
            param_name=picked_vary,
        )
        single_metrics = list(batch.get("single_metrics", []))
        ris = float(batch.get("ris", 0.0) or 0.0)
        is_index = picked_vary.strip().lower() == "index"

        rows: list[dict[str, Any]] = []
        for i, raw in enumerate(values_raw):
            metric = single_metrics[i] if i < len(single_metrics) else None
            row: dict[str, Any] = {picked_vary: dataset.convert_param_value(picked_vary, raw)}
            for key, value in picked_fixed.items():
                row[f"fixed_{key}"] = dataset.convert_param_value(key, value)

            if metric is None:
                row.update(
                    {
                        "λ(nm)": np.nan,
                        "FWHM(nm)": np.nan,
                        "Q": np.nan,
                        "RIS(nm/RIU)": ris if is_index else np.nan,
                        "FOM(1/RIU)": np.nan,
                    }
                )
            else:
                fom = abs(ris) / metric.fwhm if (is_index and metric.fwhm > 0) else np.nan
                row.update(
                    {
                        "λ(nm)": metric.resonance_wavelength,
                        "FWHM(nm)": metric.fwhm,
                        "Q": metric.q_factor,
                        "RIS(nm/RIU)": ris if is_index else np.nan,
                        "FOM(1/RIU)": fom,
                    }
                )
            rows.append(row)
        return rows

    def export_metrics_excel(
        self,
        output_path: str | None = None,
        mode: str = "single",
        selection: dict[str, Any] | None = None,
        varying_param: str | None = None,
        fixed_params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        if self.dataset.spectra_data_full is None:
            msg = "暂无光谱数据"
            self._emit_info("error", "common.error", msg)
            return False, msg

        try:
            ok, result = self._export_metrics_once(
                self.dataset,
                source_file_path=self.dataset.file_path,
                output_target=output_path,
                mode=mode,
                selection=selection,
                varying_param=varying_param,
                fixed_params=fixed_params,
            )
            if not ok:
                self._emit_info("error", "common.error", result)
                return False, result
        except Exception as exc:
            msg = str(exc)
            self._emit_info("error", "common.error", msg)
            return False, msg

        self._emit_info("success", "common.success", self._t("viz.message.metrics_exported"))
        return True, result

    def _save_single_plot(
        self,
        dataset: MultiDimSpectrumDataset,
        selection: dict[str, Any],
        save_path: str,
        y_label: str,
        title: str = "",
        window: tuple[float, float] | None = None,
    ) -> None:
        wl, spectrum, _ = dataset.get_spectrum_by_selection(selection)
        x = np.asarray(wl, dtype=float)
        line = np.asarray(spectrum, dtype=float)
        x, line = self._clip_by_wavelength_window(x, line, window)

        label_parts = [f"{k}={dataset.format_param_value(k, v, decimals=2, compact=True)}" for k, v in selection.items()]
        label = ", ".join(label_parts) if label_parts else "selection"
        payload = {
            "mode": "2d",
            "wavelengths": x,
            "spectra": line,
            "labels": [label],
            "x_label": "Wavelength (nm)",
            "y_label": y_label,
            "title": title,
        }
        export_plot_payload_png(payload, save_path, dpi=400, style_name="origin")

    def _save_sweep_plot(
        self,
        dataset: MultiDimSpectrumDataset,
        varying_param: str,
        fixed_params: dict[str, Any],
        mode: str,
        save_path: str,
        y_label: str,
        title: str = "",
        window: tuple[float, float] | None = None,
    ) -> None:
        wl, spectra, values_raw = dataset.get_sweep(varying_param, fixed_params)
        x = np.asarray(wl, dtype=float)
        lines = np.asarray(spectra, dtype=float)
        x, lines = self._clip_by_wavelength_window(x, lines, window)

        if mode == "3d":
            numeric = [dataset.convert_param_value(varying_param, v) for v in values_raw]
            if not all(isinstance(v, (int, float)) for v in numeric):
                raise ValueError("3D 模式需要数值型扫描参数")

            fixed_text = "\n".join([f"{k}={dataset.format_param_value(k, v)}" for k, v in fixed_params.items()])
            payload = {
                "mode": "3d",
                "wavelengths": x,
                "param_values": np.asarray(numeric, dtype=float),
                "spectra": lines,
                "y_label": y_label,
                "param_name": varying_param,
                "title": title,
                "fixed_text": fixed_text,
            }
            export_plot_payload_png(payload, save_path, dpi=400, style_name="origin")
            return

        labels = [f"{varying_param}={dataset.format_param_value(varying_param, v, decimals=2, compact=True)}" for v in values_raw]
        payload = {
            "mode": "2d",
            "wavelengths": x,
            "spectra": lines,
            "labels": labels,
            "x_label": "Wavelength (nm)",
            "y_label": y_label,
            "title": title,
        }
        export_plot_payload_png(payload, save_path, dpi=400, style_name="origin")

    def run_batch_export_plots(
        self,
        csv_paths: list[str],
        output_dir: str,
        mode: str = "single",
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        paths, out_dir = self._prepare_batch_export(
            csv_paths,
            output_dir,
            output_dir_error="请选择输出位置",
        )
        run_mode = normalize_export_mode(mode, default_mode="single")

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
                src = Path(file_path)
                self._log(log_callback, f"[{i + 1}/{total}] 处理: {src.name}")

                ds = MultiDimSpectrumDataset()
                ds.load_csv_multidim(file_path)
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
        mode: str = "single",
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        paths, out_dir = self._prepare_batch_export(
            csv_paths,
            output_dir,
            output_dir_error="请选择输出位置",
        )
        excel_dir = out_dir / "Excel"
        excel_dir.mkdir(parents=True, exist_ok=True)
        run_mode = normalize_export_mode(mode, default_mode="single")

        total = len(paths)
        self._log(log_callback, f"开始批量导出指标 {total} 个文件...")

        success = 0
        failed = 0
        excel_paths: list[str] = []

        for i, file_path in enumerate(paths):
            try:
                src = Path(file_path)
                self._log(log_callback, f"[{i + 1}/{total}] 处理: {src.name}")

                ds = MultiDimSpectrumDataset()
                ds.load_csv_multidim(file_path)
                ok, result = self._export_metrics_once(
                    ds,
                    source_file_path=file_path,
                    output_target=excel_dir / f"{src.stem}.xlsx",
                    mode=run_mode,
                    selection=None,
                    varying_param=None,
                    fixed_params=None,
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

    def load_csv(self, file_path: str) -> None:
        self.busy_changed.emit(True)
        try:
            self.dataset.load_csv_multidim(file_path)
            self.reset_plot_edit_state()
            schema = self._build_schema()
            self.schema_changed.emit(schema)
            self.data_loaded.emit({"file_path": file_path, "file_name": Path(file_path).name})
            self._emit_info("success", "common.success", self._t("mda.message.loaded"))
        except Exception as exc:
            self._emit_info("error", "common.error", str(exc))
        finally:
            self.busy_changed.emit(False)

    def _build_schema(self) -> dict[str, Any]:
        value_map: dict[str, list[dict[str, Any]]] = {}
        for name in self.dataset.param_names:
            entries: list[dict[str, Any]] = []
            for raw in self.dataset.get_param_unique_values(name):
                entries.append({"raw": raw, "display": self.dataset.format_param_value(name, raw)})
            value_map[name] = entries
        return {
            "param_names": list(self.dataset.param_names),
            "values": value_map,
        }

    def set_mode(self, mode: str) -> None:
        if mode in {"single", "multi", "3d"}:
            self.mode = mode

    def plot_single(self, selection: dict[str, Any]) -> None:
        if self.dataset.spectra_data_full is None:
            self._emit_info("warning", "common.warning", self._t("mda.message.no_data"))
            return
        self.mode = "single"
        self.last_single_selection = dict(selection)
        try:
            wl, spectrum, _ = self.dataset.get_spectrum_by_selection(selection)
        except Exception as exc:
            self._emit_info("warning", "common.warning", str(exc))
            return
        wl = np.asarray(wl, dtype=float)
        spectrum = np.asarray(spectrum, dtype=float)

        label_parts = []
        for key, value in selection.items():
            label_parts.append(f"{key}={self.dataset.format_param_value(key, value, decimals=2, compact=True)}")
        label = ", ".join(label_parts) if label_parts else "selection"

        try:
            wl_view, spectrum_view = self._clip_by_wavelength_window(wl, spectrum, self.wavelength_window)
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

        metric = calculate_spectrum_metrics(wl, spectrum)
        values = self._blank_metrics()
        if metric is not None:
            values["lambda"] = f"{metric.resonance_wavelength:.4f}"
            values["fwhm"] = f"{metric.fwhm:.4f}"
            values["q"] = f"{metric.q_factor:.4f}"
        self.metrics_changed.emit(values)

    def plot_sweep(self, varying_param: str, fixed_params: dict[str, Any], mode: str = "multi") -> None:
        if self.dataset.spectra_data_full is None:
            self._emit_info("warning", "common.warning", self._t("mda.message.no_data"))
            return
        run_mode = normalize_export_mode(mode, default_mode="single")
        self.mode = run_mode
        self.last_varying_param = varying_param
        self.last_fixed_params = dict(fixed_params)

        try:
            wl, spectra, values_raw = self.dataset.get_sweep(varying_param, fixed_params)
        except Exception as exc:
            self._emit_info("warning", "common.warning", str(exc))
            return
        wl = np.asarray(wl, dtype=float)
        spectra = np.asarray(spectra, dtype=float)

        labels = [f"{varying_param}={self.dataset.format_param_value(varying_param, v, decimals=2, compact=True)}" for v in values_raw]
        fixed_text = "\\n".join(
            [f"{k}={self.dataset.format_param_value(k, v)}" for k, v in fixed_params.items()]
        )
        try:
            wl_view, spectra_view = self._clip_by_wavelength_window(wl, spectra, self.wavelength_window)
        except ValueError:
            self._emit_info("warning", "common.warning", self._t("viz.message.empty_range", "当前波段范围内无可显示数据"))
            return

        if run_mode == "3d":
            numeric_params = [self.dataset.convert_param_value(varying_param, v) for v in values_raw]
            if not all(isinstance(v, (int, float)) for v in numeric_params):
                self._emit_info("warning", "common.warning", self._t("mda.message.no_data"))
                return
            payload = {
                "mode": "3d",
                "wavelengths": wl_view,
                "spectra": spectra_view,
                "param_values": np.asarray(numeric_params, dtype=float),
                "param_name": varying_param,
                "y_label": self._effective_y_label(),
                "title": self._effective_title(),
                "fixed_text": fixed_text,
            }
        else:
            payload = {
                "mode": "multi",
                "wavelengths": wl_view,
                "spectra": spectra_view,
                "labels": labels,
                "y_label": self._effective_y_label(),
                "title": self._effective_title(),
            }
        self.plot_data_changed.emit(payload)

        converted = [self.dataset.convert_param_value(varying_param, v) for v in values_raw]
        batch = calculate_batch_metrics(
            wl,
            spectra,
            param_values=converted,
            param_name=varying_param,
        )
        summary = build_summary_row(batch)
        values = self._summary_metrics_payload(summary)
        self.metrics_changed.emit(values)
