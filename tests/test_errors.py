"""Errors are classes (decision 190): a parser's message never reaches a
reason, the record, a page or the run log - only the debug log.

Every document here is made by the test that reads it, and the words a
parser is made to say are fabricated: a number in an SSN's shape and a name
nobody has. The claim each test makes is that those words reach
:func:`tracker.errors.keep` and nothing a person sees.
"""

from __future__ import annotations

import ast
import errno
import io
import json
import logging
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tracker import errors

#: Fabricated: the shape of what a W-2 says, never anybody's.
NUMBER = "123-45-6789"
NAME = "Jane Fabricated"
QUOTED = f"bad object near 'SSN {NUMBER} {NAME}'"

TRACKER = Path(__file__).resolve().parents[1] / "tracker"


def quotes_the_document(*_args, **_kwargs):
    """What a parser does on a broken file: raise, quoting the file."""
    raise ValueError(QUOTED)


def carries_client_words(text: str) -> bool:
    return NUMBER in text or NAME in text


@pytest.fixture
def kept():
    """What reaches the debug logger, for the length of one test."""
    said: list[str] = []

    class Keeper(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            said.append(record.getMessage())

    keeper = Keeper(level=logging.DEBUG)
    logger = logging.getLogger(errors.DEBUG_LOGGER)
    logger.addHandler(keeper)
    try:
        yield said
    finally:
        logger.removeHandler(keeper)


# ---------------------------------------------------------------- the class ----


def test_an_error_is_named_by_its_class_and_never_by_its_words():
    assert errors.error_class(ValueError(QUOTED)) == "ValueError"
    assert errors.error_class(zipfile.BadZipFile(QUOTED)) == "BadZipFile"


def test_an_os_error_is_named_with_its_errno_and_never_its_path():
    missing = FileNotFoundError(errno.ENOENT, "No such file", f"C:/{NAME}/W-2 {NUMBER}.pdf")
    assert errors.error_class(missing) == "FileNotFoundError (ENOENT)"
    assert errors.error_class(PermissionError(errno.EACCES, "denied")) == "PermissionError (EACCES)"


def test_an_os_error_without_an_errno_is_its_class_alone():
    assert errors.error_class(OSError(QUOTED)) == "OSError"


def test_an_errno_the_os_has_no_name_for_is_its_class_alone():
    """Decision 189's form, kept: an errno with no symbolic name adds
    nothing, since a bare number says no more than the class."""
    assert errors.error_class(OSError(987654, "odd")) == "OSError"


def test_a_store_or_record_the_disk_refused_is_said_with_its_code():
    """Decision 189's StoreUnavailable and RecordNotWritten carry a code -
    data, never prose - and are said by it, through the one rule here."""
    from tracker import ledger, store

    assert errors.error_class(ledger.RecordNotWritten("ENOSPC")) == "RecordNotWritten (ENOSPC)"
    assert errors.error_class(store.StoreUnavailable("SQLITE_BUSY")) == "StoreUnavailable (SQLITE_BUSY)"


def test_a_code_an_error_did_not_mark_as_said_is_never_said():
    """A third party's error with a ``code`` of its own - an HTTP status,
    an exit code, a parser's token - is its class alone: only a class that
    sets the marker has its code said."""
    class ParserError(Exception):
        code = QUOTED

    assert errors.error_class(ParserError(QUOTED)) == "ParserError"
    assert errors.error_class(SystemExit(QUOTED)) == "SystemExit"


# ----------------------------------------------------------------- the keep ----


def test_keep_reaches_no_console_and_no_other_logger_before_the_debug_log_has_a_place():
    """In a process of its own, because the suite's log capture attaches to
    every logger: the root logger given a console, as a hand-run CLI gives
    it (``basicConfig``), still hears nothing, and nor does stderr."""
    probe = (
        "import logging, sys\n"
        "logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)\n"
        "from tracker import errors\n"
        "try:\n"
        f"    raise ValueError({QUOTED!r})\n"
        "except ValueError as exc:\n"
        "    errors.keep('test', exc, name='W2.pdf')\n"
        f"errors.keep('test', {QUOTED!r})\n"
        "print('done')\n"
    )
    ran = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                         cwd=TRACKER.parent, check=True)
    assert ran.stdout.strip() == "done"
    assert not carries_client_words(ran.stdout + ran.stderr), ran.stderr


def test_keep_hands_the_whole_message_and_its_trace_to_the_debug_logger(kept):
    try:
        quotes_the_document()
    except ValueError as exc:
        errors.keep("validators: pdf open test", exc, name="W2.pdf")
    [said] = kept
    assert said.startswith("validators: pdf open test (W2.pdf): Traceback")
    assert QUOTED in said and "quotes_the_document" in said


def test_keep_takes_the_words_a_reading_child_sent_back(kept):
    errors.keep("content_check: the reader failed", f"{QUOTED}\nTraceback ...")
    assert kept == [f"content_check: the reader failed: {QUOTED}\nTraceback ..."]


def test_the_cli_names_a_built_in_errors_class_and_says_where_its_words_go():
    def cli(*argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "tracker.errors", *argv], capture_output=True,
                              text=True, cwd=TRACKER.parent, check=False)

    assert cli("class", "FileNotFoundError", str(errno.ENOENT)).stdout.strip() == "FileNotFoundError (ENOENT)"
    assert cli("class", "ValueError").stdout.strip() == "ValueError"
    assert cli("where").stdout.strip() == errors.WHERE_KEPT
    refused = cli("class", "NotAnError")
    assert refused.returncode == 1 and "NotAnError" in refused.stderr


# ------------------------------------------- the guard: spelled once, here ----

#: The places that still say an exception's words beside its class, each
#: with why they may: none of them is ever handed a client's document.
SAID_WHOLE_ON_PURPOSE = {
    ("ocr.py", "_build_engine"): "an import failing on this machine: the machine's words",
    ("ocr.py", "_engine"): "the graphics card's engine failing to build: the machine's words",
    ("registry.py", "household_from"): "the household's own record, which the firm writes",
    ("registry.py", "engagement_from"): "the return's own record, which the firm writes",
    ("runner.py", "_feeds_of"): "the household's own record (SPEC-190 R2: stays)",
    ("runner.py", "_parked_files"): "the return's own record could not be read (SPEC-190 R2: stays)",
    ("registry.py", "_children"): "listing a folder of the clients root: the OS's words, never a document's",
}


def _named_class_of(node: ast.AST) -> str | None:
    """``x.__class__.__name__`` or ``type(x).__name__``: ``x``, dumped."""
    if not (isinstance(node, ast.Attribute) and node.attr == "__name__"):
        return None
    inner = node.value
    if isinstance(inner, ast.Attribute) and inner.attr == "__class__":
        return ast.dump(inner.value)
    if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "type"
            and len(inner.args) == 1):
        return ast.dump(inner.args[0])
    return None


def _class_beside_its_words(parts: list[ast.AST], caught: set[str]) -> bool:
    """Whether ``parts`` - the values one string is made of - hold a caught
    exception's class name and the exception itself."""
    exceptions = {ast.dump(ast.Name(id=name, ctx=ast.Load())) for name in caught}
    classes = {named for part in parts if (named := _named_class_of(part))} & exceptions
    return bool(classes & {ast.dump(part) for part in parts})


def _is_error_class(func: ast.AST) -> bool:
    return (isinstance(func, ast.Name) and func.id == "error_class") or (
        isinstance(func, ast.Attribute) and func.attr == "error_class")


#: An exception's attributes that are not its message.
_NOT_WORDS = {"__name__", "errno", "error"}


def _words_reach(node: ast.AST, caught: set[str]) -> bool:
    """Whether a name bound by an ``except ... as`` reaches ``node``'s
    value other than through :func:`tracker.errors.error_class`."""
    if isinstance(node, ast.Call) and _is_error_class(node.func):
        return False
    if isinstance(node, ast.Attribute) and node.attr in _NOT_WORDS:
        return False
    if isinstance(node, ast.Name):
        return node.id in caught
    return any(_words_reach(child, caught) for child in ast.iter_child_nodes(node))


def _enclosing(tree: ast.AST) -> dict[int, str]:
    """Each line's innermost function, by name."""
    at: dict[int, str] = {}
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for function in sorted(functions, key=lambda n: n.end_lineno - n.lineno, reverse=True):
        for line in range(function.lineno, function.end_lineno + 1):
            at[line] = function.name
    return at


def _findings(source: str, file: str) -> list[str]:
    tree = ast.parse(source)
    caught = {h.name for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler) and h.name}
    function = _enclosing(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        parts: list[ast.AST] = []
        if isinstance(node, ast.JoinedStr):
            parts = [v.value for v in node.values if isinstance(v, ast.FormattedValue)]
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            parts = list(node.right.elts) if isinstance(node.right, ast.Tuple) else [node.right]
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            parts = [*node.args, *(kw.value for kw in node.keywords)]
            if any(kw.arg == "error" and _words_reach(kw.value, caught) for kw in node.keywords):
                found.append((node.lineno, "an exception's words handed to a reason's {error}"))
        if parts and _class_beside_its_words(parts, caught):
            found.append((node.lineno, "a class name beside the exception's own words"))
    return [f"{file}:{line} ({function.get(line, '<module>')}): {what}"
            for line, what in sorted(set(found))
            if (file, function.get(line, "")) not in SAID_WHOLE_ON_PURPOSE]


def test_the_error_class_list_is_spelled_once():
    """No module under tracker/ puts an exception's words beside its class,
    or hands its words to a reason: the one way an error is named is
    :func:`tracker.errors.error_class`."""
    found = [finding for path in sorted(TRACKER.glob("*.py")) if path.name != "errors.py"
             for finding in _findings(path.read_text(encoding="utf-8"), path.name)]
    assert found == [], "\n".join(found)


#: The one place the class an error is said as is defined.
THE_ONE_DEFINITION = ("errors.py", "error_class")

#: The places that read an errno's name for something other than saying an
#: error, each with why.
ERRNO_NAMED_ON_PURPOSE = {
    ("ledger.py", "_not_written"): "RecordNotWritten's code, which error_class then says",
}

def _is_an_exception(annotation: ast.AST | None) -> bool:
    name = (annotation.id if isinstance(annotation, ast.Name)
            else annotation.attr if isinstance(annotation, ast.Attribute)
            else annotation.value if isinstance(annotation, ast.Constant) else "")
    return isinstance(name, str) and (name.endswith(("Error", "Exception")) or name == "BaseException")


def _second_definitions(source: str, file: str) -> list[str]:
    """A function, other than :func:`tracker.errors.error_class`, that says
    how an error is named: one called ``error_class`` or ``said_as_class``,
    one that names the class of an exception it was handed, or one that
    reads an errno's symbolic name."""
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "said_as_class" and isinstance(node.ctx, ast.Store):
            found.append(f"{file}:{node.lineno}: said_as_class assigned")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        where = (file, node.name)
        if where == THE_ONE_DEFINITION:
            continue
        if node.name in {"error_class", "said_as_class"}:
            found.append(f"{file}:{node.lineno}: {node.name} defined again")
            continue
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        exceptions = {ast.dump(ast.Name(id=a.arg, ctx=ast.Load())) for a in arguments
                      if _is_an_exception(a.annotation)}
        names_a_class = any(_named_class_of(inner) in exceptions for inner in ast.walk(node))
        reads_errno = any(isinstance(inner, ast.Attribute) and inner.attr == "errorcode"
                          for inner in ast.walk(node))
        if names_a_class:
            found.append(f"{file}:{node.lineno} ({node.name}): names an exception's class itself")
        if reads_errno and where not in ERRNO_NAMED_ON_PURPOSE:
            found.append(f"{file}:{node.lineno} ({node.name}): reads an errno's name itself")
    return found


def test_the_class_an_error_is_said_as_is_defined_once():
    """Security principle 2 has one rule, :func:`tracker.errors.error_class`
    (decisions 189 and 190): 189's ``content_check.said_as_class`` moved
    there, and a second definition anywhere under tracker/ fails here."""
    found = [finding for path in sorted(TRACKER.glob("*.py"))
             for finding in _second_definitions(path.read_text(encoding="utf-8"), path.name)]
    assert found == [], "\n".join(found)
    from tracker import content_check, runner

    assert not hasattr(content_check, "said_as_class") and not hasattr(runner, "said_as_class")


@pytest.mark.parametrize("shape", [
    # decision 189's own, as it stood in content_check before 190 moved it
    "def said_as_class(exc: BaseException) -> str:\n    return exc.__class__.__name__\n",
    "def name_of(exc: Exception) -> str:\n    name = type(exc).__name__\n    return name\n",
    "def name_of(problem: OSError) -> str:\n    return errno.errorcode[problem.errno]\n",
    "said_as_class = error_class\n",
])
def test_the_guard_finds_a_second_definition(shape):
    assert _second_definitions(shape, "probe.py"), shape


@pytest.mark.parametrize("shape", [
    'f"{exc.__class__.__name__}: {exc}"',
    'f"{type(exc).__name__}: {exc!s}"',
    '"%s: %s" % (type(exc).__name__, exc)',
    '"{}: {}".format(exc.__class__.__name__, exc)',
    'reasons.UNREADABLE_PDF.format(error=str(exc))',
    'reasons.UNREADABLE_PDF.format(error=f"({exc})")',
    'reasons.UNREADABLE_PDF.format(error=exc.args[0])',
])
def test_the_guard_sees_every_shape_of_an_exceptions_words(shape):
    source = f"def f():\n    try:\n        pass\n    except Exception as exc:\n        return {shape}\n"
    assert _findings(source, "probe.py"), shape


@pytest.mark.parametrize("shape", [
    "reasons.UNREADABLE_PDF.format(error=errors.error_class(exc))",
    "reasons.VANISHED.format(error=error_class(exc))",
    "reasons.OCR_FAILED.format(error=exc.error)",
    "reasons.CONTAINER_LIMIT.format(error=LIMIT_TOTAL)",
])
def test_the_guard_passes_a_class_and_a_firm_constant(shape):
    source = f"def f():\n    try:\n        pass\n    except Exception as exc:\n        return {shape}\n"
    assert _findings(source, "probe.py") == []


# ------------- no byte of a damaged document reaches a reason, module by module ----


def test_no_byte_of_a_damaged_pdf_reaches_its_reason(tmp_path, monkeypatch, kept):
    from tracker import validators

    monkeypatch.setattr(validators, "PdfReader", quotes_the_document)
    broken = tmp_path / "W2.pdf"
    broken.write_bytes(b"%PDF-1.4\nnot really\n")
    reason = validators._pdf_error_uncached(broken)
    assert reason == validators.reasons.UNREADABLE_PDF.format(error="ValueError")
    assert any(QUOTED in said for said in kept)


def test_no_byte_of_a_damaged_photo_reaches_its_reason(tmp_path, monkeypatch, kept):
    from PIL import Image

    from tracker import validators

    monkeypatch.setattr(Image, "open", quotes_the_document)
    broken = tmp_path / "W2.jpg"
    broken.write_bytes(b"\xff\xd8\xff not really")
    reason = validators._image_error(broken)
    assert reason == validators.reasons.UNREADABLE_IMAGE.format(error="ValueError")
    assert any(QUOTED in said for said in kept)


def test_no_byte_of_a_failed_extraction_reaches_the_reading(tmp_path, monkeypatch, kept):
    from tracker import content_check

    monkeypatch.setattr(content_check, "extract_text", quotes_the_document)
    broken = tmp_path / "W2.pdf"
    broken.write_bytes(b"%PDF-1.4\nnot really\n")
    reading = content_check._extract(broken, ocr=False)
    assert reading.reason == content_check.reasons.EXTRACTION_FAILED.format(error="ValueError")
    assert reading.error == "ValueError"
    assert any(QUOTED in said for said in kept)


def test_a_workbook_packed_an_unknown_way_is_said_in_the_firms_own_sentence(tmp_path):
    """``UnknownPacking``'s message is the firm's :data:`UNKNOWN_PACKING`,
    never the file's, so it is said whole (decision 189, kept by 190's
    :func:`tracker.errors.said`)."""
    from tracker import content_check

    packed = tmp_path / "packed.xlsx"
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>", compress_type=zipfile.ZIP_BZIP2)
    reading = content_check._extract(packed, ocr=False)
    assert issubclass(content_check.UnknownPacking, ValueError)
    assert reading.reason == content_check.reasons.EXTRACTION_FAILED.format(
        error=content_check.UNKNOWN_PACKING)


def test_no_byte_of_a_failed_ocr_reaches_the_reading(tmp_path, monkeypatch, kept):
    from PIL import Image

    from tracker import content_check, ocr

    photo = tmp_path / "W2.png"
    Image.new("RGB", (40, 20), "white").save(photo)
    monkeypatch.setattr(ocr, "read_page", quotes_the_document)
    reading = content_check.extract_by_ocr(photo)
    assert reading.reason == content_check.reasons.OCR_FAILED.format(error="ValueError")
    assert reading.error == "ValueError" and reading.transient
    assert any(QUOTED in said for said in kept)


def test_no_byte_of_a_damaged_container_reaches_its_reason(monkeypatch):
    from tracker import containers

    real = zipfile.ZipFile

    def zip_that_quotes(file, *args, **kwargs):
        if isinstance(file, io.BytesIO):
            raise zipfile.BadZipFile(QUOTED)
        return real(file, *args, **kwargs)

    monkeypatch.setattr(containers.zipfile, "ZipFile", zip_that_quotes)
    monkeypatch.setattr(containers, "message_from_bytes", quotes_the_document)
    for extension, error in (("zip", "BadZipFile"), ("eml", "ValueError")):
        with pytest.raises(containers.NotOpened) as refused:
            containers.open_container(b"PK\x03\x04 not really", extension)
        assert str(refused.value) == containers.reasons.CONTAINER_DAMAGED.format(error=error)


def test_no_byte_of_what_a_reading_child_raised_crosses_into_the_reading(tmp_path, monkeypatch, kept):
    from tests import child_readers
    from tracker import content_check

    monkeypatch.setattr(content_check, "READ_IN_A_CHILD", True)
    broken = tmp_path / "W2.pdf"
    broken.write_bytes(b"%PDF-1.4\nnot really\n")
    answer, failed = content_check.in_a_child(broken, child_readers.a_reader_whose_error_quotes_the_document)
    assert answer is None and failed.error == "ValueError"
    assert not carries_client_words(failed.reason)
    assert any(child_readers.QUOTED_BY_THE_PARSER in said and "Traceback" in said for said in kept)


def test_the_app_names_an_unexpected_error_by_its_class_and_keeps_a_firm_errors_words(
        monkeypatch, capsys, kept):
    from tracker import api
    from tracker.manifest import ManifestError

    monkeypatch.setitem(api.COMMANDS, "state", quotes_the_document)
    assert api.main(["state"]) == 1
    said = json.loads(capsys.readouterr().out)["error"]
    assert said == api.UNEXPECTED_ERROR.format(error="ValueError")
    assert any(QUOTED in one for one in kept)

    def the_firm_says(*_args):
        raise ManifestError("A01: the firm's own words about its own list")

    monkeypatch.setitem(api.COMMANDS, "state", the_firm_says)
    assert api.main(["state"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "A01: the firm's own words about its own list"
