from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.utils.i18n import I18NManager
from src.viewmodels.viz_viewmodel import VizViewModel
from src.views.components.charts import SpectrumChartWidget
from src.views.components.widgets import ParamStepControl, SectionCard
from src.views.dialogs.viz_batch_dialog import VizBatchDialog
from src.views.pages.plot_edit_mixin import PlotEditMixin


class VizPage(QWidget, PlotEditMixin):
    analysis_type_changed = Signal(str)

    def __init__(self, viewmodel: VizViewModel, i18n: I18NManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.i18n = i18n
        self._init_metric_state()

        self.single_param_control: ParamStepControl | None = None
        self.vary_control: ParamStepControl | None = None
        self._sweep_values_updating = False

        self._build_ui()
        self._bind_signals()
        self.retranslate_ui()

    def _t(self, key: str, fallback: str = "") -> str:
        return self.i18n.t(self.__class__.__name__, self.tr(key), fallback)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._build_top_toolbar(root)

        self.file_label = QLabel()
        self.file_label.setProperty("class", "subtitle")
        root.addWidget(self.file_label)

        content = QHBoxLayout()
        content.setSpacing(10)
        root.addLayout(content, 1)

        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        content.addLayout(left_col, 1)

        self.single_group = QGroupBox()
        self.single_form = QFormLayout(self.single_group)
        self.single_form.setSpacing(8)

        self.sweep_group = QGroupBox()
        self.sweep_form = QFormLayout(self.sweep_group)
        self.sweep_form.setSpacing(8)
        self.sweep_values_list = QListWidget()
        self.sweep_values_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.sweep_values_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sweep_values_list.setMinimumHeight(110)

        self._build_metrics_card(left_col)
        self._build_plot_edit_card(left_col)
        left_col.addWidget(self.single_group)
        left_col.addWidget(self.sweep_group)
        left_col.addStretch(1)

        chart_card = SectionCard()
        self.chart = SpectrumChartWidget()
        chart_card.body.addWidget(self.chart)
        content.addWidget(chart_card, 3)

        self._bind_top_toolbar_signals(
            open_handler=self._open_csv_common,
            batch_handler=lambda: self._open_batch_dialog_common(VizBatchDialog),
            export_metrics_handler=self._export_metrics,
            export_plot_handler=self._export_plot,
            analysis_changed_handler=self._on_analysis_combo_changed,
            mode_changed_handler=self._on_mode_changed,
        )
        self._bind_plot_edit_signals()

    def _bind_signals(self) -> None:
        self.viewmodel.data_loaded.connect(self._on_data_loaded)
        self.viewmodel.plot_data_changed.connect(self._on_plot_data)
        self.viewmodel.metrics_changed.connect(self._on_metrics)
        self.viewmodel.index_range_changed.connect(self._on_index_range)
        self.viewmodel.message.connect(self._on_message)
        self.viewmodel.busy_changed.connect(self._set_busy)
        self.sweep_values_list.itemChanged.connect(self._on_sweep_values_changed)

    def retranslate_ui(self) -> None:
        self._retranslate_top_toolbar(
            open_button_key="viz.open_csv",
            mode_keys=("viz.mode.single", "viz.mode.multi", "viz.mode.3d"),
            default_analysis="viz",
        )

        self.single_group.setTitle(self._t("mda.single_params"))
        self.sweep_group.setTitle(self._t("mda.sweep_values", "扫描参数取值"))
        self._retranslate_metric_and_edit(plot_title_placeholder=self._t("viz.title"))

        self._rebuild_controls()
        self._apply_mode_ui()

    def set_analysis_type(self, analysis_type: str) -> None:
        self._set_analysis_type_combo(analysis_type)

    @staticmethod
    def _format_param_display(value: object, unit: str = "") -> str:
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, float)):
            num = float(value)
            text = f"{num:.6f}".rstrip("0").rstrip(".")
            return f"{text} {unit}".strip()
        return str(value)

    def _selected_sweep_indices(self) -> list[int]:
        indices: list[int] = []
        for i in range(self.sweep_values_list.count()):
            item = self.sweep_values_list.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data is not None:
                    indices.append(int(data))
        return indices

    def _rebuild_sweep_values(self, *, reset_checked: bool) -> None:
        previous = self._selected_sweep_indices() if not reset_checked else []
        self._sweep_values_updating = True
        try:
            self.sweep_values_list.clear()
            if self.single_param_control is None:
                return
            combo = self.single_param_control.combo
            for idx in range(combo.count()):
                text = combo.itemText(idx)
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, idx)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                checked = reset_checked or (not previous) or (idx in previous)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                self.sweep_values_list.addItem(item)
        finally:
            self._sweep_values_updating = False

    def _rebuild_controls(self) -> None:
        self.single_param_control = None
        self.vary_control = None

        self._clear_form_rows(self.single_form)
        self._clear_form_rows(self.sweep_form)
        self._sweep_values_updating = True
        self.sweep_values_list.clear()
        self._sweep_values_updating = False

        dataset = self.viewmodel.dataset
        if dataset.spectra_data is None:
            return

        count = int(len(dataset.spectra_data))
        if count <= 0:
            return

        param_name = (dataset.param_name or "param").strip() or "param"

        self.single_param_control = ParamStepControl()
        for idx in range(count):
            value = dataset.get_param_value(idx)
            display = self._format_param_display(value, dataset.param_unit)
            self.single_param_control.combo.addItem(display, idx)
        self.single_param_control.combo.currentIndexChanged.connect(self._on_single_selection_changed)

        index = min(max(self.viewmodel.current_index, 0), count - 1)
        self.single_param_control.combo.setCurrentIndex(index)
        self.single_form.addRow(QLabel(param_name), self.single_param_control)

        self.vary_control = ParamStepControl()
        self.vary_control.combo.addItem(param_name, param_name)
        self.vary_control.setEnabled(False)
        self.sweep_form.addRow(QLabel(self._t("mda.varying_param")), self.vary_control)
        self.sweep_form.addRow(QLabel(self._t("mda.sweep_values", "扫描参数取值")), self.sweep_values_list)
        self._rebuild_sweep_values(reset_checked=True)
        self.viewmodel.set_selected_indices(self._selected_sweep_indices(), refresh=False)

    def _on_single_selection_changed(self, _: int) -> None:
        if self.single_param_control is None:
            return
        index = self.single_param_control.combo.currentData()
        if index is None:
            return
        self.viewmodel.set_index(int(index))

    def _on_sweep_values_changed(self, _: QListWidgetItem) -> None:
        if self._sweep_values_updating:
            return
        mode = str(self.mode_combo.currentData() or "single")
        if mode == "single":
            return
        selected = self._selected_sweep_indices()
        if not selected:
            self.chart.clear()
        self.viewmodel.set_selected_indices(selected)

    def _on_mode_changed(self, _: int) -> None:
        self._apply_mode_ui()
        mode = str(self.mode_combo.currentData() or "single")
        if mode == "single":
            self.viewmodel.set_selected_indices(None, refresh=False)
        else:
            selected = self._selected_sweep_indices()
            if not selected:
                self.chart.clear()
            self.viewmodel.set_selected_indices(selected, refresh=False)
        self.viewmodel.set_mode(mode)

    def _on_analysis_combo_changed(self, _: int) -> None:
        self._emit_analysis_type_changed_from_combo("viz")

    def _on_index_range(self, maximum: int) -> None:
        if self.single_param_control is None:
            return
        expected = max(0, int(maximum) + 1)
        combo = self.single_param_control.combo
        if combo.count() != expected:
            self._rebuild_controls()
            return
        index = min(max(self.viewmodel.current_index, 0), max(0, expected - 1))
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)
        self._rebuild_sweep_values(reset_checked=False)

    def _apply_mode_ui(self) -> None:
        mode = self.mode_combo.currentData()
        is_single = mode == "single"
        self.single_group.setVisible(is_single)
        self.sweep_group.setVisible(not is_single)

    def _on_data_loaded(self, info: dict) -> None:
        self._set_file_label_from_info(info)
        self._sync_plot_edit_controls_from_viewmodel()
        self._configure_wavelength_range_controls()
        self._rebuild_controls()
        self._apply_mode_ui()

    def _set_busy(self, busy: bool) -> None:
        widgets: list[QWidget] = []
        if self.single_param_control is not None:
            widgets.append(self.single_param_control)
        if self.vary_control is not None:
            widgets.append(self.vary_control)
        widgets.append(self.sweep_values_list)
        self._set_common_busy(busy, widgets)

    def _export_metrics(self) -> None:
        self._export_metrics_by_mode(
            fallback_stem="spectrum",
            on_single=lambda target, _mode: self.viewmodel.export_metrics_excel(target),
        )

    def _export_plot(self) -> None:
        self._export_current_plot_common(
            has_data=self.viewmodel.dataset.spectra_data is not None,
            no_data_message_key="viz.message.no_data",
            success_message_key="viz.message.plot_exported",
        )
