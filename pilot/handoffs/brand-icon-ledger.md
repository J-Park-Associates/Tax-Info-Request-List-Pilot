# Handoff: the Ledger 4e icon (2026-10-01)

## Done
- Jason chose concept 4e "Gold tab" (P116) after three rounds of concepts
  (https://claude.ai/artifact/MF8rLu5xoeTXdhFdYZHPgJ). It replaces P115's
  monogram under the same file names.
- SPEC: `pilot/SPEC-icon-ledger.md`. Generator and files:
  `pilot/brand/tax-document-console/` (README says what each file is).
- Every Microsoft size is drawn at its own pixel size: pixel art at 16/20/24,
  the fitted drawing without rules at 30-47, the full fitted drawing from 48.
  New `windows/` folder: Square44x44Logo (7 scales, 14 target sizes x 3 forms)
  and Square150x150Logo (7 scales). The installer panels and lockups use the
  new mark.
- Two changes from the concept, both for the brief's 3:1 on both themes: the
  rim runs round the flap, and it is mid-blue `#6A87C2` instead of pale.
- Reviewed by independent Opus sessions over seven rounds until one came back
  with no findings (commits c90a4c1 to 3eb5ebc; each message lists what that
  round found). Outline contrast, measured at every size with blended pixels:
  3.03:1 dark, 3.09:1 light.

## Left
- Wiring the icon into the app and installer: `pilot/SPEC-icon.md`, still
  waiting on Jason's two questions there (the product's name; the side
  panel's brand spot). Its file paths are unchanged, so it applies as written.
- The `windows/` assets are for an MSIX package; nothing uses them until the
  app is packaged that way.
- Known and accepted: measured diagonally (8-connected) rather than straight
  across, the folder's rounded top-right corner dips to 1.7:1 at 36-55px.
  Every round used the straight-across measure, on which it passes.

## Files the next session needs
`pilot/SPEC-icon.md`, `pilot/brand/tax-document-console/README.md`, and the
P115/P116 rows in `pilot/DECISIONS.md`.
