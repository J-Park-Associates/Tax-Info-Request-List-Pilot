"""The firm's own documents as a corpus: the harness the backtest and the reader bench share.

Two tools measure the documents a person has already sorted by hand - ``tools/backtest.py`` scores where the
router files them, ``tools/reader_bench.py`` times the reading - and one test, ``tests/test_real_corpus.py``,
routes them on every machine that has them. All three must agree on what the expectations file means (its
columns, the blank that means "parks", the year that must be there) and on how a catalog is built for a document
that is redacted and small. So there is exactly one reader of that file and one builder of those catalogs
(decisions 70 and 185), and it is this module. It was two things before: the reader sat in a test file, and the
tools imported that test file for it, so a tool depended on a suite's collection and the report generator's
inputs named a test. A tool importing a test file is the direction nothing may point; the shared code is a tool's
module, and the tests import it from here.

What is here, and why it is not in either tool:

- the **reader** (:func:`read_expectations`, :func:`real_corpus`) and the **catalog builder**
  (:func:`catalog_rows`), which the tools reach through :func:`harness`;
- the **pass's plumbing** both tools use to read a firm document without leaking it: :func:`document_path`
  (a row's document, checked to be inside the corpus), :func:`linked_under_a_neutral_name` (its bytes under
  ``NEUTRAL_STEM``, so the router never sees the firm's file name), :func:`temp_pointed_at` (what a library
  writes through the temp folder goes with the run), :func:`unknown_catalog` (a bad catalog column, said by its
  row), :func:`outside_the_repository` and :func:`corpus_folder`;
- the four names those helpers read - ``BacktestError``, ``NEUTRAL_STEM``, ``CATALOGS`` and ``OUT_FLAG`` - which
  were the backtest's. They moved with the helpers because the backtest imports this module: a helper that read
  them back from the backtest would make a cycle between two tools. The backtest imports ``BacktestError``,
  ``CATALOGS`` and ``OUT_FLAG`` from here as its own, so the class the reader bench and the backtest raise and
  catch is one class.

**Nothing here reads a corpus on its own.** :func:`real_corpus` reads only what ``ENV_REAL_CORPUS`` names, through
:func:`tracker.settings.real_corpus_dir` (which refuses a folder inside the app, decision 185), as it did in the
test file: this module opens no second door onto the variable, and the suite's conftest still hides the variable
from every test after collection. Its errors name a row by number and the column that is wrong, never a
document's name or the file's path, which are a client's.

It has no command line and no ``sys.path`` insert: a tool or a test that imports it as ``tools.corpus`` has put the
repository on the path first.
"""

from __future__ import annotations

import csv
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from tracker.manifest import RequestItem, validated
from tracker.ocr import SCRATCH_ENV
from tracker.settings import (
    COLUMN_CATALOG,
    COLUMN_EXPECTED,
    COLUMN_FILE,
    COLUMN_YEAR,
    EXPECTATIONS_COLUMNS,
    EXPECTATIONS_FILENAME,
    inside_the_app,
    real_corpus_dir,
)
from tracker.templates import FORM_TYPES, template_items

#: Every catalog a row of the expectations file may name.
CATALOGS = tuple(entry["id"] for entry in FORM_TYPES)

#: The name every document is routed under, so the client's own naming
#: never reaches the router with the document. Nothing is filed on a name
#: any more (decision 92), but a name still leaves evidence for the person
#: reviewing, and evidence quoting a client's file name is not what this
#: tool should be scoring - or writing down.
NEUTRAL_STEM = "document"
#: The flag that names where a report is written. Its refusal quotes it
#: (:func:`outside_the_repository`), and the backtest's commands add it.
OUT_FLAG = "--out"


class BacktestError(Exception):
    """The backtest could not be run, read or scored."""


#: One row of the expectations file: (file, catalog, year, expected).
#: ``expected`` is None where the column is blank - the document must park.
#: Where it carries ``EXPECTED_SEP`` it names every request the document
#: must file under and no others (``A01+A02``, decision 94): one document
#: can carry two forms, and a harness that could only say one identifier
#: would have had to score the second filing as a miss.
Expectation = tuple[str, str, int, str | None]


def read_expectations(path: Path) -> list[Expectation]:
    """One expectations file, as rows, in the order it lists them.

    Named by its path rather than by its folder because the corpus is not
    the only caller: ``tools/backtest.py`` scores a folder against an
    expectations file a person keeps wherever they keep it, and the
    contract - the columns, the blank that means "parks", the year that
    must be there - has to have exactly one reader.

    Its errors name the row by number, counted from one as the rows' ids
    count them, and the column that is wrong - never a document's name nor
    the file's path, which are a client's and would reach the console of
    every caller (decision 185).
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in EXPECTATIONS_COLUMNS if c not in (reader.fieldnames or ())]
        if missing:
            raise ValueError(f"{EXPECTATIONS_FILENAME} is missing the column(s): {', '.join(missing)}")
        rows: list[Expectation] = []
        for line in reader:
            name = (line[COLUMN_FILE] or "").strip()
            if not name:
                continue                       # a blank line, or a spacer between engagements
            number = len(rows) + 1             # the row's id: row-N
            where = (line[COLUMN_EXPECTED] or "").strip()
            year = (line[COLUMN_YEAR] or "").strip()
            if not year.isdigit():
                raise ValueError(f"{EXPECTATIONS_FILENAME} row {number}: no engagement year "
                                 f"in the column {COLUMN_YEAR}")
            rows.append((name, (line[COLUMN_CATALOG] or "").strip(), int(year), where or None))
    return rows


def real_corpus() -> tuple[Path | None, list[Expectation]]:
    """The corpus folder and its expectations, or (None, []) when there is none.

    One answer for both halves of the skip: the variable names nothing,
    or what it names holds no expectations file.
    """
    folder = real_corpus_dir()
    if folder is None or not (folder / EXPECTATIONS_FILENAME).is_file():
        return None, []
    return folder, read_expectations(folder / EXPECTATIONS_FILENAME)


def catalog_rows(workspace: Path, form: str, year: int, built: dict) -> list[RequestItem]:
    """One catalog as an engagement gets it, built once per (form, year).

    The two rules ``tests/test_irs_forms.py`` lifts are lifted here for
    the same reasons: a redacted document is small, and its year is the
    engagement's, which the expectations file gives.
    """
    if (form, year) not in built:
        built[(form, year)] = [replace(i, min_size_kb=0, date_pattern="")
                               for i in validated(template_items(form, year=year))]
    return built[(form, year)]


def harness():
    """The reader of the expectations file, and the catalog builder, for a tool.

    Both tools ask for the pair here rather than naming each function: the
    contract between a corpus and the code has one owner, and a tool that
    parsed the file a second way would be a second owner of it that could
    drift. It used to import the pair from a test module; since the pair is
    this module's own, the call is kept only so that the two tools read it
    the one way.
    """
    return catalog_rows, read_expectations


def document_path(folder: Path, name: str, row: int) -> Path:
    """One row's document, checked to be a real file inside the corpus.

    Named by row number rather than by name: a missing document is a
    person's typo in the expectations file, and this message is the first
    place the name of a client's file would otherwise escape.
    """
    path = (folder / name).resolve()
    if folder.resolve() not in path.parents:
        raise BacktestError(f"row {row} names a path outside the corpus folder")
    if not path.is_file():
        raise BacktestError(f"row {row} names a document that is not in the corpus folder")
    return path


def linked_under_a_neutral_name(source: Path, scratch: Path, row: int) -> Path:
    """``source``'s bytes under ``NEUTRAL_STEM``, in a folder of their own.

    A hard link where the file system allows one - nothing is read and
    nothing is written - and a copy where it does not (another volume, a
    file system with no links). Either way the router sees the real bytes
    under a name that says nothing, and the folders above it are this
    scratch folder's, never the firm's.
    """
    holder = scratch / str(row)
    holder.mkdir(parents=True, exist_ok=True)
    target = holder / f"{NEUTRAL_STEM}{source.suffix}"
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return target


@contextmanager
def temp_pointed_at(folder: Path):
    """Point every way a library finds the temp folder - ``TMP``, ``TEMP``,
    ``TMPDIR`` (``ocr.SCRATCH_ENV``) and :data:`tempfile.tempdir` - at
    ``folder`` for the block, and put each back as it was afterwards, unset
    ones unset."""
    saved = {name: os.environ.get(name) for name in SCRATCH_ENV}
    saved_tempdir = tempfile.tempdir
    try:
        for name in SCRATCH_ENV:
            os.environ[name] = str(folder)
        tempfile.tempdir = str(folder)
        yield folder
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        tempfile.tempdir = saved_tempdir


def unknown_catalog(rows: list) -> str:
    """The sentence for a row that names a catalog there is not, or "" when
    every row names one. It says the row's number and never the value: an
    unquoted comma in a file name shifts the columns, so the value may be a
    piece of a client's file name, and no name is ever printed."""
    bad = [number for number, (_, catalog, _, _) in enumerate(rows, start=1) if catalog not in CATALOGS]
    if not bad:
        return ""
    more = f" (and {len(bad) - 1} more)" if len(bad) > 1 else ""
    return f"no such catalog in row {bad[0]}{more}; the catalogs are {', '.join(CATALOGS)}"


def outside_the_repository(path: Path) -> Path:
    """``path``, refused if it would land in the repository.

    A report of the firm's own documents is the firm's, and a file written
    into the tree is a file somebody commits.
    """
    resolved = path.expanduser().resolve()
    if inside_the_app(resolved):
        raise BacktestError(f"{OUT_FLAG} must name a path outside the repository: {resolved}")
    return resolved


def corpus_folder(folder: str) -> Path:
    path = Path(folder).expanduser()
    if not path.is_dir():
        raise BacktestError(f"not a folder: {path}")
    return path
