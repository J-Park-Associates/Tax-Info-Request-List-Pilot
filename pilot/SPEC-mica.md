# Pilot 0.2 - Mica window material - SPEC

Status: written and built in one session on 2026-09-29 by a one-time exception
Jason made to the one-job-per-session rule ("build it properly for mica ...
one time exception"). Decision P46 (`DECISIONS.md`). It rides pull request #9
on branch `build-d`, on top of the glass theme (`SPEC-glass.md`). Because the
builder also wrote this SPEC, the independent Review 3 must cover this file
too, and the Windows check is Jason's.

Jason's choices, taken as the recommended options (his open questions answered
"build it properly"): **page paint A** (a pale wash over Mica, the header dark
navy at higher opacity) and **level mapping A** (Mica under everything, set
once at launch; Solid paints an opaque page over it).

## 1. What this is

On Windows 11 22H2 or later the app window is drawn on Mica, the system's own
window material (a soft tint of the wallpaper, also under the title bar). The
page lays a pale wash over it, so Mica shows as a quiet tint, and the glass
theme sits on top exactly as built. On every other machine nothing changes:
the window and page look as they do in Build D.

Not built: a fourth picker choice, a live switch of the material (it would
need a new channel between the main program and the page, forbidden by P10),
acrylic, tabbed Mica, any third-party module (`vibe`, `mica-electron`), or a
frameless window.

## 2. Facts

| Fact | Where |
|---|---|
| `BrowserWindow` takes `backgroundMaterial: "mica"`; Windows 11 22H2 (build 22621) and later only | electronjs.org/docs/latest/api/browser-window |
| The web contents must be transparent (`backgroundColor: "#00000000"`) for the material to show | same |
| A framed window gets the material behind its title bar too | same |
| With Windows' Transparency effects off, Windows draws Mica as a plain colour | Windows |
| `os.release()` on Windows 11 is `10.0.<build>` | Node |

## 3. `app/main.js` (the one exception to Build D's "no main.js", P46)

Add, and nothing else:

1. `const os = require("os");` beside the other Node requires.
2. Constants and one function, before `createWindow`:
   ```
   const MICA_MIN_BUILD = 22621;      // Windows 11 22H2
   const MICA_CLEAR = "#00000000";
   function micaAvailable() {
     if (process.platform !== "win32") return false;
     const build = Number(String(os.release()).split(".")[2]);
     return Number.isInteger(build) && build >= MICA_MIN_BUILD;
   }
   ```
3. In `createWindow`: `const mica = micaAvailable();`; the two options
   `backgroundColor: mica ? MICA_CLEAR : pageBackground(),` and, spread only
   when `mica`, `backgroundMaterial: "mica"`.
4. `win.loadFile(path.join(__dirname, "renderer", "index.html"), mica ? { query: { material: "mica" } } : undefined);`
   The page learns it from its own address: no IPC, no preload change.

If the constructor throws or the platform is not Windows 11 22H2+, the window
is exactly today's (`pageBackground()`, no material, no query).

## 4. `app/renderer/glass.js`

If `new URLSearchParams(window.location.search).get("material") === "mica"`,
add `glass-mica` to `<html>`. Nothing else changes; if the script fails the
class is absent and the page paints its opaque backdrop, which is right.

## 5. `app/renderer/glass.css`

Tokens (colour literals only in token declarations, P33):
`--glass-mica-wash: rgba(243, 246, 250, 0.88)` and, in a `:root.glass-mica`
block placed **before** `:root.glass-solid`, `--glass-tint-bar: rgba(14, 37, 68, 0.85)`.

Rules, in this order, after the existing `body` rules:
- `:root.glass-mica body { background: var(--glass-backdrop-glows), var(--glass-mica-wash); }`
- `:root.glass-mica.glass-full body { background: var(--glass-mica-wash); }`
  (the Full level's glows stay on `body::before`)
- `:root.glass-mica.glass-solid body { background: var(--glass-backdrop) var(--glass-backdrop-base); }`
  (Solid paints an opaque page over Mica)

In both fallback blocks (reduced transparency, motion, more contrast, forced
colours; and no backdrop-filter) add
`:root.glass-mica body, :root.glass-mica.glass-standard body, :root.glass-mica.glass-full body, :root.glass-mica.glass-solid body { background: var(--glass-backdrop) var(--glass-backdrop-base); }`,
so the system asking for less is opaque whatever Windows draws.

## 6. Contrast (the test's mica case)

Mica's colour is unknown, so the proof treats it as any colour from black to
white. Behind the glass can then be: the wash over black, the wash over
white, the glow colours at full strength, white and `--navy-deep`
(toolbar and dialogs, as before, dialogs also under the 0.60 dim). Header:
the two wash extremes and the first glow. Every pair of SPEC-glass 10.2 still
needs 4.5:1, using the mica header tint. Text that sits directly on the page
(not on a card) is unchanged from Build D and not part of this proof.

## 7. Tests

- `tests/test_glass.py`: the contrast test gains the mica case (section 6);
  a test that the page and main.js agree (`glass-mica`, the query name and
  value, `MICA_MIN_BUILD`, `backgroundMaterial: "mica"` only under a `mica`
  condition); a test that the mica body rules exist in the order of section
  5 and the fallback blocks reset them; a node test that runs the real
  `main.js` against a stand-in Electron on a fake Windows 11 build, a fake
  Windows 10 build and a fake Linux, and checks the window options and the
  `loadFile` query in each (skipped where node is not on PATH).
- `tests/test_single_source.py::test_the_window_colour_is_read_from_the_stylesheet`
  keeps its claim (the colour is read from the stylesheet, never typed) but
  accepts `mica ? MICA_CLEAR : pageBackground()`.
- Standing: `test_layers` (no network call, no new IPC), `test_single_source`,
  `test_repo_map`, `test_pilot`, `test_tour`.

## 8. Windows check for Jason (the cloud cannot draw Mica)

On Windows 11 22H2+: (1) the title bar and the window behind the page show a
soft wallpaper tint, not white; (2) header dark, toolbar and cards still
glass and readable on a light and a dark wallpaper; (3) Screen effects: Solid
turns the page opaque, Glass returns the tint; (4) Windows Settings >
Personalization > Colors > Transparency effects off: the page goes opaque
without a restart; (5) on Windows 10 or Remote Desktop the page looks as
Build D does.

## 9. Rollback

Delete the `mica` lines of section 3 and the `glass-mica` class line of
section 4; the CSS rules for `:root.glass-mica` then never match. Nothing
else depends on them.
