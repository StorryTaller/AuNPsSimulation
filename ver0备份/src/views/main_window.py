from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QGuiApplication, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.utils.i18n import I18NManager
from src.viewmodels.mat_viewmodel import matViewModel
from src.viewmodels.mda_viewmodel import MdaViewModel
from src.viewmodels.viz_viewmodel import VizViewModel
from src.views.pages.mat_page import matPage
from src.views.pages.mda_page import MdaPage
from src.views.pages.viz_page import VizPage


class MainWindow(QMainWindow):
    def __init__(self, i18n: I18NManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self._centered_on_startup = False
        self._active_analysis_key = "viz"

        self.viz_vm = VizViewModel(i18n)
        self.mat_vm = matViewModel(i18n)
        self.mda_vm = MdaViewModel(i18n)

        self.viz_page = VizPage(self.viz_vm, i18n)
        self.mat_page = matPage(self.mat_vm, i18n)
        self.mda_page = MdaPage(self.mda_vm, i18n)

        self._build_ui()
        self._bind_signals()
        self.retranslate_ui()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._centered_on_startup:
            return
        self._center_window()
        self._centered_on_startup = True

    def _t(self, key: str, fallback: str = "") -> str:
        return self.i18n.t(self.__class__.__name__, self.tr(key), fallback)

    def _build_ui(self) -> None:
        self.resize(1480, 920)
        self.setMinimumSize(1180, 720)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav_panel = QFrame()
        nav_panel.setObjectName("NavPanel")
        nav_panel.setFixedWidth(210)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(12, 16, 12, 12)
        nav_layout.setSpacing(6)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 800;")
        nav_layout.addWidget(self.title_label)

        self.btn_nav_viz = QPushButton()
        self.btn_nav_mat = QPushButton()

        for button in [self.btn_nav_mat, self.btn_nav_viz]:
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            nav_layout.addWidget(button)

        nav_layout.addStretch(1)
        root.addWidget(nav_panel)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(10)

        self.page_title = QLabel()
        self.page_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        top_layout.addWidget(self.page_title)
        top_layout.addStretch(1)

        self.lbl_lang = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumWidth(130)
        top_layout.addWidget(self.lbl_lang)
        top_layout.addWidget(self.lang_combo)

        right_layout.addWidget(top_bar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.mat_page)
        self.stack.addWidget(self.viz_page)
        self.stack.addWidget(self.mda_page)
        right_layout.addWidget(self.stack, 1)

        root.addWidget(right, 1)

        self.btn_nav_mat.clicked.connect(lambda: self._switch_page(0))
        self.btn_nav_viz.clicked.connect(self._open_active_analysis_page)
        self.lang_combo.currentIndexChanged.connect(self._change_language)
        self.viz_page.analysis_type_changed.connect(self._on_analysis_type_changed)
        self.mda_page.analysis_type_changed.connect(self._on_analysis_type_changed)

        self._switch_page(0)

    def _bind_signals(self) -> None:
        self.i18n.language_changed.connect(self._on_language_changed)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self._t("app.title"))
        self.title_label.setText(self._t("app.title"))

        self.btn_nav_viz.setText(self._t("nav.viz"))
        self.btn_nav_mat.setText(self._t("nav.mat"))

        self.lbl_lang.setText(self._t("app.lang"))

        current_locale = self.i18n.locale
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        self.lang_combo.addItem(self._t("lang.zh_CN"), "zh_CN")
        self.lang_combo.addItem(self._t("lang.en_US"), "en_US")
        index = 0 if current_locale == "zh_CN" else 1
        self.lang_combo.setCurrentIndex(index)
        self.lang_combo.blockSignals(False)

        self.viz_page.retranslate_ui()
        self.mat_page.retranslate_ui()
        self.mda_page.retranslate_ui()

        self._update_page_title(self.stack.currentIndex())

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.btn_nav_mat.setChecked(index == 0)
        self.btn_nav_viz.setChecked(index in (1, 2))
        if index == 1:
            self._active_analysis_key = "viz"
            self.viz_page.set_analysis_type("viz")
            self.mda_page.set_analysis_type("viz")
        elif index == 2:
            self._active_analysis_key = "mda"
            self.viz_page.set_analysis_type("mda")
            self.mda_page.set_analysis_type("mda")
        self._update_page_title(index)

    def _update_page_title(self, index: int) -> None:
        title_map = {
            0: self._t("mat.title"),
            1: self._t("viz.title"),
            2: self._t("mda.title"),
        }
        self.page_title.setText(title_map.get(index, self._t("app.title")))

    def _change_language(self, _: int) -> None:
        locale = self.lang_combo.currentData()
        if locale:
            self.i18n.set_locale(str(locale))

    def _on_language_changed(self, _: str) -> None:
        self.retranslate_ui()

    def _open_active_analysis_page(self) -> None:
        self._switch_page(1 if self._active_analysis_key == "viz" else 2)

    def _on_analysis_type_changed(self, analysis_type: str) -> None:
        if analysis_type not in ("viz", "mda"):
            return
        self._active_analysis_key = analysis_type
        self.viz_page.set_analysis_type(analysis_type)
        self.mda_page.set_analysis_type(analysis_type)
        if self.stack.currentIndex() in (1, 2):
            self._switch_page(1 if analysis_type == "viz" else 2)

    def _center_window(self) -> None:
        # Prefer the screen under mouse cursor; fallback to current/primary screen.
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return

        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())
