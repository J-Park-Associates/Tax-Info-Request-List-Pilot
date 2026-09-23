"""Tests for tools/backtest.py - the score has to be honest, and quiet.

The backtest is the one measurement taken from documents a client
actually sent, so two things have to hold or the number is worse than no
number. It must score the router, not the firm's file naming: the tool
hides each document's own name, and a document whose name says one form
and whose text says another proves it. And it must carry nothing back: a
report of the firm's own documents is client data, so no file name, no
folder name and no word of a document may appear in the report or on the
console.

The corpus here is built with ``tests/samples.py``, in ``tmp_path``. No
client document is in the repository, and none ever will be.
"""

import json
import os
import sys
from pathlib import Path

import pytest

from tests.samples import lines_1099_int, text_pdf, w2_lines
from tracker.settings import COLUMN_EXPECTED, EXPECTATIONS_COLUMNS, EXPECTATIONS_FILENAME

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import backtest  # noqa: E402
from backtest import (  # noqa: E402
    BASELINE_PATH,
    CATALOGS,
    COLLECT_COLUMNS,
    HINT_COLUMN,
    NEUTRAL_STEM,
    NO_BASELINE,
    OCR_FLAG,
    OUT_FLAG,
    PARKS,
    READING_IMAGE,
    READING_KINDS,
    READING_OCR,
    READING_TEXT,
    SLOWEST_COUNT,
    BacktestError,
    Outcome,
    check,
    main,
    record,
    score,
    write_json,
    write_skeleton,
)

REPO = Path(__file__).resolve().parent.parent
YEAR = 2025
#: Nothing in the corpus is named anything a report could plausibly carry
#: by accident, so an assertion that these do not appear is a real one.
CLIENT_FOLDER = "Aardvark Holdings LLC"
W2_FILE = "Zebediah W-2 2025.pdf"
PARKING_FILE = "Zebediah extension 2025.pdf"
EMPLOYER = "Aardvark Holdings LLC"
EMPLOYEE = "Zebediah Quill"
#: Every name and every word the corpus carries, which no report may.
SECRETS = (CLIENT_FOLDER, W2_FILE, PARKING_FILE, EMPLOYEE, "Aardvark", "Zebediah", ".pdf")


def expectations_for(folder: Path, rows: list[str]) -> Path:
    path = folder / EXPECTATIONS_FILENAME
    path.write_text("\n".join([",".join(EXPECTATIONS_COLUMNS), *rows, ""]), encoding="utf-8")
    return path


def two_documents(tmp_path: Path) -> Path:
    """A W-2 that belongs on a row and an extension request that belongs to nobody."""
    folder = tmp_path / "corpus"
    inside = folder / CLIENT_FOLDER
    inside.mkdir(parents=True)
    text_pdf(inside / W2_FILE, w2_lines(EMPLOYEE, EMPLOYER, YEAR))
    text_pdf(inside / PARKING_FILE,
             [f"Form 4868 Application for Automatic Extension of Time To File {YEAR}"])
    expectations_for(folder, [
        f"{CLIENT_FOLDER}/{W2_FILE},1040,{YEAR},A01",
        f"{CLIENT_FOLDER}/{PARKING_FILE},1040,{YEAR},",
    ])
    return folder


def run(folder: Path) -> dict:
    outcomes, seconds = backtest.route_corpus(folder, folder / EXPECTATIONS_FILENAME)
    return score(outcomes, seconds)


# ------------------------------------------------------------- the score ----


def test_documents_filed_where_the_router_would_file_them_score_full_agreement(tmp_path):
    data = run(two_documents(tmp_path))
    assert data["documents"] == 2 and data["routed"] == 2
    assert data["agreement"] == 1.0 and data["agreed"] == 2
    assert data["parked"] == 1 and data["parked_share"] == 0.5
    assert data["confusions"] == []
    rows = data["catalogs"]["1040"]["rows"]
    assert rows["A01"] == {"filed_here": 1, "parked": 0, "filed_elsewhere": 0}
    assert rows[PARKS] == {"filed_here": 1, "parked": 0, "filed_elsewhere": 0}


def test_a_document_is_routed_by_its_text_and_never_by_its_own_name(tmp_path):
    """The firm names its files after the form; a backtest that read the
    name would be scoring the naming, and would call a misnamed document
    right for the wrong reason."""
    folder = tmp_path / "corpus"
    folder.mkdir()
    text_pdf(folder / W2_FILE, lines_1099_int("First National Bank", EMPLOYEE, YEAR))
    expectations_for(folder, [f"{W2_FILE},1040,{YEAR},A02"])
    data = run(folder)
    assert data["agreement"] == 1.0                      # A02 is the interest row, not the W-2 row
    assert data["catalogs"]["1040"]["rows"]["A02"]["filed_here"] == 1


def test_a_document_with_no_text_layer_is_counted_apart_and_is_not_parked(tmp_path):
    """A scan's only remaining evidence is the name this tool hides, so it
    is neither routed nor held against the router: it is its own number."""
    folder = tmp_path / "corpus"
    folder.mkdir()
    text_pdf(folder / W2_FILE, [""])                     # a valid PDF with nothing to read
    expectations_for(folder, [f"{W2_FILE},1040,{YEAR},A01"])
    data = run(folder)
    assert data["no_text"] == 1 and data["no_text_share"] == 1.0
    assert data["routed"] == 0 and data["parked"] == 0
    assert data["agreement"] is None
    assert data["catalogs"]["1040"]["no_text"] == 1 and data["catalogs"]["1040"]["parked"] == 0


def test_the_name_documents_are_routed_under_reaches_no_keyword_in_any_catalog():
    """The hiding works by giving every document one neutral name. If that
    word were a keyword somewhere, the router would file on it."""
    from tracker.content_check import contains_keyword
    from tracker.templates import template_items

    for catalog in CATALOGS:
        for item in template_items(catalog, year=YEAR):
            for keyword in (*item.required_keywords, *item.any_keywords):
                assert not contains_keyword(NEUTRAL_STEM, keyword), (catalog, item.identifier, keyword)


# ------------------------------------------------------- what it gives back ----


def test_the_report_and_the_console_name_no_file_and_no_folder(tmp_path, capsys):
    folder = two_documents(tmp_path)
    out = tmp_path / "report.json"
    assert main(["run", str(folder), OUT_FLAG, str(out)]) == 0
    printed = capsys.readouterr().out
    written = out.read_text(encoding="utf-8")
    for secret in SECRETS:
        assert secret not in printed, secret
        assert secret not in written, secret
    assert json.loads(written)["agreement"] == 1.0       # it did say something


def test_the_slowest_documents_are_named_by_row_number_and_nothing_else():
    many = [Outcome(row=n, catalog="1040", expected="A01", got="A01", no_text=False, seconds=n / 100)
            for n in range(1, SLOWEST_COUNT + 3)]
    slowest = score(many, 1.0)["timing"]["slowest"]
    assert len(slowest) == SLOWEST_COUNT
    assert [s["row"] for s in slowest] == list(range(len(many), len(many) - SLOWEST_COUNT, -1))
    for entry in slowest:
        assert set(entry) == {"row", "seconds"}


def test_the_backtest_report_counts_readings_by_kind():
    """Decision 127. A photo takes the OCR path a scanned PDF takes, and
    the two cost different amounts of time, so the report splits them:
    the reader benchmark has to be able to say what a photo costs without
    a folder of text-layer PDFs flattening the number. Counts only - the
    split names no document, like everything else here."""
    outcomes = [
        Outcome(row=1, catalog="1040", expected="A01", got="A01", no_text=False,
                seconds=0.1, kind=READING_TEXT),
        Outcome(row=2, catalog="1040", expected="A01", got="A01", no_text=False,
                seconds=1.4, kind=READING_OCR),
        Outcome(row=3, catalog="1040", expected="C01", got="C01", no_text=False,
                seconds=2.2, kind=READING_IMAGE),
        Outcome(row=4, catalog="1040", expected=None, got=None, no_text=True,
                seconds=1.9, kind=READING_IMAGE),
    ]
    by_kind = score(outcomes, 5.6)["timing"]["readings_by_kind"]
    assert by_kind == {READING_TEXT: 1, READING_OCR: 1, READING_IMAGE: 2}
    assert set(by_kind) == set(READING_KINDS)          # every kind counted, always
    assert sum(by_kind.values()) == len(outcomes)


def test_a_photo_is_read_as_a_photo_and_needs_the_ocr_flag_like_any_scan(tmp_path):
    """``route_one`` names the reading each document got. An image is its
    own kind even before anything reads it - it never has a text layer -
    and without ``--ocr`` it is unrouted, exactly as a scan is."""
    from PIL import Image

    from tracker.templates import template_items

    photo = tmp_path / "receipt.jpg"
    Image.new("RGB", (400, 200), "white").save(photo)
    rows = list(template_items("1040", year=YEAR))

    got, no_text, kind = backtest.route_one(photo, rows, ocr=False)
    assert got is None and no_text and kind == READING_IMAGE


def test_a_disagreement_is_reported_as_the_pair_it_is():
    outcomes = [
        Outcome(row=1, catalog="1040", expected="A01", got="A02", no_text=False, seconds=0.1),
        Outcome(row=2, catalog="1040", expected="A01", got="A02", no_text=False, seconds=0.1),
        Outcome(row=3, catalog="1040", expected="C01", got=None, no_text=False, seconds=0.1),
    ]
    data = score(outcomes, 0.3)
    assert data["confusions"] == [
        {"expected": "A01", "got": "A02", "count": 2},
        {"expected": "C01", "got": PARKS, "count": 1},
    ]
    assert data["catalogs"]["1040"]["confusions"] == data["confusions"]
    assert data["agreement"] == 0.0 and data["parked"] == 1
    rows = data["catalogs"]["1040"]["rows"]
    assert rows["A01"]["filed_elsewhere"] == 2 and rows["C01"]["parked"] == 1


# ---------------------------------------------------------------- collect ----


def test_collect_writes_a_skeleton_with_a_blank_answer_and_the_folder_as_the_hint(tmp_path):
    folder = two_documents(tmp_path)
    out = tmp_path / "skeleton.csv"
    assert write_skeleton(folder, out, "1040", YEAR) == 2
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ",".join(COLLECT_COLUMNS)
    assert lines[1] == f"{CLIENT_FOLDER}/{W2_FILE},1040,{YEAR},,{CLIENT_FOLDER}"
    assert lines[2] == f"{CLIENT_FOLDER}/{PARKING_FILE},1040,{YEAR},,{CLIENT_FOLDER}"
    assert COLUMN_EXPECTED in COLLECT_COLUMNS and HINT_COLUMN in COLLECT_COLUMNS


def test_collect_refuses_to_overwrite_an_expectations_file(tmp_path):
    """A filled-in file is hours of a person's reading; a second collect
    after one more document arrived would erase every answer."""
    folder = two_documents(tmp_path)
    with pytest.raises(BacktestError, match="never overwritten"):
        write_skeleton(folder, folder / EXPECTATIONS_FILENAME, "1040", YEAR)


def test_collect_writes_only_documents_a_catalog_would_look_at(tmp_path):
    """A file type no catalog row accepts is no catalog's business, and the
    sheet of answers beside the corpus is not a client document however
    many catalogs take a spreadsheet."""
    folder = two_documents(tmp_path)
    (folder / CLIENT_FOLDER / "vacation photo.bmp").write_bytes(b"BM" + b"J" * 900)
    assert (folder / EXPECTATIONS_FILENAME).is_file()
    assert write_skeleton(folder, folder / "skeleton.csv", "1040", YEAR) == 2


# ------------------------------------------------------- the one number ----


def a_report(tmp_path: Path, agreement: float) -> Path:
    path = tmp_path / "report.json"
    write_json(path, score([Outcome(row=1, catalog="1040", expected="A01",
                                    got="A01" if agreement else "A02",
                                    no_text=False, seconds=0.1)], 0.1))
    return path


def test_record_writes_the_agreement_as_the_number_to_beat(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline = record(a_report(tmp_path, 1.0), baseline_path)
    assert baseline["agreement"] == 1.0 and baseline["documents"] == 1
    written = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert written == baseline and written["note"] and written["recorded"]


def test_check_fails_below_the_baseline_and_passes_at_or_above_it(tmp_path, capsys):
    write_json(tmp_path / "high.json", {"agreement": 1.0, "documents": 9, "recorded": "2026-09-18", "note": ""})
    write_json(tmp_path / "low.json", {"agreement": 0.0, "documents": 9, "recorded": "2026-09-18", "note": ""})
    report = a_report(tmp_path, 0.0)
    assert check(report, tmp_path / "high.json") == 1
    assert "BELOW" in capsys.readouterr().out
    assert check(report, tmp_path / "low.json") == 0


def test_check_says_plainly_that_nobody_has_measured_when_no_baseline_is_recorded(tmp_path, capsys):
    """An unknown baseline is never reported as met: the message says the
    owner has not run the backtest at the office yet, and exits 0 because
    there is nothing to have failed."""
    write_json(tmp_path / "none.json", {"agreement": None, "documents": 0, "recorded": None, "note": ""})
    assert check(a_report(tmp_path, 1.0), tmp_path / "none.json") == 0
    assert NO_BASELINE in capsys.readouterr().out


def test_the_committed_baseline_records_no_agreement_until_the_office_run():
    shipped = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert shipped["agreement"] is None and shipped["documents"] == 0
    assert shipped["note"] == backtest.UNMEASURED_NOTE


# ------------------------------------------------ nothing reaches the tree ----

#: Folders whose contents change for reasons that are nobody's doing.
_UNWATCHED = {".git", ".claude", "__pycache__", ".pytest_cache", ".ruff_cache",
              "node_modules", "build-portable", "dist", "build"}


def repository_snapshot() -> dict[str, int]:
    found = {}
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in _UNWATCHED]
        for name in filenames:
            path = Path(dirpath) / name
            found[str(path.relative_to(REPO))] = path.stat().st_mtime_ns
    return found


def test_the_tool_writes_nothing_under_the_repository_root(tmp_path, capsys, monkeypatch):
    """Everything a pass makes - the catalogs it builds, the links it
    routes, the report - belongs outside the tree, because all of it is
    made from client documents."""
    folder = two_documents(tmp_path)
    monkeypatch.chdir(tmp_path)
    before = repository_snapshot()
    assert main(["run", str(folder), OUT_FLAG, str(tmp_path / "report.json"), OCR_FLAG]) == 0
    assert main(["collect", str(folder), "--catalog", "1040", "--year", str(YEAR),
                 OUT_FLAG, str(tmp_path / "skeleton.csv")]) == 0
    assert repository_snapshot() == before
    # And it refuses to be pointed at the tree in the first place.
    assert main(["run", str(folder), OUT_FLAG, str(REPO / "report.json")]) == 2
    assert "outside the repository" in capsys.readouterr().err
    assert repository_snapshot() == before


def test_a_row_naming_a_document_that_is_not_there_is_reported_by_its_number(tmp_path):
    """The one message that would otherwise carry a client's file name."""
    folder = tmp_path / "corpus"
    folder.mkdir()
    expectations_for(folder, [f"{W2_FILE},1040,{YEAR},A01"])
    with pytest.raises(BacktestError) as raised:
        run(folder)
    assert "row 1" in str(raised.value) and W2_FILE not in str(raised.value)
