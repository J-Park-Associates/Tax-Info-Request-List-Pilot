# Orchestrator's rulings before the combined review (2026-09-30)

On the F7 builder's three open choices (`pilot/handoffs/F7-build.md`):

1. **The refusal sentence fills the product's name from `product_name()`.** Accepted: `test_single_source` forbids typing the product name in `tracker/`, and the words shown are the SPEC's.
2. **`redirected_copies()` answers nothing when `TRACKER_DATA_HOME` is set.** Accepted: a person who names a data folder means it, and without this the suite on this PC would read the real Claude copy.
3. **`run_checks.ps1` started the app itself (its step 8).** Rejected: the script never started the app before, and the first start is the hands-on step 19, watched as the one-time setup runs. SPEC-F7 R4 asked for it without weighing that. Folded: step 8 now records how to start the app (Start menu, or `explorer.exe` with the shortcut, never `Start-Process`) and starts nothing; `PROMPT-0.3.md`'s note says the same.

The branches were combined in landing order with merge commits: F7 (`ae5219f`) as `d51cac3`, then the Taxpayer words (`9e20f2c`, stacked on the firm columns `61901ba`) as `2ee1dce`. Only the generated map conflicted; it was regenerated.

## Rulings on the combined review (`combined-review.md`)

- **M1 (the editor's "this client is not chased by email").** Accepted; fix as the review says: an `EDITOR_HELP` override beside `EDITOR_LABELS` in `tracker/api.py`, and the editor's help lines added to the client-word test (`tests/test_api.py` near 9294).
- **S1 (other sentences that still say "client").** Accepted, ruled by one rule rather than asked: "client" stays where it names the firm's clients' data in general or the `Clients` folder on disk (the folder ruling of P196, as the folder buttons already do); it becomes "Taxpayer" where it means the person on a return and "Household" where it means a listed household. Each line the review names (`settings.py:145/147`, `runner.py:288`, `settings.py:973-984`, `api.py:648`, `api.py:3852`) is changed or listed in SPEC-taxpayer-words with its reason. No question for Jason.
- **S2 (an unlistable Packages folder raises a raw PermissionError).** Accepted; fix. `redirected_copies()` and the probe catch `OSError`; the first screen says one sentence naming the error's class and the folder, never a traceback, and the rest of the first screen still shows (fail loudly, never fail whole). A test pins it.
- **S3 (the installer is started from the agent's shell).** Accepted as a check item, not code: the 0.3 install on 9/30 landed in the real `Programs` folder (the Claude copy holds no `Programs` folder), but the next Windows check confirms it. Added to `PROMPT-0.3.md`'s note.
- **S4 (`pilot/HANDOFF.md` is stale).** Accepted; fix: name F7 and say the three builds are combined and reviewed.
- **S5 (1100 px measured outside the app).** Accepted as a check item: one look at 1100 px in the next Windows check, added to the same note.
- **NITs.** Comments saying Client/Clients where P196 changed the screen word: fix. The two place names in `pilot/wording-shell.tsv`: fix. The contradictory second line when the app itself is redirected: fix by not naming the redirected copy as "never used" while R1 is refusing (R1's sentence alone). The 4-column loading rows: match the five columns. The `test_shell_menu` timing flake on 3.11: predates this work (passes alone, passes on `392ec27`); not fixed here, recorded in the handoff.
