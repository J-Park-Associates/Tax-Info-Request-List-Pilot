"""The graphics card pack: the folder that lets the reader use an NVIDIA card.

Decision 169, ruling 2. The app ships ONNX Runtime's graphics card build,
which reads on the processor on any machine, and **not** the NVIDIA
libraries it needs to read on a card - CUDA 13 and cuDNN 9, about 1.6 GB.
Those are this pack: one flat folder, ``gpu-runtime``, copied beside
``tracker-api.exe`` on a machine with a supported NVIDIA card (the office
machine), and nowhere else. A fresh install for another firm stays small
and works on any PC; the office gets the card. At the start of a pass the
reader loads the libraries from that folder, proves the card with a
one-page self-test, and says in the run log's first line which device read
(:mod:`tracker.ocr`).

Why a flat folder of DLLs rather than the wheels themselves: the NVIDIA
wheels lay their libraries out in package folders (``nvidia/cu13/bin/
x86_64``, ``nvidia/cudnn/bin``) that only make sense inside a Python
environment, and the frozen app has none. ``onnxruntime.preload_dlls``
takes one folder and loads each library from it by name, and cuDNN finds
its own sub-libraries beside itself.

What goes in is exactly the DLLs of the wheels ``requirements-gpu.txt``
pins, installed with ``--no-deps`` into an environment of their own by
``Build GPU Pack.bat``, which then runs::

    python tools/gpu_pack.py <that environment's site-packages> <out folder>

Nothing here downloads anything: the batch file's pip does, from the
pinned list, and only when a person runs it.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

#: The pack's folder name, which the reader looks for beside the app.
PACK_DIR_NAME = "gpu-runtime"
#: Where, under a site-packages folder, the pinned NVIDIA wheels put their
#: Windows libraries: the CUDA 13 runtime, cuBLAS, cuFFT, cuRAND, NVRTC and
#: nvJitLink together, and cuDNN on its own.
LIBRARY_FOLDERS = (
    Path("nvidia") / "cu13" / "bin" / "x86_64",
    Path("nvidia") / "cudnn" / "bin",
)
#: Libraries the reader cannot do without: ONNX Runtime's CUDA provider
#: loads these by name. A pack missing one is refused, not shipped.
REQUIRED = ("cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll", "cufft64_12.dll",
            "cudnn64_9.dll")


class PackError(Exception):
    """The environment does not hold what a pack needs."""


def libraries(site_packages: Path) -> list[Path]:
    """Every DLL the pinned NVIDIA wheels installed under ``site_packages``."""
    found = []
    for folder in LIBRARY_FOLDERS:
        found.extend(sorted((Path(site_packages) / folder).glob("*.dll")))
    names = {path.name for path in found}
    if missing := [name for name in REQUIRED if name not in names]:
        raise PackError(f"not in {site_packages}: {', '.join(missing)} - install requirements-gpu.txt "
                        "there first")
    return found


def build_pack(site_packages: Path, out: Path) -> Path:
    """Copy the libraries into ``out`` (made, or emptied first) as one flat
    folder, and return it."""
    out = Path(out)
    if out.name != PACK_DIR_NAME:
        # It empties the folder it is given: never one mistyped.
        raise PackError(f"the pack's folder must be named {PACK_DIR_NAME}, not {out.name!r}")
    found = libraries(site_packages)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for path in found:
        shutil.copy2(path, out / path.name)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python tools/gpu_pack.py",
        description="Make the graphics card pack (a flat folder of the NVIDIA libraries) "
                    "from an environment holding requirements-gpu.txt.")
    parser.add_argument("site_packages", help="that environment's site-packages folder")
    parser.add_argument("out", help=f"the folder to make (copy it beside tracker-api.exe as {PACK_DIR_NAME})")
    ns = parser.parse_args(argv)
    try:
        pack = build_pack(Path(ns.site_packages), Path(ns.out))
    except PackError as exc:
        print(f"No pack made: {exc}", file=sys.stderr)
        return 1
    files = list(pack.iterdir())
    size = sum(path.stat().st_size for path in files)
    print(f"{pack}: {len(files)} libraries, {size / 1e6:,.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
