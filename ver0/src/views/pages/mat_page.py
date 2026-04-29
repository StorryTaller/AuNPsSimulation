from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.utils.dialog_path_memory import DialogPathMemory
from src.utils.i18n import I18NManager
from src.viewmodels.mat_viewmodel import matViewModel
from src.views.components.widgets import AppInfoBar, SectionCard


class matPage(QWidget):
    INPUT_WIDTH = 260
    INPUT_HEIGHT = 32
    BUTTON_WIDTH = 100
    BUTTON_HEIGHT = 32
    ACTION_BUTTON_WIDTH = 100
    ACTION_BUTTON_HEIGHT = 32
    DATASET_LIST_HEIGHT = 32
    PARAM_LIST_HEIGHT = 32

    def __init__(self, viewmodel: matViewModel, i18n: I18NManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.i18n = i18n

        self.batch_files: list[str] = []
        self._param_row_map: dict[QWidget, QCheckBox] = {}
        self._busy = False
        self._build_ui()
        self._bind_signals()
        self.retranslate_ui()

    def _t(self, key: str, fallback: str = "") -> str:
        return self.i18n.t(self.__class__.__name__, self.tr(key), fallback)

    def _setup_line_edit(self, edit: QLineEdit, *, read_only: bool = False) -> None:
        edit.setReadOnly(read_only)
        edit.setMinimumSize(self.INPUT_WIDTH, self.INPUT_HEIGHT)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _setup_button(self, button: QPushButton, *, width: int = BUTTON_WIDTH) -> None:
        button.setFixedSize(width, self.BUTTON_HEIGHT)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _setup_dataset_combo(self, widget: QComboBox) -> None:
        widget.setMinimumSize(
            self.INPUT_WIDTH + self.ACTION_BUTTON_WIDTH + 16,
            self.INPUT_HEIGHT,
        )
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _setup_dataset_list(self, widget: QListWidget, *, height: int) -> None:
        widget.setMinimumSize(
            self.INPUT_WIDTH + self.ACTION_BUTTON_WIDTH + 16,
            height,
        )
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll)

        content = QWidget()
        content.setMinimumWidth(1080)
        self.scroll.setWidget(content)

        content_grid = QGridLayout(content)
        content_grid.setContentsMargins(12, 12, 12, 12)
        content_grid.setHorizontalSpacing(10)
        content_grid.setVerticalSpacing(10)
        content_grid.setColumnStretch(0, 5)
        content_grid.setColumnStretch(1, 4)
        # 左侧上方保持紧凑，剩余高度交给左下与右侧日志
        content_grid.setRowStretch(0, 0)
        content_grid.setRowStretch(1, 1)

        # 单/批量转换
        self.batch_card = SectionCard()
        self.batch_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        batch_grid = QGridLayout()
        batch_grid.setHorizontalSpacing(8)
        batch_grid.setVerticalSpacing(8)
        batch_grid.setColumnMinimumWidth(0, 110)
        batch_grid.setColumnMinimumWidth(1, self.INPUT_WIDTH)
        batch_grid.setColumnMinimumWidth(2, self.ACTION_BUTTON_WIDTH)
        batch_grid.setColumnStretch(1, 1)

        self.batch_file_edit = QLineEdit()
        self.batch_out_edit = QLineEdit()
        self.cmb_spec = QComboBox()
        self.cmb_lambda = QComboBox()
        self.cmb_param = QComboBox()
        self.btn_batch_scan = QPushButton()
        self.btn_convert_batch = QPushButton()

        self._setup_line_edit(self.batch_file_edit, read_only=True)
        self._setup_line_edit(self.batch_out_edit, read_only=True)
        self._setup_button(self.btn_batch_scan)
        self.btn_convert_batch.setFixedSize(self.ACTION_BUTTON_WIDTH, self.ACTION_BUTTON_HEIGHT)
        self.btn_convert_batch.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._setup_dataset_combo(self.cmb_spec)
        self._setup_dataset_combo(self.cmb_lambda)
        self._setup_dataset_combo(self.cmb_param)

        self.batch_label_files = QLabel()
        self.batch_label_out = QLabel()
        self.batch_label_spec = QLabel()
        self.batch_label_lambda = QLabel()
        self.batch_label_param = QLabel()

        batch_grid.addWidget(self.batch_label_files, 0, 0)
        batch_grid.addWidget(self.batch_file_edit, 0, 1)

        batch_grid.addWidget(self.batch_label_out, 1, 0)
        batch_grid.addWidget(self.batch_out_edit, 1, 1)

        batch_grid.addWidget(self.btn_batch_scan, 0, 2, 1, 1, Qt.AlignmentFlag.AlignLeft)
        batch_grid.addWidget(self.btn_convert_batch, 1, 2, 1, 1, Qt.AlignmentFlag.AlignLeft)

        batch_grid.addWidget(self.batch_label_spec, 2, 0)
        batch_grid.addWidget(self.cmb_spec, 2, 1, 1, 2)

        batch_grid.addWidget(self.batch_label_lambda, 3, 0)
        batch_grid.addWidget(self.cmb_lambda, 3, 1, 1, 2)

        batch_grid.addWidget(self.batch_label_param, 4, 0)
        batch_grid.addWidget(self.cmb_param, 4, 1, 1, 2)

        self.batch_card.body.addLayout(batch_grid)
        content_grid.addWidget(self.batch_card, 0, 0)

        # 多维转换
        self.multi_card = SectionCard()
        self.multi_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        multi_grid = QGridLayout()
        multi_grid.setHorizontalSpacing(8)
        multi_grid.setVerticalSpacing(8)
        multi_grid.setColumnMinimumWidth(0, 110)
        multi_grid.setColumnMinimumWidth(1, self.INPUT_WIDTH)
        multi_grid.setColumnMinimumWidth(2, self.ACTION_BUTTON_WIDTH)
        multi_grid.setColumnStretch(1, 1)

        self.multi_mat_edit = QLineEdit()
        self.multi_out_edit = QLineEdit()
        self.btn_multi_scan = QPushButton()
        self.multi_spec_combo = QComboBox()
        self.multi_lambda_combo = QComboBox()
        self.multi_params_list = QListWidget()
        self.btn_convert_multi = QPushButton()

        self._setup_line_edit(self.multi_mat_edit, read_only=True)
        self._setup_line_edit(self.multi_out_edit, read_only=True)
        self._setup_button(self.btn_multi_scan)
        self._setup_dataset_combo(self.multi_spec_combo)
        self._setup_dataset_combo(self.multi_lambda_combo)
        self._setup_dataset_list(self.multi_params_list, height=self.PARAM_LIST_HEIGHT)
        self.multi_params_list.setObjectName("MultiParamList")
        self.multi_params_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.multi_params_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # 参数变量列表占据多维转换卡片剩余高度
        self.multi_params_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.btn_convert_multi.setFixedSize(self.ACTION_BUTTON_WIDTH, self.ACTION_BUTTON_HEIGHT)
        self.btn_convert_multi.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.multi_label_mat = QLabel()
        self.multi_label_out = QLabel()
        self.multi_label_spec = QLabel()
        self.multi_label_lambda = QLabel()
        self.multi_label_params = QLabel()

        multi_grid.addWidget(self.multi_label_mat, 0, 0)
        multi_grid.addWidget(self.multi_mat_edit, 0, 1)

        multi_grid.addWidget(self.multi_label_out, 1, 0)
        multi_grid.addWidget(self.multi_out_edit, 1, 1)

        multi_grid.addWidget(self.btn_multi_scan, 0, 2, 1, 1, Qt.AlignmentFlag.AlignLeft)
        multi_grid.addWidget(self.btn_convert_multi, 1, 2, 1, 1, Qt.AlignmentFlag.AlignLeft)

        multi_grid.addWidget(self.multi_label_spec, 2, 0)
        multi_grid.addWidget(self.multi_spec_combo, 2, 1, 1, 2)

        multi_grid.addWidget(self.multi_label_lambda, 3, 0)
        multi_grid.addWidget(self.multi_lambda_combo, 3, 1, 1, 2)

        multi_grid.addWidget(self.multi_label_params, 4, 0)
        multi_grid.addWidget(self.multi_params_list, 4, 1, 1, 2)
        multi_grid.setRowStretch(4, 1)

        self.multi_card.body.addLayout(multi_grid)
        content_grid.addWidget(self.multi_card, 1, 0)

        self.log_card = SectionCard()
        self.log_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(220)
        self.log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_card.body.addWidget(self.log_text)
        content_grid.addWidget(self.log_card, 0, 1, 2, 1)

        self.btn_batch_scan.clicked.connect(self._scan_batch)
        self.btn_convert_batch.clicked.connect(self._convert_batch)

        self.btn_multi_scan.clicked.connect(self._scan_multi)
        self.btn_convert_multi.clicked.connect(self._convert_multi)

        for edit in (self.batch_file_edit, self.batch_out_edit, self.multi_mat_edit, self.multi_out_edit):
            edit.setCursor(Qt.CursorShape.PointingHandCursor)
            edit.installEventFilter(self)

    def _bind_signals(self) -> None:
        self.viewmodel.batch_datasets_scanned.connect(self._on_batch_datasets_scanned)
        self.viewmodel.multi_datasets_scanned.connect(self._on_multi_datasets_scanned)
        self.viewmodel.log_message.connect(self._append_log)
        self.viewmodel.task_result.connect(self._on_task_result)
        self.viewmodel.message.connect(self._on_message)
        self.viewmodel.busy_changed.connect(self._set_busy)

    def retranslate_ui(self) -> None:
        self.batch_card.set_title(self._t("mat.batch.title"))
        self.multi_card.set_title(self._t("mat.multidim.title"))
        self.log_card.set_title(self._t("mat.log.title"))

        self.batch_label_files.setText(self._t("mat.select_files"))
        self.batch_label_out.setText(self._t("mat.select_output_dir"))
        self.batch_label_spec.setText(self._t("mat.dataset.spectrum"))
        self.batch_label_lambda.setText(self._t("mat.dataset.lambda"))
        self.batch_label_param.setText(self._t("mat.dataset.param"))

        self.btn_batch_scan.setText(self._t("mat.scan_dataset"))
        self.btn_convert_batch.setText(self._t("mat.convert.batch"))

        self.multi_label_mat.setText(self._t("mat.input_mat"))
        self.multi_label_out.setText(self._t("mat.select_output_dir"))
        self.multi_label_spec.setText(self._t("mat.dataset.spectrum"))
        self.multi_label_lambda.setText(self._t("mat.dataset.lambda"))
        self.multi_label_params.setText(self._t("mat.dataset.params"))

        self.btn_multi_scan.setText(self._t("mat.scan_dataset"))
        self.btn_convert_multi.setText(self._t("mat.convert.multidim"))

        self._ensure_auto_combo_item(self.cmb_spec)
        self._ensure_auto_combo_item(self.cmb_lambda)
        self._ensure_auto_combo_item(self.cmb_param)
        self._ensure_auto_combo_item(self.multi_spec_combo)
        self._ensure_auto_combo_item(self.multi_lambda_combo)
        self._refresh_convert_actions()

    def _ensure_auto_combo_item(self, combo: QComboBox) -> None:
        if combo.count() == 0:
            combo.addItem(self._t("common.auto"))
        combo.setCurrentIndex(0)

    def _append_log(self, text: str) -> None:
        self.log_text.append(text)

    def _on_message(self, level: str, title: str, content: str) -> None:
        method = getattr(AppInfoBar, level, AppInfoBar.info)
        method(self, title, content)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        controls = [
            self.batch_file_edit,
            self.batch_out_edit,
            self.btn_batch_scan,
            self.btn_convert_batch,
            self.cmb_spec,
            self.cmb_lambda,
            self.cmb_param,
            self.multi_mat_edit,
            self.multi_out_edit,
            self.btn_multi_scan,
            self.btn_convert_multi,
            self.multi_spec_combo,
            self.multi_lambda_combo,
            self.multi_params_list,
        ]
        for ctrl in controls:
            ctrl.setDisabled(busy)
        if not busy:
            self._refresh_convert_actions()

    def _refresh_convert_actions(self) -> None:
        batch_ready = bool(self.batch_files) and bool(self.batch_out_edit.text().strip())
        multi_ready = (
            bool(self.multi_mat_edit.text().strip())
            and bool(self.multi_out_edit.text().strip())
            and bool(self._checked_params())
        )
        self.btn_convert_batch.setEnabled((not self._busy) and batch_ready)
        self.btn_convert_multi.setEnabled((not self._busy) and multi_ready)

        if not self.batch_files:
            self.btn_convert_batch.setToolTip(self._t("mat.message.need_mat_file"))
        elif not self.batch_out_edit.text().strip():
            self.btn_convert_batch.setToolTip(self._t("mat.message.need_output"))
        else:
            self.btn_convert_batch.setToolTip(self._t("mat.convert.batch"))

        if not self.multi_mat_edit.text().strip():
            self.btn_convert_multi.setToolTip(self._t("mat.message.need_mat_file"))
        elif not self.multi_out_edit.text().strip():
            self.btn_convert_multi.setToolTip(self._t("mat.message.need_output"))
        elif not self._checked_params():
            self.btn_convert_multi.setToolTip(self._t("mat.message.need_params", "请至少选择一个参数变量"))
        else:
            self.btn_convert_multi.setToolTip(self._t("mat.convert.multidim"))

    def _on_task_result(self, payload: dict) -> None:
        if "success_count" in payload:
            msg = self._t("mat.message.batch_summary").format(
                success=payload.get("success_count", 0),
                failed=payload.get("failed_count", 0),
            )
            self._append_log(msg)
            return

        if payload.get("output_csv"):
            self._append_log(f"{self._t('mat.message.convert_done')}: {payload.get('output_csv')}")
        if payload.get("normalized_csv"):
            self._append_log(f"Ncsv: {payload.get('normalized_csv')}")

    def _on_batch_datasets_scanned(self, options: dict[str, list[str]]) -> None:
        all_names = options.get("all", [])
        spec_names = options.get("spectrum", all_names)
        lambda_names = options.get("lambda", all_names)
        param_names = options.get("param", all_names)
        self._fill_batch_dataset_lists(spec_names, lambda_names, param_names)

    def _on_multi_datasets_scanned(self, options: dict[str, list[str]]) -> None:
        all_names = options.get("all", [])
        spec_names = options.get("spectrum", all_names)
        lambda_names = options.get("lambda", all_names)
        param_names = options.get("param", all_names)
        self._fill_multi_dataset_lists(spec_names, lambda_names, param_names)

    def _fill_combo(self, widget: QComboBox, names: list[str]) -> None:
        widget.clear()
        widget.addItem(self._t("common.auto"))
        for name in names:
            widget.addItem(name)
        widget.setCurrentIndex(0)

    def _fill_batch_dataset_lists(
        self,
        spec_names: list[str],
        lambda_names: list[str],
        param_names: list[str],
    ) -> None:
        self._fill_combo(self.cmb_spec, spec_names)
        self._fill_combo(self.cmb_lambda, lambda_names)
        self._fill_combo(self.cmb_param, param_names)

    def _fill_multi_dataset_lists(
        self,
        spec_names: list[str],
        lambda_names: list[str],
        param_names: list[str],
    ) -> None:
        self._fill_combo(self.multi_spec_combo, spec_names)
        self._fill_combo(self.multi_lambda_combo, lambda_names)

        self._param_row_map.clear()
        self.multi_params_list.clear()
        for name in param_names:
            item = QListWidgetItem()
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setSizeHint(QSize(0, 34))
            self.multi_params_list.addItem(item)

            row = QWidget(self.multi_params_list)
            row.setObjectName("ParamRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.setSpacing(0)

            checkbox = QCheckBox(str(name), row)
            checkbox.setObjectName("ParamCheckbox")
            checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
            checkbox.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            row_layout.addWidget(checkbox)

            self.multi_params_list.setItemWidget(item, row)
            self._param_row_map[row] = checkbox
            row.installEventFilter(self)
        self._refresh_convert_actions()

    def _param_checkbox_for_item(self, item: QListWidgetItem) -> QCheckBox | None:
        row = self.multi_params_list.itemWidget(item)
        if row is None:
            return None
        return row.findChild(QCheckBox, "ParamCheckbox")

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() == QEvent.Type.MouseButtonRelease:
            if watched is self.batch_file_edit:
                if self.batch_file_edit.isEnabled():
                    self._pick_batch_files()
                return True
            if watched is self.batch_out_edit:
                if self.batch_out_edit.isEnabled():
                    self._pick_batch_output_dir()
                return True
            if watched is self.multi_mat_edit:
                if self.multi_mat_edit.isEnabled():
                    self._pick_multi_mat()
                return True
            if watched is self.multi_out_edit:
                if self.multi_out_edit.isEnabled():
                    self._pick_multi_output()
                return True

        checkbox = self._param_row_map.get(watched)
        if checkbox is not None and event.type() == QEvent.Type.MouseButtonRelease:
            checkbox.setChecked(not checkbox.isChecked())
            self._refresh_convert_actions()
            return True
        return super().eventFilter(watched, event)

    def _selected_combo_text(self, widget: QComboBox) -> str:
        text = widget.currentText().strip()
        if not text:
            return self._t("common.auto")
        return text

    def _checked_params(self) -> list[str]:
        params: list[str] = []
        for i in range(self.multi_params_list.count()):
            item = self.multi_params_list.item(i)
            checkbox = self._param_checkbox_for_item(item)
            if checkbox is not None and checkbox.isChecked():
                params.append(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        return params

    # ------- 单/批量 -------
    def _pick_batch_files(self) -> None:
        files, _ = DialogPathMemory.get_open_file_names(
            self,
            self._t("mat.select_files"),
            f"{self._t('dialog.filter.mat')};;{self._t('dialog.filter.any')}",
        )
        if files:
            self.batch_files = files
            first_name = Path(files[0]).name
            summary = self._t(
                "mat.message.files_selected",
                "{count} file(s) selected, first: {first}",
            )
            self.batch_file_edit.setText(summary.format(count=len(files), first=first_name))
            self._scan_batch()
            self._refresh_convert_actions()

    def _pick_batch_output_dir(self) -> None:
        path = DialogPathMemory.get_existing_directory(self, self._t("dialog.select_output_dir"))
        if path:
            self.batch_out_edit.setText(path)
            self._refresh_convert_actions()

    def _scan_batch(self) -> None:
        source = self.batch_files[0] if self.batch_files else ""
        self.viewmodel.scan_batch_datasets(source)

    def _convert_batch(self) -> None:
        self.viewmodel.convert_batch_async(
            mat_file_paths=self.batch_files,
            output_dir=self.batch_out_edit.text().strip(),
            spectrum_dataset_name=self._selected_combo_text(self.cmb_spec),
            lambda_dataset_name=self._selected_combo_text(self.cmb_lambda),
            param_dataset_name=self._selected_combo_text(self.cmb_param),
        )

    # ------- 多维 -------
    def _pick_multi_mat(self) -> None:
        path, _ = DialogPathMemory.get_open_file_name(
            self,
            self._t("dialog.select_mat"),
            f"{self._t('dialog.filter.mat')};;{self._t('dialog.filter.any')}",
        )
        if path:
            self.multi_mat_edit.setText(path)
            self._scan_multi()
            self._refresh_convert_actions()

    def _pick_multi_output(self) -> None:
        path = DialogPathMemory.get_existing_directory(self, self._t("dialog.select_output_dir"))
        if path:
            self.multi_out_edit.setText(path)
            self._refresh_convert_actions()

    def _scan_multi(self) -> None:
        self.viewmodel.scan_multi_datasets(self.multi_mat_edit.text().strip())

    def _convert_multi(self) -> None:
        self.viewmodel.convert_multidim_async(
            mat_file_path=self.multi_mat_edit.text().strip(),
            output_dir=self.multi_out_edit.text().strip(),
            spectrum_dataset_name=self._selected_combo_text(self.multi_spec_combo),
            lambda_dataset_name=self._selected_combo_text(self.multi_lambda_combo),
            param_dataset_names=self._checked_params(),
        )
