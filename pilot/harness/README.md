# The screenshot harness

Draws the app's new screen in the cloud's Chromium with **made-up names only**,
so the layout can be looked at before the pages and the engine part exist
(SPEC-shell section 14.4). It is never loaded by the app, never packaged, and
pytest does not run it.

What is in it:

| File | What it is |
|---|---|
| `stub.js` | A stand-in for the tracker: the Smith Family, Rivera Design LLC, Ana Lopez and 500 generated households, the firm's counts, and the new vocabulary blocks (`screen`, `menu`) laid over the real API's vocabulary. |
| `app-stub.js` | A double of `app.js`: the names `shell.js` and `pages.js` use, and nothing else. It is the contract, written as code. The real `pages.js` is loaded with it. |
| `sheet-stub.js` | A stand-in for the side sheet's opener (`openCheck`, `openReminder`) and its frame, until `sheet.js` exists. |
| `boot.js` | Starts the double and maps the menu's accelerators (Ctrl+1 to Ctrl+4, Ctrl+F, F5, F9) to the menu channel, because a browser has no menu bar. |
| `serve.mjs`, `make_vocab.py` | A tiny local server and a dump of the real API's vocabulary. |
| `shoot.mjs` | Shoots every scenario, light and dark, at 1100 x 700 and 1400 x 900, plus a contrast-theme shot and a smoke run of the **real** `app.js` on the stub tracker. |

Run it from the repository root (Playwright's Chromium is already in the cloud):

```
HARNESS_PYTHON=<python with the tracker importable> node pilot/harness/shoot.mjs <output folder> [scenario ...]
```

With no scenario names it shoots them all. It exits with a list of problems
(page errors, a side panel that did not fill) if there are any.
