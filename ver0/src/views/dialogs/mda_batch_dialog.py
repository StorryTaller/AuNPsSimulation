from __future__ import annotations

from PySide6.QtWidgets import QWidget

from src.utils.i18n import I18NManager
from src.viewmodels.mda_viewmodel import MdaViewModel
from src.views.dialogs.batch_dialog_base import BatchExportDialogBase


class MdaBatchDialog(BatchExportDialogBase):
    def __init__(
        self,
        viewmodel: MdaViewModel,
        i18n: I18NManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(viewmodel, i18n, default_mode="single", parent=parent)
