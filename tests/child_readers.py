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


def a_page_read_that_never_finishes(path: Path, *, ocr: bool = True):
    """The real reading, with the reader blocked for ever on the first page
    it is handed - a page RapidOCR never finishes, which nothing inside the
    child can interrupt (decision 169, ruling 5): the document's stop ends
    the child."""
    from tracker import ocr as reader

    reader.read_page = lambda _image, **_kwargs: _never_finishes(path, "page")
    return content_check.extract(path, ocr=ocr)


def the_childs_process_id(path: Path, *, ocr: bool = True):
    """A reading whose words are the child's own process id: which child
    read it, for the claims about one child serving a pass."""
    return content_check.Extraction(str(os.getpid()))


def a_reader_that_dies_on_a_crash(path: Path, *, ocr: bool = True):
    """The real reading, except that a file named for a crash ends the
    process on the spot - no exception, no answer, as pdfium does."""
    if "crash" in path.name:
        os._exit(3)
    return content_check.extract(path, ocr=ocr)


def a_reader_that_starts_a_reader_of_its_own(path: Path, *, ocr: bool = True):
    """A reader that has started a process of its own and then never
    finishes. The helper's process id is left
    beside the document for the test to look for afterwards."""
    helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    reached(path, "helper").write_text(str(helper.pid), encoding="utf-8")
    _never_finishes(path, "waiting")


# ------------------------------------------- the graphics card, in a child ----
#
# Decision 169 (REVIEW-169, S-2): the card's claims run in a real child
# here, because the suite's own card is a fake that never crosses into one.
# The child has no pack (it is not the frozen app), so these stand in for
# what the reader says there. Each answers "<process id> <processor only>",
# so a test can tell which child read and whether it was told to keep off
# the card.


def _who_read() -> content_check.Extraction:
    from tracker import ocr as reader

    return content_check.Extraction(f"{os.getpid()} {reader._PROCESSOR_ONLY}")


def a_reader_that_tells_the_pass(path: Path, *, ocr: bool = True):
    """In a child that may use the card, a document named for a fault says
    the card failed on it, and one named for an unusable pack says the pack
    could not be used - as the reader's own notes do (``take_notes``)."""
    from tracker import ocr as reader

    if not reader._PROCESSOR_ONLY:
        if "fault" in path.name:
            reader._NOTES.append(("gpu-fault", path.name))
        elif "unusable" in path.name:
            reader._NOTES.append(("pack-unusable", "the self-test read nothing"))
    return _who_read()


def a_card_that_dies(path: Path, *, ocr: bool = True):
    """A native crash on the card - an access violation, not an exception:
    a child that may use the card ends on the spot; one kept on the
    processor reads."""
    from tracker import ocr as reader

    if not reader._PROCESSOR_ONLY:
        os._exit(3)
    return _who_read()


_SERVED = 0


def a_reader_that_dies_once_used(path: Path, *, ocr: bool = True):
    """A crash that only a child which has already served a document has:
    what the earlier documents left behind, never this file's own."""
    global _SERVED
    _SERVED += 1
    if _SERVED > 1:
        os._exit(3)
    return _who_read()


def a_reader_that_needs_too_much_memory(path: Path, *, ocr: bool = True):
    """A document named for its size wants more memory than the child's
    job allows (SPEC-169 section 9); any other reads."""
    if "big" in path.name:
        hold = bytearray(3 * 1024**3)
        return content_check.Extraction(str(len(hold)))
    return _who_read()


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


def where_temporary_files_go() -> tuple[str, ...]:
    """Every way a library finds the temp folder, as the child sees it, and
    a file actually made there - for the claim that a reading child keeps
    its temporary files in its own folder (decision 186)."""
    import tempfile

    handle, made = tempfile.mkstemp(prefix="reading-")
    os.close(handle)
    return (tempfile.gettempdir(), os.environ["TMP"], os.environ["TEMP"], os.environ["TMPDIR"], made,
            str(os.getpid()))
