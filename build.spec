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

# Locate pydivert package to bundle WinDivert binaries.
# The DLL/SYS files live in pydivert/windivert_dll/ — we must place them
# in the same relative path inside the bundle so pydivert can find them.
pydivert_path = os.path.dirname(importlib.import_module("pydivert").__file__)
windivert_binaries = []
dll_dir = os.path.join(pydivert_path, "windivert_dll")
if os.path.isdir(dll_dir):
    for fname in os.listdir(dll_dir):
        if fname.lower().startswith("windivert") and (
            fname.endswith(".dll") or fname.endswith(".sys")
        ):
            windivert_binaries.append(
                (os.path.join(dll_dir, fname), os.path.join("pydivert", "windivert_dll"))
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
        "pystray",
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
    icon=os.path.join("assets", "freakuency.ico"),
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
