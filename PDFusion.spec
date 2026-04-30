# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec per PDFusion.
Ottimizzato per ridurre la dimensione del bundle escludendo moduli Qt non necessari.
"""

import sys
from pathlib import Path

block_cipher = None

APP_DIR = Path(SPECPATH)
SRC_DIR = APP_DIR / "src"
ASSETS_DIR = APP_DIR / "assets"

a = Analysis(
    [str(SRC_DIR / "main.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[
        (str(ASSETS_DIR / "icons"), "assets/icons"),
        (str(ASSETS_DIR / "licenses" / "templates"), "assets/licenses/templates"),
        (str(SRC_DIR / "styles" / "pdfusion.qss"), "styles"),
    ],
    hiddenimports=[
        "pikepdf._core",
        "reportlab.graphics",
        "PIL._tkinter_finder",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Moduli Qt non usati — riducono significativamente il bundle
        "PyQt6.Qt3DAnimation",
        "PyQt6.Qt3DCore",
        "PyQt6.Qt3DExtras",
        "PyQt6.Qt3DInput",
        "PyQt6.Qt3DLogic",
        "PyQt6.Qt3DRender",
        "PyQt6.QtBluetooth",
        "PyQt6.QtCharts",
        "PyQt6.QtDataVisualization",
        "PyQt6.QtDesigner",
        "PyQt6.QtHelp",
        "PyQt6.QtLocation",
        "PyQt6.QtMultimedia",
        "PyQt6.QtMultimediaWidgets",
        "PyQt6.QtNfc",
        "PyQt6.QtOpenGL",
        "PyQt6.QtPositioning",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtQuickWidgets",
        "PyQt6.QtRemoteObjects",
        "PyQt6.QtSensors",
        "PyQt6.QtSerialPort",
        "PyQt6.QtSql",
        "PyQt6.QtTest",
        "PyQt6.QtTextToSpeech",
        "PyQt6.QtWebChannel",
        "PyQt6.QtWebEngine",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebSockets",
        "PyQt6.QtXml",
        # Altro
        "matplotlib",
        "scipy",
        "numpy",
        "pandas",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFusion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminale
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_DIR / "icons" / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PDFusion",
)

# macOS: crea un bundle .app
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PDFusion.app",
        icon=str(ASSETS_DIR / "icons" / "app.icns"),
        bundle_identifier="com.pdfusion.app",
        info_plist={
            "CFBundleDisplayName": "PDFusion",
            "CFBundleVersion": "0.1.11",
            "CFBundleShortVersionString": "0.1.11",
            "NSHighResolutionCapable": True,
        },
    )
