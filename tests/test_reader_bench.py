"""Tests for tools/reader_bench.py - the bench that measures the reader's
settings on the firm's own paper (P283).

Three things have to hold or its numbers are worse than none. The settings
must really reach the reader (the bench reads in its own process, because a
reading child imports the reader afresh at the shipped settings, and puts
everything back when it is done). The four outcomes must mean what the SPEC
says, because the office chooses the shipped settings by them. And nothing
may leave it but counts and seconds: a report of the firm's own documents is
client data, so no document name, folder, word or path may appear in the
report or on the console.

The reader is a stand-in throughout (``content_check._ocr_pdf`` and
``_ocr_image`` patched to return a made-up reading chosen by the settings in
force, so a test can make one variant file a document and another park it),
except the last test, which reads one drawn page with the real reader. The
corpus is built in ``tmp_path`` from ``tests/samples.py``: no client's
document is in the repository, and none ever will be.
"""

from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.samples import lines_1099_int, scanned_pdf, text_pdf, w2_lines
from tracker import content_check, ocr, reasons
from tracker.records import Routing
from tracker.settings import EXPECTATIONS_COLUMNS, EXPECTATIONS_FILENAME, process_scratch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import reader_bench  # noqa: E402
from reader_bench import (  # noqa: E402
    BENCH_NOTE,
    CEILING_SECONDS_PER_PAGE,
    DELININGS,
    DPIS,
    FLOORS,
    MEDIUM_NOT_MEASURED,
    OUT_FLAG,
    TIERS,
    BacktestError,
    grid,
    long_side,
    main,
    run_bench,
)

REPO = Path(__file__).resolve().parent.parent
YEAR = 2025
#: Nothing in a corpus is named anything a report could plausibly carry by
#: accident, so an assertion that these do not appear is a real one.
CLIENT_FOLDER = "Aardvark Holdings LLC"
SECRET_WORDS = ("Aardvark", "Zebediah", "Quillfeather", ".pdf", ".jpg", "document.pdf")
#: The settings that restrict the grid to the shipped variant alone.
SHIPPED_ONLY = ["--dpi", "144", "--floor", "0.5", "--delining", "off", "--tier", "small"]

GOOD_1099 = "\n".join(lines_1099_int("Harbor Test Bank", "John A. Smith", YEAR))
#: A broker's consolidated page names three 1099 forms, so three requests
#: accept it on their form numbers: nothing is filed, and it parks as
#: matched only by OCR with all three - the interest request among them - on
#: its shortlist.
A_BROKER_PAGE = "\n".join(["Consolidated Form 1099 Tax Statement 2025", "Form 1099-INT", "Form 1099-B",
                           "Form 1099-MISC"])
NOTHING = "Quarterly newsletter of the Harbor Test Club"
A_W2 = "\n".join(w2_lines("Jane Doe", "Harbor Test Co", YEAR))
REAL_WARM_UP = ocr.warm_up


# ------------------------------------------------------------ the helpers ----


def a_corpus(tmp_path: Path, entries: list[tuple[str, str, str]]) -> Path:
    """A folder of documents and its expectations file. Each entry is
    (kind, file name, the expected row - blank for a document meant to park);
    a kind is ``scan`` (image-only PDF), ``text`` (a PDF with a text layer),
    ``photo`` (a JPEG) or ``scan2`` (a two-page scan)."""
    from PIL import Image

    folder = tmp_path / "corpus"
    inside = folder / CLIENT_FOLDER
    inside.mkdir(parents=True)
    rows = []
    for kind, name, expected in entries:
        path = inside / name
        if kind == "scan":
            scanned_pdf(path, ["x"])
        elif kind == "scan2":
            sheets = [Image.new("RGB", (400, 500 + 10 * i), "white") for i in range(2)]
            sheets[0].save(path, "PDF", save_all=True, append_images=sheets[1:])
        elif kind == "text":
            text_pdf(path, w2_lines("Jane Doe", "Harbor Test Co", YEAR))
        else:
            Image.new("RGB", (400, 200), "white").save(path)
        rows.append(f"{CLIENT_FOLDER}/{name},1040,{YEAR},{expected}")
    (folder / EXPECTATIONS_FILENAME).write_text(
        "\n".join([",".join(EXPECTATIONS_COLUMNS), *rows, ""]), encoding="utf-8")
    return folder


def the_five_outcomes(tmp_path: Path) -> Path:
    """Row 1 files right, 2 is meant to park and parks, 3 parks with its
    row on the shortlist, 4 parks with no lead, 5 files elsewhere; row 6 has
    a text layer."""
    return a_corpus(tmp_path, [
        ("scan", "one.pdf", "A02"), ("scan", "two.pdf", ""), ("scan", "three.pdf", "A02"),
        ("scan", "four.pdf", "A02"), ("scan", "five.pdf", "A02"), ("text", "six.pdf", "A01")])


@pytest.fixture
def stand_in(monkeypatch):
    """The reader replaced by a made-up one: ``pages`` maps a row (counted
    from one, as the expectations file lists them) to its reading - a string,
    or a function of the settings in force. ``calls`` records (row, the
    settings in force, whether the reading switch was on)."""
    reader = SimpleNamespace(pages={}, calls=[])

    def read(path):
        row = int(path.parent.name)               # linked as <scratch>/<row>/document.<ext>
        reader.calls.append((row, ocr.SETTINGS, content_check.READ_IN_A_CHILD))
        what = reader.pages[row]
        return what(ocr.SETTINGS) if callable(what) else what

    monkeypatch.setattr(content_check, "_ocr_pdf", read)
    monkeypatch.setattr(content_check, "_ocr_image", read)
    monkeypatch.setattr(ocr, "warm_up", lambda: (ocr.DEVICE_PROCESSOR, ""))
    return reader


def the_five_readings(stand_in) -> None:
    stand_in.pages = {1: GOOD_1099, 2: NOTHING, 3: A_BROKER_PAGE, 4: NOTHING, 5: A_W2}


def run(tmp_path: Path, folder: Path, *flags: str) -> tuple[int, dict]:
    """The ``run`` command: its exit code and the report it wrote."""
    out = tmp_path / "report.json"
    code = main(["run", str(folder), OUT_FLAG, str(out), *flags])
    return code, (json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {})


# --------------------------------------------------------------- the grid ----


def test_the_grid_is_every_dpi_floor_delining_and_tier(capsys):
    variants = grid()
    assert len(variants) == len(DPIS) * len(FLOORS) * len(DELININGS) * len(TIERS) == 36
    names = [variant.name for variant in variants]
    assert len(set(names)) == 36
    assert {(v.settings.render_dpi, v.settings.confident_score, v.settings.delining, v.settings.model_tier)
            for v in variants} == {(d, f, x, t) for d in DPIS for f in FLOORS for x in DELININGS for t in TIERS}
    assert "dpi144-floor0.50-off-small" in names and "dpi300-floor0.85-on-medium" in names
    assert main(["variants"]) == 0
    assert capsys.readouterr().out.splitlines() == names                 # one a line
    assert main(["variants", "--dpi", "300", "--tier", "small"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "dpi144-floor0.50-off-small", *[n for n in names if n.startswith("dpi300") and n.endswith("small")]]


def test_the_shipped_variant_is_always_measured_first(tmp_path, stand_in):
    assert grid()[0].settings == ocr.SHIPPED and grid()[0].name == "dpi144-floor0.50-off-small"
    left_out = grid((300,), (0.85,), (True,), ("small",))
    assert [v.name for v in left_out] == ["dpi144-floor0.50-off-small", "dpi300-floor0.85-on-small"]

    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    code, report = run(tmp_path, folder, "--dpi", "300", "--floor", "0.85", "--delining", "on", "--tier", "small")
    assert code == 0
    assert [v["name"] for v in report["variants"]] == ["dpi144-floor0.50-off-small", "dpi300-floor0.85-on-small"]


def test_each_variants_long_side_holds_a_letter_page_at_its_dpi():
    assert [long_side(dpi) for dpi in DPIS] == [2000, 2200, 3300]
    for variant in grid():
        dpi = variant.settings.render_dpi
        assert variant.settings.max_side_len == max(2000, math.ceil(11 * dpi)) >= 11 * dpi
    assert grid()[0].settings.max_side_len == ocr.SHIPPED.max_side_len == 2000


# ------------------------------------------------------- what it counts ----


def test_a_document_with_a_text_layer_is_counted_and_never_read_by_the_reader(tmp_path, stand_in):
    """The reader's settings cannot change a text layer, so the document is
    counted and never routed again: the stand-in is never asked for it."""
    the_five_readings(stand_in)
    code, report = run(tmp_path, the_five_outcomes(tmp_path), *SHIPPED_ONLY)
    assert code == 0
    assert report["corpus"] == {"documents": 6, "text_layer": 1, "scans": 5, "photos": 0, "pages": 5}
    assert sorted({row for row, _settings, _switch in stand_in.calls}) == [1, 2, 3, 4, 5]
    assert sum(report["variants"][0]["outcomes"].values()) == 5


def test_the_four_outcomes_are_counted_as_the_spec_defines_them(tmp_path, stand_in):
    """One of each: filed right, meant to park and parked, parked with the
    expected row on its shortlist, parked with no lead, filed elsewhere. A
    setting reaches the reader: at 300 dpi row 4 is read well and files."""
    the_five_readings(stand_in)
    stand_in.pages[4] = lambda settings: GOOD_1099 if settings.render_dpi == 300 else NOTHING
    code, report = run(tmp_path, the_five_outcomes(tmp_path),
                       "--dpi", "144,300", "--floor", "0.5", "--delining", "off", "--tier", "small")
    assert code == 0
    shipped, sharper = report["variants"]
    assert shipped["outcomes"] == {"right": 2, "parked_shortlist": 1, "parked_no_lead": 1, "wrong": 1}
    assert sharper["name"] == "dpi300-floor0.50-off-small"
    assert sharper["outcomes"] == {"right": 3, "parked_shortlist": 1, "parked_no_lead": 0, "wrong": 1}


def test_parked_documents_are_counted_by_code_and_ocr_only_has_its_share(tmp_path, stand_in):
    the_five_readings(stand_in)
    _code, report = run(tmp_path, the_five_outcomes(tmp_path), *SHIPPED_ONLY)
    shipped = report["variants"][0]
    assert shipped["parked_by_code"] == {reasons.OCR_ONLY_CODE: 1, reasons.UNMATCHED_CODE: 2}
    assert shipped["ocr_only"] == 1 and shipped["ocr_only_share"] == 0.2          # one of five read


def test_the_report_holds_counts_and_seconds_and_no_name_path_or_word(tmp_path, stand_in, capsys):
    """File names, the folder, the readings' words, the corpus path and the
    models folder are all distinctive made-up words: none is anywhere in the
    report or in what was printed."""
    models = tmp_path / "medium-models-Quillfeather"
    models.mkdir()
    for name in ocr.MODEL_TIERS["medium"]:
        (models / name).write_bytes(b"")
    folder = a_corpus(tmp_path, [("scan", "Zebediah Quill scan.pdf", "A02"),
                                 ("photo", "Zebediah Quill photo.jpg", ""),
                                 ("text", "Zebediah Quill W-2.pdf", "A01")])
    stand_in.pages = {
        1: GOOD_1099.replace("John A. Smith", "Zebediah Quill").replace("Harbor Test Bank", "Aardvark Holdings"),
        2: "Quillfeather Zebediah Quill notes"}

    code, report = run(tmp_path, folder, "--models", str(models), "--dpi", "144", "--floor", "0.5",
                       "--delining", "off")
    assert code == 0
    printed = capsys.readouterr()
    written = json.dumps(report) + (tmp_path / "report.json").read_text(encoding="utf-8")
    assert [v["measured"] for v in report["variants"]] == [True, True]       # small and medium both read
    assert report["note"] == BENCH_NOTE and report["schema"] == 1
    for secret in (*SECRET_WORDS, str(folder), str(models), "model_folder"):
        assert secret not in written, secret
        assert secret not in printed.out and secret not in printed.err, secret
    assert report["variants"][0]["settings"] == {"render_dpi": 144, "confident_score": 0.5, "max_side_len": 2000,
                                                 "delining": False, "model_tier": "small"}


def test_the_report_is_refused_inside_the_repository(tmp_path, stand_in, capsys):
    the_five_readings(stand_in)
    folder = the_five_outcomes(tmp_path)
    refused = REPO / "reader-bench-report.json"
    assert main(["run", str(folder), OUT_FLAG, str(refused), *SHIPPED_ONLY]) == 2
    assert "outside the repository" in capsys.readouterr().err
    assert not refused.exists() and stand_in.calls == []                     # refused before anything is read


def test_the_medium_tier_is_not_measured_without_its_models_and_says_so(tmp_path, stand_in):
    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    medium_name = "dpi144-floor0.50-off-medium"
    flags = ["--dpi", "144", "--floor", "0.5", "--delining", "off"]

    _code, report = run(tmp_path, folder, *flags)
    shipped, medium = report["variants"]
    assert shipped["measured"] and medium["name"] == medium_name
    assert medium == {"name": medium_name, "settings": medium["settings"], "measured": False,
                      "note": MEDIUM_NOT_MEASURED}
    assert medium["settings"]["model_tier"] == "medium"
    assert all(settings.model_tier == "small" for _row, settings, _switch in stand_in.calls)

    half = tmp_path / "half-models"
    half.mkdir()
    (half / ocr.MODEL_TIERS["medium"][0]).write_bytes(b"")                   # one of its two files
    _code, report = run(tmp_path, folder, "--models", str(half), *flags)
    assert report["variants"][1]["measured"] is False and report["variants"][1]["note"] == MEDIUM_NOT_MEASURED

    (half / ocr.MODEL_TIERS["medium"][1]).write_bytes(b"")
    _code, report = run(tmp_path, folder, "--models", str(half), *flags)
    assert report["variants"][1]["measured"] is True
    assert any(s.model_tier == "medium" and s.model_folder == str(half) for _row, s, _switch in stand_in.calls)


def test_the_bench_never_downloads_a_model(tmp_path, stand_in, monkeypatch):
    """With rapidocr's downloader made to fail the test if it is reached, a
    run with the medium tier and no models completes: the medium variant is
    not measured, and the shipped one builds the real engine from the models
    the app carries."""
    from rapidocr.utils import download_file

    def reached(cls, params):
        raise AssertionError("the bench reached rapidocr's downloader")

    monkeypatch.setattr(download_file.DownloadFile, "run", classmethod(reached))
    monkeypatch.setattr(ocr, "_refuse_downloads", lambda: None)              # keep this guard in place
    monkeypatch.setattr(ocr, "warm_up", REAL_WARM_UP)
    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])

    code, report = run(tmp_path, folder, "--tier", "medium", "--dpi", "144", "--floor", "0.5", "--delining", "off")

    assert code == 0
    assert [v["measured"] for v in report["variants"]] == [True, False]
    assert report["variants"][1]["note"] == MEDIUM_NOT_MEASURED


def test_the_settings_and_the_reading_switch_are_put_back_after_the_run(tmp_path, stand_in, monkeypatch):
    """The reading runs in this process, with the child switch off and the
    variant's settings in force; afterwards both are as they were - also
    after a run that raised."""
    monkeypatch.setattr(content_check, "READ_IN_A_CHILD", True)
    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    expectations = folder / EXPECTATIONS_FILENAME
    before = ocr.SETTINGS
    variants = grid((144, 300), (0.5,), (False,), ("small",))

    run_bench(folder, expectations, variants, out=io.StringIO())

    assert ocr.SETTINGS is before and content_check.READ_IN_A_CHILD is True
    assert [switch for _row, _settings, switch in stand_in.calls] == [False, False]
    assert [s.render_dpi for _row, s, _switch in stand_in.calls] == [144, 300]
    assert not process_scratch().exists()

    def boom(link, items, **_kwargs):
        raise RuntimeError("the reader fell over")

    monkeypatch.setattr(reader_bench, "route_file", boom)
    with pytest.raises(RuntimeError):
        run_bench(folder, expectations, variants, out=io.StringIO())
    assert ocr.SETTINGS is before and content_check.READ_IN_A_CHILD is True
    assert not process_scratch().exists()


def test_the_seconds_are_counted_per_page_and_against_the_ceiling(tmp_path, monkeypatch):
    """A two-page scan that took 14 s is 7 s a page, over the ceiling; a
    one-page scan at 3 s and a photo at 5 s are not. Per document the scans
    are 14 and 3; per page every document counts by its own pages."""
    seconds = {1: 14.0, 2: 3.0, 3: 5.0}

    def routed(link, items, **_kwargs):
        return Routing(path=link, identifier=None, reason="", seconds=seconds[int(link.parent.name)],
                       code=reasons.UNMATCHED_CODE)

    monkeypatch.setattr(reader_bench, "route_file", routed)
    monkeypatch.setattr(ocr, "warm_up", lambda: (ocr.DEVICE_PROCESSOR, ""))
    folder = a_corpus(tmp_path, [("scan2", "ten.pdf", ""), ("scan", "one.pdf", ""), ("photo", "pic.jpg", "")])

    code, report = run(tmp_path, folder, *SHIPPED_ONLY)

    assert code == 0 and CEILING_SECONDS_PER_PAGE == 6.0
    assert report["corpus"] == {"documents": 3, "text_layer": 0, "scans": 2, "photos": 1, "pages": 4}
    timing = report["variants"][0]["seconds"]
    assert timing["per_page_median"] == 5.0 and timing["per_page_worst"] == 7.0
    assert timing["scan_median"] == 8.5 and timing["scan_worst"] == 14.0
    assert timing["photo_median"] == 5.0 and timing["photo_worst"] == 5.0
    assert timing["over_ceiling"] == 1 and timing["first_load"] >= 0


def test_review_codes_counts_codes_and_prints_nothing_else(tmp_path, monkeypatch, capsys):
    """A made-up ``firm`` reply whose rows carry made-up names and reasons:
    the output is the code counts and nothing else."""
    reply = {
        "returns": [{"path": "/clients/Aardvark Holdings LLC/2025/1040 - Zebediah Quill", "name": "Zebediah Quill"}],
        "files": [
            {"return": "/clients/Aardvark Holdings LLC", "name": "Zebediah W-2.pdf", "code": "ocr-only",
             "suggestion": "Quillfeather 1099-INT"},
            {"return": "/clients/Aardvark Holdings LLC", "name": "Zebediah scan.pdf", "code": "ocr-only"},
            {"name": "Zebediah memo.pdf", "code": "unmatched", "reason": "Quillfeather matched no request"},
            {"name": "Zebediah odd.pdf", "code": "/clients/Aardvark Holdings LLC/odd"},
            {"name": "Zebediah none.pdf"},
        ],
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(reply)))
    out = tmp_path / "codes.json"

    assert main(["review-codes", OUT_FLAG, str(out)]) == 0

    printed = capsys.readouterr().out
    expected = {"ocr-only": 2, "other": 2, "unmatched": 1}
    assert json.loads(printed) == expected and json.loads(out.read_text(encoding="utf-8")) == expected
    for secret in (*SECRET_WORDS, "Quill", "clients"):
        assert secret not in printed and secret not in out.read_text(encoding="utf-8"), secret


def test_review_codes_names_what_is_wrong_with_a_reply_and_exits_2(monkeypatch, capsys):
    for text in ("not json at all", json.dumps({"returns": []}), json.dumps([1, 2])):
        monkeypatch.setattr(sys, "stdin", io.StringIO(text))
        assert main(["review-codes"]) == 2
        assert capsys.readouterr().err.startswith("reader bench: ")
    with pytest.raises(BacktestError):
        reader_bench.review_codes({"files": "no"})


# --------------------------------------------------------- the real reader ----


def test_a_real_scan_is_read_under_each_dpi_it_is_asked_for(tmp_path, capsys):
    """The real reader, one drawn image-only 1099-INT page, two variants:
    the shipped 144 dpi and 300. Each is measured and files the scan under
    its request, so the bench's in-process reading, the settings seam and the
    router's rule work together end to end."""
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    scanned_pdf(folder / CLIENT_FOLDER / "one.pdf", lines_1099_int("Harbor Test Bank", "John A. Smith", YEAR))

    code, report = run(tmp_path, folder, "--dpi", "144,300", "--floor", "0.5", "--delining", "off", "--tier", "small")

    assert code == 0, capsys.readouterr().err
    assert [v["name"] for v in report["variants"]] == ["dpi144-floor0.50-off-small", "dpi300-floor0.50-off-small"]
    for variant in report["variants"]:
        assert variant["measured"], variant
        assert variant["outcomes"] == {"right": 1, "parked_shortlist": 0, "parked_no_lead": 0, "wrong": 0}, variant
        assert variant["seconds"]["per_page_median"] > 0
    assert report["corpus"] == {"documents": 1, "text_layer": 0, "scans": 1, "photos": 0, "pages": 1}
