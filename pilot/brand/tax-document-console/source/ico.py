"""Pack per-size PNG renders into one Windows .ico.

Sizes below 256 are stored as 32-bit BGRA bitmaps with an AND mask - the form
every Windows icon consumer reads, including resource compilers that choke on
PNG entries; 256 is stored as PNG, as Windows Vista onward expects.
"""
import io
import struct

from PIL import Image


def _dib(im: Image.Image) -> bytes:
    w, h = im.size
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    px = im.load()
    rows = []
    for y in range(h - 1, -1, -1):                    # bottom-up
        row = bytearray()
        for x in range(w):
            r, g, b, a = px[x, y]
            row += bytes((b, g, r, a))
        rows.append(bytes(row))
    stride = ((w + 31) // 32) * 4                     # 1-bit rows padded to 32 bits
    mask = []
    for y in range(h - 1, -1, -1):
        bits = bytearray(stride)
        for x in range(w):
            if px[x, y][3] == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        mask.append(bytes(bits))
    return header + b"".join(rows) + b"".join(mask)


def pack(pngs: dict[int, bytes]) -> bytes:
    sizes = sorted(pngs)
    blobs = []
    for s in sizes:
        im = Image.open(io.BytesIO(pngs[s])).convert("RGBA")
        if im.size != (s, s):
            raise ValueError(f"render for {s}px came back {im.size}")
        im.putalpha(im.getchannel("A").point(lambda a: 0 if a < 8 else a))
        blobs.append(pngs[s] if s >= 256 else _dib(im))
    out = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    for s, blob in zip(sizes, blobs, strict=True):
        d = 0 if s >= 256 else s
        out += struct.pack("<BBBBHHII", d, d, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    return out + b"".join(blobs)
