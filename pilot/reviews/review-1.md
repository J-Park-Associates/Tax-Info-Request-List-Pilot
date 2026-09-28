# Review 1 - Builds A (#6) and B (#4)

Independent reviewer (Opus, built nothing), 2026-09-28. Python 3.11 only.

## Build B (#4) - no blocking findings

Content equals SPEC sections 7 and 8 exactly (P24 included); scope, standing
rules and all 18 section 11 tests hold; 293 tests pass. Driven in headless
Chromium: terms, focus trap, tour steps, fallbacks and wrap-up comparison all
behave.

1. **should-fix** `app/renderer/pilot-style.css:160-176` vs `:197-205` - the
   stage strip overflows the 400px card (up to 105px) and hides the current
   stage on late steps, because `.pilot-tour-card li` outranks
   `.pilot-tour-stage`. Fix: selector `.pilot-tour-stages .pilot-tour-stage`,
   `margin-bottom: 0`, `padding: 1px 5px` (measured overflow 0 on every step).
2. **should-fix** `pilot/HANDOFF.md` - B's "For the reviewer" note is stale
   (P24 fixed it). Replace with: "P24's four fallbacks are in; the test
   requires a non-empty fallback whenever anchors are non-empty."

## Build A (#6) - no blocking findings

Renames match 3a; P19 deny list and its test are right; `setup.iss` and the
`.bat` are correct Inno Setup 6 / batch; Tester Guide covers all sections.
801 passed, 3 skipped, 1 failed - the Tesseract test, which fails identically
on `main` (P25).

3. **should-fix** `pilot/Build Pilot Installer.bat:25` - a git failure (not
   a checkout, or no git) reads as a clean tree, so an uncommitted build could
   ship (breaks P13). Fix: before the dirty check,
   `git rev-parse --verify HEAD >nul 2>&1` and on error print "This folder is
   not a git checkout, or git is not installed: the installer must be built
   from a commit." and exit 1.
4. **should-fix** `tests/test_pilot_installer.py:120-130` - the version test
   only parses its own temporary file. Fix: delete it here; the integrate
   step adds a real check (the `.bat`'s own `node -p` expression against the
   merged `pilot-content.js`).
5. **nit** `setup.iss:31-32`, `.bat:49-53` - `x64compatible` needs Inno Setup
   6.3+. Fix: the not-found message says "Inno Setup 6.3 or later".
6. **nit** `pilot/HANDOFF.md` - says three Tesseract failures; it is one
   failure and three skips.

## Merging B then A onto main

Only real conflict: `pilot/HANDOFF.md` (keep both entries). The map files are
regenerated. Merged tree: ruff clean, 397 + 422 passed, the one Tesseract
failure as on `main`; the `.bat`'s version read returns `0.1`.
