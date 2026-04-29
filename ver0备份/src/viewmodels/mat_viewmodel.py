from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from src.models.file_converter import matFileConverter
from src.utils.i18n import I18NManager
from src.utils.thread_worker import create_worker_thread
from src.viewmodels.base_viewmodel import BaseViewModel


class matViewModel(BaseViewModel):
    batch_datasets_scanned = Signal(dict)
    multi_datasets_scanned = Signal(dict)
    log_message = Signal(str)
    task_result = Signal(dict)
    message = Signal(str, str, str)
    busy_changed = Signal(bool)

    def __init__(self, i18n: I18NManager, parent: QObject | None = None) -> None:
        super().__init__(i18n, parent)
        self.converter = matFileConverter()
        self._thread = None
        self._worker = None

    def _scan_datasets(self, mat_path: str, signal: Signal) -> None:
        if not mat_path:
            self._emit_info("warning", "common.warning", self._t("mat.message.need_mat_file"))
            return
        options = self.converter.get_available_datasets(mat_path)
        signal.emit(options)
        self._emit_info("info", "common.info", self._t("mat.message.scan_done"))

    def scan_batch_datasets(self, mat_path: str) -> None:
        self._scan_datasets(mat_path, self.batch_datasets_scanned)

    def scan_multi_datasets(self, mat_path: str) -> None:
        self._scan_datasets(mat_path, self.multi_datasets_scanned)

    def _start_task(self, fn, *args, **kwargs) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._emit_info("warning", "common.warning", self._t("msg.thread_busy"))
            return

        thread, worker = create_worker_thread(fn, *args, **kwargs)
        self._thread = thread
        self._worker = worker

        self.busy_changed.emit(True)

        worker.progress.connect(self.log_message.emit)
        worker.result.connect(self._on_task_result)
        worker.error.connect(self._on_task_error)
        worker.finished.connect(self._on_task_finished)

        thread.start()

    def _on_task_result(self, result: Any) -> None:
        payload = result if isinstance(result, dict) else {"result": result}
        self.task_result.emit(payload)
        if payload.get("success") is False:
            self._emit_info("error", "common.error", self._t("mat.message.convert_failed"))
        else:
            self._emit_info("success", "common.success", self._t("mat.message.convert_done"))

    def _on_task_error(self, trace: str) -> None:
        self.log_message.emit(trace)
        self._emit_info("error", "common.error", self._t("mat.message.convert_failed"))

    def _on_task_finished(self) -> None:
        self.busy_changed.emit(False)
        self._thread = None
        self._worker = None

    def convert_single_async(
        self,
        mat_file_path: str,
        output_file_path: str,
        spectrum_dataset_name: str,
        lambda_dataset_name: str,
        param_dataset_name: str,
    ) -> None:
        if not mat_file_path:
            self._emit_info("warning", "common.warning", self._t("mat.message.need_mat_file"))
            return
        if not output_file_path:
            self._emit_info("warning", "common.warning", self._t("mat.message.need_output"))
            return

        self._start_task(
            self.converter.convert_single_mat_to_csv,
            mat_file_path,
            output_file_path,
            spectrum_dataset_name,
            lambda_dataset_name,
            param_dataset_name,
        )

    def convert_batch_async(
        self,
        mat_file_paths: list[str],
        output_dir: str,
        spectrum_dataset_name: str,
        lambda_dataset_name: str,
        param_dataset_name: str,
    ) -> None:
        if not mat_file_paths:
            self._emit_info("warning", "common.warning", self._t("mat.message.need_mat_file"))
            return
        if not output_dir:
            self._emit_info("warning", "common.warning", self._t("mat.message.need_output"))
            return

        def _run_batch(log_callback=None):
            return self.converter.batch_convert_single_mat_to_csv(
                mat_file_paths=mat_file_paths,
                output_dir=output_dir,
                spectrum_dataset_name=spectrum_dataset_name,
                lambda_dataset_name=lambda_dataset_name,
                param_dataset_name=param_dataset_name,
                log_callback=log_callback,
            )

        self._start_task(_run_batch)

    def convert_multidim_async(
        self,
        mat_file_path: str,
        output_dir: str,
        spectrum_dataset_name: str,
        lambda_dataset_name: str,
        param_dataset_names: list[str],
    ) -> None:
        if not mat_file_path:
            self._emit_info("warning", "common.warning", self._t("mat.message.need_mat_file"))
            return
        if not output_dir:
            self._emit_info("warning", "common.warning", self._t("mat.message.need_output"))
            return
        if not param_dataset_names:
            self._emit_info("warning", "common.warning", self._t("mat.dataset.params"))
            return

        self._start_task(
            self.converter.convert_multidim_mat_to_csv,
            mat_file_path,
            output_dir,
            spectrum_dataset_name,
            lambda_dataset_name,
            param_dataset_names,
        )
