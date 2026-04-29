from __future__ import annotations

from PySide6.QtWidgets import QWidget

from src.utils.i18n import I18NManager
from src.viewmodels.viz_viewmodel import VizViewModel
from src.views.dialogs.batch_dialog_base import BatchExportDialogBase


class VizBatchDialog(BatchExportDialogBase):
    def __init__(
        self,
        viewmodel: VizViewModel,
        i18n: I18NManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(viewmodel, i18n, default_mode="multi", parent=parent)
