# Form validation and data inputs audit, 2026-10-12

Run by Jason's instruction on `claude/admiring-goodall-vhomni`, after the path
traversal audit of the same day (`AUDIT-2026-10-12-path-traversal.md`). The
question asked: do the app's forms validate only in the page, and what happens
to empty, extremely long, and special-character input? The audit was done
black-box against the real API: a scratch clients root under a private
settings folder and data home, then every form's payload sent to
`python -m tracker.api <command>` the way `app/main.js` sends it, with empty
values, 10,000-character values, `<script>alert(1)</script>`, `' OR 1=1 --`,
emoji with a zero-width joiner, and a right-to-left override. Every reply was
read, and the files each accepted value reached (the record, the Status
Report, the practice's status page, the letter's HTML and text, the client's
`_README.txt`) were opened and searched. It changed no code.

## 1. The answer

**There is no page-only validation to bypass.** The renderer holds one
HTML limit (the signature box's `maxlength="200"`, `app/renderer/pilot.js`)
and refuses nothing else itself; every rule lives in the Python API and the
store, so a payload the page would never send meets the same refusal as one it
would. The page draws every value with DOM text nodes and has no `innerHTML`;
the two HTML sinks (the pages through `page.esc`, the letter's clipboard HTML
through `page.esc` in `reminder.render_html`) escape every value, and the
status page and the letter were confirmed to carry `&lt;script&gt;`, never the
tag. The store is parameterised SQLite: `' OR 1=1 --` is an acceptable request
identifier, is stored verbatim and reads back unchanged. A `javascript:` link
is refused wherever a link is typed. Folder names refuse the zero-width joiner
and the right-to-left override by code point, with the character named.

**Empty submissions** are refused with one plain sentence each: "may not be
empty", "The editor sent no rows", "Tick at Least One Request", "Add at Least
One Person", "Pick the request to rename and type its new identifier", "Pick
the file and the request it belongs to". An empty `edit-household` is a
no-change save, which is right.

**Extremely long input** is bounded almost everywhere: one-line text at
1,000 characters (`records.TEXT_MAX`), long text at 20,000
(`records.LONG_TEXT_MAX`), folder names at 80 (`layout.NAME_MAX_CHARS`), a
short title at 20, a signature at 200, a count at 1 to 9,999, a year at 1900
to 2099. The exceptions are the findings below.

## 2. Findings

Severity is for the firm's own single-user desktop app, where every typed
value is the firm's; none is reachable by a client.

| # | Where | Finding | Severity | Suggested fix |
|---|---|---|---|---|
| V1 | `tracker/api.py` `_cmd_create` (the `members=` line) | `members` sent as a string instead of a list is iterated character by character: `"Jane"` becomes the four members `J`, `a`, `n`, `e`, saved without complaint. `_cmd_edit_household` treats the same string as lines (`splitlines()`), so the two forms disagree. | Low (the page sends a list) | Give create the same `splitlines()` treatment or refuse a non-list with `MEMBERS` must be a list; one rule for both, in one helper. |
| V2 | `tracker/api.py` `_people_from_spec`, `tracker/records.py` `person_from_json`, `tracker/store.py` admission | A person's name has no bound: a 10,000-character taxpayer name was saved to the record and read back. Every other name is held to `records.text_problem`. A person's name is what the name check searches every page of every document for, so an unbounded one costs every pass. | Medium | Hold `name` to `records.text_problem` (one line, at most 1,000 characters) in `_people_from_spec` and in the store's `people_from_json` admission, with the same sentence. |
| V3 | `tracker/settings.py` `set_firm`, `set_firm_phone` (`_set_text`) | The firm's name and phone are stripped and otherwise stored as typed: a 10,000-character name, a newline, a NUL and an ANSI escape were all accepted. Both go into every letter's text and signature. | Low | Hold both to `records.text_problem` (one line, at most 1,000 characters, no control character) before writing, and say so. |
| V4 | `tracker/records.py` `identifier_problem`, `short_title_problem` | A request identifier and a short title refuse Windows' illegal characters but not an invisible one: a short title of `W-2` plus a right-to-left override, and one with a zero-width joiner, were both saved. Both begin or sit inside every working copy's file name, and a right-to-left override in a file name is the classic trick that makes Explorer show `W-2 fdp.exe` as `W-2 exe.pdf`. Folder names already refuse these through `layout.is_invisible`. | Medium | Ask `layout.is_invisible` of each character in both, with the folder-name sentence ("may not contain an invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)"). |
| V5 | `tracker/records.py` `identifier_problem`; `tracker/layout.py` `refuse_a_path_past_the_limit` | An identifier has no length rule of its own, so a 200-character one is refused only by the path-length check, whose sentence says "shorten the household or the return name", neither of which is the problem. | Low (message) | Cap the identifier (80 characters, as a folder name is) with its own sentence, checked before the path room. |
| V6 | `tracker/store.py` `record` (the `raise StoreError(f"{exc}; nothing was written")` line) | A typed value that breaks a store rule is refused with the wording for a corrupt journal on disk: "J Park & Associates/Smith: line 2 of the record is malformed (household_changed carries details whose 'members' must be a list of text); the journal is not applied past it; nothing was written". The record was not touched (confirmed: two lines before and after, none holding the value), but a person reads that their record is broken. Hit by a 10,000-character member, a 10,000-character link, a 25,000-character firm name. | Medium (message) | When admission refuses an event that has not been written, word it as a refusal of the change: "This change carries 'members' that must be a list of text; nothing was written", keeping the line-number form for a line read from disk. |
| V7 | `tracker/layout.py` `NAME_REFUSED`; `tracker/door.py` `NOT_UNDER_ROOT`; `layout.NOT_A_RETURN` | A refusal echoes the whole typed value: a 10,000-character household name, return name or engagement path comes back as a 10,000-character sentence in the page's notice. | Low (message) | Cut the echoed value to about 80 characters with an ellipsis; the reason already names the limit and the length. |
| V8 | `tracker/api.py` `_read_spec` | Stdin that is not JSON at all surfaces as "The app hit an error it did not expect (JSONDecodeError)" and writes the error log; a JSON list or `null` gets the intended "The app sent something that is not a JSON object". The shell always sends `JSON.stringify`, so only a hand-run command can hit it. | Low | Catch `json.JSONDecodeError` beside the shape check and give it the same sentence. |
| V9 | `app/renderer/pilot.js` `maxlength="200"` vs `tracker/api.py` `SIGNED_BY_LONGEST` | The one page-side limit is not pinned to the API's constant by `tests/test_single_source.py`; the API refuses 201 characters today, so this is drift risk only. | Low | Add the pin. |

Also seen, by design and left alone: a request may accept `exe, bat`
extensions (the review-copy path marks such files as from the internet,
decision 190); the client name `<script>alert(1)</script>` becomes the folder
`1040 - -script-alert(1)--script-` through `scaffold.sanitize_component`, a
silent change the dialog should probably show; the client's `_README.txt`
carries the household's contact text as typed, which is the firm's own
wording.

## 3. What the error messages say

Good: "'' is not a household name: may not be empty"; "Row 1: Short name may
have at most 20 characters, got 25"; "Row 1: Expected Count must be a whole
number from 1 to 9999"; "Due Date must be YYYY-MM-DD, got 'yesterday'"; "The
start time '25:00' is not allowed; write it as HH:MM, two digits each, from
00:00 to 23:59"; "The link 'javascript:alert(1)' is not a web address; a link
must start with http:// or https://"; "the list changed since you opened it;
reopen and make your change again". Each names the field, the rule and the
value.

Confusing: V5's "shorten the household or the return name" for a long
identifier; V6's "line 2 of the record is malformed ... the journal is not
applied past it" for a typing mistake; V7's 10,000-character echo;
`pilot-record`'s refusal, which is written for a developer ("pilot-record
takes {} to read, or "terms" as ...") though the page never sends anything
else.

## 4. What is left

Nothing was changed. V2, V4 and V6 are worth a SPEC together: one rule for a
person's name, invisible characters refused wherever a value becomes part of
a file name, and a refusal of a change worded as one. V1, V3, V5, V7, V8 and
V9 are one-line fixes that can ride the same build. Each has a black-box
reproduction above; the harness was a scratch script and is not kept.
