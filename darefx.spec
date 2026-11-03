# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

block_cipher = None

# Detect platform
is_win = sys.platform.startswith("win")
icon_file = "assets/logo/darefx-app.ico" if is_win else "assets/logo/darefx-app.png"

datas = [
    ("assets", "assets"),
]

hiddenimports = [
    "darefx",
    "darefx.gui",
    "darefx.gui.main_window",
    "darefx.gui.worker",
    "darefx.gui.styles",
    "darefx.gui.components",
    "darefx.gui.components.metric_card",
    "darefx.gui.components.positions_table",
    "darefx.gui.components.control_panel",
    "darefx.gui.components.analysis_panel",
    "darefx.gui.components.settings_dialog",
    "darefx.trading",
    "darefx.trading.mt5_bridge",
    "darefx.trading.metaapi_bridge",
    "darefx.trading.bot",
    "darefx.risk",
    "darefx.risk.circuit_breaker",
    "darefx.risk.position_sizing",
    "darefx.risk.economic_news_filter",
    "darefx.analysis",
    "darefx.analysis.market_analyzer",
    "darefx.analysis.reconciler",
    "darefx.analysis.system_evaluator",
    "darefx.features",
    "darefx.features.indicators",
    "darefx.models",
    "darefx.models.lightgbm_trainer",
    "darefx.notifications",
    "darefx.notifications.telegram_notifier",
    "darefx.notifications.telegram_server",
    "PySide6.QtSvg",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

a = Analysis(
    ["app.py"],
    pathex=["src", "."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "notebook"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DareFX",
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
    icon=icon_file if os.path.exists(icon_file) else None,
)
