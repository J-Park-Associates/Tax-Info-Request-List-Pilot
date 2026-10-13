"""Tests for tools/reader_bench.py - the bench that measures the reader's
settings on the firm's own paper (P283, extended by P285 to the preparation
of a page).

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

import dataclasses
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
    ABLATIONS,
    BENCH_NOTE,
    CEILING_SECONDS_PER_PAGE,
    DPIS,
    FLOORS,
    MEDIUM_NOT_MEASURED,
    OUT_FLAG,
    PREPS,
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
SHIPPED_ONLY = ["--dpi", "300", "--floor", "0.5", "--prep", "prep", "--tier", "small", "--ablation", "off"]

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
            text_pdf(path, w2_lines("Jane Doe", "Harbor Test Co", YEAR), style="padded")
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


def test_the_grid_is_every_dpi_floor_preparation_and_tier_and_the_ablation(capsys):
    variants = grid()
    assert len(variants) == len(DPIS) * len(FLOORS) * len(PREPS) * len(TIERS) + len(ABLATIONS) == 21
    names = [variant.name for variant in variants]
    assert len(set(names)) == 21
    main_grid = {(v.settings.render_dpi, v.settings.confident_score, v.settings.deskew, v.settings.model_tier)
                 for v in variants[:-5]}
    assert main_grid == {(d, f, p == "prep", t) for d in DPIS for f in FLOORS for p in PREPS for t in TIERS}
    assert names[0] == "dpi300-floor0.50-prep-small"
    assert "dpi144-floor0.70-raw-medium" in names and "dpi300-floor0.50-prep-otsu-small" in names
    assert names[-5:] == [f"dpi300-floor0.50-prep-{ablation}-small" for ablation in ABLATIONS]
    assert main(["variants"]) == 0
    assert capsys.readouterr().out.splitlines() == names                 # one a line
    assert main(["variants", "--dpi", "144", "--tier", "small", "--ablation", "off"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "dpi300-floor0.50-prep-small", *[n for n in names[:-5] if n.startswith("dpi144") and n.endswith("small")]]


def test_the_shipped_variant_is_always_measured_first(tmp_path, stand_in):
    assert grid()[0].settings == ocr.SHIPPED and grid()[0].name == "dpi300-floor0.50-prep-small"
    left_out = grid((144,), (0.7,), ("raw",), ("small",), ablation=False)
    assert [v.name for v in left_out] == ["dpi300-floor0.50-prep-small", "dpi144-floor0.70-raw-small"]

    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    code, report = run(tmp_path, folder, "--dpi", "144", "--floor", "0.7", "--prep", "raw", "--tier", "small",
                       "--ablation", "off")
    assert code == 0
    assert [v["name"] for v in report["variants"]] == ["dpi300-floor0.50-prep-small", "dpi144-floor0.70-raw-small"]


def test_each_variants_long_side_holds_a_letter_page_at_its_dpi():
    assert [long_side(dpi) for dpi in DPIS] == [3300, 2000]
    for variant in grid():
        dpi = variant.settings.render_dpi
        assert variant.settings.max_side_len == max(2000, math.ceil(11 * dpi)) >= 11 * dpi
    assert grid()[0].settings.max_side_len == ocr.SHIPPED.max_side_len == 3300


def test_the_raw_variant_at_144_dpi_is_the_reading_before_p285():
    by_name = {variant.name: variant for variant in grid()}
    assert by_name["dpi144-floor0.50-raw-small"].settings == ocr.RAW
    assert by_name["dpi300-floor0.50-raw-small"].settings == dataclasses.replace(
        ocr.RAW, render_dpi=300, max_side_len=3300)           # P283's dpi300-floor0.50-off-small
    assert by_name["dpi144-floor0.50-prep-small"].settings == dataclasses.replace(
        ocr.SHIPPED, render_dpi=144, max_side_len=2000)


def test_each_ablation_row_turns_off_one_step_of_the_shipped_settings():
    by_name = {variant.name: variant.settings for variant in grid()}
    expected = {"no-deskew": {"deskew": False}, "no-binarize": {"binarize": "off"},
                "otsu": {"binarize": "otsu"}, "no-denoise": {"denoise": False},
                "no-delining": {"delining": False}}
    assert list(expected) == list(ABLATIONS)
    for ablation, change in expected.items():
        settings = by_name[f"dpi300-floor0.50-prep-{ablation}-small"]
        differs = {field.name for field in dataclasses.fields(ocr.ReaderSettings)
                   if getattr(settings, field.name) != getattr(ocr.SHIPPED, field.name)}
        assert differs == set(change), ablation
        assert settings == dataclasses.replace(ocr.SHIPPED, **change)


def test_ablation_off_leaves_the_ablation_rows_out():
    names = [variant.name for variant in grid(ablation=False)]
    assert len(names) == 16
    assert not any(f"prep-{ablation}-" in name for name in names for ablation in ABLATIONS)
    assert len(grid(DPIS, FLOORS, PREPS, ("small",), ablation=False)) == 8


def test_the_office_prompt_names_the_grid_its_first_variant_and_its_flags():
    """The prompt the office session follows says how many variants the grid
    has and which one is first, so a session whose ``variants`` prints
    anything else stops; it uses the flags the bench has and never the one
    P285 took away."""
    prompt = (REPO / "pilot" / "PROMPT-reader-bench.md").read_text(encoding="utf-8")
    variants = grid()

    assert f"the {len(variants)} names" in prompt
    assert f"check the first is {variants[0].name}" in prompt
    assert "--prep" in prompt and "--ablation" in prompt
    assert "--delining" not in prompt


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
    setting reaches the reader: at 300 dpi row 4 is read well and files, at
    144 it does not."""
    the_five_readings(stand_in)
    stand_in.pages[4] = lambda settings: GOOD_1099 if settings.render_dpi == 300 else NOTHING
    code, report = run(tmp_path, the_five_outcomes(tmp_path),
                       "--dpi", "144,300", "--floor", "0.5", "--prep", "prep", "--tier", "small",
                       "--ablation", "off")
    assert code == 0
    shipped, coarser = report["variants"]
    assert shipped["outcomes"] == {"right": 3, "parked_shortlist": 1, "parked_no_lead": 0, "wrong": 1}
    assert coarser["name"] == "dpi144-floor0.50-prep-small"
    assert coarser["outcomes"] == {"right": 2, "parked_shortlist": 1, "parked_no_lead": 1, "wrong": 1}


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

    code, report = run(tmp_path, folder, "--models", str(models), "--dpi", "300", "--floor", "0.5",
                       "--prep", "prep", "--ablation", "off")
    assert code == 0
    printed = capsys.readouterr()
    written = json.dumps(report) + (tmp_path / "report.json").read_text(encoding="utf-8")
    assert [v["measured"] for v in report["variants"]] == [True, True]       # small and medium both read
    assert report["note"] == BENCH_NOTE and report["schema"] == 2
    for secret in (*SECRET_WORDS, str(folder), str(models), "model_folder"):
        assert secret not in written, secret
        assert secret not in printed.out and secret not in printed.err, secret


def test_the_report_states_every_step_and_is_schema_2(tmp_path, stand_in):
    """A variant's settings are the fields that decide the reading - the dpi,
    the floor, the long side, each step of the preparation and the tier - and
    never the models folder."""
    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])

    code, report = run(tmp_path, folder, *SHIPPED_ONLY)

    assert code == 0 and report["schema"] == 2
    assert report["variants"][0]["settings"] == {
        "render_dpi": 300, "confident_score": 0.5, "max_side_len": 3300, "deskew": True,
        "binarize": "sauvola", "denoise": True, "delining": True, "model_tier": "small"}
    assert set(report["variants"][0]["settings"]) == {
        "render_dpi", "confident_score", "max_side_len", "deskew", "binarize", "denoise", "delining",
        "model_tier"}                                                  # never the models folder


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
    medium_name = "dpi300-floor0.50-prep-medium"
    flags = ["--dpi", "300", "--floor", "0.5", "--prep", "prep", "--ablation", "off"]

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

    code, report = run(tmp_path, folder, "--tier", "medium", "--dpi", "300", "--floor", "0.5", "--prep", "prep",
                       "--ablation", "off")

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
    variants = grid((144,), (0.5,), ("prep",), ("small",), ablation=False)

    run_bench(folder, expectations, variants, out=io.StringIO())

    assert ocr.SETTINGS is before and content_check.READ_IN_A_CHILD is True
    assert [switch for _row, _settings, switch in stand_in.calls] == [False, False]
    assert [s.render_dpi for _row, s, _switch in stand_in.calls] == [300, 144]
    assert not process_scratch().exists()

    def boom(*_args, **_kwargs):
        raise RuntimeError("the survey fell over")

    monkeypatch.setattr(reader_bench, "survey", boom)
    with pytest.raises(RuntimeError):
        run_bench(folder, expectations, variants, out=io.StringIO())
    assert ocr.SETTINGS is before and content_check.READ_IN_A_CHILD is True
    assert not process_scratch().exists()


def _route_failing_at(monkeypatch, failure, when):
    """``route_file`` as it is, except that under settings ``when`` accepts it
    raises ``failure``."""
    real = reader_bench.route_file

    def route(link, items, **kwargs):
        if when(ocr.SETTINGS):
            raise failure
        return real(link, items, **kwargs)

    monkeypatch.setattr(reader_bench, "route_file", route)


def test_a_variant_whose_reading_raises_is_unmeasured_and_the_run_goes_on(tmp_path, stand_in, monkeypatch, capsys):
    """The report is on disk after every variant, so the night survives one
    that fails. The raising one is recorded unmeasured with its exception's
    class and nothing of its message (which could carry a path); the ones
    either side of it are measured."""
    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    _route_failing_at(monkeypatch, MemoryError(str(tmp_path / "Zebediah")),
                      lambda settings: settings.render_dpi == 300 and not settings.deskew)

    code, report = run(tmp_path, folder, "--dpi", "300,144", "--floor", "0.5", "--prep", "prep,raw",
                       "--tier", "small", "--ablation", "off")

    assert code == 0
    assert [(v["name"], v["measured"]) for v in report["variants"]] == [
        ("dpi300-floor0.50-prep-small", True), ("dpi300-floor0.50-raw-small", False),
        ("dpi144-floor0.50-prep-small", True), ("dpi144-floor0.50-raw-small", True)]
    failed = next(v for v in report["variants"] if not v["measured"])
    assert "MemoryError" in failed["note"] and "Zebediah" not in failed["note"]
    printed = capsys.readouterr()
    assert "Zebediah" not in printed.out + printed.err


def test_a_ctrl_c_writes_the_report_so_far_and_exits_130_with_one_sentence(tmp_path, stand_in, monkeypatch, capsys):
    stand_in.pages = {1: GOOD_1099}
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    _route_failing_at(monkeypatch, KeyboardInterrupt(), lambda settings: settings.render_dpi == 144)
    monkeypatch.setattr(content_check, "READ_IN_A_CHILD", True)

    code, report = run(tmp_path, folder, "--dpi", "144,300", "--floor", "0.5", "--prep", "prep", "--tier", "small",
                       "--ablation", "off")

    assert code == 130
    assert [(v["name"], v["measured"]) for v in report["variants"]] == [("dpi300-floor0.50-prep-small", True)]
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and err.startswith("reader bench: interrupted")
    assert ocr.SETTINGS is ocr.SHIPPED and not process_scratch().exists()
    assert content_check.READ_IN_A_CHILD is True


def test_a_bad_catalog_is_named_by_its_row_number_and_never_by_its_value(tmp_path, stand_in, capsys):
    """An unquoted comma in a file name shifts the columns, so the catalog
    column can hold a piece of a client's file name: the sentence says the
    row, and the value is not in it."""
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02"), ("scan", "two.pdf", "A02")])
    path = folder / EXPECTATIONS_FILENAME
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[2] = lines[2].replace(",1040,", ",Zebediah W-2.pdf,")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert main(["run", str(folder), OUT_FLAG, str(tmp_path / "report.json"), *SHIPPED_ONLY]) == 2

    err = capsys.readouterr().err
    assert "row 2" in err and "Zebediah" not in err and ".pdf" not in err
    assert stand_in.calls == []


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
    """A made-up ``firm`` reply, behind two count lines, whose rows carry
    made-up names and reasons: the output is the code counts and nothing
    else."""
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
    from tracker import progress
    stdout = (progress.count_line(0, 50) + progress.count_line(25, 50) + json.dumps(reply) + "\n").encode()
    monkeypatch.setattr(reader_bench, "_run_firm", lambda: a_firm_run(stdout))
    out = tmp_path / "codes.json"

    assert main(["review-codes", OUT_FLAG, str(out)]) == 0

    printed = capsys.readouterr().out
    expected = {"ocr-only": 2, "other": 2, "unmatched": 1}
    assert json.loads(printed) == expected and json.loads(out.read_text(encoding="utf-8")) == expected
    for secret in (*SECRET_WORDS, "Quill", "clients"):
        assert secret not in printed and secret not in out.read_text(encoding="utf-8"), secret


def test_review_codes_names_what_is_wrong_with_a_reply_and_exits_2(monkeypatch, capsys):
    for text in ("not json at all", json.dumps({"returns": []}), json.dumps([1, 2])):
        monkeypatch.setattr(reader_bench, "_run_firm", lambda text=text: a_firm_run(text.encode() + b"\n"))
        assert main(["review-codes"]) == 2
        assert capsys.readouterr().err.startswith("reader bench: ")
    with pytest.raises(BacktestError):
        reader_bench.review_codes({"files": "no"})


# --------------------------------------------------------- the real reader ----


def test_a_real_scan_is_read_under_each_dpi_it_is_asked_for(tmp_path, capsys):
    """The real reader, one drawn image-only 1099-INT page, three variants:
    the shipped one (prepared, 300 dpi), then the raw reading at 300 and at
    144. Each is measured and files the scan under its request, so the bench's
    in-process reading, the settings seam and the router's rule work together
    end to end."""
    folder = a_corpus(tmp_path, [("scan", "one.pdf", "A02")])
    scanned_pdf(folder / CLIENT_FOLDER / "one.pdf", lines_1099_int("Harbor Test Bank", "John A. Smith", YEAR))

    code, report = run(tmp_path, folder, "--dpi", "144,300", "--floor", "0.5", "--prep", "raw", "--tier", "small",
                       "--ablation", "off")

    assert code == 0, capsys.readouterr().err
    assert [v["name"] for v in report["variants"]] == [
        "dpi300-floor0.50-prep-small", "dpi300-floor0.50-raw-small", "dpi144-floor0.50-raw-small"]
    for variant in report["variants"]:
        assert variant["measured"], variant
        assert variant["outcomes"] == {"right": 1, "parked_shortlist": 0, "parked_no_lead": 0, "wrong": 0}, variant
        assert variant["seconds"]["per_page_median"] > 0
    assert report["corpus"] == {"documents": 1, "text_layer": 0, "scans": 1, "photos": 0, "pages": 1}


# ------------------------------------------- review-codes asks firm itself ----
# (P286, pilot/SPEC-review-codes-pipe.md). No test starts a real firm: a child
# of the suite's environment without child_env() is an unarmed child to the
# tripwire. The reply bytes are made with progress.count_line, the format's
# only encoder.


def a_firm_run(stdout: bytes = b"", stderr: bytes = b"", code: int = 0):
    """What `_run_firm` returns: a finished process with made-up output."""
    import subprocess
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


def a_reply(files=None) -> bytes:
    """A made-up firm reply as one stdout line, rows carrying made-up names."""
    rows = [{"name": "Zebediah memo.pdf", "code": "unmatched", "reason": "Quillfeather matched nothing"}]
    return (json.dumps({"files": rows if files is None else files}) + "\n").encode()


def counts_of(monkeypatch, capsys, run_result, *args):
    """Run `review-codes` with `_run_firm` returning (or raising) `run_result`."""
    def fake():
        if isinstance(run_result, BaseException):
            raise run_result
        return run_result
    monkeypatch.setattr(reader_bench, "_run_firm", fake)
    code = main(["review-codes", *args])
    seen = capsys.readouterr()
    return code, seen.out, seen.err


def test_the_reply_is_the_last_stdout_line_without_the_progress_key(monkeypatch, capsys):
    from tracker import progress
    stdout = (progress.count_line(0, 9) + json.dumps({"note": "an earlier line"}) + "\n"
              + a_reply().decode() + progress.count_line(9, 9)).encode()

    code, out, err = counts_of(monkeypatch, capsys, a_firm_run(stdout))

    assert code == 0 and json.loads(out) == {"unmatched": 1} and err == ""


def test_count_lines_before_the_reply_are_ignored_however_many(monkeypatch, capsys):
    from tracker import progress
    for how_many in (0, 2, 5):
        for ending in ("\n", "\r\n"):
            counts = "".join(progress.count_line(done, 100).rstrip("\n") + ending for done in range(how_many))
            stdout = (counts + a_reply().decode().rstrip("\n") + ending + ending).encode()
            code, out, _ = counts_of(monkeypatch, capsys, a_firm_run(stdout))
            assert code == 0 and json.loads(out) == {"unmatched": 1}, (how_many, ending)


def test_no_reply_or_a_reply_that_is_not_json_is_named_without_echoing_the_line(monkeypatch, capsys):
    from tracker import progress
    cases = [
        (b"", reader_bench.FIRM_NO_REPLY.format(code=0)),
        (progress.count_line(0, 3).encode(), reader_bench.FIRM_NO_REPLY.format(code=0)),
        (b"Zebediah Quillfeather says hello\n", reader_bench.FIRM_NOT_AN_OBJECT.format(code=0)),
        (b"[1, 2, \"Zebediah\"]\n", reader_bench.FIRM_NOT_AN_OBJECT.format(code=0)),
        (b"\xff\xfe Zebediah\n", reader_bench.FIRM_NOT_AN_OBJECT.format(code=0)),
    ]
    for stdout, sentence in cases:
        code, out, err = counts_of(monkeypatch, capsys, a_firm_run(stdout))
        assert code == 2 and out == "" and err == f"reader bench: {sentence}\n", stdout
        assert "Zebediah" not in err and "Quillfeather" not in err


def test_a_refused_reply_is_said_by_its_kind_and_never_by_its_sentence(monkeypatch, capsys):
    from tracker import progress
    sentence = "Cannot walk /clients/Aardvark Holdings LLC for Zebediah Quill: held by Quillfeather"
    cases = [(json.dumps(progress.failure_reply(sentence, kind)), 1, kind) for kind in progress.FAILURE_KINDS]
    cases += [
        (json.dumps({"error": sentence, "failure": {"sentence": sentence, "kind": "made-up"}}), 1, "unknown"),
        (json.dumps({"error": sentence}), 0, "unknown"),
        (json.dumps({"files": []}), 1, "unknown"),     # exit 1 with no failure at all
    ]
    for text, exit_code, kind in cases:
        code, out, err = counts_of(monkeypatch, capsys, a_firm_run(text.encode() + b"\n", code=exit_code))
        assert code == 2 and out == "", text
        assert err == "reader bench: " + reader_bench.FIRM_REFUSED.format(kind=kind, code=exit_code) + "\n", text
        for secret in (*SECRET_WORDS, "Quill", "clients"):
            assert secret not in err, secret


def test_firm_is_started_with_stdin_closed_and_the_current_environment(monkeypatch, capsys):
    import subprocess

    from tracker import runner
    seen = {}

    def recorded(command, **kwargs):
        seen["command"], seen["kwargs"] = command, kwargs
        return a_firm_run(a_reply())

    monkeypatch.setattr(subprocess, "run", recorded)

    assert main(["review-codes"]) == 0 and json.loads(capsys.readouterr().out) == {"unmatched": 1}
    assert seen["command"] == [sys.executable, "-m", "tracker.api", runner.FIRM_COMMAND]
    kwargs = seen["kwargs"]
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["capture_output"] is True and "stdout" not in kwargs and "stderr" not in kwargs, \
        "stdout and stderr are both kept (capture_output is subprocess's own spelling of PIPE for both)"
    assert "env" not in kwargs, "the current environment, not a copy"
    assert kwargs["cwd"] == reader_bench.ROOT and (reader_bench.ROOT / "tracker").is_dir()
    assert kwargs["timeout"] == runner.FILL_TIME_LIMIT_SECONDS
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_a_firm_that_runs_too_long_or_cannot_start_is_said_by_kind(monkeypatch, capsys):
    import subprocess

    from tracker import errors, runner

    def raising(error):
        def run(*_args, **_kwargs):
            raise error
        return run

    monkeypatch.setattr(subprocess, "run", raising(subprocess.TimeoutExpired("Zebediah", 300)))
    assert main(["review-codes"]) == 2
    minutes = runner.FILL_TIME_LIMIT_SECONDS // 60
    assert capsys.readouterr().err == "reader bench: " + reader_bench.FIRM_TOO_LONG.format(minutes=minutes) + "\n"

    failure = PermissionError(13, "Zebediah's folder")
    monkeypatch.setattr(subprocess, "run", raising(failure))
    assert main(["review-codes"]) == 2
    err = capsys.readouterr().err
    assert err == "reader bench: " + reader_bench.FIRM_NOT_STARTED.format(kind=errors.error_class(failure)) + "\n"
    assert "PermissionError" in err and "Zebediah" not in err


def test_what_firm_wrote_on_stderr_is_counted_and_never_shown(monkeypatch, capsys):
    noise = b"Traceback: Zebediah Quillfeather\n  File /clients/Aardvark Holdings LLC\n\n"
    refused = a_firm_run(b"Zebediah\n", noise, code=1)

    code, out, err = counts_of(monkeypatch, capsys, refused)

    assert code == 2 and out == ""
    assert err == ("reader bench: " + reader_bench.FIRM_NOT_AN_OBJECT.format(code=1)
                   + reader_bench.FIRM_STDERR_ON_FAILURE.format(lines="2 lines") + "\n")
    assert err.endswith("(it also wrote 2 lines on stderr, not shown)\n")

    code, out, err = counts_of(monkeypatch, capsys, a_firm_run(a_reply(), noise))

    assert code == 0 and json.loads(out) == {"unmatched": 1}
    assert err == "reader bench: the firm command also wrote 2 lines on stderr, not shown\n"
    for secret in (*SECRET_WORDS, "Quill", "clients", "Traceback"):
        assert secret not in out and secret not in err, secret

    one = b"Traceback: Hieronymus Wigglesworth\n\n"
    no_files = a_firm_run(b'{"returns": []}\n', one)

    code, out, err = counts_of(monkeypatch, capsys, no_files)

    assert code == 2 and out == ""
    assert err == "reader bench: the firm command's reply holds no list of files (it also wrote 1 line on stderr, not shown)\n"
    for secret in ("Hieronymus", "Wigglesworth", "Traceback"):
        assert secret not in out and secret not in err, secret

    code, out, err = counts_of(monkeypatch, capsys, a_firm_run(a_reply(), one))

    assert code == 0 and err == "reader bench: the firm command also wrote 1 line on stderr, not shown\n"


def test_review_codes_never_reads_its_own_stdin(monkeypatch, capsys):
    class Unreadable:
        def read(self, *_args):
            raise AssertionError("review-codes read its own stdin")

        readline = readlines = __iter__ = read

    monkeypatch.setattr(sys, "stdin", Unreadable())

    code, out, _ = counts_of(monkeypatch, capsys, a_firm_run(a_reply()))

    assert code == 0 and json.loads(out) == {"unmatched": 1}


def test_review_codes_refuses_an_out_inside_the_repository_before_firm_starts(monkeypatch, capsys):
    def never():
        raise AssertionError("firm was started")

    monkeypatch.setattr(reader_bench, "_run_firm", never)

    assert main(["review-codes", OUT_FLAG, str(REPO / "codes.json")]) == 2
    assert capsys.readouterr().err.startswith("reader bench: ")


def test_the_usage_names_no_pipe(capsys):
    where = [(reader_bench.__doc__ or "", "the bench's docstring"),
             *((( REPO / name).read_text(encoding="utf-8"), name)
               for name in ("docs/tools.md", "pilot/PROMPT-reader-bench.md", "pilot/mactest/PROMPT-OCR-SCANS.md"))]
    for text, name in where:
        named = [line for line in text.splitlines() if "review-codes" in line]
        assert named, name
        for line in named:
            assert "|" not in line, (name, line)
    with pytest.raises(SystemExit):
        main(["--help"])
    helped = capsys.readouterr().out
    assert "review-codes" in helped and "stdin" not in helped
