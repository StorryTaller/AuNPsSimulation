from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

APP_NAME = "AuNPsSimulation"
PACKAGING_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGING_DIR.parent
DIST_DIR = PACKAGING_DIR / "dist"
BUILD_DIR = PACKAGING_DIR / "build"
SPEC_DIR = PACKAGING_DIR
BUILD_VENV_DIR = PACKAGING_DIR / ".venv_build"


def _run(command: list[str], cwd: Path = ROOT_DIR) -> None:
    subprocess.run(command, check=True, cwd=cwd)


def _ensure_build_python() -> Path:
    python_exe = BUILD_VENV_DIR / "Scripts" / "python.exe"
    if python_exe.exists():
        return python_exe

    _run([sys.executable, "-m", "venv", str(BUILD_VENV_DIR)])
    if not python_exe.exists():
        raise RuntimeError("创建构建虚拟环境失败，未找到 python.exe")
    return python_exe


def _ensure_build_dependencies(python_exe: Path) -> None:
    requirements_file = ROOT_DIR / "requirements.txt"
    _run([str(python_exe), "-m", "pip", "install", "-U", "pip"])
    _run([str(python_exe), "-m", "pip", "install", "-r", str(requirements_file)])
    _run([str(python_exe), "-m", "pip", "install", "-U", "pyinstaller"])


def _build_exe(python_exe: Path) -> Path:
    entry = ROOT_DIR / "src" / "main.py"
    res_dir = ROOT_DIR / "src" / "res"
    qss_file = ROOT_DIR / "src" / "views" / "styles" / "style.qss"
    pyside_plugins_dir = BUILD_VENV_DIR / "Lib" / "site-packages" / "PySide6" / "plugins"

    if not pyside_plugins_dir.exists():
        raise RuntimeError(f"未找到 PySide6 插件目录: {pyside_plugins_dir}")

    command = [
        str(python_exe),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(ROOT_DIR / "src"),
        "--name",
        APP_NAME,
        "--add-data",
        f"{res_dir};src/res",
        "--add-data",
        f"{qss_file};src/views/styles",
        "--add-data",
        f"{pyside_plugins_dir};PySide6/plugins",
        "--exclude-module",
        "PyQt5",
        "--exclude-module",
        "PyQt6",
        "--exclude-module",
        "PySide2",
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "IPython",
        "--exclude-module",
        "sphinx",
        "--exclude-module",
        "sphinxcontrib",
        "--exclude-module",
        "docutils",
        "--exclude-module",
        "pyqtgraph",
        "--exclude-module",
        "torch",
        "--exclude-module",
        "torchvision",
        "--exclude-module",
        "torchaudio",
        "--exclude-module",
        "tensorflow",
        "--exclude-module",
        "jax",
        "--exclude-module",
        "jaxlib",
        str(entry),
    ]
    subprocess.run(command, check=True, cwd=ROOT_DIR)
    return DIST_DIR / f"{APP_NAME}.exe"


def _build_zip(exe_path: Path) -> Path:
    zip_path = DIST_DIR / f"{APP_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(exe_path, arcname=exe_path.name)
    return zip_path


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("build_windows.py 仅支持 Windows 环境。")

    python_exe = _ensure_build_python()
    _ensure_build_dependencies(python_exe)
    exe_path = _build_exe(python_exe)
    zip_path = _build_zip(exe_path)

    print(f"EXE: {exe_path}")
    print(f"ZIP: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
