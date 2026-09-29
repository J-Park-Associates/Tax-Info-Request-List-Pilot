"""The glass theme (pilot SPEC-glass): its lens map, page hooks, style and script.

Everything is read as text; nothing here needs a browser. The rendered checks
(contrast sweep, reduced-preference emulation, speed) run in scratch scripts
and their results are recorded in the handoff.
"""

import importlib.util
import struct
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RENDERER = REPO / "app" / "renderer"


def _load_lens_generator():
    spec = importlib.util.spec_from_file_location("make_glass_lens", REPO / "pilot" / "make_glass_lens.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decode_png(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, header = 8, b"", None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    return header, zlib.decompress(idat)


def test_the_lens_map_is_what_its_generator_draws():
    lens = _load_lens_generator()
    header, raw = _decode_png((RENDERER / "glass-lens.png").read_bytes())
    assert header == (lens.SIZE, lens.SIZE, 8, 2, 0, 0, 0)
    stride = 1 + lens.SIZE * 3
    assert len(raw) == stride * lens.SIZE
    for y in range(lens.SIZE):
        row = raw[y * stride : (y + 1) * stride]
        assert row[0] == 0, y
        for x in range(lens.SIZE):
            assert tuple(row[1 + x * 3 : 4 + x * 3]) == lens.pixel(x, y), (x, y)
