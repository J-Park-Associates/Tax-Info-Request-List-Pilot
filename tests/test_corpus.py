"""Tests for tools/corpus.py - the harness the backtest and the reader bench share.

The corpus is the firm's own documents, so what this module says about a bad
row must never be what a bad row says: the errors name a row by number and the
column that is wrong, and no document's name, no catalog value and no path
reaches a caller's console (decision 185). Everything here is made up under
``tmp_path`` and nothing reads ``ENV_REAL_CORPUS``; the rows that route a real
folder are ``tests/test_real_corpus.py``'s.
"""

import sys
from pathlib import Path

import pytest

from tools import corpus
from tracker.settings import COLUMN_YEAR, EXPECTATIONS_COLUMNS, EXPECTATIONS_FILENAME

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import backtest  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
#: Names no message may carry, which are a client's.
CLIENT_FILE = "Zebediah Quill W-2 2025.pdf"
OTHER_FILE = "Aardvark Holdings 1098 2025.pdf"


def expectations_file(folder: Path, rows: list[str]) -> Path:
    path = folder / EXPECTATIONS_FILENAME
    path.write_text("\n".join([",".join(EXPECTATIONS_COLUMNS), *rows, ""]), encoding="utf-8")
    return path


def test_the_backtests_error_is_the_corpus_own():
    """The class is defined once. The backtest imported as the suite imports it
    (bare, after its ``sys.path`` insert) and as the reader bench does
    (``tools.backtest``) are two copies of that module, and each re-imports this
    module's one class rather than defining its own."""
    from tools import backtest as backtest_in_tools

    assert backtest.BacktestError is corpus.BacktestError
    assert backtest_in_tools.BacktestError is corpus.BacktestError
    assert backtest.CATALOGS is corpus.CATALOGS
    assert backtest.OUT_FLAG == corpus.OUT_FLAG


def test_a_row_with_no_year_is_refused_by_its_number_and_never_its_name(tmp_path):
    path = expectations_file(tmp_path, [f"{CLIENT_FILE},1040,2025,A01", f"{OTHER_FILE},1040,,A02"])
    with pytest.raises(ValueError) as raised:
        corpus.read_expectations(path)
    said = str(raised.value)
    assert "row 2" in said and COLUMN_YEAR in said
    for secret in (CLIENT_FILE, OTHER_FILE, "Zebediah", "Aardvark", str(tmp_path)):
        assert secret not in said, secret


def test_a_blank_line_is_no_row_and_a_blank_expected_column_is_none(tmp_path):
    path = expectations_file(tmp_path, [f"{CLIENT_FILE},1040,2025,A01", ",,,", f"{OTHER_FILE},1040,2025,"])
    assert corpus.read_expectations(path) == [(CLIENT_FILE, "1040", 2025, "A01"), (OTHER_FILE, "1040", 2025, None)]


def test_a_bad_catalog_is_said_by_its_row_and_never_its_value():
    rows = [(CLIENT_FILE, "1040", 2025, "A01"), (OTHER_FILE, "Zebediah-not-a-catalog", 2025, None)]
    said = corpus.unknown_catalog(rows)
    assert "row 2" in said
    for secret in ("Zebediah", "not-a-catalog", CLIENT_FILE, OTHER_FILE):
        assert secret not in said, secret
    assert "more" not in said, "one bad row is not 'and more'"

    rows.append((CLIENT_FILE, "Quillfeather", 2025, None))
    assert "(and 1 more)" in corpus.unknown_catalog(rows)
    assert corpus.unknown_catalog(rows[:1]) == ""


def test_a_report_inside_the_repository_is_refused(tmp_path):
    with pytest.raises(corpus.BacktestError, match=corpus.OUT_FLAG):
        corpus.outside_the_repository(REPO / "report.json")
    unresolved = tmp_path / "somewhere" / ".." / "report.json"
    assert corpus.outside_the_repository(unresolved) == (tmp_path / "report.json").resolve()


def test_a_document_is_named_by_its_row_when_it_is_missing_or_outside_the_corpus(tmp_path):
    folder = tmp_path / "corpus"
    folder.mkdir()
    (tmp_path / "elsewhere.pdf").write_bytes(b"%PDF-1.4\n")
    (folder / CLIENT_FILE).write_bytes(b"%PDF-1.4\n")
    assert corpus.document_path(folder, CLIENT_FILE, 1) == (folder / CLIENT_FILE).resolve()
    for name, row in ((OTHER_FILE, 3), ("../elsewhere.pdf", 4)):
        with pytest.raises(corpus.BacktestError) as raised:
            corpus.document_path(folder, name, row)
        said = str(raised.value)
        assert f"row {row}" in said
        for secret in (OTHER_FILE, "elsewhere", "Aardvark", str(tmp_path)):
            assert secret not in said, secret


def test_a_document_is_linked_under_a_name_that_says_nothing(tmp_path):
    source = tmp_path / CLIENT_FILE
    source.write_bytes(b"%PDF-1.4\nthe same bytes\n")
    scratch = tmp_path / "scratch"
    link = corpus.linked_under_a_neutral_name(source, scratch, 7)
    assert link == scratch / "7" / f"{corpus.NEUTRAL_STEM}.pdf"
    assert link.read_bytes() == source.read_bytes()
    assert "Zebediah" not in str(link)


def test_the_harness_is_this_modules_own_reader_and_builder():
    assert corpus.harness() == (corpus.catalog_rows, corpus.read_expectations)
