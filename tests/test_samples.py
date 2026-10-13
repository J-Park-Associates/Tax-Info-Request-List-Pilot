"""Tests for tests/samples.py - the made-up documents the whole suite starts from.

The claim worth a file of its own is the PDF writer. The suite had three
hand-built writers whose bytes tests lean on (a size floor, a count of
pages, the text a reader gets back), and they became one ``text_pdf`` with a
style for each (SPEC-architecture R2.2). Each style must write, byte for
byte, what its old writer wrote. The old writers are gone, so the proof that
outlives them is a digest and a size of what each wrote on three inputs,
taken from the writers themselves before they were deleted.
"""

import hashlib

import pytest

from tests.samples import BARE, PADDED, PAGE, STYLES, text_pdf
from tracker.content_check import extract_text

#: (style, text or lines, pages) -> (sha256 of the file, its size), as the old
#: writers wrote them: ``samples.text_pdf`` for ``padded`` (a list of lines),
#: ``test_scanner.text_pdf`` for ``page`` (a string, escaped, any pages) and
#: ``test_content_check.text_pdf`` for ``bare`` (one string, as it stands).
OLD_BYTES = [
    (PADDED, ["Form W-2 Wage and Tax Statement 2025", "John Smith"], 1,
     "18afb11e3d19ea997c82c7ecaf4ba75b5744df9a9da175acc8629ed5df750027", 8918),
    (PADDED, [""], 1,
     "9a089129ebb043611c6d93bfa7f28704dc68d804ed58ea49d1832a0a5185e13f", 8839),
    (PADDED, [f"line {i} (é)" for i in range(60)], 1,
     "c79a81acc249c8ac4f9af69c50b88c59dc858cb8b6ddf041061c610f363b0b37", 10862),
    (PAGE, "Chase Bank Statement Dec 2025", 1,
     "434bf33203d5cfd1fc6a2920db966b46ae0802ad151778526f7e60f4a1c34567", 612),
    (PAGE, "Line one\nLine (two) \\ three\né", 1,
     "d694ccc1cc2052fceddba867dba43b9567d6535e11bb151b5e3525587fd0107e", 631),
    (PAGE, "", 3,
     "7a2da83ac34b0be3b2fcd3d7ed50a64daee938e0785c1360f54f70e8d9b104ae", 887),
    (BARE, "Chase Bank Statement December 2025", 1,
     "9b7201965f009d6b47b0c8bc1b25c7db4c566489630a32a5ae9f6d80665d834f", 608),
    (BARE, "", 1,
     "f1dcd81c04bf6fa74776c253491c3753249b9bbac4c4e3b478f2e37449fc977d", 574),
    (BARE, "Form 1098 Mortgage Interest Statement 2025", 1,
     "74a906f7cd698b6a8e27a10ed5c53f2444a6b6e7591cd0cdc2600885036b379b", 616),
]


@pytest.mark.parametrize("style, said, pages, digest, size", OLD_BYTES,
                         ids=[f"{row[0]}-{n}" for n, row in enumerate(OLD_BYTES)])
def test_each_pdf_style_writes_the_bytes_its_old_writer_wrote(tmp_path, style, said, pages, digest, size):
    written = text_pdf(tmp_path / "x.pdf", said, pages=pages, style=style).read_bytes()
    assert (hashlib.sha256(written).hexdigest(), len(written)) == (digest, size)


def test_the_page_style_is_the_default_and_a_list_of_lines_reads_as_one_string_split_on_newlines(tmp_path):
    by_string = text_pdf(tmp_path / "a.pdf", "one\ntwo (three)").read_bytes()
    by_list = text_pdf(tmp_path / "b.pdf", ["one", "two (three)"], style=PAGE).read_bytes()
    assert by_string == by_list


@pytest.mark.parametrize("style, said", [(PAGE, "Form W-2 Wage and Tax Statement 2025"),
                                         (PADDED, ["Form W-2 Wage and Tax Statement 2025"]),
                                         (BARE, "Form W-2 Wage and Tax Statement 2025")])
def test_every_pdf_style_has_a_text_layer_that_reads_back(tmp_path, style, said):
    written = text_pdf(tmp_path / "x.pdf", said, style=style)
    assert "Form W-2 Wage and Tax Statement 2025" in extract_text(written)


def test_the_padded_style_is_the_one_with_a_realistic_size_and_the_others_are_small(tmp_path):
    sizes = {style: text_pdf(tmp_path / f"{style}.pdf", [""] if style == PADDED else "", style=style).stat().st_size
             for style in STYLES}
    assert sizes[PADDED] > 8192 > max(sizes[PAGE], sizes[BARE])


def test_only_the_page_style_writes_more_than_one_page(tmp_path):
    assert text_pdf(tmp_path / "x.pdf", "x", pages=2, style=PAGE).is_file()
    for style, said in ((PADDED, ["x"]), (BARE, "x")):
        with pytest.raises(ValueError, match="one page"):
            text_pdf(tmp_path / "y.pdf", said, pages=2, style=style)


def test_a_style_that_does_not_exist_is_refused_by_name(tmp_path):
    with pytest.raises(ValueError, match="no style 'plain'"):
        text_pdf(tmp_path / "x.pdf", "x", style="plain")


def test_the_padded_style_takes_lines_and_the_bare_style_one_string(tmp_path):
    with pytest.raises(TypeError, match="list of lines"):
        text_pdf(tmp_path / "x.pdf", "one string", style=PADDED)
    with pytest.raises(TypeError, match="one string"):
        text_pdf(tmp_path / "x.pdf", ["a list"], style=BARE)
