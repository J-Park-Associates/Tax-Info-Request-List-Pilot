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


def a_photo_open_that_never_finishes(path: Path, *, ocr: bool = True):
    """The open test and the reading, with the open test's Pillow open of a
    photo blocked for ever - where a native decoder stuck on a picture
    would hold it. Only the open test's call blocks (the frame that asks is
    ``validators._image_error``); the reading's own open of the picture
    goes through, so the claim is about the open test and nothing else."""
    from PIL import Image

    real_open = Image.open

    def open_(*args, **kwargs):
        if sys._getframe(1).f_code.co_name == "_image_error":
            _never_finishes(path, "photo-open")
        return real_open(*args, **kwargs)

    Image.open = open_
    return content_check.open_and_read(path, ocr=ocr)


def a_pdf_open_that_never_finishes(path: Path, *, ocr: bool = True):
    """The open test and the reading, with the open test's pypdf open of a
    PDF blocked for ever (decision 153). The bomb 150 proved the stop with
    is now refused by pypdf itself, so this is the open test's bound with
    no library in the claim: whatever the next pypdf refuses, a PDF whose
    open never returns is still ended at the stop. Only ``validators``'
    ``PdfReader`` - the open test's - blocks; the reading reads with
    pdfplumber and pdfium, never pypdf."""
    from tracker import validators

    validators.PdfReader = lambda *_args, **_kwargs: _never_finishes(path, "pdf-open")
    return content_check.open_and_read(path, ocr=ocr)


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


# ----------------------------------------- the opener of an email or a zip ----
#
# Decision 154: a container is opened in the same child, through
# ``tracker.containers._CHILD_OPENER``. The container rests in the client's
# folder for the year, where a mark beside it would be a stray the next
# pass sorts; so an opener's mark goes where the test says, through
# MARKS_VARIABLE, which the child inherits with the rest of the environment.

#: The environment variable naming the folder an opener's marks go in.
MARKS_VARIABLE = "TRACKER_TEST_MARKS"


def opener_reached(path: Path, stage: str) -> Path:
    """Where an opener stand-in marks that it reached ``stage`` opening ``path``."""
    return Path(os.environ[MARKS_VARIABLE]) / f"{Path(path).name}.{stage}"


def a_container_parser_that_never_finishes(path: Path):
    """The real opening, with the parser itself blocked for ever - where a
    loop in olefile, email or zipfile nobody has found yet would hold it.
    The mark carries the child's process id."""
    from tracker import containers

    def blocked(_walk, _data, _extension, *, depth):
        opener_reached(path, "parser").write_text(str(os.getpid()), encoding="utf-8")
        threading.Event().wait()

    containers._Walk.open = blocked
    return containers.open_file(path)


def a_container_parser_that_crashes(path: Path):
    """The real opening, except that the parser ends the process on the
    spot - no exception, no answer, as a crash in native code does."""
    from tracker import containers

    def crashes(_walk, _data, _extension, *, depth):
        opener_reached(path, "parser").write_text(str(os.getpid()), encoding="utf-8")
        os._exit(3)

    containers._Walk.open = crashes
    return containers.open_file(path)
