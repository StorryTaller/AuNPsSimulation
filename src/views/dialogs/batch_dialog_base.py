from __future__ import annotations

from typing import Any

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.utils.dialog_path_memory import DialogPathMemory
from src.utils.i18n import I18NManager
from src.utils.thread_worker import create_worker_thread
from src.views.components.widgets import AppInfoBar, SectionCard


class BatchExportDialogBase(QDialog):
    def __init__(
        self,
        viewmodel: Any,
        i18n: I18NManager,
        *,
        default_mode: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.i18n = i18n
        self.default_mode = default_mode if default_mode in {"single", "multi", "3d"} else "single"
        self.selected_files: list[str] = []
        self._thread = None
        self._worker = None

        self._build_ui()
        self.retranslate_ui()

    def has_running_task(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _t(self, key: str, fallback: str = "") -> str:
        return self.i18n.t(self.__class__.__name__, self.tr(key), fallback)

    def _toast_parent(self) -> QWidget:
        host = self.parentWidget()
        return host if host is not None else self

    def _build_ui(self) -> None:
        self.setModal(True)
        self.setMinimumSize(760, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        settings_card = SectionCard()
        root.addWidget(settings_card)

        row_files = QHBoxLayout()
        row_files.setSpacing(8)
        self.btn_select_files = QPushButton()
        self.files_hint = QLineEdit()
        self.files_hint.setReadOnly(True)
        row_files.addWidget(self.btn_select_files)
        row_files.addWidget(self.files_hint, 1)
        settings_card.body.addLayout(row_files)

        row_out = QHBoxLayout()
        row_out.setSpacing(8)
        self.lbl_output_dir = QLabel()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.btn_browse_output = QPushButton()
        row_out.addWidget(self.lbl_output_dir)
        row_out.addWidget(self.output_dir_edit, 1)
        row_out.addWidget(self.btn_browse_output)
        settings_card.body.addLayout(row_out)

        row_mode = QHBoxLayout()
        row_mode.setSpacing(8)
        self.lbl_mode = QLabel()
        self.mode_combo = QComboBox()
        row_mode.addWidget(self.lbl_mode)
        row_mode.addWidget(self.mode_combo, 1)
        settings_card.body.addLayout(row_mode)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.btn_export_metrics = QPushButton()
        self.btn_export_plot = QPushButton()
        action_row.addWidget(self.btn_export_metrics)
        action_row.addWidget(self.btn_export_plot)
        root.addLayout(action_row)

        log_card = SectionCard()
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(280)
        log_card.body.addWidget(self.log_edit)
        root.addWidget(log_card, 1)

        self.settings_card = settings_card
        self.log_card = log_card

        self.btn_select_files.clicked.connect(self._select_files)
        self.btn_browse_output.clicked.connect(self._select_output_dir)
        self.btn_export_metrics.clicked.connect(self._run_export_metrics)
        self.btn_export_plot.clicked.connect(self._run_export_plots)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self._t("viz.batch.title"))
        self.settings_card.set_title(self._t("viz.batch.settings"))
        self.log_card.set_title(self._t("viz.batch.log"))
        self.btn_select_files.setText(self._t("viz.batch.select_csvs"))
        self.files_hint.setPlaceholderText(self._t("viz.batch.files.none"))
        self.lbl_output_dir.setText(self._t("viz.batch.output_dir"))
        self.btn_browse_output.setText(self._t("viz.batch.browse"))
        self.lbl_mode.setText(self._t("viz.batch.mode"))
        self.btn_export_metrics.setText(self._t("viz.batch.export_metrics"))
        self.btn_export_plot.setText(self._t("viz.batch.export_plot"))

        self.mode_combo.blockSignals(True)
        current_mode = self.mode_combo.currentData() if self.mode_combo.count() else self.default_mode
        self.mode_combo.clear()
        self.mode_combo.addItem(self._t("viz.batch.mode.single"), "single")
        self.mode_combo.addItem(self._t("viz.batch.mode.multi"), "multi")
        self.mode_combo.addItem(self._t("viz.batch.mode.3d"), "3d")
        modes = ["single", "multi", "3d"]
        fallback_index = modes.index(self.default_mode)
        idx = modes.index(current_mode) if current_mode in modes else fallback_index
        self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.blockSignals(False)
        self._refresh_action_state()

    def _set_busy(self, busy: bool) -> None:
        self.btn_select_files.setDisabled(busy)
        self.btn_browse_output.setDisabled(busy)
        self.mode_combo.setDisabled(busy)
        if busy:
            self.btn_export_metrics.setDisabled(True)
            self.btn_export_plot.setDisabled(True)
        else:
            self._refresh_action_state()

    def _refresh_action_state(self) -> None:
        output_dir = self.output_dir_edit.text().strip()
        ready = bool(self.selected_files) and bool(output_dir) and not self.has_running_task()
        self.btn_export_metrics.setEnabled(ready)
        self.btn_export_plot.setEnabled(ready)

        if not self.selected_files:
            tooltip = self._t("viz.batch.need_files")
        elif not output_dir:
            tooltip = self._t("viz.batch.need_output")
        else:
            tooltip = self._t("viz.batch.run")
        self.btn_export_metrics.setToolTip(tooltip)
        self.btn_export_plot.setToolTip(tooltip)

    def _append_log(self, text: str) -> None:
        self.log_edit.append(text)

    def _refresh_file_hint(self) -> None:
        if not self.selected_files:
            self.files_hint.setText("")
            self.files_hint.setPlaceholderText(self._t("viz.batch.files.none"))
            return
        msg = self._t("viz.batch.files.selected").format(count=len(self.selected_files))
        self.files_hint.setText(msg)

    def _select_files(self) -> None:
        files, _ = DialogPathMemory.get_open_file_names(
            self,
            self._t("dialog.select_csv"),
            f"{self._t('dialog.filter.csv')};;{self._t('dialog.filter.any')}",
        )
        if files:
            self.selected_files = files
            self._refresh_file_hint()
            self._refresh_action_state()

    def _select_output_dir(self) -> None:
        path = DialogPathMemory.get_existing_directory(self, self._t("dialog.select_output_dir"))
        if path:
            self.output_dir_edit.setText(path)
            self._refresh_action_state()

    def _ensure_task_ready(self) -> tuple[str, str] | None:
        if not self.selected_files:
            AppInfoBar.warning(self._toast_parent(), self._t("common.warning"), self._t("viz.batch.need_files"))
            return None
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            AppInfoBar.warning(self._toast_parent(), self._t("common.warning"), self._t("viz.batch.need_output"))
            return None
        if self._thread is not None and self._thread.isRunning():
            AppInfoBar.warning(self._toast_parent(), self._t("common.warning"), self._t("msg.thread_busy"))
            return None
        mode = str(self.mode_combo.currentData() or self.default_mode)
        return output_dir, mode

    def _start_task(self, task) -> None:
        prepared = self._ensure_task_ready()
        if prepared is None:
            return
        output_dir, mode = prepared

        self.log_edit.clear()
        self._set_busy(True)

        thread, worker = create_worker_thread(
            task,
            list(self.selected_files),
            output_dir,
            mode,
        )
        self._thread = thread
        self._worker = worker

        worker.progress.connect(self._append_log)
        worker.result.connect(self._on_result)
        worker.error.connect(self._on_error)
        thread.finished.connect(self._on_finished)

        thread.start()

    def _run_export_metrics(self) -> None:
        self._start_task(self.viewmodel.run_batch_export_metrics)

    def _run_export_plots(self) -> None:
        self._start_task(self.viewmodel.run_batch_export_plots)

    def _on_result(self, result: Any) -> None:
        payload = result if isinstance(result, dict) else {"result": result}
        success = int(payload.get("success_count", 0))
        failed = int(payload.get("failed_count", 0))
        summary = self._t("viz.batch.summary").format(success=success, failed=failed)
        self._append_log(summary)

        saved_images = int(payload.get("saved_images", 0) or 0)
        if saved_images > 0:
            self._append_log(f"{self._t('viz.batch.images_saved')}: {saved_images}")

        excel_path = str(payload.get("excel_path", "") or "")
        if excel_path:
            self._append_log(f"{self._t('viz.batch.excel_saved')}: {excel_path}")
        AppInfoBar.success(self._toast_parent(), self._t("common.success"), summary)

    def _on_error(self, trace: str) -> None:
        self._append_log(trace)
        AppInfoBar.error(self._toast_parent(), self._t("common.error"), self._t("viz.batch.failed"))

    def _on_finished(self) -> None:
        self._set_busy(False)
        self._thread = None
        self._worker = None

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.has_running_task():
            AppInfoBar.warning(self._toast_parent(), self._t("common.warning"), self._t("msg.thread_busy"))
            event.ignore()
            return
        super().closeEvent(event)
