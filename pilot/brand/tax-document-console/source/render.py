"""Rasterise SVG strings to PNG at exact pixel sizes with headless Chromium.

Chromium, not a Python SVG library, because it is the renderer the app itself
uses (Electron): the icon pixels match what the window will draw. Set
CHROME_PATH to use a particular Chromium; otherwise Playwright's own is used.
"""
import os

from playwright.sync_api import sync_playwright


class Renderer:
    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
        self._page = self._browser.new_page(device_scale_factor=1)
        return self

    def png(self, svg: str, w: int, h: int | None = None, scale: float = 1) -> bytes:
        h = h or w
        self._page.set_viewport_size({"width": int(w * scale), "height": int(h * scale)})
        pw, ph = w * scale, h * scale
        sized = svg.replace("<svg ", f'<svg width="{pw}" height="{ph}" ', 1)
        html = ("<html><body style='margin:0;background:transparent'>"
                f"<div style='width:{pw}px;height:{ph}px'>{sized}</div></body></html>")
        self._page.set_content(html)
        return self._page.screenshot(omit_background=True,
                                     clip={"x": 0, "y": 0, "width": w * scale, "height": h * scale})

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()
