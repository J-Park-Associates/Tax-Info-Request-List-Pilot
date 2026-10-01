# Orchestrator's rulings before the combined review (2026-09-30)

On the F7 builder's three open choices (`pilot/handoffs/F7-build.md`):

1. **The refusal sentence fills the product's name from `product_name()`.** Accepted: `test_single_source` forbids typing the product name in `tracker/`, and the words shown are the SPEC's.
2. **`redirected_copies()` answers nothing when `TRACKER_DATA_HOME` is set.** Accepted: a person who names a data folder means it, and without this the suite on this PC would read the real Claude copy.
3. **`run_checks.ps1` started the app itself (its step 8).** Rejected: the script never started the app before, and the first start is the hands-on step 19, watched as the one-time setup runs. SPEC-F7 R4 asked for it without weighing that. Folded: step 8 now records how to start the app (Start menu, or `explorer.exe` with the shortcut, never `Start-Process`) and starts nothing; `PROMPT-0.3.md`'s note says the same.

The branches were combined in landing order with merge commits: F7 (`ae5219f`) as `d51cac3`, then the Taxpayer words (`9e20f2c`, stacked on the firm columns `61901ba`) as `2ee1dce`. Only the generated map conflicted; it was regenerated.
