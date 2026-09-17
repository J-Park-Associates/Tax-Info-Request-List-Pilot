# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the frozen tracker API that "Build App.bat" ships
beside the Electron shell.

Committed, rather than regenerated from command-line flags on every build,
so what gets frozen is part of the commit that gets built: the same spec,
the same pinned freezer (requirements-build.txt), the same output. The
executable's name is read from app/package.json (config.apiName), the one
place it lives - the shell looks for the same name at run time.
"""

import json
from pathlib import Path

API_NAME = json.loads(Path("app/package.json").read_text(encoding="utf-8"))["config"]["apiName"]

a = Analysis(
    ["api_entry.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=API_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=API_NAME,
)
