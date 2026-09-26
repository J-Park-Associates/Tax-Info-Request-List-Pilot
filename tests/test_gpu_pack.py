"""Tests for tools/gpu_pack.py - the graphics card pack (decision 169, ruling 2).

The NVIDIA wheels are 1.6 GB and never enter the suite: their layout is
made here, with a few bytes standing for each library, and the tool is held
to what the reader needs of it - one flat folder, every library the pinned
wheels install, and a refusal where one ONNX Runtime needs is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import gpu_pack  # noqa: E402

from tracker import ocr  # noqa: E402

CUDA = ("cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll", "cufft64_12.dll",
        "curand64_10.dll", "nvrtc64_130_0.dll", "nvJitLink_130_0.dll")
CUDNN = ("cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll")


def wheels_installed(site: Path, *, leave_out: str = "") -> Path:
    """A site-packages holding the pinned wheels' libraries, as they lay them out."""
    for folder, names in ((gpu_pack.LIBRARY_FOLDERS[0], CUDA), (gpu_pack.LIBRARY_FOLDERS[1], CUDNN)):
        (site / folder).mkdir(parents=True)
        for name in names:
            if name != leave_out:
                (site / folder / name).write_bytes(name.encode())
    (site / "nvidia" / "cudnn" / "include").mkdir()
    (site / "nvidia" / "cudnn" / "include" / "cudnn.h").write_text("not a library")
    return site


def test_the_pack_is_one_flat_folder_of_every_library_the_wheels_installed(tmp_path):
    site = wheels_installed(tmp_path / "site-packages")
    out = tmp_path / "build" / gpu_pack.PACK_DIR_NAME
    out.mkdir(parents=True)
    (out / "left from last time.dll").write_bytes(b"old")

    assert gpu_pack.main([str(site), str(out)]) == 0

    assert sorted(path.name for path in out.iterdir()) == sorted(CUDA + CUDNN)
    assert (out / "cudnn64_9.dll").read_bytes() == b"cudnn64_9.dll"
    assert gpu_pack.PACK_DIR_NAME == ocr.GPU_PACK_DIR_NAME          # the folder the reader looks for


def test_a_pack_missing_a_library_onnx_runtime_loads_is_refused(tmp_path, capsys):
    site = wheels_installed(tmp_path / "site-packages", leave_out="cudnn64_9.dll")
    out = tmp_path / gpu_pack.PACK_DIR_NAME

    assert gpu_pack.main([str(site), str(out)]) == 1
    assert "cudnn64_9.dll" in capsys.readouterr().err
    assert not out.exists()
    with pytest.raises(gpu_pack.PackError):
        gpu_pack.libraries(site)


def test_the_pack_is_made_only_in_a_folder_named_for_it(tmp_path, capsys):
    """REVIEW-169 N-3: making the pack empties its folder first, so a
    mistyped folder is refused, and left as it was, rather than emptied."""
    site = wheels_installed(tmp_path / "site-packages")
    wrong = tmp_path / "Documents"
    wrong.mkdir()
    (wrong / "a letter.docx").write_bytes(b"keep me")

    assert gpu_pack.main([str(site), str(wrong)]) == 1
    assert gpu_pack.PACK_DIR_NAME in capsys.readouterr().err
    assert (wrong / "a letter.docx").read_bytes() == b"keep me"
