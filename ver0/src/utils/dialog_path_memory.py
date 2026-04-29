from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import QFileDialog, QWidget


class DialogPathMemory:
    """Remember the last browsed directory for file/folder dialogs."""

    KEY_LAST_DIR = "dialogs/last_directory"

    @classmethod
    def _settings(cls) -> QSettings:
        return QSettings()

    @classmethod
    def _existing_dir_or_empty(cls, path: str) -> str:
        candidate = Path(path).expanduser()
        if candidate.is_absolute() and candidate.exists() and candidate.is_dir():
            return str(candidate)
        return ""

    @classmethod
    def _fallback_home_dir(cls) -> str:
        home = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
        if home:
            return home
        return str(Path.home())

    @classmethod
    def start_dir(cls, fallback: str = "") -> str:
        saved = str(cls._settings().value(cls.KEY_LAST_DIR, "", type=str) or "")
        saved_dir = cls._existing_dir_or_empty(saved)
        if saved_dir:
            return saved_dir

        fallback_dir = cls._existing_dir_or_empty(fallback)
        if fallback_dir:
            return fallback_dir

        return cls._fallback_home_dir()

    @classmethod
    def remember(cls, path: str) -> None:
        if not path:
            return

        candidate = Path(path).expanduser()
        folder = candidate if candidate.is_dir() else candidate.parent
        if folder.exists() and folder.is_dir():
            cls._settings().setValue(cls.KEY_LAST_DIR, str(folder))

    @classmethod
    def get_existing_directory(cls, parent: QWidget, title: str, fallback: str = "") -> str:
        path = QFileDialog.getExistingDirectory(parent, title, cls.start_dir(fallback))
        if path:
            cls.remember(path)
        return path

    @classmethod
    def get_open_file_name(
        cls,
        parent: QWidget,
        title: str,
        file_filter: str,
        fallback: str = "",
    ) -> tuple[str, str]:
        path, selected_filter = QFileDialog.getOpenFileName(
            parent,
            title,
            cls.start_dir(fallback),
            file_filter,
        )
        if path:
            cls.remember(path)
        return path, selected_filter

    @classmethod
    def get_open_file_names(
        cls,
        parent: QWidget,
        title: str,
        file_filter: str,
        fallback: str = "",
    ) -> tuple[list[str], str]:
        paths, selected_filter = QFileDialog.getOpenFileNames(
            parent,
            title,
            cls.start_dir(fallback),
            file_filter,
        )
        if paths:
            cls.remember(paths[0])
        return paths, selected_filter

    @classmethod
    def get_save_file_name(
        cls,
        parent: QWidget,
        title: str,
        default_name: str,
        file_filter: str,
        fallback: str = "",
    ) -> tuple[str, str]:
        base_dir = cls.start_dir(fallback)
        initial = str(Path(base_dir) / default_name) if default_name else base_dir
        path, selected_filter = QFileDialog.getSaveFileName(
            parent,
            title,
            initial,
            file_filter,
        )
        if path:
            cls.remember(path)
        return path, selected_filter
