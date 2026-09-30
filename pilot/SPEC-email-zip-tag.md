# SPEC-email-zip-tag: "Email or Zip" as a status tag (P116, built as P125)

Pilot 0.3. Written 2026-09-29 23:40 PDT on `claude/email-zip-tag` (from `main`
at 877c7a2). Lane 2 of the night's four lanes.

## 1. The ruling and its reason

Jason, 2026-09-29, answering `pilot/HANDOFF.md` "Open for Jason" item 5 with
"Short tag words" (P116): the status of a file that came in an email or zip
and is not filed into another household (code `opened-not-across`) stays in
the status column, but its words become a short tag that fits the 160px
column at the 1100px minimum window. The words it had become the tooltip.
He chose this over a badge by the file name, a wider column, or keeping the
words with an ellipsis.

This SPEC turns P116 into build detail; it does not reopen it.

| # | Ruling | Reason |
|---|---|---|
| 1 | The tag is **"Email or Zip"** (Jason's working words). | Three words, Title Case, 75.8px wide in the app's font (section 4), so it never needs an ellipsis. |
| 2 | Its tooltip is **"Came in Email or Zip"**: the words it replaced, unchanged. | P116: "the full sentence stays in the hover tip". Every tooltip is five words or fewer (SPEC-shell 11). The long engine sentence is too long for a tooltip, and it stays where it already shows (the index, the letter, the log). |
| 3 | The tooltip shows **every time**, cut or not. Any other status still shows its own words only when they are cut (`setTipIfCut`, unchanged). | A tag alone could be misread: on a document's row, "Email or Zip" does not say the document *came out of* one. The words it stands for are therefore always one hover away. |
| 4 | The tip words live in a new table, `reasons.REASON_TIPS` (code to words), sent to the app as `vocab.reason_tips`. `SHORT_REASONS` stays one plain string per code. | Other readers already use `SHORT_REASONS` and `vocab.reasons` as strings (`tests/test_reasons.py`, `test_api.py`, the side sheet). A separate table changes none of them, and the next label that becomes a tag is a one-line addition. |
| 5 | The renderer finds a row's tip from the row's reason **code** (`spec.reason`), never from its words. If the vocabulary has no `reason_tips` table, the row fails loudly (`Error("reason_tips")`, which `pagesSafe` reports as that row's notice). | Words are keyed by code throughout (SPEC-shell 11.5). A missing table means the app and the engine are out of step, and that must not pass silently. |
| 6 | The file name stays plain text (ruling 24, SPEC-shell 3.9 and 6.7). | Unchanged. An email or a zip is never opened from here. |
| 7 | The side sheet's status line keeps the short tag, the same words as the row. | The sheet is one of the three places `pagesReason` is used. Keeping it the same means one word per code on every screen. The row's tooltip carries the longer words. |

No owner question. Jason's working words fit with room to spare, so this SPEC
builds them as they are.

## 2. Files, functions and lines

| File | Change |
|---|---|
| `tracker/reasons.py` | `SHORT_REASONS["opened-not-across"]`: "Came in Email or Zip" becomes "Email or Zip". New `REASON_TIPS = {"opened-not-across": "Came in Email or Zip"}` after `SHORT_REASONS`, with its reasoning in the comment. |
| `tracker/api.py` | `_vocab()`: one added key, `"reason_tips": dict(reasons.REASON_TIPS)`, with a one-line comment, directly after `"reasons": dict(reasons.SHORT_REASONS),` (lines 1694-1695). No other line in `api.py` changes. |
| `app/renderer/pages.js` | `pagesRow`: the status cell gets `setTip(status, tip)` when `vocab.reason_tips[spec.reason]` exists, and `setTipIfCut` otherwise. It throws if `spec.reason` is set and the vocabulary has no `reason_tips`. `pagesNeedsReview` and `pagesReturnGroups` (`parkedSpec`) add `reason: <code>` to each parked file's row spec. |
| `docs/repo-map.curated.json` | The note for `app/renderer/pages.js` names `vocab.reason_tips`. Then `python tools/repo_map.py update`. |

**Owning tests:**
- `tests/test_reasons.py`: new `test_a_label_shortened_into_a_tag_keeps_the_words_it_replaced_as_its_tooltip`.
- `tests/test_api.py`: `test_the_vocabulary_carries_the_menu_the_screen_and_the_short_words` checks `reason_tips`. `test_every_short_word_the_engine_adds_is_five_words_or_fewer` checks the tips too. Title Case is already checked for every word the vocabulary draws, by `test_every_drawn_word_the_vocabulary_carries_is_in_title_case`.
- `tests/test_shell.py`: the page stub carries `reason_tips` and records which tips are cut-only (`cutTips`). New `test_a_status_that_is_a_tag_always_carries_the_words_it_stands_for_as_its_tooltip`. `test_a_returns_needs_you_group_holds_parked_files_then_moved_then_requests_then_the_buckets` expects the stub's new tag.

These guards also run: `tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py` and `tests/test_vocab_report.py`.

## 3. What staff will notice

- On a return page's Needs you group and on the Needs Review page, a file that
  came out of an email or zip and was not filed across households reads
  **Email or Zip** in the status column. It is never cut with "...".
- Hovering that status shows **Came in Email or Zip**.
- Nothing else moves: the file name is still plain text, the row is still in
  the "Emails and zips" sub-group, and the step is still **Check**.

## 4. Proof that it fits

The status column is a fixed 160px grid track at every window width
(`--size-col-status`, `shell.css` `.row`). The minimum window of 1100px
leaves it at 160px. The words were measured on this PC (Windows 11, Chromium
152, the engine Electron uses) in a 160px box styled like `.row-status`:
`"Segoe UI Variable Text"` (installed and used), 14px, weight 600, `nowrap`.
The width is the text range's `getBoundingClientRect().width`, and "cut" means
`scrollWidth > clientWidth`.

| Words | Width | Cut |
|---|---|---|
| Email or Zip | 75.8px | no |
| Came in Email or Zip (old) | 131.2px | no |

The tag fits with 84px to spare, and would still fit in the cloud's DejaVu
Sans (about 12% wider, per `shell-S4-review-1.md`). The unit tests run in
Node, which has no font engine, so they cannot measure width. The width is
proven by this measurement, and step 5 of `pilot/wintest/PROMPT-shell.md`
re-checks it by eye.

**Finding for the orchestrator (no change made):** the old words also fit on
Windows. The "cut" was measured in the cloud's DejaVu Sans; the Windows check
skipped step 5. P116 stands as Jason ruled it. In the same measurement, three
*other* labels are cut on Windows, and each already shows its words in its
tooltip: "Looks Like Wrong Document" (183.7px), "Names Another Household"
(172.3px) and "Claimed by Two Requests" (161.7px). All other labels fit.

## 5. Documents this change makes true (same commit)

- `pilot/SPEC-shell.md` 11.5: the row for `opened-not-across`. The "Also open
  for Jason" paragraph notes that P116 answered it.
- `pilot/HANDOFF.md` "Open for Jason" item 5: answered by P116, built as P125.
- `pilot/wording-shell.tsv`: two rows, `reasons.opened-not-across` and
  `reason_tips.opened-not-across`.
- `pilot/wintest/PROMPT-shell.md` step 5 and `PROMPT-shell-local.md` item 4:
  what to check now (the tag whole at 1100px; the tooltip).
- `pilot/DECISIONS.md`: P125.
- The repository map, refreshed. The vocabulary report (`docs/vocab-coverage.md`)
  covers routing keywords, not screen words, so it does not change; it is
  rebuilt and checked anyway.
- The README and `docs/runbook.md` do not name the screen words, so they have
  no line to change.
