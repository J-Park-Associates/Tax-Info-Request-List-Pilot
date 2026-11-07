"""Tests for tracker/ocr.py - the reader (decision 169).

Two kinds of claim. The reading claims run the **real** engine on the
processor - RapidOCR and its shipped models - over pages drawn here with
Pillow: no binary is committed and no client's document is near the suite.
The graphics card claims cannot run on the real card (CI has none), so the
card's engine is a fake that says which providers its sessions got and
fails the way a card that has faulted fails; everything around it - the
pack, the self-test, the switch to the processor, the run log and the
pass's warning - is the real code.

The few claims here that reach the reading's child reach it through
content_check, as the pass does: a real child process, with the stand-in
readers of tests/child_readers.py and the stops patched down to seconds. The
child's own tests - one child per pass, the card in a real child, the memory
watch, the awake clock and the scratch - are tests/test_reader_child.py's
(P338): the tests whose highest home is the module they left for.
"""

from __future__ import annotations

import datetime as dt
import socket
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import ocr_helpers
from tests.builders import make_engagement
from tests.children import CRASHED, STOPPED, eventually, no_child_left, running
from tests.ocr_helpers import PAGE_WORDS, FakeEngine
from tests.samples import scanned_pdf, text_pdf
from tracker import content_check, ocr, reader_child, reasons, verdicts
from tracker.content_check import check_content, extract
from tracker.keywords import contains_keyword
from tracker.manifest import RequestItem

W2_WORDS = ["Form W-2 Wage and Tax Statement 2025",
            "b Employer identification number (EIN)",
            "1 Wages, tips, other compensation"]


def w2_scan(path: Path) -> Path:
    """A one-page scanned W-2: no text layer, only pixels."""
    return scanned_pdf(path, W2_WORDS)


def w2_photo(path: Path, *, turn: int = 0) -> Path:
    """A photo of a W-2's head, turned ``turn`` degrees in its pixels."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1100, 260), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(W2_WORDS):
        draw.text((30, 30 + 70 * i), line, font=ImageFont.load_default(size=40), fill="black")
    if turn:
        image = image.rotate(turn, expand=True, fillcolor="white")
    image.save(path)
    return path


# ------------------------------------------------------ the real reader ----


def test_a_scan_is_read_by_rapidocr(tmp_path):
    """A PDF with no text layer is read by the reader shipped in the app,
    on the processor, and the reading is OCR's (``from_ocr``: decision 50's
    stricter rule still applies to it)."""
    scan = w2_scan(tmp_path / "scan.pdf")

    assert extract(scan, ocr=False).needs_ocr                     # no words without the reader
    reading = extract(scan)
    assert reading.from_ocr and not reading.transient, reading.reason
    assert contains_keyword(reading.text, "wage and tax statement")
    assert contains_keyword(reading.text, "employer identification number")
    rules = RequestItem(identifier="A01", document="W-2", required_keywords=("W-2", "wage and tax statement"))
    assert check_content(scan, rules).ok


def test_a_real_scan_whose_title_shows_1099_int_files_on_the_rows_looser_keywords(tmp_path):
    """P282 end to end with the real reader: an image-only PDF drawn with a
    made-up 1099-INT is read by RapidOCR, its title shows the form number a
    request accepts on its looser keywords, and it files under that request
    with the scan sentence instead of parking as Read From Scan Only. The
    same page turned a quarter must never misfile under the 1098 request: it
    files the 1099-INT row or parks with it on the shortlist - whether the
    reader scrambles a particular page's title is the reader's, not the
    rule's."""
    from tests.samples import lines_1099_int
    from tracker.router import MATCHED_FROM_SCAN, route_file

    interest = RequestItem(identifier="A02", document="1099-INT", period="TY2025",
                           allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("1099-int",))
    mortgage = RequestItem(identifier="C01", document="1098", period="TY2025",
                           allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("1098",))
    lines = lines_1099_int("Harbor Test Bank", "John A. Smith", 2025)

    upright = scanned_pdf(tmp_path / "scan 0001.pdf", lines)
    routing = route_file(upright, [interest, mortgage])
    assert routing.identifier == "A02", routing.reason
    assert routing.reason == MATCHED_FROM_SCAN and routing.code == reasons.MATCHED_CODE

    sideways = scanned_pdf(tmp_path / "scan 0002.pdf", lines, rotate=90)
    routed = route_file(sideways, [interest, mortgage])
    assert routed.identifier in (None, "A02"), routed.reason
    assert "C01" not in routed.candidates and routed.identifier != "C01"


def test_a_photo_is_read_by_rapidocr(tmp_path):
    """A photo takes the scan's path: read by the same reader, from_ocr."""
    for name in ("w-2.png", "w-2.jpg"):
        reading = extract(w2_photo(tmp_path / name))
        assert reading.from_ocr, (name, reading.reason)
        assert contains_keyword(reading.text, "wage and tax statement"), name


def test_a_sideways_page_keeps_its_words(tmp_path, monkeypatch):
    """Ruling 6 as re-ruled: RapidOCR turns tall crops and flips upside-down
    ones itself, so a page photographed a quarter turn or a half turn round
    keeps the words its keywords are found in. Nothing turns the page: the
    engine is handed the pixels as they stand. (What such a page loses is
    the order of its lines - the gap the amendment "169, upright" closes.)"""
    from PIL import Image

    handed = []
    real = ocr._pixels
    monkeypatch.setattr(ocr, "_pixels", lambda image: handed.append(image.size) or real(image))
    for turn in (90, 180):
        picture = w2_photo(tmp_path / f"turned {turn}.png", turn=turn)
        reading = extract(picture)
        assert reading.from_ocr, (turn, reading.reason)
        assert contains_keyword(reading.text, "wage and tax statement"), (turn, reading.text)
        assert contains_keyword(reading.text, "W-2"), (turn, reading.text)
        assert handed[-1] == Image.open(picture).size             # not turned
    assert handed[0][1] > handed[0][0]                              # the quarter turn stayed tall


def test_a_full_read_opens_no_socket_writes_no_temporary_file_and_fetches_nothing(tmp_path, monkeypatch):
    """Decision 169, rulings 1 and 8. RapidOCR imports ``requests`` for a
    model downloader; the reader names every model by path and replaces the
    downloader with a refusal, so a whole reading - the engine built from
    nothing, a page read - opens no socket. And it writes no temporary file,
    which is why decision 137's scratch folder for OCR is gone."""
    import rapidocr.utils.download_file as download_file

    monkeypatch.setattr(ocr, "_ENGINE", None)                      # the engine's build is in the claim
    monkeypatch.setattr(ocr, "_DEVICE", "")
    monkeypatch.setattr(download_file.DownloadFile, "run", download_file.DownloadFile.run)
    scan = w2_scan(tmp_path / "scan.pdf")
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporary))
    for name in ("TMP", "TEMP", "TMPDIR"):
        monkeypatch.setenv(name, str(temporary))

    class NoSocket(socket.socket):
        def __init__(self, *args, **kwargs):
            raise AssertionError("the reader opened a socket")

    monkeypatch.setattr(socket, "socket", NoSocket)
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: pytest.fail("the reader opened a connection"))
    reading = extract(scan)

    assert reading.from_ocr and contains_keyword(reading.text, "wage and tax statement")
    assert list(temporary.iterdir()) == []
    with pytest.raises(ocr.ReaderUnavailable, match="nothing is fetched"):
        download_file.DownloadFile.run(SimpleNamespace(file_url="https://example.invalid/model.onnx"))


def test_a_missing_model_means_the_reader_cannot_run_and_the_scan_waits(tmp_path, monkeypatch):
    """Ruling 9: the reader ships inside the app, so "cannot run" is a
    model missing or broken - the machine's fault, transient, never kept,
    and never a download. The sentence is reader-neutral."""
    monkeypatch.setattr(ocr, "_ENGINE", None)
    monkeypatch.setattr(ocr, "models_folder", lambda: tmp_path / "no models here")
    scan = w2_scan(tmp_path / "scan.pdf")

    reading = extract(scan)
    assert reading.text is None and reading.transient
    assert reading.code == reasons.NO_TEXT_LAYER.code
    assert "the reader could not run on this machine" in reading.reason
    assert "OCR is not installed" not in reading.reason


def test_the_reader_switches_its_librarys_telemetry_off_before_any_session(monkeypatch):
    """P263: ONNX Runtime's macOS wheel carries a telemetry client with an HTTP path, and nothing
    in the reader's path talks to the network. Building the engine tells the library to send
    none, once, before the logger is set and before any session is made. The models are real
    and the build is real; only the library's two functions are recorders around the real ones."""
    import onnxruntime

    seen = []
    real_severity = onnxruntime.set_default_logger_severity
    monkeypatch.setattr(onnxruntime, "disable_telemetry_events", lambda: seen.append("telemetry off"))
    monkeypatch.setattr(onnxruntime, "set_default_logger_severity",
                        lambda level: seen.append("logger") or real_severity(level))

    ocr._build_engine(cuda=False)

    assert seen[:2] == ["telemetry off", "logger"] and seen.count("telemetry off") == 1


def test_a_library_without_the_telemetry_switch_is_said_as_unavailable(monkeypatch):
    """P263: a wheel that cannot be told to send nothing is not run; the reader says so, loudly,
    like a missing import, and no engine is built."""
    import onnxruntime

    monkeypatch.delattr(onnxruntime, "disable_telemetry_events")

    with pytest.raises(ocr.ReaderUnavailable, match="disable_telemetry_events"):
        ocr._build_engine(cuda=False)


def test_the_graphics_cards_way_in_switches_telemetry_off_before_it_loads_anything(monkeypatch, tmp_path):
    """P263: the card's engine imports the library on its own path (``_on_the_card``), and the
    switch is thrown there too, before the pack's libraries are loaded."""
    import onnxruntime

    loaded = []
    monkeypatch.setattr(onnxruntime, "preload_dlls", lambda **kwargs: loaded.append(kwargs))
    monkeypatch.delattr(onnxruntime, "disable_telemetry_events")

    with pytest.raises(ocr.ReaderUnavailable, match="disable_telemetry_events"):
        ocr._on_the_card(tmp_path)

    assert loaded == []


def _box(left, top, right, bottom):
    return [(left, top), (right, top), (right, bottom), (left, bottom)]


def test_the_lines_are_built_from_the_boxes_in_reading_order():
    """The seam of ruling 6 builds lines only: boxes on one line (centres
    within half a typical height) join left to right, lines run top to
    bottom, and nothing is turned. What is dropped is the boxes under the
    confidence floor (the next claims) and blank text."""
    result = SimpleNamespace(
        boxes=[_box(300, 100, 400, 120), _box(10, 10, 100, 30), _box(110, 12, 200, 32),
               _box(10, 102, 90, 121), _box(10, 200, 50, 220)],
        txts=("second-right", "first-left", "first-right", "second-left", "  "),
        scores=(0.99, 0.99, 0.99, 0.99, 0.99))
    assert ocr._upright_lines(result) == ["first-left first-right", "second-left second-right"]
    assert ocr._upright_lines(SimpleNamespace(boxes=None, txts=None)) == []


def test_a_box_under_the_confidence_floor_is_not_read():
    """P282's guard 2, made the product's own number: a box the reader
    scored under ``CONFIDENT_SCORE`` is dropped before the lines are built,
    so a doubtful word can never be what files a document."""
    result = SimpleNamespace(
        boxes=[_box(10, 10, 100, 30), _box(10, 60, 100, 80)],
        txts=("Form 1099-INT", "Form 1098"),
        scores=(0.99, ocr.CONFIDENT_SCORE - 0.01))
    assert ocr._upright_lines(result) == ["Form 1099-INT"]


def test_a_box_at_the_confidence_floor_is_read():
    """The floor is inclusive: a score of exactly ``CONFIDENT_SCORE`` is read."""
    result = SimpleNamespace(
        boxes=[_box(10, 10, 100, 30)], txts=("Form 1099-INT",), scores=(ocr.CONFIDENT_SCORE,))
    assert ocr._upright_lines(result) == ["Form 1099-INT"]


def test_a_reading_without_confidence_scores_fails_loudly():
    """rapidocr always gives one score per box; a reading that silently
    skipped the floor would file on words the floor exists to drop."""
    result = SimpleNamespace(boxes=[_box(10, 10, 100, 30)], txts=("Form 1099-INT",), scores=None)
    with pytest.raises(ValueError, match="no confidence scores"):
        ocr._upright_lines(result)


# ------------------------------------------- the reader's settings (P283, P285) ----


@pytest.fixture
def own_settings():
    """The reader's settings as the test found them, put back after it (the
    engine is let go with them): a test that tries other settings leaves
    nothing for the next."""
    previous = ocr.SETTINGS
    try:
        yield
    finally:
        ocr.use_settings(previous)


class RecordedEngine:
    """Stands in for ``rapidocr.RapidOCR``: records the params it is built with."""

    built: list[dict] = []

    def __init__(self, params=None):
        type(self).built.append(dict(params or {}))


@pytest.fixture
def recorded_engines(monkeypatch):
    """``rapidocr.RapidOCR`` replaced by a recorder, and the list it fills."""
    import rapidocr

    RecordedEngine.built = []
    monkeypatch.setattr(rapidocr, "RapidOCR", RecordedEngine)
    return RecordedEngine.built


def test_the_shipped_settings_are_the_prepared_reading_at_300_dpi():
    """P285: the product reads a page drawn at 300 dpi and prepared (turned
    level, black and white by Sauvola, cleared of specks and of box rules),
    with the 0.5 floor and the small models; this process reads with them.
    ``RAW`` is the reading P283 shipped: 144 dpi, floor 0.5, long side 2000,
    every step off."""
    assert ocr.SHIPPED == ocr.ReaderSettings(
        render_dpi=300, confident_score=0.5, max_side_len=3300, deskew=True, binarize="sauvola",
        denoise=True, delining=True, model_tier="small", model_folder="")
    assert ocr.SETTINGS is ocr.SHIPPED
    assert ocr.SHIPPED.confident_score == ocr.CONFIDENT_SCORE
    assert ocr.RAW == ocr.ReaderSettings()
    assert (ocr.RAW.render_dpi, ocr.RAW.confident_score, ocr.RAW.max_side_len) == (144, 0.5, 2000)
    assert not (ocr.RAW.deskew or ocr.RAW.denoise or ocr.RAW.delining) and ocr.RAW.binarize == "off"
    assert ocr.BINARIZERS == ("off", "otsu", "sauvola")


def test_the_engine_is_built_with_the_settings_floor_and_long_side(recorded_engines, own_settings):
    """With the shipped settings the params carry the floor 0.5, the long side
    of a letter page at 300 dpi (3300, P285), the detector held to its own
    2000-pixel copy (``Det.limit_type`` ``max``, so a 3300 page is not
    detected whole and the process stays under the reading child's 4 GB),
    and the three shipped model paths; with other settings, theirs."""
    folder = ocr.models_folder()
    ocr._build_engine(cuda=False)
    shipped = recorded_engines[-1]
    assert shipped["Global.text_score"] == 0.5 and shipped["Global.max_side_len"] == 3300
    assert shipped["Det.limit_type"] == "max" and "Det.limit_side_len" not in shipped
    assert shipped["Det.model_type"].value == "small" and shipped["Rec.model_type"].value == "small"
    assert shipped["Det.model_path"] == str(folder / ocr.DETECTION_MODEL)
    assert shipped["Rec.model_path"] == str(folder / ocr.RECOGNITION_MODEL)
    assert shipped["Cls.model_path"] == str(folder / ocr.DIRECTION_MODEL)

    ocr.use_settings(ocr.ReaderSettings(render_dpi=144, confident_score=0.7, max_side_len=2000))
    ocr._build_engine(cuda=False)
    other = recorded_engines[-1]
    assert other["Global.text_score"] == 0.7 and other["Global.max_side_len"] == 2000
    assert other["Det.model_path"] == shipped["Det.model_path"]       # the same small models


def test_the_medium_tier_reads_its_models_from_the_folder_it_is_given(tmp_path, recorded_engines, own_settings):
    """The medium models are never shipped: the tier's detection and
    recognition files come from the folder the bench was given, and the
    direction model is still the app's own."""
    medium_det, medium_rec = ocr.MODEL_TIERS["medium"]
    for name in (medium_det, medium_rec):
        (tmp_path / name).write_bytes(b"")
    ocr.use_settings(ocr.ReaderSettings(model_tier="medium", model_folder=str(tmp_path)))

    ocr._build_engine(cuda=False)

    params = recorded_engines[-1]
    assert params["Det.model_path"] == str(tmp_path / medium_det)
    assert params["Rec.model_path"] == str(tmp_path / medium_rec)
    assert params["Cls.model_path"] == str(ocr.models_folder() / ocr.DIRECTION_MODEL)
    assert params["Det.model_type"].value == "medium" and params["Rec.model_type"].value == "medium"


def test_the_medium_tier_without_its_models_is_unavailable_and_fetches_nothing(
        tmp_path, recorded_engines, own_settings):
    """No folder, or a folder missing one file: the reader says which model
    is missing, builds nothing, and rapidocr's downloader - replaced by a
    refusal before any engine is built - is never reached, so the sentence
    is a missing model and never a request to fetch one."""
    medium_det, medium_rec = ocr.MODEL_TIERS["medium"]
    ocr.use_settings(ocr.ReaderSettings(model_tier="medium"))
    with pytest.raises(ocr.ReaderUnavailable, match=f"the model {medium_det} is missing") as raised:
        ocr._build_engine(cuda=False)
    assert "download" not in str(raised.value)

    (tmp_path / medium_det).write_bytes(b"")
    ocr.use_settings(ocr.ReaderSettings(model_tier="medium", model_folder=str(tmp_path)))
    with pytest.raises(ocr.ReaderUnavailable, match=f"the model {medium_rec} is missing") as raised:
        ocr._build_engine(cuda=False)
    assert "download" not in str(raised.value)
    assert recorded_engines == []


def test_using_other_settings_drops_the_built_engine_and_says_what_it_replaced(monkeypatch, own_settings):
    other = ocr.ReaderSettings(render_dpi=200)
    monkeypatch.setattr(ocr, "_ENGINE", object())
    monkeypatch.setattr(ocr, "_DEVICE", ocr.DEVICE_PROCESSOR)

    assert ocr.use_settings(other) is ocr.SHIPPED
    assert ocr.SETTINGS is other
    assert ocr._ENGINE is None and ocr._DEVICE == ""
    assert ocr.use_settings(ocr.SHIPPED) is other


def test_unknown_settings_are_refused(own_settings):
    """An unknown tier, an unknown way to make a page black and white, a dpi
    under 72 and a floor outside 0-1 are refused before anything changes."""
    for settings in (ocr.ReaderSettings(model_tier="large"), ocr.ReaderSettings(binarize="adaptive"),
                     ocr.ReaderSettings(render_dpi=71),
                     ocr.ReaderSettings(confident_score=-0.01), ocr.ReaderSettings(confident_score=1.01)):
        with pytest.raises(ValueError):
            ocr.use_settings(settings)
        assert ocr.SETTINGS is ocr.SHIPPED
    ocr.use_settings(ocr.ReaderSettings(render_dpi=72, confident_score=1.0))     # the edges are allowed


def test_the_floor_follows_the_settings(own_settings):
    """A box scored 0.6 is read at the shipped 0.5 floor and dropped when
    the settings ask for 0.7."""
    result = SimpleNamespace(boxes=[_box(10, 10, 100, 30), _box(10, 60, 100, 80)],
                             txts=("Form 1099-INT", "Box one"), scores=(0.99, 0.6))
    assert ocr._upright_lines(result) == ["Form 1099-INT", "Box one"]
    ocr.use_settings(ocr.ReaderSettings(confident_score=0.7))
    assert ocr._upright_lines(result) == ["Form 1099-INT"]


def test_delining_removes_long_rules_and_keeps_the_words():
    """A letter page at 200 dpi drawn in memory: a full-width rule, a
    full-height rule and a line of text crossing neither. After ``delined``
    the rules' rows and columns are white away from the text, the text's ink
    is still there, the size is unchanged and the page it was given is not."""
    import numpy
    from PIL import Image, ImageDraw, ImageFont

    page = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(page)
    draw.rectangle((0, 1100, 1699, 1102), fill="black")             # a rule across the page
    draw.rectangle((900, 0, 902, 2199), fill="black")               # a rule down the page
    draw.text((100, 200), "Wage and Tax Statement 2025", font=ImageFont.load_default(size=30), fill="black")
    before = numpy.asarray(page).copy()
    ink_before = int((before[150:300, 80:700, 0] < 128).sum())
    assert ink_before > 0

    cleaned = ocr.delined(page)

    after = numpy.asarray(cleaned)
    assert cleaned.size == page.size and cleaned.mode == "RGB"
    assert (after[1101, :, :] >= 250).all()                         # the rule's row, every column
    assert (after[:, 901, :] >= 250).all()                          # the rule's column, every row
    assert int((after[150:300, 80:700, 0] < 128).sum()) >= 0.9 * ink_before
    assert (numpy.asarray(page) == before).all()                    # the page given is untouched


@pytest.mark.parametrize("thickness", [1, 2, 3])
def test_delining_rejoins_a_letter_a_rule_crossed(thickness):
    """A letter page at 144 dpi drawn in memory: a full-width rule of 1, 2 or
    3 px, a 4 px wide, 25 px tall stroke crossing it, and a mid-grey block
    touching neither. After ``delined`` every pixel of the stroke's columns
    is black from top to bottom (the cut a rule and the growth's margin made
    is bridged), the rule's row is white away from the stroke, and the grey
    block still reads mid-grey: the repair touched nothing outside the rule."""
    import numpy
    from PIL import Image, ImageDraw

    page = Image.new("RGB", (1224, 1584), "white")
    draw = ImageDraw.Draw(page)
    rule_top = 800
    draw.rectangle((0, rule_top, 1223, rule_top + thickness - 1), fill="black")
    stroke_top = rule_top + thickness // 2 - 12
    draw.rectangle((300, stroke_top, 303, stroke_top + 24), fill="black")
    draw.rectangle((600, 300, 619, 319), fill=(128, 128, 128))        # glyph-sized, so not a rule

    after = numpy.asarray(ocr.delined(page))

    assert (after[stroke_top:stroke_top + 25, 300:304, 0] < 64).all()
    assert (after[rule_top:rule_top + thickness, 400:1223, :] >= 250).all()
    assert (abs(after[300:320, 600:620, 0].astype(int) - 128) <= 8).all()


# ------------------------------------------------- the stage (P285) ----

LETTER_300 = (2550, 3300)         # a letter page at 300 dpi, width by height


def a_page_of(lines, size=LETTER_300, *, font_size=60, spacing=104):
    """A white page with ``lines`` drawn in black, in memory."""
    from PIL import Image, ImageDraw, ImageFont

    page = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default(size=font_size)
    for i, line in enumerate(lines):
        draw.text((160, 180 + spacing * i), line, font=font, fill="black")
    return page


def an_interest_page(*, squares: bool = False):
    """A made-up 1099-INT at 300 dpi, and with ``squares`` two 30 px black
    squares 2000 px apart on an otherwise empty row, whose centroids give a
    measure of the lean independent of the estimator."""
    from PIL import ImageDraw

    from tests.samples import lines_1099_int

    page = a_page_of(lines_1099_int("Harbor Test Bank", "John A. Smith", 2025))
    if squares:
        draw = ImageDraw.Draw(page)
        draw.rectangle((200, 2000, 229, 2029), fill="black")
        draw.rectangle((2200, 2000, 2229, 2029), fill="black")
    return page


def grey_of(page):
    import numpy

    return numpy.asarray(page.convert("L")).copy()


def lean_of_squares(page) -> float:
    """The angle in degrees of the line through the centroids of the two
    squares in the band they sit in (the only ink there)."""
    import math

    import cv2
    import numpy

    ink = (grey_of(page)[1800:2300] < 128).astype(numpy.uint8)
    count, _labels, _stats, centres = cv2.connectedComponentsWithStats(ink, connectivity=8)
    assert count == 3, count                                     # the paper and the two squares
    (x1, y1), (x2, y2) = sorted(map(tuple, centres[1:]))
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def only_the_grey(page):
    """``page`` as a stage with a step on but nothing to do returns it: grey, as RGB."""
    from PIL import Image

    return Image.fromarray(grey_of(page), "L").convert("RGB")


def test_a_thick_stroke_is_type_and_a_thin_one_a_rule_whatever_their_length(tmp_path):
    """A rule is long and thin (P285, SPEC 9.2): on a letter page at 300 dpi a
    3 px wide stroke 600 px tall and a 600 px wide one 3 px tall are whitened,
    while the stems of large type, a 16 px wide bar 160 px tall and a 160 x 16
    one (a 28 pt bold stem), come back unchanged pixel for pixel; and the
    1100 x 260 canvas of a photo of a W-2's head, whose type is 40 px, comes
    back with exactly the ink it had."""
    import numpy
    from PIL import Image, ImageDraw

    page = Image.new("L", LETTER_300, 255)
    draw = ImageDraw.Draw(page)
    draw.rectangle((300, 400, 302, 999), fill=0)                  # a thin rule down, 600 long
    draw.rectangle((800, 400, 1399, 402), fill=0)                 # a thin rule across, 600 long
    draw.rectangle((300, 1600, 315, 1759), fill=0)                # a stem, 16 x 160
    draw.rectangle((800, 1600, 959, 1615), fill=0)                # a bar, 160 x 16
    before = numpy.asarray(page).copy()

    after = ocr._delined_grey(before)

    assert (after[400:1000, 300:303] == 255).all() and (after[400:403, 800:1400] == 255).all()
    assert (after[1600:1760, 300:316] == 0).all() and (after[1600:1616, 800:960] == 0).all()
    assert numpy.array_equal(after[1500:], before[1500:])           # nothing else on the page moved

    photo = grey_of(Image.open(w2_photo(tmp_path / "w-2.png")))
    assert numpy.array_equal(ocr._delined_grey(photo), photo)


def test_every_step_off_hands_the_engine_the_page_as_it_stands(monkeypatch, own_settings):
    """"Raw" in the bench is P283's reading: with every step off ``prepared``
    returns the very image it was given, and the engine is handed its pixels
    byte for byte (dtype, shape, values)."""
    import dataclasses

    import numpy

    page = a_page_of(["Form 1099-INT"], (600, 300), font_size=40)
    kept = []

    class KeepsThePixels(FakeEngine):
        def __call__(self, pixels):
            kept.append(pixels)
            return super().__call__(pixels)

    off = dataclasses.replace(ocr.SHIPPED, deskew=False, binarize="off", denoise=False, delining=False)
    for settings in (ocr.RAW, off):
        assert ocr.prepared(page, settings) is page
        ocr.use_settings(settings)
        monkeypatch.setattr(ocr, "_ENGINE", KeepsThePixels(ocr.DEVICE_PROCESSOR, ["a line"]))
        monkeypatch.setattr(ocr, "_DEVICE", ocr.DEVICE_PROCESSOR)
        assert ocr.read_page(page) == "a line"
        expected = ocr._pixels(page)
        assert kept[-1].dtype == expected.dtype and kept[-1].shape == expected.shape
        assert numpy.array_equal(kept[-1], expected)


def test_the_engine_is_handed_the_prepared_page(monkeypatch, own_settings):
    """``read_page`` prepares the page under the settings in force and hands
    the engine the pixels of what came back."""
    page, marker, asked, seen = object(), object(), [], []
    monkeypatch.setattr(ocr, "prepared", lambda image, settings: asked.append((image, settings)) or marker)
    monkeypatch.setattr(ocr, "_pixels", lambda image: seen.append(image) or "pixels")
    ocr.use_settings(ocr.SHIPPED)
    monkeypatch.setattr(ocr, "_ENGINE", FakeEngine(ocr.DEVICE_PROCESSOR, ["a line"]))
    monkeypatch.setattr(ocr, "_DEVICE", ocr.DEVICE_PROCESSOR)

    assert ocr.read_page(page) == "a line"

    assert asked == [(page, ocr.SHIPPED)] and seen == [marker]


def test_a_page_skewed_two_degrees_is_read_level_within_a_third_of_a_degree():
    """A made-up 1099-INT turned two degrees: the stage measures the lean as
    two degrees, and after it the line through the two squares on the page is
    level to within 0.3 degrees (a measure independent of the estimator)."""
    import dataclasses

    leaning = an_interest_page(squares=True).rotate(2, fillcolor="white")
    assert abs(lean_of_squares(leaning)) > 1.5
    assert abs(ocr._skew_degrees(grey_of(leaning)) - 2.0) <= 0.3

    level = ocr.prepared(leaning, dataclasses.replace(ocr.RAW, deskew=True, max_side_len=3300))

    assert abs(lean_of_squares(level)) <= 0.3


def test_a_level_page_is_left_untouched_by_deskewing():
    import dataclasses

    page = an_interest_page()
    assert ocr._skew_degrees(grey_of(page)) == 0.0

    after = ocr.prepared(page, dataclasses.replace(ocr.RAW, deskew=True, max_side_len=3300))

    assert after.tobytes() == only_the_grey(page).tobytes()


def test_a_page_skewed_twelve_degrees_is_left_alone():
    """A lean past five degrees is not guessed at: the search reaches half a
    degree past the limit, so this page shows its best at the edge and the
    stage changes nothing but the grey."""
    import dataclasses

    leaning = an_interest_page().rotate(12, fillcolor="white")
    assert ocr._skew_degrees(grey_of(leaning)) == 0.0

    after = ocr.prepared(leaning, dataclasses.replace(ocr.RAW, deskew=True, max_side_len=3300))

    assert after.tobytes() == only_the_grey(leaning).tobytes()


def test_a_quarter_turned_page_is_not_turned_by_deskewing(tmp_path):
    """A page turned a quarter has no plain winner among the small angles,
    and is left for the engine, which already reads it (decision 169, ruling 6)."""
    from PIL import Image

    photo = Image.open(w2_photo(tmp_path / "quarter.png", turn=90))

    assert photo.height > photo.width
    assert ocr._skew_degrees(grey_of(photo)) == 0.0


def test_sauvola_blackens_faded_text_and_leaves_a_shadow_white_where_otsu_blackens_it():
    """Faded text (grey 150 on grey 230 paper) is black after Sauvola's
    threshold and the paper far from it stays white; a smooth shadow (230
    falling to 100 across the page) and no text at all stays white where
    Otsu's one threshold blackens a third of the page."""
    import cv2
    import numpy
    from PIL import Image, ImageDraw, ImageFont

    from tests.samples import lines_1099_int

    size = (1600, 1000)
    faded, marks = Image.new("L", size, 230), Image.new("L", size, 0)
    for layer, fill in ((faded, 150), (marks, 255)):
        draw = ImageDraw.Draw(layer)
        draw.fontmode = "1"                                  # hard pixels: each one is text or paper
        for i, line in enumerate(lines_1099_int("Harbor Test Bank", "John A. Smith", 2025)):
            draw.text((60, 60 + 100 * i), line, font=ImageFont.load_default(size=40), fill=fill)
    text = numpy.asarray(marks) > 0
    out = ocr._sauvola(numpy.asarray(faded).copy())

    assert text.sum() > 10_000
    assert (out[text] == 0).mean() >= 0.95
    window = ocr._sauvola_window(size[1], size[0])
    near = cv2.dilate(text.astype(numpy.uint8), numpy.ones((2 * window + 1, 2 * window + 1), numpy.uint8)) > 0
    assert (out[~near] == 255).all()

    shadow = numpy.tile(numpy.linspace(230, 100, size[0]), (size[1], 1)).astype(numpy.uint8)
    assert (ocr._sauvola(shadow) == 255).all()
    assert (ocr._otsu(shadow) == 0).mean() > 0.30


def test_the_sauvola_window_is_about_one_character_and_always_odd():
    """A hundredth of the shorter side: 25 px on a letter page at 300 dpi,
    15 (the floor) at 144 dpi, 25 on a phone photo held to 3300 by 2475."""
    assert ocr._sauvola_window(3300, 2550) == 25
    assert ocr._sauvola_window(1584, 1224) == 15
    assert ocr._sauvola_window(2475, 3300) == 25
    assert all(ocr._sauvola_window(n, n + 37) % 2 == 1 and ocr._sauvola_window(n + 37, n) % 2 == 1
               for n in range(100, 5001))


def test_a_lone_speck_is_removed_and_an_is_dot_and_a_hairline_are_kept():
    """A one-pixel and a two-pixel speck go; a three-pixel L, a 3 x 3 dot (an
    i's) and a one-pixel-wide, forty-long stroke stay, and every other pixel
    of the page is unchanged."""
    import numpy

    page = numpy.full((200, 200), 255, numpy.uint8)
    page[10, 10] = 0                                         # a 1-pixel speck
    page[10, 50:52] = 0                                      # a 2-pixel speck
    page[60, 10:12] = 0                                      # a 3-pixel L
    page[61, 10] = 0
    page[60:63, 60:63] = 0                                   # a 3 x 3 dot
    page[120:160, 100] = 0                                   # a hairline, 40 long
    expected = page.copy()
    expected[10, 10] = 255
    expected[10, 50:52] = 255

    after = ocr._despeckled(page)

    assert numpy.array_equal(after, expected)


def test_a_page_longer_than_the_long_side_is_held_to_it_before_it_is_prepared(tmp_path):
    """A legal page at 300 dpi (2550 by 4200) is held to a long side of 3300
    under the shipped settings; a letter page keeps its size; under the raw
    settings no page is ever resized. A letter PDF page as the reader renders
    it (pypdfium2 rounds a side up, so 2550 by 3301 at the shipped 300 dpi)
    is one pixel over the long side, and comes back 2549 by 3300: the hold
    is to the number, and the long side stays 3300 (SPEC 9.5)."""
    import pypdfium2 as pdfium
    from PIL import Image

    legal = Image.new("RGB", (2550, 4200), "white")
    letter = Image.new("RGB", LETTER_300, "white")

    held = ocr.prepared(legal, ocr.SHIPPED)
    assert max(held.size) == 3300 and held.size == (2004, 3300)
    assert ocr.prepared(letter, ocr.SHIPPED).size == letter.size
    assert ocr.prepared(legal, ocr.RAW) is legal

    pdf = text_pdf(tmp_path / "letter.pdf", "a line", style="bare")
    doc = pdfium.PdfDocument(pdf)
    try:
        page_of = doc[0]
        rendered = page_of.render(
            scale=content_check.render_scale(*page_of.get_size())).to_pil().convert("RGB")
    finally:
        doc.close()
    assert ocr.SETTINGS is ocr.SHIPPED and rendered.size == (2550, 3301)
    assert ocr.prepared(rendered, ocr.SHIPPED).size == (2549, 3300)


def test_the_stage_never_touches_the_page_it_is_given_and_is_the_same_every_time():
    """The page's bytes are the same after the stage as before, and preparing
    it twice gives the same pixels."""
    page = an_interest_page(squares=True).rotate(2, fillcolor="white")
    before = page.tobytes()

    first, second = ocr.prepared(page, ocr.SHIPPED), ocr.prepared(page, ocr.SHIPPED)

    assert page.tobytes() == before
    assert first.tobytes() == second.tobytes() and first.mode == "RGB" and first.size == page.size


def a_crooked_scan(path: Path, lines, degrees: float) -> Path:
    """``tests.samples.scanned_pdf``'s page (150 dpi, no text layer) turned
    ``degrees`` on the same canvas, as a flatbed scan of a page laid down a
    little crooked. The canvas is kept: ``scanned_pdf(rotate=...)`` grows it,
    and at that size the arm64 wheel of OpenCV 5.0.0.93 segfaults inside
    rapidocr's own ``cv2.resize`` (found by the P285 build; the SPEC's
    handoff names it)."""
    from PIL import Image, ImageDraw, ImageFont

    page = Image.new("RGB", (1275, 1650), "white")
    draw = ImageDraw.Draw(page)
    for i, line in enumerate(lines):
        draw.text((80, 90 + 52 * i), line, font=ImageFont.load_default(size=30), fill="black")
    page.rotate(degrees, fillcolor="white").save(path, "PDF", resolution=150)
    return path


def test_a_prepared_real_scan_of_a_1099_int_files_under_p282_level_and_skewed_two_degrees(tmp_path):
    """The real reader under the shipped settings, end to end: an image-only
    PDF of a made-up 1099-INT, and the same lines scanned two degrees
    crooked, each file under the request that accepts it on its looser
    keyword when the title shows the form number - read from a scan."""
    from tests.samples import lines_1099_int
    from tracker.router import MATCHED_FROM_SCAN, route_file

    interest = RequestItem(identifier="A02", document="1099-INT", period="TY2025",
                           allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("1099-int",))
    mortgage = RequestItem(identifier="C01", document="1098", period="TY2025",
                           allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("1098",))
    lines = lines_1099_int("Harbor Test Bank", "John A. Smith", 2025)

    scans = {"level": scanned_pdf(tmp_path / "scan level.pdf", lines),
             "crooked": a_crooked_scan(tmp_path / "scan crooked.pdf", lines, 2)}
    for name, scan in scans.items():
        routing = route_file(scan, [interest, mortgage])
        assert routing.identifier == "A02", (name, routing.reason)
        assert routing.reason == MATCHED_FROM_SCAN, name


def test_a_large_title_keeps_its_form_number_when_prepared(own_settings):
    """The real reader under the shipped settings, on a letter page at 300 dpi:
    "Form 1099-INT Interest Income" in 150 px type over a made-up body in 46 px
    type with a 3 px box around it. The box-line step once took the stems of
    large type for rules and the reader lost the form number the title guard
    (P282) depends on (``orm 099 1 n:crcs: ncomc``): the first line read from
    the prepared page still holds "1099-INT", as the unprepared page's does."""
    import dataclasses

    from PIL import Image, ImageDraw, ImageFont

    from tests.samples import lines_1099_int

    page = Image.new("RGB", LETTER_300, "white")
    draw = ImageDraw.Draw(page)
    draw.text((100, 100), "Form 1099-INT Interest Income", font=ImageFont.load_default(size=150), fill="black")
    body = ImageFont.load_default(size=46)
    for i, line in enumerate(lines_1099_int("Harbor Test Bank", "John A. Smith", 2025)[1:]):
        draw.text((200, 500 + 80 * i), line, font=body, fill="black")
    draw.rectangle((150, 450, 2400, 1250), outline="black", width=3)

    unprepared = dataclasses.replace(ocr.SHIPPED, deskew=False, binarize="off", denoise=False, delining=False)
    first = {}
    for name, settings in (("raw", unprepared), ("prepared", ocr.SHIPPED)):
        ocr.use_settings(settings)
        first[name] = ocr.read_page(page).splitlines()[0]
    assert "1099-INT" in first["raw"], first
    assert "1099-INT" in first["prepared"], first


def a_five_page_scan(path: Path, lines: list[str]) -> Path:
    """Five image-only pages, each drawn the way ``samples.scanned_pdf`` draws
    one (the same 1275 x 1650 canvas, 150 dpi, the same font and spacing), in
    one PDF with no text layer."""
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default(size=30)
    pages = []
    for _page in range(5):
        page = Image.new("RGB", (1275, 1650), "white")
        draw = ImageDraw.Draw(page)
        for i, line in enumerate(lines[:28]):
            draw.text((80, 90 + 52 * i), line, font=font, fill="black")
        pages.append(page)
    pages[0].save(path, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    return path


def test_the_shipped_reading_of_a_scan_fits_the_reading_child(tmp_path, in_a_child):
    """The shipped reading of a five-page scan, through the product's own
    path (the judgment in the pass's reading child, on the processor, under
    the shipped settings), gets a reading and not a crash. The child ends a
    reading that passes its cap, which is 4 GB from P285 (decision 169's
    2 GB was a reader at 144 dpi); the first build's detector read each 300
    dpi page whole, reached 2.8 GB, and was ended as ``reading-crashed`` at
    the 2 GB cap, and with the detector held the five pages still crossed 2
    GB. The detector now reads its own 2000-pixel copy (``Det.limit_type``
    ``max``) and the cap is 4 GB, so the child stays inside it. The
    judgment carries no word of the document (decision 189), so the claim
    asks a question - a row keyed on the form number - and reads the answer."""
    from tests.samples import lines_1099_int

    assert ocr.SETTINGS is ocr.SHIPPED
    scan = a_five_page_scan(tmp_path / "five pages.pdf",
                            lines_1099_int("Harbor Test Bank", "John A. Smith", 2025))

    form_number = verdicts.RowQuestion(required_keywords=("1099-INT",))

    judgment = content_check.judge_bounded(scan, verdicts.Questions(rows=(form_number,)))

    reading = judgment.extraction
    assert reading.reason != CRASHED and not reading.transient, reading.reason
    assert reading.from_ocr and judgment.has_words, reading.reason
    assert judgment.rows[form_number].required_matched
    assert no_child_left()


# ----------------------------------------------------- the graphics card ----


a_card = ocr_helpers.a_card


def w2_rows():
    return [RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                        min_size_kb=0, required_keywords=("W-2",), expected_count=5)]


def scans_in_the_inbox(engagement, names_and_pages: dict[str, int]):
    """Scanned PDFs of ``pages`` pages each, dropped in the inbox."""
    from PIL import Image

    from tracker.layout import inbox_of

    for name, pages in names_and_pages.items():
        sheets = [Image.new("RGB", (400, 500 + 10 * i + len(name)), "white") for i in range(pages)]
        sheets[0].save(inbox_of(engagement) / name, "PDF", save_all=True, append_images=sheets[1:])


def a_pass(root: Path, day: int = 1):
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, run_registry

    return run_registry(discover_engagements(root), today=dt.date(2026, 7, day), reminders=REMINDERS_NEVER)


def test_no_gpu_pack_means_the_cpu_without_a_word(tmp_path, monkeypatch, a_card):
    """R-2: with no ``gpu-runtime`` folder the reader never asks for the
    card - no library loaded, no CUDA engine requested, so no error lines -
    and says nothing but "processor" in the run log's first line."""
    from tracker.runner import append_log

    for module in (ocr, reader_child):
        monkeypatch.setattr(module, "gpu_pack", lambda: None)
    engagement = make_engagement(tmp_path / "root", w2_rows())
    scans_in_the_inbox(engagement, {"one.pdf": 1})

    report = a_pass(tmp_path / "root")

    assert a_card.built == ["processor"] and a_card.loaded == []
    assert report.reader == ocr.DEVICE_PROCESSOR and report.reader_note == ""
    assert report.warnings == []
    first, *rest = append_log(tmp_path / "runs.log", report).read_text(encoding="utf-8").splitlines()
    assert first.endswith("reader=processor")
    assert not any("graphics card" in line for line in rest)


def test_a_pack_is_used_only_when_every_session_is_on_cuda_and_the_self_test_reads(tmp_path, a_card):
    """R-2: with the pack, its libraries are loaded, the engine is built
    asking for CUDA, each of the three sessions must have got
    ``CUDAExecutionProvider`` first, and the one-page self-test must read.
    Then the run log says "graphics card"; anything less is the processor
    and one run-log line saying why - never a pass warning."""
    from tracker.runner import append_log

    engagement = make_engagement(tmp_path / "root", w2_rows())
    scans_in_the_inbox(engagement, {"one.pdf": 1})

    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS)
    report = a_pass(tmp_path / "root")
    assert a_card.loaded == [str(a_card.pack)]
    assert a_card.built == ["card"] and a_card.gpu.calls >= 2      # the self-test, and the scan
    assert report.reader == ocr.DEVICE_GRAPHICS_CARD and report.reader_note == ""
    assert append_log(tmp_path / "card.log", report).read_text(encoding="utf-8").splitlines()[0] \
        .endswith("reader=graphics card")

    # One session quietly on the processor: not the card.
    a_card.built.clear()
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS)
    a_card.gpu.providers["text_rec"] = ["CPUExecutionProvider"]
    scans_in_the_inbox(engagement, {"two.pdf": 1})
    report = a_pass(tmp_path / "root", day=2)
    assert a_card.built == ["card", "processor"]
    assert report.reader == ocr.DEVICE_PROCESSOR and report.warnings == []
    said = ocr.PACK_UNUSABLE.format(reason="the text_rec session got CPUExecutionProvider")
    assert report.reader_note == said
    lines = append_log(tmp_path / "rec.log", report).read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("reader=processor") and lines[1].strip() == said

    # Every session on CUDA, and the self-test reads nonsense.
    a_card.built.clear()
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, ["nonsense"])
    scans_in_the_inbox(engagement, {"three.pdf": 1})
    report = a_pass(tmp_path / "root", day=3)
    assert a_card.built == ["card", "processor"]
    assert report.reader == ocr.DEVICE_PROCESSOR and report.warnings == []
    assert report.reader_note == ocr.PACK_UNUSABLE.format(reason="the self-test read 'nonsense'")


def test_a_gpu_fault_switches_the_rest_of_the_pass_to_the_cpu(tmp_path, a_card):
    """Ruling 3. The card faults on the second page of the first scan
    (ONNX Runtime's "CUDA failure 999", after which every later call in the
    process fails). That page is read again on the processor, the rest of
    the scan and the next scan are read on the processor from the start,
    the pass says so once, and no reading failed. The next pass tries the
    card again."""
    from tracker.index import read_index
    from tracker.runner import append_log

    engagement = make_engagement(tmp_path / "root", w2_rows())
    scans_in_the_inbox(engagement, {"one.pdf": 3, "two.pdf": 1})
    # Call 1 is the self-test, call 2 the first page, call 3 the second.
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS, fail_from=3)

    report = a_pass(tmp_path / "root")

    assert a_card.gpu.calls == 3                                   # never asked again after the fault
    assert a_card.built == ["card", "processor"]
    assert a_card.cpu.calls == 3                                   # page 2 again, page 3, the next scan
    assert report.reader == ocr.DEVICE_GRAPHICS_CARD                 # it began on the card
    assert report.warnings == [ocr.GPU_FAULT_WARNING.format(file="one.pdf")]
    log = append_log(tmp_path / "runs.log", report).read_text(encoding="utf-8")
    # Counted by its code, the file never named (decision 186).
    assert "one.pdf" not in log and "graphics-card-fault=1" in log
    rows = read_index(engagement)
    assert sorted(row.original_name for row in rows) == ["one.pdf", "two.pdf"]
    assert all(row.identifier == "A01" for row in rows), [row.reason for row in rows]

    # The next pass: the card again.
    a_card.built.clear()
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS)
    scans_in_the_inbox(engagement, {"three.pdf": 1})
    report = a_pass(tmp_path / "root", day=2)
    assert a_card.built == ["card"] and report.warnings == []


# ----------------------------------------------- one child for the pass ----


in_a_child = ocr_helpers.in_a_child
a_short_stop = ocr_helpers.a_short_stop


def test_the_document_stop_ends_a_page_the_reader_never_finishes(tmp_path, a_short_stop):
    """Ruling 5: RapidOCR takes no timeout, and nothing inside the child can
    interrupt a page it is reading. The document's stop ends the child: the
    reading is abandoned, and nothing is left running."""
    from tests import child_readers

    a_short_stop.setattr(content_check, "_CHILD_READER", child_readers.a_page_read_that_never_finishes)
    scan = w2_scan(tmp_path / "scan.pdf")

    reading = content_check.judge_bounded(scan, verdicts.Questions()).extraction

    mark = child_readers.reached(scan, "page")
    assert mark.is_file()                                          # it was inside the page
    assert reading.text is None and reading.reason == STOPPED and not reading.transient
    assert eventually(lambda: not running(int(mark.read_text(encoding="utf-8"))))
    assert no_child_left()


#: A pass, as a process of its own, that opens its reading session, reads
#: one document - so its child is alive and idle, waiting for the next -
#: says the child's process id, and waits to be killed.
A_PASS_BETWEEN_DOCUMENTS = """
import sys, time
from pathlib import Path
sys.path[:0] = [sys.argv[2]]
from tests import child_readers
from tracker import content_check, reader_child
with reader_child.reading_session():
    answer, failed = content_check.in_a_child(Path(sys.argv[1]), child_readers.the_childs_process_id)
    Path(sys.argv[1] + ".child").write_text(answer.text, encoding="utf-8")
    time.sleep(600)
"""


def test_no_reading_child_outlives_the_pass(tmp_path):
    """150's third guarantee, for the long-lived child: killed the way Task
    Scheduler kills it - outright, no code of the pass's runs - the pass
    takes its child with it, even one idle between documents."""
    import subprocess
    import sys

    repo = str(Path(__file__).resolve().parents[1])
    page = text_pdf(tmp_path / "page.pdf", "Form W-2 2025", style="bare")
    mark = Path(f"{page}.child")
    the_pass = subprocess.Popen([sys.executable, "-c", A_PASS_BETWEEN_DOCUMENTS, str(page), repo])
    try:
        assert eventually(mark.is_file, within=60), "the pass never read its document"
        child = int(mark.read_text(encoding="utf-8"))
        assert running(child)                                      # alive, between documents

        the_pass.kill()
        the_pass.wait(30)

        assert eventually(lambda: not running(child), within=10), "the child outlived its pass"
    finally:
        if the_pass.poll() is None:
            the_pass.kill()


# ------------------------------------------- the short-path warning (§9) ----


def test_run_from_source_the_app_is_never_too_deep():
    assert not getattr(sys, "frozen", False)
    assert ocr.reader_path_warning() == ""


def test_a_library_past_the_limit_means_the_app_must_move(tmp_path, monkeypatch):
    """SPEC-169 section 9 and REVIEW-169 N-5: any library of the app's
    whose full path passes the limit (240, a margin below where loading was
    seen to fail) is the warning. (The limit is patched down to the test's
    own folder.)"""
    app = tmp_path / "tracker-api" / "_internal"
    (app / "cv2").mkdir(parents=True)
    library = app / "cv2" / "opencv_world.dll"
    library.write_bytes(b"")
    (app / "cv2" / "a very long name that is not a library at all.txt").write_bytes(b"")
    monkeypatch.setattr(ocr, "READER_PATH_LIMIT", len(str(library.resolve())))
    assert ocr.reader_path_warning(app) == ""
    monkeypatch.setattr(ocr, "READER_PATH_LIMIT", len(str(library.resolve())) - 1)
    assert ocr.reader_path_warning(app) == ocr.READER_PATH_WARNING
    assert ocr.READER_PATH_WARNING.startswith(
        "Move the app to a shorter folder, for example C:\\JPA App")


@pytest.mark.skipif(sys.platform != "win32", reason="a directory junction is Windows'")
def test_a_short_junction_to_a_deep_folder_is_still_too_deep(tmp_path, monkeypatch):
    """N-5: the frozen app loads from its real folder, so a short junction
    to a deep one does not help, and the check reads the real path."""
    import subprocess

    deep = tmp_path / "a deep folder a deep folder a deep folder" / "tracker-api" / "_internal"
    deep.mkdir(parents=True)
    (deep / "onnxruntime.dll").write_bytes(b"")
    short = tmp_path / "s"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(short), str(deep)], check=True,
                   capture_output=True)
    try:
        monkeypatch.setattr(ocr, "READER_PATH_LIMIT", len(str(short / "onnxruntime.dll")) + 5)
        assert ocr.reader_path_warning(short) == ocr.READER_PATH_WARNING
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(short)], check=True, capture_output=True)
