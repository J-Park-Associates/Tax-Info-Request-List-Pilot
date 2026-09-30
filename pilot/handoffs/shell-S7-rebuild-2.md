# Shell S7 - rebuild 2 (after review 2)

Documentation fix for review 2's F1, plus the one test tweak from its notes.
No other code changed.

## F1

In `pilot/handoffs/shell-S7.md`:
- "Left for S6": the hover delay is now stated as 300 ms (ruling 7,
  replacing SPEC 8.5's 500). The proposed SPEC 8.5 edit also says a tip hidden
  because its control scrolled out of view does not come back when the control
  scrolls back; it returns only on the next hover or focus.
- "For Jason": the scrolled-away tip is now HIDDEN (Floating UI `hide()`),
  not clipped, and stays hidden until shown again. The hover-delay line says
  300 ms.
- The proposed decision row now mentions `hide()`.

## Test tweak

`tests/test_shell.py`: the script-source regex in
`test_the_loading_order_is_the_specs_and_the_csp_is_unchanged` is now
case-insensitive (`re.I`). Proof on a scratch copy of the tree outside the
repository: adding `<SCRIPT SRC="https://cdn.example.com/x.js"></SCRIPT>` to
`index.html` makes that test fail.

## Gate

`test_shell`: 37 passed on Python 3.11 and on 3.13 (one process each, in
turn). `ruff check .` is clean. Then the repository map was updated and
`check` and `test_repo_map` run.
