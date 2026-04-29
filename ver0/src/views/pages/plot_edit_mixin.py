from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.dialog_path_memory import DialogPathMemory
from src.views.components.widgets import AppInfoBar, SectionCard


class PlotEditMixin:
    _METRIC_KEYS = ("lambda", "fwhm", "q", "ris", "fom")
    _METRIC_UNIT_MAP = {
        "lambda": "nm",
        "fwhm": "nm",
        "q": "",
        "ris": "nm/RIU",
        "fom": "1/RIU",
    }

    def _init_metric_state(self) -> None:
        self._metric_keys = self._METRIC_KEYS
        self._metric_name_labels: dict[str, QLabel] = {}
        self._metric_labels: dict[str, QLabel] = {}
        self._metric_unit_labels: dict[str, QLabel] = {}
        self._metric_unit_map: dict[str, str] = dict(self._METRIC_UNIT_MAP)
        self._wavelength_min = 0.0
        self._wavelength_max = 0.0

    def _build_top_toolbar(self, root: QVBoxLayout) -> None:
        top = QHBoxLayout()
        top.setSpacing(8)
        self.btn_open = QPushButton()
        self.btn_batch = QPushButton()
        self.btn_export_metrics = QPushButton()
        self.btn_export_plot = QPushButton()
        self.analysis_combo = QComboBox()
        self.mode_combo = QComboBox()

        self.analysis_combo.addItem("1D", "viz")
        self.analysis_combo.addItem("nD", "mda")
        self.mode_combo.addItem("single", "single")
        self.mode_combo.addItem("multi", "multi")
        self.mode_combo.addItem("3d", "3d")

        top.addWidget(self.btn_open)
        top.addWidget(self.btn_batch)
        top.addWidget(self.btn_export_metrics)
        top.addWidget(self.btn_export_plot)
        top.addSpacing(12)
        top.addWidget(self.mode_combo)
        top.addStretch(1)
        top.addWidget(self.analysis_combo)
        root.addLayout(top)
        self._refresh_data_action_state()

    def _bind_top_toolbar_signals(
        self,
        *,
        open_handler: Callable[[], None],
        batch_handler: Callable[[], None],
        export_metrics_handler: Callable[[], None],
        export_plot_handler: Callable[[], None],
        analysis_changed_handler: Callable[[int], None],
        mode_changed_handler: Callable[[int], None],
    ) -> None:
        self.btn_open.clicked.connect(open_handler)
        self.btn_batch.clicked.connect(batch_handler)
        self.btn_export_metrics.clicked.connect(export_metrics_handler)
        self.btn_export_plot.clicked.connect(export_plot_handler)
        self.analysis_combo.currentIndexChanged.connect(analysis_changed_handler)
        self.mode_combo.currentIndexChanged.connect(mode_changed_handler)

    def _retranslate_top_toolbar(
        self,
        *,
        open_button_key: str,
        mode_keys: tuple[str, str, str],
        default_analysis: str,
    ) -> None:
        self.btn_open.setText(self._t(open_button_key))
        self.btn_batch.setText(self._t("viz.batch.button"))
        self.btn_export_metrics.setText(self._t("viz.export_metrics"))
        self.btn_export_plot.setText(self._t("viz.export_plot"))

        self.analysis_combo.blockSignals(True)
        current_analysis = str(self.analysis_combo.currentData() or default_analysis)
        self.analysis_combo.clear()
        self.analysis_combo.addItem(self._t("analysis.type.viz"), "viz")
        self.analysis_combo.addItem(self._t("analysis.type.mda"), "mda")
        self.analysis_combo.setCurrentIndex(0 if current_analysis == "viz" else 1)
        self.analysis_combo.blockSignals(False)

        self.mode_combo.blockSignals(True)
        current_mode = self.mode_combo.currentData()
        self.mode_combo.clear()
        self.mode_combo.addItem(self._t(mode_keys[0]), "single")
        self.mode_combo.addItem(self._t(mode_keys[1]), "multi")
        self.mode_combo.addItem(self._t(mode_keys[2]), "3d")
        idx = {"single": 0, "multi": 1, "3d": 2}.get(current_mode, 0)
        self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.blockSignals(False)
        self._refresh_data_action_state()

    def _has_loaded_plot_data(self) -> bool:
        dataset = getattr(self.viewmodel, "dataset", None)
        if dataset is None:
            return False
        return (
            getattr(dataset, "spectra_data", None) is not None
            or getattr(dataset, "spectra_data_full", None) is not None
        )

    def _refresh_data_action_state(self, *, busy: bool = False) -> None:
        enabled = (not busy) and self._has_loaded_plot_data()
        self.btn_export_metrics.setEnabled(enabled)
        self.btn_export_plot.setEnabled(enabled)
        if enabled:
            self.btn_export_metrics.setToolTip(self._t("viz.tooltip.export_metrics", "导出当前数据指标"))
            self.btn_export_plot.setToolTip(self._t("viz.tooltip.export_plot", "导出当前图像"))
        else:
            tooltip = self._t("viz.tooltip.open_csv_first", "打开 csv 后可用")
            self.btn_export_metrics.setToolTip(tooltip)
            self.btn_export_plot.setToolTip(tooltip)

    def _set_analysis_type_combo(self, analysis_type: str) -> None:
        index = 0 if analysis_type == "viz" else 1
        self.analysis_combo.blockSignals(True)
        self.analysis_combo.setCurrentIndex(index)
        self.analysis_combo.blockSignals(False)

    def _emit_analysis_type_changed_from_combo(self, default_analysis: str) -> None:
        self.analysis_type_changed.emit(str(self.analysis_combo.currentData() or default_analysis))

    @staticmethod
    def _clear_form_rows(form: QFormLayout) -> None:
        while form.rowCount() > 0:
            form.removeRow(0)

    def _build_metrics_card(self, parent_layout: QVBoxLayout) -> None:
        metrics_card = SectionCard()
        self.metrics_form = QFormLayout()
        for key in self._metric_keys:
            name_label = QLabel()
            value = QLabel("-")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setStyleSheet("font-weight: 700; color: #0078D4;")
            unit = QLabel("")
            unit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            unit.setMinimumWidth(52)
            value_cell = QWidget()
            value_layout = QHBoxLayout(value_cell)
            value_layout.setContentsMargins(0, 0, 0, 0)
            value_layout.setSpacing(6)
            value_layout.addStretch(1)
            value_layout.addWidget(value)
            value_layout.addWidget(unit)
            self._metric_name_labels[key] = name_label
            self._metric_labels[key] = value
            self._metric_unit_labels[key] = unit
            self.metrics_form.addRow(name_label, value_cell)
        metrics_card.body.addLayout(self.metrics_form)
        parent_layout.addWidget(metrics_card)
        self.metrics_card = metrics_card

    def _build_plot_edit_card(self, parent_layout: QVBoxLayout) -> None:
        self.edit_card = SectionCard()
        self.edit_form = QFormLayout()
        self.edit_form.setSpacing(8)

        self.plot_title_label = QLabel()
        self.plot_title_edit = QLineEdit()
        self.y_axis_title_label = QLabel()
        self.y_axis_title_edit = QLineEdit()
        self.range_label = QLabel()
        self.range_start_spin = QDoubleSpinBox()
        self.range_end_spin = QDoubleSpinBox()
        self.btn_reset_range = QPushButton()

        for spin in (self.range_start_spin, self.range_end_spin):
            spin.setDecimals(2)
            spin.setSingleStep(1.0)
            spin.setSuffix(" nm")
            spin.setKeyboardTracking(False)
            spin.setEnabled(False)
        self.btn_reset_range.setEnabled(False)

        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(6)
        range_layout.addWidget(self.range_start_spin)
        range_layout.addWidget(self.range_end_spin)
        range_layout.addWidget(self.btn_reset_range)

        self.edit_form.addRow(self.plot_title_label, self.plot_title_edit)
        self.edit_form.addRow(self.y_axis_title_label, self.y_axis_title_edit)
        self.edit_form.addRow(self.range_label, range_widget)
        self.edit_card.body.addLayout(self.edit_form)
        parent_layout.addWidget(self.edit_card)

    def _bind_plot_edit_signals(self) -> None:
        self.plot_title_edit.textChanged.connect(self.viewmodel.set_custom_plot_title)
        self.y_axis_title_edit.textChanged.connect(self.viewmodel.set_custom_y_label)
        self.range_start_spin.valueChanged.connect(self._on_wavelength_range_changed)
        self.range_end_spin.valueChanged.connect(self._on_wavelength_range_changed)
        self.btn_reset_range.clicked.connect(self._reset_wavelength_range)

    def _retranslate_metric_and_edit(self, *, plot_title_placeholder: str) -> None:
        self.file_label.setText(f"{self._t('viz.file.current')}: {self._t('viz.file.none')}")
        self.metrics_card.set_title(self._t("mda.metrics.title"))
        self.edit_card.set_title(self._t("viz.edit.title"))
        self.plot_title_label.setText(self._t("viz.edit.plot_title"))
        self.y_axis_title_label.setText(self._t("viz.edit.y_title"))
        self.range_label.setText(self._t("viz.edit.wavelength_range"))
        self.btn_reset_range.setText(self._t("viz.edit.range_reset"))
        self.plot_title_edit.setPlaceholderText(plot_title_placeholder)
        self.y_axis_title_edit.setPlaceholderText(self._t("viz.ylabel.extinction", "Absorption (a.u.)"))

        labels = {
            "lambda": self._t("viz.metric.lambda"),
            "fwhm": self._t("viz.metric.fwhm"),
            "q": self._t("viz.metric.q"),
            "ris": self._t("viz.metric.ris"),
            "fom": self._t("viz.metric.fom"),
        }
        for key in self._metric_keys:
            self._metric_name_labels[key].setText(labels[key])
            self._metric_unit_labels[key].setText(self._metric_unit_map.get(key, ""))

    @staticmethod
    def _format_metric_display(value: object) -> str:
        text = str(value if value is not None else "-").strip()
        if not text:
            text = "-"
        return text

    def _on_plot_data(self, payload: dict[str, Any]) -> None:
        mode = payload.get("mode", "single")
        if mode == "3d":
            self.chart.plot_3d(
                payload.get("wavelengths"),
                payload.get("param_values"),
                payload.get("spectra"),
                payload.get("y_label", self._t("viz.ylabel.extinction")),
                payload.get("param_name", "param"),
                title=payload.get("title", ""),
                fixed_text=payload.get("fixed_text", ""),
            )
            return

        self.chart.plot_2d(
            payload.get("wavelengths"),
            payload.get("spectra"),
            labels=payload.get("labels"),
            y_label=payload.get("y_label", self._t("viz.ylabel.extinction")),
            title=payload.get("title", ""),
        )

    def _on_metrics(self, values: dict[str, Any]) -> None:
        for key, label in self._metric_labels.items():
            label.setText(self._format_metric_display(values.get(key, "-")))

    def _on_message(self, level: str, title: str, content: str) -> None:
        method = getattr(AppInfoBar, level, AppInfoBar.info)
        method(self, title, content)

    def _set_common_busy(self, busy: bool, extra_widgets: list[QWidget] | None = None) -> None:
        widgets: list[QWidget] = [
            self.btn_open,
            self.btn_batch,
            self.btn_export_metrics,
            self.btn_export_plot,
            self.analysis_combo,
            self.mode_combo,
            self.plot_title_edit,
            self.y_axis_title_edit,
        ]
        widgets.extend(extra_widgets or [])
        for widget in widgets:
            widget.setDisabled(busy)
        self._refresh_data_action_state(busy=busy)

        wavelengths = self.viewmodel.dataset.wavelengths_nm
        has_wavelengths = wavelengths is not None and len(wavelengths) > 0
        self.range_start_spin.setEnabled((not busy) and has_wavelengths)
        self.range_end_spin.setEnabled((not busy) and has_wavelengths)
        self.btn_reset_range.setEnabled((not busy) and has_wavelengths)

    def _set_file_label_from_info(self, info: dict[str, Any]) -> None:
        name = info.get("file_name", self._t("viz.file.none"))
        self.file_label.setText(f"{self._t('viz.file.current')}: {Path(str(name)).name}")

    def _open_csv_common(self) -> None:
        path, _ = DialogPathMemory.get_open_file_name(
            self,
            self._t("dialog.select_csv"),
            f"{self._t('dialog.filter.csv')};;{self._t('dialog.filter.any')}",
        )
        if path:
            self.viewmodel.load_csv(path)

    def _open_batch_dialog_common(self, dialog_type: type[Any]) -> None:
        dialog = dialog_type(self.viewmodel, self.i18n, self)
        dialog.exec()

    def _choose_metrics_export_target(self, *, fallback_stem: str) -> str:
        source = Path(self.viewmodel.dataset.file_path) if self.viewmodel.dataset.file_path else None
        default_name = f"{(source.stem if source else fallback_stem)}.xlsx"
        target, _ = DialogPathMemory.get_save_file_name(
            self,
            self._t("dialog.select_export_metrics"),
            default_name,
            "Excel files (*.xlsx)",
        )
        return str(target or "")

    def _export_metrics_by_mode(
        self,
        *,
        fallback_stem: str,
        on_single: Callable[[str, str], None],
        on_non_single: Callable[[str, str], None] | None = None,
    ) -> None:
        target = self._choose_metrics_export_target(fallback_stem=fallback_stem)
        if not target:
            return

        mode = str(self.mode_combo.currentData() or "single")
        if mode == "single" or on_non_single is None:
            on_single(target, mode)
            return
        on_non_single(target, mode)

    def _export_current_plot_common(
        self,
        *,
        has_data: bool,
        no_data_message_key: str,
        success_message_key: str,
    ) -> None:
        if (not has_data) or self.viewmodel.dataset.file_path is None:
            AppInfoBar.warning(self, self._t("common.warning"), self._t(no_data_message_key))
            return

        source = Path(self.viewmodel.dataset.file_path)
        mode = str(self.mode_combo.currentData() or "single")
        default_name = f"{source.stem}_{mode}.png"
        target, _ = DialogPathMemory.get_save_file_name(
            self,
            self._t("dialog.select_export_plot"),
            default_name,
            "PNG files (*.png)",
        )
        if not target:
            return

        try:
            saved_path = self.chart.export_current(target, dpi=400, style_name="origin")
        except Exception as exc:
            AppInfoBar.error(self, self._t("common.error"), str(exc))
            return

        AppInfoBar.success(
            self,
            self._t("common.success"),
            f"{self._t(success_message_key)}: {Path(saved_path).name}",
        )

    def _sync_plot_edit_controls_from_viewmodel(self) -> None:
        self.plot_title_edit.blockSignals(True)
        self.plot_title_edit.setText(self.viewmodel.custom_plot_title)
        self.plot_title_edit.blockSignals(False)

        self.y_axis_title_edit.blockSignals(True)
        self.y_axis_title_edit.setText(self.viewmodel.custom_y_label)
        self.y_axis_title_edit.blockSignals(False)

    def _configure_wavelength_range_controls(self) -> None:
        wavelengths = self.viewmodel.dataset.wavelengths_nm
        if wavelengths is None or len(wavelengths) == 0:
            for spin in (self.range_start_spin, self.range_end_spin):
                spin.setEnabled(False)
            self.btn_reset_range.setEnabled(False)
            return

        self._wavelength_min = float(min(wavelengths))
        self._wavelength_max = float(max(wavelengths))
        if self._wavelength_min > self._wavelength_max:
            self._wavelength_min, self._wavelength_max = self._wavelength_max, self._wavelength_min

        for spin in (self.range_start_spin, self.range_end_spin):
            spin.blockSignals(True)
            spin.setRange(self._wavelength_min, self._wavelength_max)
            spin.setEnabled(True)
            spin.blockSignals(False)

        self.btn_reset_range.setEnabled(True)
        self._reset_wavelength_range()

    def _on_wavelength_range_changed(self, _: float) -> None:
        start = float(self.range_start_spin.value())
        end = float(self.range_end_spin.value())

        if start > end:
            sender = self.sender()
            if sender is self.range_start_spin:
                self.range_end_spin.blockSignals(True)
                self.range_end_spin.setValue(start)
                self.range_end_spin.blockSignals(False)
                end = start
            else:
                self.range_start_spin.blockSignals(True)
                self.range_start_spin.setValue(end)
                self.range_start_spin.blockSignals(False)
                start = end

        self.viewmodel.set_wavelength_window(start, end)

    def _reset_wavelength_range(self) -> None:
        self.range_start_spin.blockSignals(True)
        self.range_end_spin.blockSignals(True)
        self.range_start_spin.setValue(self._wavelength_min)
        self.range_end_spin.setValue(self._wavelength_max)
        self.range_start_spin.blockSignals(False)
        self.range_end_spin.blockSignals(False)
        self.viewmodel.set_wavelength_window(None, None)
