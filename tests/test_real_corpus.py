"""The firm's own documents, routed the way the IRS's own forms are.

``tests/irs/`` holds the blank forms as the IRS and two states publish them and
``tests/test_catalog.py`` holds cases typed from what the documents say.
Neither is a client's document: a real W-2 comes out of a payroll
provider's portal with that provider's layout, a real broker statement
carries a cover page nobody reconstructs, and the thirteenth reading
cannot see either. This harness routes the firm's own redacted documents
- the ones a person has already checked - against the shipped catalogs
exactly as ``tests/test_irs_forms.py`` routes the corpus: through
``create_template()`` and ``load_manifest()``, with the size floor and
the Period's year check lifted, because a redacted document is small and
its year is the engagement's.

They live outside the repository, in the folder ``ENV_REAL_CORPUS``
names, with an ``EXPECTATIONS_FILENAME`` beside them saying where each
one belongs. Client data never enters the repo - redaction is a person's
judgement, not a guarantee, and a document that is in the tree is in
every clone and every build - so the corpus is not committed, cannot be,
and the suite must be green without it. With no folder, or a folder with
no expectations file, the routing test skips and says which variable to
set; nothing here fails because a machine has no corpus.

A row naming a document that is not in the folder fails by name: an
expectation the harness silently dropped would be a document nobody is
routing and everybody believes is covered.
"""

import csv
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_scanner import text_pdf
from tracker.manifest import RequestItem, create_template, load_manifest
from tracker.router import route_file
from tracker.settings import (
    COLUMN_CATALOG,
    COLUMN_EXPECTED,
    COLUMN_FILE,
    COLUMN_YEAR,
    ENV_REAL_CORPUS,
    EXPECTATIONS_COLUMNS,
    EXPECTATIONS_FILENAME,
    real_corpus_dir,
)
from tracker.templates import template_items

#: One row of the expectations file: (file, catalog, year, expected).
#: ``expected`` is None where the column is blank - the document must park.
Expectation = tuple[str, str, int, str | None]


def read_expectations(path: Path) -> list[Expectation]:
    """One expectations file, as rows, in the order it lists them.

    Named by its path rather than by its folder because the corpus is not
    the only caller: ``tools/backtest.py`` scores a folder against an
    expectations file a person keeps wherever they keep it, and the
    contract - the columns, the blank that means "parks", the year that
    must be there - has to have exactly one reader.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in EXPECTATIONS_COLUMNS if c not in (reader.fieldnames or ())]
        if missing:
            raise ValueError(f"{path} is missing the column(s): {', '.join(missing)}")
        rows = []
        for line in reader:
            name = (line[COLUMN_FILE] or "").strip()
            if not name:
                continue                       # a blank line, or a spacer between engagements
            where = (line[COLUMN_EXPECTED] or "").strip()
            year = (line[COLUMN_YEAR] or "").strip()
            if not year.isdigit():
                raise ValueError(f"{path}: {name} has no engagement year")
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
        manifest = workspace / f"{form}-{year}.xlsx"
        create_template(manifest, template_items(form, year=year))
        built[(form, year)] = [replace(i, min_size_kb=0, date_pattern="") for i in load_manifest(manifest)]
    return built[(form, year)]


FOLDER, EXPECT = real_corpus()
#: Nothing to route: one case that skips, so the suite says why rather than
#: quietly collecting no tests at all.
NOTHING: Expectation = ("", "", 0, None)


@pytest.fixture(scope="module")
def catalogs(tmp_path_factory):
    workspace = tmp_path_factory.mktemp("catalogs")
    built: dict = {}

    def rows(form, year):
        return catalog_rows(workspace, form, year, built)

    return rows


@pytest.mark.parametrize("name, form, year, expected", EXPECT or [NOTHING],
                         ids=[f"{n}-{f}" for n, f, _, _ in EXPECT] or ["no-corpus"])
def test_the_firms_own_documents_file_where_they_belong_or_park(catalogs, name, form, year, expected):
    if not EXPECT:
        pytest.skip(f"{ENV_REAL_CORPUS} names no folder holding {EXPECTATIONS_FILENAME}")
    path = FOLDER / name
    assert path.is_file(), f"{EXPECTATIONS_FILENAME} names {name}, which is not in {FOLDER}"
    routing = route_file(path, catalogs(form, year))
    assert routing.identifier == expected, (name, form, routing.reason)


# ------------------------------------------------- the harness itself ----
#
# A machine with no corpus runs everything below, so the harness is
# tested wherever the suite runs: the reading, the routing and the skip.


def scratch_corpus(parent: Path) -> Path:
    """Two documents and the expectations file that places them, in a folder of their own."""
    folder = parent / "corpus"
    folder.mkdir()
    text_pdf(folder / "w-2 redacted.pdf", "\n".join([
        "Form W-2 Wage and Tax Statement 2025",
        "a Employee's social security number 123-45-6789",
    ]))
    text_pdf(folder / "extension redacted.pdf",
             "Form 4868 Application for Automatic Extension of Time To File 2025")
    (folder / EXPECTATIONS_FILENAME).write_text("\n".join([
        ",".join(EXPECTATIONS_COLUMNS),
        "w-2 redacted.pdf,1040,2025,A01",
        "extension redacted.pdf,1040,2025,",
        "",
    ]), encoding="utf-8")
    return folder


def test_a_corpus_is_read_and_routed_the_way_the_shipped_catalogs_route(tmp_path, monkeypatch):
    corpus = scratch_corpus(tmp_path)
    monkeypatch.setenv(ENV_REAL_CORPUS, str(corpus))
    folder, rows = real_corpus()
    assert folder == corpus
    assert rows == [("w-2 redacted.pdf", "1040", 2025, "A01"),
                    ("extension redacted.pdf", "1040", 2025, None)]
    built: dict = {}
    for name, form, year, expected in rows:
        routing = route_file(folder / name, catalog_rows(tmp_path, form, year, built))
        assert routing.identifier == expected, (name, routing.reason)


def test_a_blank_expected_column_means_the_document_must_park(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_REAL_CORPUS, str(scratch_corpus(tmp_path)))
    _, rows = real_corpus()
    assert rows[1][3] is None            # blank is not the empty string: nothing files under ""


def test_an_expectations_file_missing_a_column_is_named_not_guessed(tmp_path, monkeypatch):
    (tmp_path / EXPECTATIONS_FILENAME).write_text(f"{COLUMN_FILE},{COLUMN_CATALOG}\na.pdf,1040\n", encoding="utf-8")
    monkeypatch.setenv(ENV_REAL_CORPUS, str(tmp_path))
    with pytest.raises(ValueError, match=COLUMN_YEAR):
        real_corpus()


def test_no_corpus_is_no_failure_only_nothing_to_route(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_REAL_CORPUS, raising=False)
    assert real_corpus() == (None, [])
    monkeypatch.setenv(ENV_REAL_CORPUS, str(tmp_path / "not there"))
    assert real_corpus() == (None, [])
    monkeypatch.setenv(ENV_REAL_CORPUS, str(tmp_path))       # a folder, but no expectations file
    assert real_corpus() == (None, [])
