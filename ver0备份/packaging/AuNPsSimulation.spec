# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\Code\\VSCode\\Python\\Software\\AuNPsSimulation\\ver2\\src\\main.py'],
    pathex=['E:\\Code\\VSCode\\Python\\Software\\AuNPsSimulation\\ver2\\src'],
    binaries=[],
    datas=[('E:\\Code\\VSCode\\Python\\Software\\AuNPsSimulation\\ver2\\src\\res', 'src/res'), ('E:\\Code\\VSCode\\Python\\Software\\AuNPsSimulation\\ver2\\src\\views\\styles\\style.qss', 'src/views/styles'), ('E:\\Code\\VSCode\\Python\\Software\\AuNPsSimulation\\ver2\\packaging\\.venv_build\\Lib\\site-packages\\PySide6\\plugins', 'PySide6/plugins')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'pytest', 'IPython', 'sphinx', 'sphinxcontrib', 'docutils', 'pyqtgraph', 'torch', 'torchvision', 'torchaudio', 'tensorflow', 'jax', 'jaxlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AuNPsSimulation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
