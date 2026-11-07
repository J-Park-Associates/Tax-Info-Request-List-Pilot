"""What content_check's test files share: ``item``, the one-row request a rule is tried against.

``tests/test_content_check.py`` wrote it for itself, and with P336
(SPEC-architecture-p4 P4.10) the matcher's and the rules' tests left it for
``tests/test_keywords.py``, each still building its rows with it. A test
file may not import another (``tests/test_suite_shape.py``), so what both
read sits here, in a module that is not a test file, and every user imports
it; the map draws the edge as "exercised by".

Nothing here is new behaviour: :func:`item` is test_content_check's own,
moved with its words. It is not a fixture, so a user imports it by name.
"""

from tracker.manifest import RequestItem


def item(**kwargs) -> RequestItem:
    return RequestItem(identifier="A01", document="Doc", **kwargs)
