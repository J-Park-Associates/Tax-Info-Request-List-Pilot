# Handoff: the Tax Document Console icon (2026-09-30)

## What was done

- Three icon options were drawn and reviewed (Vault, Tick, Nest). Jason then
  picked a different concept, generated with Nano Banana from a prompt written
  in this session (`pilot/brand/tax-document-console/concept-approved.png`).
- That concept was redrawn as exact geometry and hand-tuned per size. An
  independent reviewer, a fresh agent each round, measured every size pixel by
  pixel; findings were fixed and re-reviewed until round 18 returned no
  findings (63 fixes).
- Every file the app, its build and its installer need was exported to
  `pilot/brand/tax-document-console/`, with the generator in its `source/`.
  A rebuild reproduces the committed files byte for byte.
- Decision P115 records the pick. `pilot/SPEC-icon.md` is the SPEC for wiring
  the files in.

## What is left

1. Jason answers the two questions at the top of `pilot/SPEC-icon.md` (keep the
   product name for now; which brand shows in the side panel).
2. A build session wires the icon in, exactly as `SPEC-icon.md` says, and runs
   the tests it names.
3. A review session that did not build it; then the Windows check in the SPEC.
4. The three unpicked options were not committed. Their comparison page is an
   Artifact in Jason's account, "Tax Document Console Marks".

## Files the next session needs

- `pilot/SPEC-icon.md`
- `pilot/brand/tax-document-console/README.md`, and the files it lists
- `Build App.bat`, `app/main.js`, `pilot/installer/setup.iss`, `api_entry.spec`,
  looked up through `tools/repo_map.py show`

Do not edit the artwork by hand. Change `source/mark.py`, rebuild, and read
the sheet's 16, 20 and 24px zooms. The README lists two deliberate choices a
reviewer may flag and that should stay as they are.
