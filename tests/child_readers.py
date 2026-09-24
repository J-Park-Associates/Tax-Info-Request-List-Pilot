"""Stand-in readers for the reading's child process (decision 150).

The pass reads each document in a child process it can stop
(``tracker.content_check.extract_bounded``). A child imports the reader
afresh, so a patch made in the test's own process never reaches it; the
tests hand the child one of these instead, through
``content_check._CHILD_READER``, and each one makes its patch **inside**
the child before it reads. Each is a module-level function, because the
child is handed it by reference and imports this module to find it.

A stand-in that blocks leaves a mark beside the document first - the
document's own name plus the stage it reached - so a test can say where
the child was when the stop came, not only that it came. Nothing here is
a client's: every document is made by the test that reads it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from tracker import content_check


def reached(path: Path, stage: str) -> Path:
    """Where a stand-in marks that it reached ``stage`` reading ``path``."""
    return Path(f"{path}.{stage}")


def _never_finishes(path: Path, stage: str) -> None:
    reached(path, stage).write_text(str(os.getpid()), encoding="utf-8")
    threading.Event().wait()


def a_text_layer_that_never_finishes(path: Path, *, ocr: bool = True):
    """The real reading, with the PDF text layer blocked for ever."""
    content_check._extract_pdf = lambda _pdf: _never_finishes(path, "text-layer")
    return content_check.extract(path, ocr=ocr)


def a_render_that_never_finishes(path: Path, *, ocr: bool = True):
    """The real reading, with every page render blocked for ever."""
    import pypdfium2

    pypdfium2.PdfPage.render = lambda _page, **_kwargs: _never_finishes(path, "render")
    return content_check.extract(path, ocr=ocr)


def a_reader_that_dies_on_a_crash(path: Path, *, ocr: bool = True):
    """The real reading, except that a file named for a crash ends the
    process on the spot - no exception, no answer, as pdfium does."""
    if "crash" in path.name:
        os._exit(3)
    return content_check.extract(path, ocr=ocr)


def a_reader_that_starts_a_reader_of_its_own(path: Path, *, ocr: bool = True):
    """A reader that has started a process of its own, the way OCR starts
    Tesseract, and then never finishes. The helper's process id is left
    beside the document for the test to look for afterwards."""
    helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    reached(path, "helper").write_text(str(helper.pid), encoding="utf-8")
    _never_finishes(path, "waiting")


def where_temporary_files_go(path: Path, *, ocr: bool = True):
    """A reading whose words are the child's temporary folder."""
    return content_check.Extraction(tempfile.gettempdir())
