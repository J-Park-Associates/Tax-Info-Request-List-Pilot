"""Draw the glass theme's refraction map, ``app/renderer/glass-lens.png``.

The map is the second input of an SVG ``feDisplacementMap``: the red channel
says how far to slide the backdrop sideways and the green channel how far to
slide it up or down, with 128 meaning "not at all". Only a thin band along
each edge is non-neutral, so the backdrop bends at the rim of a glass surface
and is untouched in the middle (SPEC-glass section 6.3).

Standard library only (``zlib`` and ``struct``): the pilot adds no package for
one small picture. The file is committed; ``tests/test_glass.py`` decodes it
and compares every pixel with :func:`pixel`, so the picture and this drawing
rule cannot drift apart.

Run:  python pilot/make_glass_lens.py [out-path]
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

SIZE = 256
BAND = 20
NEUTRAL = 128
REACH = 127
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "app" / "renderer" / "glass-lens.png"


def _channel(pos: int) -> int:
    """One axis: positive near the low edge, negative near the high edge."""
    low = pos
    high = SIZE - 1 - pos
    nearest = min(low, high)
    t = min(nearest / BAND, 1.0)
    strength = (1.0 - t) ** 2
    if low <= high:
        return round(NEUTRAL + REACH * strength)
    return round(NEUTRAL - REACH * strength)


def pixel(x: int, y: int) -> tuple[int, int, int]:
    """The (R, G, B) of the pixel at column ``x``, row ``y``."""
    return (_channel(x), _channel(y), NEUTRAL)


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def png_bytes() -> bytes:
    """The whole PNG: 8-bit RGB, no interlace, filter byte 0, one IDAT."""
    rows = bytearray()
    for y in range(SIZE):
        rows.append(0)
        for x in range(SIZE):
            rows.extend(pixel(x, y))
    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("usage: python pilot/make_glass_lens.py [out-path]", file=sys.stderr)
        return 2
    out = Path(args[0]) if args else DEFAULT_OUT
    data = png_bytes()
    out.write_bytes(data)
    print(f"wrote {out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
