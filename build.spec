# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Freakuency.

Build with:
    pyinstaller build.spec

Produces: dist/Freakuency/ (one-dir mode)
"""

import os
import sys
import importlib

block_cipher = None

# Locate pydivert package to bundle WinDivert binaries
pydivert_path = os.path.dirname(importlib.import_module("pydivert").__file__)
windivert_binaries = []
for fname in os.listdir(pydivert_path):
    if fname.lower().startswith("windivert") and (
        fname.endswith(".dll") or fname.endswith(".sys")
    ):
        windivert_binaries.append(
            (os.path.join(pydivert_path, fname), ".")
        )

# Also check pydivert/lib subdirectory
lib_dir = os.path.join(pydivert_path, "lib")
if os.path.isdir(lib_dir):
    for fname in os.listdir(lib_dir):
        if fname.lower().startswith("windivert"):
            windivert_binaries.append(
                (os.path.join(lib_dir, fname), ".")
            )

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=windivert_binaries,
    datas=[
        ("assets", "assets"),
    ],
    hiddenimports=[
        "customtkinter",
        "psutil",
        "pydivert",
        "PIL",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Freakuency",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Freakuency",
)
