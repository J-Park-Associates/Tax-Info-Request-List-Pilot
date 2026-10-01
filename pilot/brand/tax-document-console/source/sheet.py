"""Contact sheet for the chosen mark: every size 1:1 on light and dark, 8x zooms, the vector mark on cream."""
import io
import sys

from mark import SIZES, bare_mark
from PIL import Image
from raster import icon_png
from render import Renderer


def main(out):
    with Renderer() as r:
        imgs = {s: Image.open(io.BytesIO(icon_png(r, s))) for s in SIZES}
        big = Image.open(io.BytesIO(r.png(bare_mark("color"), 208, 208)))
    W = sum(SIZES) + 12 * len(SIZES) + 24
    H = 2 * 280 + 32 * 8 + 48 + 240
    sh = Image.new("RGBA", (max(W, 1400), H), (255, 255, 255, 255))
    for row, bg in enumerate([(243, 243, 243, 255), (32, 32, 32, 255)]):
        band = Image.new("RGBA", (sh.width, 280), bg)
        x = 12
        for s in SIZES:
            band.alpha_composite(imgs[s], (x, 12 + 256 - s))
            x += s + 12
        sh.alpha_composite(band, (0, row * 280))
    y, x = 2 * 280 + 16, 12
    for s in (16, 20, 24, 32):
        z = imgs[s].resize((s * 8, s * 8), Image.NEAREST)
        bg = Image.new("RGBA", z.size, (243, 243, 243, 255))
        bg.alpha_composite(z)
        sh.alpha_composite(bg, (x, y))
        x += s * 8 + 16
    cream = Image.new("RGBA", (big.width + 32, big.height + 16), (245, 240, 232, 255))
    cream.alpha_composite(big, (16, 8))
    sh.alpha_composite(cream, (12, y + 32 * 8 + 16))
    sh.convert("RGB").save(out)


if __name__ == "__main__":
    main(sys.argv[1])
