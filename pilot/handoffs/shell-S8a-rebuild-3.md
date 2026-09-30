# Shell S8a rebuild 3 (ruling 15: firm Needs Review file names are live links)

Builder: Sonnet 5.5, on `claude/shell-s8a-links` from `cf0975c`. Jason's
ruling 15: a file name on the firm-wide Needs Review page reveals that working
copy in File Explorer - reveal only, name only, no path drawn (same principle
as rulings 8-13 and review 1 F1).

## The firm shape, for S5

```
firm = {
  "returns": [...unchanged...],
  "files": [ { "return", "year", "name", "handle", "code", "received", "suggestion",
               "open_key": "<kind> <row>[ #n]" | "" }, ... ],
  "totals": {...unchanged...},
  "paths":  { "<open_key>": "<absolute path of that working copy>", ... },   # NEW, top level
  "next_sort": ...
}
```

- `files[].open_key` is the key of the file's working copy in `firm.paths`, or
  `""` where the row has no copy (a program, a refused file with no
  `prepared_location`, a moved copy whose bytes are nowhere). Draw the name as
  plain text when it is `""`; otherwise the name is a link that calls the
  shell's `open(paths[open_key], "reveal")`.
- Parked rows use `_shown_copy_key` (so a parked read PDF's key is its
  `review_copy` key, kind `file`; the rest are `shown_copy`, kind `reveal`);
  moved-by-hand rows use `_moved_copy_key` (`moved_copy`, kind `reveal`). These
  are the builders `state` uses, so a file has exactly one key and one kind
  (review 2 finding 1): a path is never under two kinds in `firm.paths`.
  A key is `<word> <row>`; the word is looked up in `vocab.path_kinds`.
- A row's key is only its own return's (the preserved original's place in that
  record), so two returns can spell one key for different paths. The later one
  gets ` #2`, ` #3`, ... (deterministic, in the reply's file order; the same key
  for the same path stays one key). The kind is still the first word.
- `firm.paths` holds only paths for keys some `files[]` entry carries. Nothing
  else (no folder, no return path) is in it. The shell (`app/main.js` `learn()`)
  already reads a reply's top-level `paths`, so **no main.js change**: verified
  with the real main.js under node (a firm key reveals; an unreported path and a
  plain open of a reveal-only key are refused).

## Cost

Keys and paths come from the record's `prepared_location` / `moved_to` alone;
`locate()` joins strings. No stat, no client document read, no extra record
read. The 750-returns / 3 s firm budget was NOT re-measured here (no such
fixture in this sandbox); the added work is one string join per parked or
moved file.

## Tests (`tests/test_api.py`)

- parked: `open_key` equals the return's `shown_key` and `paths` names the real
  copy; `""` for a program (the existing firm-field test now asserts it).
- moved: key equals `state.moved[].open_key`, path is where the hand put it;
  `""` and empty `paths` once the bytes are gone.
- one key, one kind, one key per path across `firm.paths`.
- the real reply's `paths` through the real `app/main.js`: reveal of a firm key
  works; plain open and an unreported path are refused.
- two returns with the same key for different paths: `key`, `key #2`;
  the same path keeps its key.

Mutation check (scratch, 6 of 6 killed): drop the `paths` write; parked uses the
review key; moved uses the shown key; no suffix loop; no remap in `_cmd_firm`;
no top-level `paths`.

## Files

`tracker/api.py` (`_firm_row` third value, `_firm_key`, `_cmd_firm`),
`tests/test_api.py`, this file, and the regenerated map.
