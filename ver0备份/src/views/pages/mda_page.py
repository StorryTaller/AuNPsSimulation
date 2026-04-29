from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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

        self._build_metrics_card(left_col)
        self._build_plot_edit_card(left_col)
        left_col.addWidget(self.single_group)
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

    def retranslate_ui(self) -> None:
        self._retranslate_top_toolbar(
            open_button_key="mda.open_csv",
            mode_keys=("mda.mode.single", "mda.mode.multi", "mda.mode.3d"),
            default_analysis="mda",
        )

        self.single_group.setTitle(self._t("mda.single_params"))
        self._retranslate_metric_and_edit(plot_title_placeholder=self._t("mda.title"))

        self._rebuild_controls()

    def set_analysis_type(self, analysis_type: str) -> None:
        self._set_analysis_type_combo(analysis_type)

    def _on_data_loaded(self, info: dict) -> None:
        self._set_file_label_from_info(info)
        self._sync_plot_edit_controls_from_viewmodel()
        self._configure_wavelength_range_controls()

    def _on_schema(self, schema: dict) -> None:
        self.schema = schema
        self._rebuild_controls()
        self._request_plot()

    def _rebuild_controls(self) -> None:
        self.single_controls.clear()
        self._clear_form_rows(self.single_form)

        params = self.schema.get("param_names", [])
        value_map = self.schema.get("values", {})
        if not params:
            return

        for param in params:
            control = ParamStepControl()
            for entry in value_map.get(param, []):
                control.combo.addItem(str(entry.get("display")), entry.get("raw"))
            control.combo.currentIndexChanged.connect(self._request_plot)
            self.single_controls[param] = control
            self.single_form.addRow(QLabel(param), control)

    def _on_mode_changed(self, _: int) -> None:
        self._request_plot()

    def _on_analysis_combo_changed(self, _: int) -> None:
        self._emit_analysis_type_changed_from_combo("mda")

    def _single_selection(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, control in self.single_controls.items():
            result[name] = control.combo.currentData()
        return result

    def _sweep_selection(self) -> tuple[str, dict[str, object]]:
        params = list(self.schema.get("param_names", []))
        if not params:
            return "", {}
        vary = params[0]
        selection = self._single_selection()
        fixed = {name: value for name, value in selection.items() if name != vary}
        return vary, fixed

    def _request_plot(self) -> None:
        mode = str(self.mode_combo.currentData() or "single")
        if mode == "single":
            selection = self._single_selection()
            if selection:
                self.viewmodel.plot_single(selection)
            return

        vary, fixed = self._sweep_selection()
        if vary:
            self.viewmodel.plot_sweep(vary, fixed, mode)

    def _set_busy(self, busy: bool) -> None:
        self._set_common_busy(busy, list(self.single_controls.values()))

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
        vary, fixed = self._sweep_selection()
        self.viewmodel.export_metrics_excel(
            target,
            mode=mode,
            varying_param=vary,
            fixed_params=fixed,
        )

    def _export_plot(self) -> None:
        self._export_current_plot_common(
            has_data=self.viewmodel.dataset.spectra_data_full is not None,
            no_data_message_key="mda.message.no_data",
            success_message_key="mda.message.plot_exported",
        )
