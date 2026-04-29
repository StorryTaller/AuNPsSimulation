from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from PySide6.QtCore import QCoreApplication, QObject, Signal


class I18NManager(QObject):
    """基于 JSON 词典的轻量 i18n 管理器。"""

    language_changed = Signal(str)

    def __init__(self, translations_dir: str | Path, default_locale: str = "zh_CN") -> None:
        super().__init__()
        self.translations_dir = Path(translations_dir)
        self._catalog: Dict[str, str] = {}
        self._locale = ""
        self.set_locale(default_locale)

    @property
    def locale(self) -> str:
        return self._locale

    def available_locales(self) -> list[str]:
        locales: list[str] = []
        if not self.translations_dir.exists():
            return locales
        for path in sorted(self.translations_dir.glob("*.json")):
            locales.append(path.stem)
        return locales

    def set_locale(self, locale: str) -> None:
        locale = locale.strip() or "zh_CN"
        candidate = self.translations_dir / f"{locale}.json"
        if not candidate.exists():
            fallback = self.translations_dir / "zh_CN.json"
            candidate = fallback if fallback.exists() else candidate

        catalog: Dict[str, str] = {}
        if candidate.exists():
            try:
                catalog = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                catalog = {}

        old_locale = self._locale
        self._catalog = catalog
        self._locale = candidate.stem if candidate.exists() else locale
        if self._locale != old_locale:
            self.language_changed.emit(self._locale)

    def t(self, context: str, key: str, fallback: str = "") -> str:
        """按 key 获取翻译文本。"""
        key_for_lookup = QCoreApplication.translate(context, key)
        if key_for_lookup in self._catalog:
            return self._catalog[key_for_lookup]
        if key in self._catalog:
            return self._catalog[key]
        if fallback:
            return fallback
        return key
