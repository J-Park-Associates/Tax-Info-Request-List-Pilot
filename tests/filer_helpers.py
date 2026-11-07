"""What the filer's family of test files shares, in one place.

``tests/test_filer.py`` wrote these for itself. With P331
(SPEC-architecture-p4 P4.4) the tests that drive only the code that moved to
``tracker/copies.py`` - a working copy's name, the room a return has, the
byte-proved copy, the rename-only move and the stranded-temp sweep - left it
for ``tests/test_copies.py``, each still reading the helpers it was written
against. A test file may not import another (``tests/test_suite_shape.py``),
so what both files read sits here, in a module that is not a test file, and
each names it; the map draws the edge as "exercised by". Each later move out
of the filer (SPEC-architecture-p4 section 4.1) adds here what its split
shares.

From ``tests/test_filer.py``, with their words: :func:`originals` (the
client's folder for a return's year), :class:`RequestFiles` and
:func:`prepared` (a request's files in Prepared, and the review folder),
:func:`review_dir`, :func:`_catalog_w2` (the 1040 catalog's A01, decision
144), and the fabricated client path a refused read names
(:data:`A_CLIENT_PATH`, :func:`_refused_with_a_client_path`) with
:func:`_logged_outside_the_debug_log`, which reads what was logged outside
the debug log (decision 190). Nothing here is new behaviour.

**No fixture lives here.** The one fixture both files take, ``engagement``,
is ``tests.builders``' ``engagement_fixture(ITEMS)``, named once in each
file; a fixture imported by name and then taken as a parameter trips ruff's
F811 (``tests/store_helpers.py``).
"""

from dataclasses import replace
from pathlib import Path

from tracker.layout import originals_of
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)


def originals(engagement):
    """The folder the client sees for this return's year: where an original
    rests once the pass has moved it out of the inbox (decision 125)."""
    return originals_of(engagement)


class RequestFiles:
    """What one request's folder was, flat (decision 168): its working copies
    sit in Prepared itself, and a file is the request's when its name begins
    with the identifier (``tracker.scaffold.assign_files``). So ``/ name``
    is where a file named for the request goes - ``Prepared/A01 - name``,
    or ``Prepared/<name>`` for a name that already begins with it - and
    ``iterdir()`` is the request's files. Dragging a copy "into C01" is
    renaming it under C01's name beside the others, which is the only way a
    person can move a copy between requests now."""

    def __init__(self, root: Path, identifier: str):
        self.root, self.identifier = root, identifier

    def __truediv__(self, name: str) -> Path:
        from tracker.scaffold import matches_identifier

        if matches_identifier(name, self.identifier):
            return self.root / name
        return self.root / f"{self.identifier} - {name}"

    def iterdir(self):
        from tracker.scaffold import assign_files

        return iter(assign_files(self.root, [self.identifier])[self.identifier])

    def mkdir(self, **_kwargs) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def prepared(engagement, folder_prefix):
    """The review folder itself, or one request's files as a
    :class:`RequestFiles` - there is no folder per request (decision 168)."""
    root = engagement / PREPARED_DIR_NAME
    if folder_prefix == REVIEW_DIR_NAME:
        return root / REVIEW_DIR_NAME
    return RequestFiles(root, folder_prefix.split(" ")[0])


def review_dir(engagement):
    return engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME


def _catalog_w2(**changes):
    """The 1040 catalog's A01, as a return created today would have it."""
    from tracker.templates import template_items

    return replace(template_items("1040", year=2025)[0], **changes)


#: A fabricated OS error's path, shaped like a client's inbox (decision 190).
A_CLIENT_PATH = "/Clients/Test Household/Drop files here/W2.pdf"


def _refused_with_a_client_path(*_args, **_kwargs):
    import errno

    raise PermissionError(errno.EACCES, "Permission denied", A_CLIENT_PATH)


def _logged_outside_the_debug_log(caplog) -> str:
    """Every line logged, but the debug log's, where the words are kept on
    purpose (tracker.errors.keep)."""
    from tracker.errors import DEBUG_LOGGER

    return "\n".join(record.getMessage() for record in caplog.records if record.name != DEBUG_LOGGER)
