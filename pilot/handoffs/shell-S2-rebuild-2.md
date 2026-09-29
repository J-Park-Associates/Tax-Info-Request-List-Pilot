# Shell S2 rebuild 2

Branch `claude/shell-s2-menus`, built from `91bc194` (local branch `rebuild-s2-2`).

## Finding 2 (review 2)

The map's `app/preload.js` role said "Nothing else crosses" but left out
`logError` and `onProgress`.

## Fixed how

`docs/repo-map.curated.json`, `app/preload.js` role: added "tracker.logError(text)
on 'log-error' (kept only in the error log the API named) and
tracker.onProgress(listener), which hears 'tracker-progress'" before the
onAfterInstallDone and menu entries, using the review's wording. Then
`tools/repo_map.py update`. No code changed. Finding 1 was verified to still hold
("one of three main-to-renderer channels, with tracker-progress and MENU_CHANNEL").

## Checks

`repo_map.py check` reports the map current. `tests/test_repo_map.py`: 80 passed.

Last commit: see `git log -1` on the branch (the commit that adds this file).
