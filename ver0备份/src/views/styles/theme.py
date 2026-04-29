from __future__ import annotations

from pathlib import Path


def build_theme() -> dict[str, str]:
    return {
        "APP_BG": "#F2F5F9",
        "CARD_BG": "#FFFFFF",
        "BORDER": "#D8E1EA",
        "TEXT": "#1F2D3D",
        "TEXT_SUB": "#52677A",
        "PRIMARY": "#0078D4",
        "PRIMARY_HOVER": "#2B88D8",
        "SUCCESS": "#0E9F6E",
        "WARNING": "#D97706",
        "ERROR": "#DC2626",
        "INFO": "#0EA5E9",
    }


def load_qss_with_theme(qss_path: str | Path, theme: dict[str, str]) -> str:
    text = Path(qss_path).read_text(encoding="utf-8")
    for key, value in theme.items():
        text = text.replace(f"@{key}@", value)
    return text
