from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def _bootstrap_windows_icu_for_pyside() -> None:
    """Preload system ICU DLLs to avoid Anaconda ICU symbol conflicts."""
    if sys.platform != "win32":
        return

    system32 = Path(r"C:\Windows\System32")
    for dll_name in ("icuuc.dll", "icuin.dll"):
        dll_path = system32 / dll_name
        if dll_path.exists():
            try:
                ctypes.WinDLL(str(dll_path))
            except OSError:
                # Best effort only. If preload fails, keep original behavior.
                pass


_bootstrap_windows_icu_for_pyside()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.utils.i18n import I18NManager
from src.utils.runtime_paths import get_app_root
from src.views.main_window import MainWindow
from src.views.styles.theme import build_theme, load_qss_with_theme


def _build_ui_font() -> QFont:
    """Use Arial for Latin glyphs and DengXian for CJK glyphs via fallback."""
    font = QFont()
    if hasattr(font, "setFamilies"):
        font.setFamilies(["Arial", "DengXian", "等线"])
    else:
        font.setFamily("Arial")
    return font


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(_build_ui_font())

    base_dir = get_app_root()
    i18n = I18NManager(base_dir / "res" / "translations", default_locale="zh_CN")

    app.setApplicationName(i18n.t("main", "app.title", "AuNPs Simulation"))
    app.setOrganizationName("AuNPsSimulation")

    qss_path = base_dir / "views" / "styles" / "style.qss"
    app.setStyleSheet(load_qss_with_theme(qss_path, build_theme()))

    window = MainWindow(i18n)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
