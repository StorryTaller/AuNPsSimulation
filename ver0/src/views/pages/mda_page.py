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
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.i18n import I18NManager
from src.viewmodels.mda_viewmodel import MdaViewModel
from src.views.components.charts import SpectrumChartWidget
from src.views.components.widgets import ParamStepControl, SectionCard
from src.views.dialogs.mda_batch_dialog import MdaBatchDialog
from src.views.pages.plot_edit_mixin import PlotEditMixin


class MdaPage(QWidget, PlotEditMixin):
    analysis_type_changed = Signal(str)

    def __init__(self, viewmodel: MdaViewModel, i18n: I18NManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.i18n = i18n

        self.schema: dict = {"param_names": [], "values": {}}
        self.single_controls: dict[str, ParamStepControl] = {}
        self.vary_control: ParamStepControl | None = None
        self._sweep_values_updating = False
        self._init_metric_state()

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
        sweep_layout = QVBoxLayout(self.sweep_group)
        sweep_layout.setContentsMargins(8, 8, 8, 8)
        sweep_layout.setSpacing(6)
        self.sweep_form = QFormLayout()
        self.sweep_hint_label = QLabel()
        sweep_actions = QHBoxLayout()
        sweep_actions.setContentsMargins(0, 0, 0, 0)
        sweep_actions.setSpacing(6)
        self.btn_sweep_select_all = QPushButton()
        self.btn_sweep_clear = QPushButton()
        sweep_actions.addWidget(self.btn_sweep_select_all)
        sweep_actions.addWidget(self.btn_sweep_clear)
        sweep_actions.addStretch(1)
        self.sweep_values_list = QListWidget()
        self.sweep_values_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.sweep_values_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sweep_values_list.setMinimumHeight(110)
        sweep_layout.addLayout(self.sweep_form)
        sweep_layout.addWidget(self.sweep_hint_label)
        sweep_layout.addLayout(sweep_actions)
        sweep_layout.addWidget(self.sweep_values_list, 1)

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
            batch_handler=lambda: self._open_batch_dialog_common(MdaBatchDialog),
            export_metrics_handler=self._export_metrics,
            export_plot_handler=self._export_plot,
            analysis_changed_handler=self._on_analysis_combo_changed,
            mode_changed_handler=self._on_mode_changed,
        )
        self._bind_plot_edit_signals()

    def _bind_signals(self) -> None:
        self.viewmodel.schema_changed.connect(self._on_schema)
        self.viewmodel.plot_data_changed.connect(self._on_plot_data)
        self.viewmodel.metrics_changed.connect(self._on_metrics)
        self.viewmodel.message.connect(self._on_message)
        self.viewmodel.data_loaded.connect(self._on_data_loaded)
        self.viewmodel.busy_changed.connect(self._set_busy)
        self.sweep_values_list.itemChanged.connect(self._on_sweep_values_changed)
        self.btn_sweep_select_all.clicked.connect(lambda: self._set_all_sweep_values_checked(True))
        self.btn_sweep_clear.clicked.connect(lambda: self._set_all_sweep_values_checked(False))

    def retranslate_ui(self) -> None:
        self._retranslate_top_toolbar(
            open_button_key="mda.open_csv",
            mode_keys=("mda.mode.single", "mda.mode.multi", "mda.mode.3d"),
            default_analysis="mda",
        )

        self.single_group.setTitle(self._t("mda.single_params"))
        self.btn_sweep_select_all.setText(self._t("mda.sweep_select_all", "全选"))
        self.btn_sweep_clear.setText(self._t("mda.sweep_clear", "清空"))
        self._retranslate_metric_and_edit(plot_title_placeholder=self._t("mda.title"))

        self._rebuild_controls(reset_sweep=False)
        self._refresh_sweep_value_panel()

    def set_analysis_type(self, analysis_type: str) -> None:
        self._set_analysis_type_combo(analysis_type)

    def _on_data_loaded(self, info: dict) -> None:
        self._set_file_label_from_info(info)
        self._sync_plot_edit_controls_from_viewmodel()
        self._configure_wavelength_range_controls()

    def _on_schema(self, schema: dict) -> None:
        self.schema = schema
        self._rebuild_controls(reset_sweep=True)
        self._request_plot()

    def _rebuild_controls(self, *, reset_sweep: bool) -> None:
        self.single_controls.clear()
        self.vary_control = None
        self._clear_form_rows(self.single_form)
        self._clear_form_rows(self.sweep_form)

        params = self.schema.get("param_names", [])
        value_map = self.schema.get("values", {})
        if not params:
            self._rebuild_sweep_values(reset_checked=True)
            self._refresh_sweep_value_panel()
            return

        for param in params:
            control = ParamStepControl()
            for entry in value_map.get(param, []):
                control.combo.addItem(str(entry.get("display")), entry.get("raw"))
            control.combo.currentIndexChanged.connect(self._request_plot)
            self.single_controls[param] = control
            self.single_form.addRow(QLabel(param), control)

        self.vary_control = ParamStepControl()
        for param in params:
            self.vary_control.combo.addItem(str(param), param)
        self.vary_control.combo.currentIndexChanged.connect(self._on_varying_param_changed)
        self.sweep_form.addRow(QLabel(self._t("mda.varying_param")), self.vary_control)

        self._rebuild_sweep_values(reset_checked=reset_sweep)
        self._refresh_sweep_value_panel()

    def _varying_param(self) -> str:
        params = list(self.schema.get("param_names", []))
        if not params:
            return ""
        if self.vary_control is not None:
            current = self.vary_control.combo.currentData()
            if current in params:
                return str(current)
        return str(params[0])

    def _rebuild_sweep_values(self, *, reset_checked: bool) -> None:
        varying = self._varying_param()
        entries = list(self.schema.get("values", {}).get(varying, [])) if varying else []
        previous_checked: list[object] = []
        if not reset_checked:
            previous_checked = self._selected_sweep_values()

        self._sweep_values_updating = True
        try:
            self.sweep_values_list.clear()
            for entry in entries:
                raw = entry.get("raw")
                text = str(entry.get("display", raw))
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, raw)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)

                checked = reset_checked or any(raw == v for v in previous_checked)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                self.sweep_values_list.addItem(item)
        finally:
            self._sweep_values_updating = False

    def _refresh_sweep_value_panel(self) -> None:
        base_title = self._t("mda.sweep_values", "扫描参数取值（多线/3D）")
        varying = self._varying_param()
        title = f"{base_title} ({varying})" if varying else base_title
        self.sweep_group.setTitle(title)

        mode = str(self.mode_combo.currentData() or "single")
        enabled = mode != "single" and bool(self.schema.get("param_names", []))
        self.sweep_group.setVisible(enabled)
        if enabled:
            self.sweep_hint_label.setText(self._t("mda.sweep_values_hint", "勾选需要显示/导出的取值"))
        else:
            self.sweep_hint_label.setText(
                self._t("mda.sweep_values_hint_single", "当前为单线模式，切换到多线(2D)/三维(3D)后生效")
            )
        self.sweep_group.setEnabled(True)
        if self.vary_control is not None:
            self.vary_control.setEnabled(enabled)
        self.btn_sweep_select_all.setEnabled(enabled)
        self.btn_sweep_clear.setEnabled(enabled)
        self.sweep_values_list.setEnabled(enabled)
        self._refresh_fixed_controls()

    def _refresh_fixed_controls(self) -> None:
        mode = str(self.mode_combo.currentData() or "single")
        varying = self._varying_param()
        for name, control in self.single_controls.items():
            control.setEnabled(mode == "single" or name != varying)

    def _on_varying_param_changed(self, _: int) -> None:
        self._rebuild_sweep_values(reset_checked=True)
        self._refresh_sweep_value_panel()
        mode = str(self.mode_combo.currentData() or "single")
        if mode != "single":
            self._request_plot()

    def _on_mode_changed(self, _: int) -> None:
        self._refresh_sweep_value_panel()
        self._request_plot()

    def _on_analysis_combo_changed(self, _: int) -> None:
        self._emit_analysis_type_changed_from_combo("mda")

    def _on_sweep_values_changed(self, _: QListWidgetItem) -> None:
        if self._sweep_values_updating:
            return
        mode = str(self.mode_combo.currentData() or "single")
        if mode != "single":
            self._request_plot()

    def _set_all_sweep_values_checked(self, checked: bool) -> None:
        if self.sweep_values_list.count() == 0:
            return
        self._sweep_values_updating = True
        try:
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            for i in range(self.sweep_values_list.count()):
                item = self.sweep_values_list.item(i)
                if item is not None:
                    item.setCheckState(state)
        finally:
            self._sweep_values_updating = False

        mode = str(self.mode_combo.currentData() or "single")
        if mode == "single":
            return
        if checked:
            self._request_plot()
        else:
            self.chart.clear()

    def _single_selection(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, control in self.single_controls.items():
            result[name] = control.combo.currentData()
        return result

    def _sweep_selection(self) -> tuple[str, dict[str, object]]:
        params = list(self.schema.get("param_names", []))
        if not params:
            return "", {}
        vary = self._varying_param()
        selection = self._single_selection()
        fixed = {name: value for name, value in selection.items() if name != vary}
        return vary, fixed

    def _selected_sweep_values(self) -> list[object]:
        selected: list[object] = []
        for i in range(self.sweep_values_list.count()):
            item = self.sweep_values_list.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def _ensure_sweep_values_selected(self) -> bool:
        if self._selected_sweep_values():
            return True
        self.chart.clear()
        self._on_message(
            "warning",
            self._t("common.warning"),
            self._t("mda.message.select_sweep_values", "请至少选择一个参数值"),
        )
        return False

    def _request_plot(self) -> None:
        mode = str(self.mode_combo.currentData() or "single")
        if mode == "single":
            selection = self._single_selection()
            if selection:
                self.viewmodel.plot_single(selection)
            return

        vary, fixed = self._sweep_selection()
        if vary:
            selected_values = self._selected_sweep_values()
            if not selected_values:
                self._ensure_sweep_values_selected()
                return
            self.viewmodel.plot_sweep(vary, fixed, mode, selected_values=selected_values)

    def _set_busy(self, busy: bool) -> None:
        widgets = list(self.single_controls.values()) + [
            self.sweep_values_list,
            self.btn_sweep_select_all,
            self.btn_sweep_clear,
        ]
        if self.vary_control is not None:
            widgets.append(self.vary_control)
        self._set_common_busy(busy, widgets)
        if not busy:
            self._refresh_sweep_value_panel()

    def _export_metrics(self) -> None:
        self._export_metrics_by_mode(
            fallback_stem="mda_metrics",
            on_single=lambda target, mode: self.viewmodel.export_metrics_excel(
                target,
                mode=mode,
                selection=self._single_selection(),
            ),
            on_non_single=lambda target, mode: self._export_metrics_sweep_mode(target, mode),
        )

    def _export_metrics_sweep_mode(self, target: str, mode: str) -> None:
        if not self._ensure_sweep_values_selected():
            return
        vary, fixed = self._sweep_selection()
        self.viewmodel.export_metrics_excel(
            target,
            mode=mode,
            varying_param=vary,
            fixed_params=fixed,
            selected_values=self._selected_sweep_values(),
        )

    def _export_plot(self) -> None:
        mode = str(self.mode_combo.currentData() or "single")
        if mode != "single" and not self._ensure_sweep_values_selected():
            return
        self._export_current_plot_common(
            has_data=self.viewmodel.dataset.spectra_data_full is not None,
            no_data_message_key="mda.message.no_data",
            success_message_key="mda.message.plot_exported",
        )
