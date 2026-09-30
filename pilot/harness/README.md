# The screenshot harness

Draws the app's new screen in the cloud's Chromium with **made-up names only**,
so the layout can be looked at before the pages and the engine part exist
(SPEC-shell section 14.4). It is never loaded by the app, never packaged, and
pytest does not run it.

What is in it:

| File | What it is |
|---|---|
| `stub.js` | A stand-in for the tracker: the Smith Family, Rivera Design LLC, Ana Lopez and 500 generated households, in the shapes the joined engine sends - `firm` (returns with `year` and `label`, files with `handle`, `year` and `open_key`, and the top-level `paths` of those keys, ruling 15), `state` (the copies' keys `shown_key`, `open_key`, `open_keys`, `paths`, and the reminder card) and the writes the side sheet makes (assign, dismiss, restore, reminder, approve), which change the made-up return so the sheet moves on. Its words are the engine's own, `tracker.api._vocab()` of this tree, and `tests/test_shell.py` holds its replies to the real ones (`test_the_harness_stub_speaks_the_apis_vocabulary`, `test_the_harness_stub_replies_have_the_shape_of_the_engines`). |
| `make_vocab.py` | Dumps `tracker.api._vocab()` of this tree as JSON for the server, every run. (S6b removed the snapshot `vocab-mirror.json` and the `HARNESS_LIVE_VOCAB` switch: live is the only mode.) |
| `app-stub.js` | A double of `app.js`: the names `shell.js` and `pages.js` use, and nothing else. It is the contract, written as code. The real `pages.js` is loaded with it (`?mode=double`; the side sheet needs the real `app.js`, so `sheet.js` is left out there). |
| `accel.js`, `boot.js` | The menu's accelerators (Ctrl+1 to Ctrl+4, Ctrl+F, F5, F9) mapped to the menu channel, because a browser has no menu bar (both modes); the double's start. |
| `serve.mjs` | A tiny local server. The default mode is `real`: the real `app.js` and `sheet.js` on the stub tracker. |
| `shoot.mjs` | Shoots every scenario, light and dark, at 1100 x 700 and 1400 x 900 - including the side sheet (Check a file with More open, a moved copy, an email, a photo, from the firm page, loading; Draft reminder held and ready), the roll, safeguards, about and folders-skipped dialogs, and a link's tooltip - plus a contrast-theme shot and a smoke run of the real `app.js`. |
| `interact.mjs` | Drives the shell, the sheet (open, Tab, Esc, More, Next, a write and the move to the next file, from the firm page, a failed read, the reminder), the three link kinds, the right-click menus and Shift+F10, a menu channel that throws, and the four dialogs, and asserts what happens. |

Run it from the repository root (Playwright's Chromium is already in the cloud):

```
HARNESS_PYTHON=<python with the tracker importable> node pilot/harness/shoot.mjs <output folder> [scenario ...]
```

With no scenario names it shoots them all. It exits with a list of problems
(page errors, a side panel that did not fill) if there are any.
