# Shell S1 rebuild 2

Branch `claude/sharp-goldberg-jmfynk`.

**Finding (review 2, F1).** `shell-S1.md` still recorded the old
`draft.ready` (drafted this week and nothing holds it) in its notes and in
the first proposed decision row, and the new "Could not be read" word was
not in a proposed row.

**Fixed how.** Documentation only, no code. Both places now say: ready =
drafted this draft-week and not yet approved (an approval the letter was
edited after does not count); held = the holding rows plus the unsorted
inbox files; a hold does not unmake ready (SPEC 6.3). A new proposed row
says a return the firm view cannot read shows "Could not be read"
(`api.FIRM_UNREADABLE`), the detail goes to the error log, it counts as
needing a person, and the words need Jason's approval (not in
`wording-shell.tsv`).

The last commit is the one that adds this file (the sha is in the final
report).
