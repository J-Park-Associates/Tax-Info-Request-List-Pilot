"""The suite's guards, registered as four plugins in the order that keeps the order the suite was built on.

``pytest_plugins`` below lists them; each holds one concern, and what each says of itself is in its own module
docstring:

- ``tests/plugin_isolation.py`` - the test's own folders: an app folder of its own for every test, so no test sees
  another's store or the checkout's settings (decision 185);
- ``tests/plugin_fakes.py`` - the stand-ins every test gets (the scheduler, the floor's computer, the firm-cache fill,
  the test cache, the reading child, the room measure) and the fakes a test turns them off with;
- ``tests/plugin_agreement.py`` - the view and the store held to the record after every test (decisions 89, 91, 101
  and 102);
- ``tests/plugin_session.py`` - the session's tripwire, the xdist hooks, ``--record-golden`` and the office-shaped copy.

**Why the list is in this order.** pytest sets a plugin's autouse fixtures up in the list's order and, inside one
plugin, by name (a conftest's, by name too); it tears them down in the reverse. The suite was built on the order that
name order gave one file (the app folder first, the agreement fixtures last), and the cut keeps it: each plugin holds
a run of autouse names that sit together in that list, so no hook and no fixture dependency is needed.
``tests/test_suite_shape.py``'s ``AUTOUSE_ORDER`` pins the order.

**Why the list is here and not in the root ``conftest.py``.** ``tests/conftest.py`` is loaded at start-up, because
``testpaths = ["tests"]`` or an argument under ``tests/`` always reaches it, so pytest reads the list there. Measured
with pytest 9.1.1: a plain run, a run of one file, a run from another directory and a run with ``-n 2`` all load it.
Nothing is re-exported from this file: a test names the plugin or builder that holds what it uses (P329).
"""

pytest_plugins = ["tests.plugin_isolation", "tests.plugin_fakes", "tests.plugin_agreement", "tests.plugin_session"]
