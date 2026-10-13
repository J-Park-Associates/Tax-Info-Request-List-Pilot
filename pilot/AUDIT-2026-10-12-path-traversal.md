# Path traversal audit, 2026-10-12

Run by Jason's instruction on `claude/admiring-goodall-vhomni`, head
`6f6410b` (main after pull request #54). The question asked: can anyone open
a file that is not theirs by changing a file name? The audit read every
place a name or a path from outside the program becomes a path on disk: the
Electron shell's one open door, every `tracker.api` command the page can
send, the stored locations a record carries, the names a client gives the
files in their drop folder, and the names a person types in the editor. It
changed no code. This note is the only thing it adds.

## 1. The answer

No path traversal was found. A changed file name cannot open, move, copy or
report a file outside the places the layout allows, and there is no web
server, no URL handler and no network path to try one against: the only way
a path is opened is the shell's `open-path` channel, and the only paths it
opens are the ones the Python API itself reported.

The system holds because every path from outside goes through one of five
doors, and each door rebuilds or judges the path instead of trusting it:

| Door | Where | What it does |
|---|---|---|
| The shell's open | `app/main.js` `openPath` / `openChecked` | Opens a path only when it is exactly (string equality) one the API reported in `state.paths`, `firm.paths` or as the error log; `lstat`s it, refuses a symbolic link or junction, and opens a folder only as a folder and a file only as a file. The renderer never builds a path of its own (`tests/test_shell_menu.py`, `tests/test_single_source.py`). |
| The engagement flag | `tracker/door.py` `return_dir`, `household_dir` | Every command's `--engagement <folder>` is resolved, placed under the resolved clients root by `layout.place_of`, required to be a return (or a household) by position, and then **rebuilt** from the root and its parsed names through `return_dir_for`, so a `..`, a link or a path in the client tree is refused with the layout's sentence (`tests/test_door.py`). |
| Typed names | `tracker/layout.py` `segment_problem`, `records.identifier_problem`, `records.short_title_problem`, `scaffold.sanitize_component` | A household, return, feed or related-household name must be one folder name: no `\ / : * ? " < > |` or control character, a letter or digit first (so `.` and `..` are refused), no trailing dot or space, no device name. A request identifier and short title are refused on the same characters, and `prepared_name_for` sanitises every part again before a working copy is named. |
| Stored locations | `tracker/store.py` admission `a_place`, `tracker/layout.py` `place_problem`, `tracker/filer.py` `_refuse_a_step_outside`, `_refuse_a_step_through_a_link` | A record's `prepared_location`, `pbc_location`, `container` and every step's ends are written relative to the return and read back only through `layout.locate`, which is lexical. Each is judged by `place_problem` when a line is admitted and again before every step: under the return, its household's `_Opened`, or a household's inbox or year folder; never absolute, never above the root, never another return, never the private tree's own files. A removal may touch only the return itself or its own year's `_Opened`. |
| Row handles from the page | `tracker/filer.py` `_find_row`, `_names_row`, `_hand_over` | The `original` a click sends is a key matched against the index (its location, its ledger key or its name); the path acted on is the row's recorded location, never the string the page sent. A hand-over's `target` is a dictionary lookup against the feed list the API itself built (`_fed_returns`), so a path not already on that list is refused by name. |

A client's own file names reach the program only as `Path.name` of what the
walk found in their inbox, which cannot carry a separator on the system that
runs the walk; a subfolder is recorded one name per part through
`layout.recorded_subfolder_part`, which the store's admission re-checks; and
`door.through_a_link` refuses anything reached through a link below the
clients root, so a junction planted in a drop folder moves nothing.

## 2. Observations (nothing to fix)

| # | Where | Observation | Done |
|---|---|---|---|
| O1 | `tracker/firm_cache.py`, `tracker/api.py` `firm-last` | The firm view's cache keeps each row's `paths` as the API built them and `firm-last` reports them to the shell again without re-judging them against the layout. The cache sits in the tracker's data folder on the firm's machine, never in a tree a client is shared, and the shell still `lstat`s each path and refuses a link. | Nothing to do. Noted as the one place a reported path comes from a file rather than a fresh walk. |
| O2 | `tracker/records.py` `name_problem` | A row's `original_name`, `prepared_location` and `pbc_location` deliberately accept any text, `..` and `/` included, because real files carry such names (decision 104). Safety rests entirely on `layout.place_problem` at admission and before each step, and the audit confirmed both are applied. | Nothing to do. Design, worded in the docstring. |
| O3 | `tracker/layout.py` `place_problem` | A step may **read** another household's inbox or year folder (a feed takes its original from another household; decision 129). So a line forged into a household's own record could name another household's original as a row's source. Writing that record needs the firm's private tree, which no client is ever shared, and every move still passes the link check. | Nothing to do. The rule is as decision 180 and 187 state it; `tests/test_layout.py` pins which places read and write. |

## 3. What is left

Nothing from this audit. The next session that changes `door.py`,
`layout.place_problem`, `layout.segment_problem`, the shell's `openPath` or
the store's admission should re-read section 1's table and keep each door's
test (`test_door`, `test_layout`, `test_store`, `test_shell_menu`,
`test_single_source`) passing.
