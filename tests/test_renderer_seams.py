"""The renderer's scripts, and the names each one takes from another.

The page is eight classic scripts that share one global scope: a top-level
``function``, ``let`` or ``const`` in one is a name every other can read, and
nothing says which. That is the seam a split of ``app.js`` cuts through
(SPEC-architecture D-2), and the guards that keep the page safe read the
scripts through :data:`tests.node_harness.RENDERER_SCRIPTS` - the list
``index.html`` loads - or a named part of it (R3.2), so a part that named a
script the page does not load would be a claim about nothing.
"""

from tests.node_harness import APP_SCRIPTS, PILOT_SCRIPTS, RENDERER_SCRIPTS, SHELL_SCRIPTS


def test_every_named_part_of_the_renderer_is_inside_the_scripts_the_page_loads():
    """R3.2: each list of scripts a claim covers is the page's own list or a
    part of it, and the app's scripts and the pilot's are the whole of it
    between them."""
    for part in (APP_SCRIPTS, PILOT_SCRIPTS, SHELL_SCRIPTS):
        assert part and set(part) <= set(RENDERER_SCRIPTS), part
        assert len(set(part)) == len(part), part
    assert set(SHELL_SCRIPTS) <= set(APP_SCRIPTS)
    assert sorted((*APP_SCRIPTS, *PILOT_SCRIPTS)) == sorted(RENDERER_SCRIPTS)
    assert "app.js" in APP_SCRIPTS and len(set(RENDERER_SCRIPTS)) == len(RENDERER_SCRIPTS)
