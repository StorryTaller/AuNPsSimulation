from __future__ import annotations

import inspect
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot


class ThreadWorker(QObject):
    """在线程中执行函数并通过信号回传结果。"""

    started = Signal()
    progress = Signal(str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    @Slot()
    def run(self) -> None:
        self.started.emit()
        try:
            kwargs = dict(self._kwargs)
            signature = inspect.signature(self._fn)
            if "log_callback" in signature.parameters and "log_callback" not in kwargs:
                kwargs["log_callback"] = self.progress.emit
            value = self._fn(*self._args, **kwargs)
            self.result.emit(value)
        except Exception:
            self.error.emit(traceback.format_exc())
        finally:
            self.finished.emit()


def create_worker_thread(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[QThread, ThreadWorker]:
    thread = QThread()
    worker = ThreadWorker(fn, *args, **kwargs)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    return thread, worker
