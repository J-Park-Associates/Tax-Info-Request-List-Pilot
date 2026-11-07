"""What content_check's test files share: ``item``, the one-row request a rule is tried against, and
``an_engagement``, an engagement the store holds.

``tests/test_content_check.py`` wrote both for itself. With P336
(SPEC-architecture-p4 P4.10) the matcher's and the rules' tests left it for
``tests/test_keywords.py``, each still building its rows with :func:`item`;
with P337 (P4.11) the verdict cache's own tests left it for
``tests/test_verdicts.py``, which builds its rows with :func:`item` and its
engagements with :func:`an_engagement`, as the cache tests that stay do. A
test file may not import another (``tests/test_suite_shape.py``), so what
more than one reads sits here, in a module that is not a test file, and
every user imports it; the map draws the edge as "exercised by".

Nothing here is new behaviour: both are test_content_check's own, moved
with their words. Neither is a fixture, so a user imports each by name.
"""

from tests.builders import make_engagement
from tracker.manifest import RequestItem


def item(**kwargs) -> RequestItem:
    return RequestItem(identifier="A01", document="Doc", **kwargs)


def an_engagement(tmp_path, *rules):
    """An engagement the store holds, whose request list is ``rules``."""
    return make_engagement(tmp_path / "Clients", list(rules), household="Smith Family",
                           scaffold=False)
