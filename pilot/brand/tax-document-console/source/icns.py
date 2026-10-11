"""Pack per-size PNG renders into one macOS .icns.

Written beside ``ico.py`` and by the same rule (P232): the Mac's icon and the
Windows one come out of one export, from the same renders, so the two cannot
drift and no Mac is needed to make either. ``iconutil`` would take an
``.iconset`` folder of the same PNGs, but it exists only on a Mac; the format
is small enough to write out, and writing it is what lets the artwork's
generator run anywhere it runs today.

An .icns is the four bytes ``icns`` and the file's length, then one element
per image: a four-letter type, the element's length (its own eight-byte header
included), and the data - here always a PNG, which every macOS that can run the
Console (14 and later) reads. The ten types are Apple's, and the three
retina pairs repeat a render rather than draw one twice, because the pixels
of a 32px icon are the same pixels whether it is the 32px icon or the 16px
icon at 2x:

========  ======  ====================
type      pixels  what it is
========  ======  ====================
``icp4``  16      16x16
``icp5``  32      32x32
``ic07``  128     128x128
``ic08``  256     256x256
``ic09``  512     512x512
``ic10``  1024    512x512 at 2x
``ic11``  32      16x16 at 2x
``ic12``  64      32x32 at 2x
``ic13``  256     128x128 at 2x
``ic14``  512     256x256 at 2x
========  ======  ====================

Every element is checked against its PNG's own header: a render that came back
the wrong size, or is not a PNG, raises rather than shipping an icon macOS
would silently draw blank.
"""
import struct

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: (type, pixels), in the order the elements are written.
ELEMENTS = (
    ("icp4", 16), ("icp5", 32), ("ic11", 32), ("ic12", 64),
    ("ic07", 128), ("ic13", 256), ("ic08", 256), ("ic14", 512), ("ic09", 512), ("ic10", 1024),
)
#: The renders it needs, smallest first.
SIZES = tuple(sorted({pixels for _kind, pixels in ELEMENTS}))


def _png_size(png: bytes) -> tuple[int, int]:
    """(width, height) from a PNG's IHDR, or a ValueError saying it is not one."""
    if png[:8] != PNG_SIGNATURE or png[12:16] != b"IHDR" or len(png) < 24:
        raise ValueError("an .icns element must be a PNG")
    return struct.unpack(">II", png[16:24])


def pack(pngs: dict[int, bytes]) -> bytes:
    """One .icns from ``pngs`` (pixels -> that size's PNG), holding every size in :data:`SIZES`."""
    missing = [s for s in SIZES if s not in pngs]
    if missing:
        raise ValueError(f"no render for {missing} px; an .icns needs {list(SIZES)}")
    body = b""
    for kind, pixels in ELEMENTS:
        png = pngs[pixels]
        if _png_size(png) != (pixels, pixels):
            raise ValueError(f"render for {pixels}px came back {_png_size(png)}")
        body += kind.encode("ascii") + struct.pack(">I", 8 + len(png)) + png
    return b"icns" + struct.pack(">I", 8 + len(body)) + body
