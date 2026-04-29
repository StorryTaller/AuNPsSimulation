from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from qfluentwidgets import InfoBar, InfoBarPosition

    _HAS_FLUENT = True
except Exception:
    InfoBar = None
    InfoBarPosition = None
    _HAS_FLUENT = False


class SectionCard(QFrame):
    """页面分区卡片。"""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        self._layout.addWidget(self.title_label)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        self._layout.addLayout(self.body)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)


class ParamStepControl(QWidget):
    """参数选择控件：下拉框 + 左右步进按钮。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.combo = QComboBox(self)
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo.setMinimumWidth(130)

        self.btn_prev = QToolButton(self)
        self.btn_next = QToolButton(self)
        self._setup_step_button(self.btn_prev, "<")
        self._setup_step_button(self.btn_next, ">")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)

        self.btn_prev.clicked.connect(lambda: self.step(-1))
        self.btn_next.clicked.connect(lambda: self.step(1))

    @staticmethod
    def _setup_step_button(button: QToolButton, text: str) -> None:
        button.setObjectName("ParamStepButton")
        button.setText(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(22, 22)

    def step(self, delta: int) -> None:
        count = self.combo.count()
        if count <= 0:
            return
        current = self.combo.currentIndex()
        if current < 0:
            current = 0
        target = max(0, min(count - 1, current + int(delta)))
        if target != current:
            self.combo.setCurrentIndex(target)


class _FallbackToast(QFrame):
    COLOR_MAP = {
        "success": "#0E9F6E",
        "info": "#0EA5E9",
        "warning": "#D97706",
        "error": "#DC2626",
    }

    def __init__(
        self,
        parent: QWidget,
        level: str,
        title: str,
        content: str,
        duration: int,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(
            "QFrame {"
            f"background: {self.COLOR_MAP.get(level, '#0EA5E9')};"
            "color: white; border-radius: 10px; }"
            "QLabel { background: transparent; color: white; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 700;")
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(content_label)

        self.adjustSize()
        self._place(parent)
        self.show()
        QTimer.singleShot(duration, self.close)

    def _place(self, parent: QWidget) -> None:
        margin = 16
        w = min(self.width(), max(280, parent.width() - margin * 2))
        self.resize(w, self.height())
        x = parent.width() - self.width() - margin
        y = margin
        self.move(max(8, x), y)


class AppInfoBar:
    """统一封装通知弹窗，优先使用 qfluentwidgets 的 InfoBar。"""

    @staticmethod
    def _resolve_parent(parent: QWidget | None) -> QWidget | None:
        if isinstance(parent, QWidget):
            direct_parent = parent.parentWidget()
            if isinstance(direct_parent, QWidget):
                return direct_parent
            return parent
        active = QApplication.activeWindow()
        if isinstance(active, QWidget):
            return active
        return None

    @classmethod
    def _show(
        cls,
        parent: QWidget | None,
        level: str,
        title: str,
        content: str,
        duration: int = 2500,
    ) -> None:
        anchor = cls._resolve_parent(parent)

        if _HAS_FLUENT:
            method = getattr(InfoBar, level, None)
            if callable(method):
                try:
                    method(
                        title=title,
                        content=content,
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=duration,
                        parent=anchor,
                    )
                    return
                except TypeError:
                    # 某些环境下 qfluentwidgets 与 Qt 绑定混用会触发 parent 类型不兼容。
                    # 出现兼容性问题时退回到内置 Toast，避免业务流程被中断。
                    pass
                except Exception:
                    pass

        if anchor is not None:
            _FallbackToast(anchor, level, title, content, duration)

    @classmethod
    def success(cls, parent: QWidget | None, title: str, content: str, duration: int = 2200) -> None:
        cls._show(parent, "success", title, content, duration)

    @classmethod
    def info(cls, parent: QWidget | None, title: str, content: str, duration: int = 2500) -> None:
        cls._show(parent, "info", title, content, duration)

    @classmethod
    def warning(cls, parent: QWidget | None, title: str, content: str, duration: int = 2800) -> None:
        cls._show(parent, "warning", title, content, duration)

    @classmethod
    def error(cls, parent: QWidget | None, title: str, content: str, duration: int = 4500) -> None:
        cls._show(parent, "error", title, content, duration)
