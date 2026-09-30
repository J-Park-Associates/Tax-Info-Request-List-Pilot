# Orchestrator rulings on the lane 4 re-check (after a640630)

Re-check: `pilot/reviews/lists-recheck.md` - M1 PASS, S1 PASS, one new MUST. Ruled 2026-09-30.

| Finding | Ruling |
|---|---|
| MUST-R1 - when the linked household's lock is held (a pass is sorting it), Edit Household exits 1 with "another pass holds this return's lock ... nothing was changed", though the household being edited was already saved; and because the editor always sends the related list, a contact-only save hits it too (tracker/api.py:4187-4190) | **Fold, two parts.** (1) Touch another household only when its record disagrees with what was saved: if the other side already agrees (the usual contact-only save), take no lock and write nothing there. (2) When another household's lock is held, the save succeeds for the household edited and the reply says so truthfully: the edited household is saved and the link on the named other household is not yet made; saving again after its sort finishes it (M1's repair). Exit 0 with a notice, never exit 1, never "nothing was changed". Words through the vocabulary, within the screen-word rules; add them to the wording table. Tests: a contact-only save with a linked household locked succeeds with no notice and no write to it; a link change with the other household locked saves the edited household, says the truthful notice, and a later save completes the link. Both fail on a640630. |

One fold commit with the re-check and this rulings file. Rerun tests/test_api.py, tests/test_households.py, tests/test_vocab_report.py and tests/test_single_source.py (words) on both interpreters, pass lines and exit codes. The reviewer then re-checks MUST-R1.
