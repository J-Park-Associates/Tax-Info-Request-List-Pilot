# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the frozen tracker API that "Build App.bat" (and, on a
Mac, "build-mac.sh") ships beside the Electron shell.

Committed, rather than regenerated from command-line flags on every build,
so what gets frozen is part of the commit that gets built: the same spec,
the same pinned freezer (requirements-build.txt), the same output. The
executable's name is read from app/package.json (config.apiName), the one
place it lives - the shell looks for the same name at run time.

On a Mac (SPEC-mac R13) the freeze is Apple silicon only: ``target_arch`` is
"arm64", not "universal2", because ONNX Runtime publishes no x86_64 Mac wheel
and a universal2 freeze would be a lie about half its slices (P243). The API
is a console binary inside the app bundle, so it carries no icon (the bundle's
own icon is the shell's), and ``codesign_identity=None`` has PyInstaller sign
it ad hoc, which Apple silicon requires of any Mach-O it runs; the entitlements
file stays None until signing lands (P239). ``freeze_support()`` already runs
in api_entry.py, which is what lets a reading child start under ``spawn``.
"""

import json
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

API_NAME = json.loads(Path("app/package.json").read_text(encoding="utf-8"))["config"]["apiName"]

# The reader (decision 169). rapidocr names its parts through a table it
# imports lazily, which the freezer cannot follow, so its modules are
# named here - all but the engines the app never runs (it runs ONNX
# Runtime only). Its three models and its two settings files are data:
# they ship inside the app, and nothing is ever downloaded.
READER_ENGINES_NOT_SHIPPED = ("pytorch", "paddle", "openvino", "mnn", "tensorrt")
READER_MODULES = collect_submodules(
    "rapidocr",
    filter=lambda name: not any(f".inference_engine.{engine}" in name
                                for engine in READER_ENGINES_NOT_SHIPPED))
READER_DATA = collect_data_files(
    "rapidocr", includes=["config.yaml", "default_models.yaml", "models/*.onnx"])
#: OpenCV's video codec library (31 MB), which reading never uses (R-11;
#: the frozen smoke read proves nothing needed it).
NOT_SHIPPED_BINARIES = ("opencv_videoio_ffmpeg",)

a = Analysis(
    ["api_entry.py"],
    pathex=[],
    binaries=[],
    datas=READER_DATA,
    hiddenimports=["onnxruntime", *READER_MODULES],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.startswith(NOT_SHIPPED_BINARIES)]
pyz = PYZ(a.pure)

# What differs by platform and nothing else: see the docstring for the Mac.
if sys.platform == "darwin":
    PLATFORM_OPTIONS = {"target_arch": "arm64", "codesign_identity": None, "entitlements_file": None}
else:
    # The same icon as the shell's program file (pilot SPEC-icon, item 6); the
    # path is relative to where Build App.bat runs PyInstaller, the repo root.
    PLATFORM_OPTIONS = {"icon": "app/assets/icon.ico"}

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
    **PLATFORM_OPTIONS,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=API_NAME,
)
