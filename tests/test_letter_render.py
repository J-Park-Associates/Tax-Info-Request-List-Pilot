"""Tests for tracker/letter_render.py - the letter's look: the emphasis
ladder and its colours, the letter's shapes and the HTML the clipboard takes.

Most of what the module promises is held by tests/test_reminder.py, whose
tests draft a letter and render it through ``render_html``, which stays in the
reminder because it is typed by the reminder's own ``ReminderDraft``; each of
them calls the reminder too, so the SPEC's rule keeps them there. The first
test below moved here from tests/test_reminder.py (SPEC-architecture-p5
R5.11.4, P348), byte for byte: it constructs :class:`Emphasis` and reads the
ladder's tables and calls nothing of the reminder. The rest call the module's
own functions directly, each named for the claim it makes. Made-up words only.
"""

from tracker.letter_render import (
    HOLD_COLOUR,
    LETTER_INK,
    RUN_CONSEQUENCES,
    RUN_DEADLINE_DATE,
    RUN_TARGET,
    STAGE_COLOURS,
    STAGE_EMPHASIS,
    Emphasis,
    Letter,
    Run,
    Section,
    render_text_html,
    run_emphasis,
    stage_colour,
    stage_emphasis,
)


def test_the_emphasis_table_matches_the_design_notes():
    """Where each stage spends its colour and its weight, pinned: one table
    serves the letter, the clipboard and the card, and stage 1's colour is
    the body's own ink, so applying it colours nothing."""
    from tracker.page import PALETTE

    assert STAGE_EMPHASIS == {
        1: Emphasis(),
        2: Emphasis(target_colour=True),
        3: Emphasis(deadline_colour=True, dates_bold=True, list_bold=True),
        4: Emphasis(subject_colour=True, subject_bold=True, deadline_colour=True,
                    dates_bold=True, consequences_bold=True, list_colour=True, list_bold=True),
    }
    assert STAGE_COLOURS == {1: "slate_600", 2: "gold_800", 3: "warning_600", 4: "danger_600"}
    assert PALETTE[STAGE_COLOURS[1]] == PALETTE[LETTER_INK["body"]]
    assert HOLD_COLOUR == STAGE_COLOURS[3]


def test_html_for_a_letter_a_person_wrote_keeps_their_paragraphs_in_the_letters_type_with_no_style_block_and_no_address():
    """A draft somebody edited has no Letter behind it, so there is no stage
    to put emphasis on and none is put: their paragraphs, in the letter's own
    type, inline styles only, and nothing fetched."""
    import re

    from tracker.page import FONT_SANS, PALETTE

    text = "\nHello Pat,\n\nWe still need your W-2.\nThank you.\n\n\nBest,\nJ\n"
    markup = render_text_html(text)

    assert markup.startswith(f'<div style="font-family: {FONT_SANS}; font-size: 15px; ')
    assert f"color: {PALETTE[LETTER_INK['body']]}" in markup
    assert f"background-color: {PALETTE[LETTER_INK['paper']]}" in markup
    paragraphs = re.findall(r"<p style=\"margin: 0 0 14px;\">(.*?)</p>", markup)
    assert paragraphs == ["Hello Pat,", "We still need your W-2.<br />Thank you.", "Best,<br />J"]
    for forbidden in ("<style", "class=", "href=", "src=", "<link", "@import", "javascript:",
                      "<script", "<b ", "<span"):
        assert forbidden not in markup, forbidden
    for colour in STAGE_COLOURS.values():
        if PALETTE[colour] != PALETTE[LETTER_INK["body"]]:
            assert PALETTE[colour] not in markup


def test_html_for_a_letter_a_person_wrote_shows_markup_in_their_words_as_words():
    markup = render_text_html("Call <b>me</b> & we'll talk")
    assert "<b>" not in markup
    assert "Call &lt;b&gt;me&lt;/b&gt; &amp; we" in markup


def test_a_blank_draft_is_an_empty_letter_not_an_empty_paragraph():
    assert "<p " not in render_text_html("\n\n  \n")


def test_the_letter_flattens_to_the_text_a_person_pastes():
    """Letter.text is the one place the letter becomes text: blocks in order,
    one blank line between them, the intro's own breaks kept, the share link
    indented under the drop sentence and one newline at the end."""
    letter = Letter(
        greeting="Hello,",
        progress="Of the 2 items we asked for, 1 is in.",
        intro="First line\nsecond line",
        sections=(Section("MISSING", ("  - W-2", "  - 1099")),),
        drop=("Drop it in the shared", "folder:"),
        link="https://share.example.test/x",
        deadline=(Run("Please send by "), Run("June 1", RUN_TARGET), Run(".")),
        close="Thank you.",
        signoff=("Best,", "J Park"),
        stage=2,
    )
    assert letter.deadline_text == "Please send by June 1."
    assert letter.text() == (
        "Hello,\n\nOf the 2 items we asked for, 1 is in.\n\nFirst line\nsecond line\n\n"
        "MISSING\n  - W-2\n  - 1099\n\nDrop it in the shared\nfolder:\n  https://share.example.test/x\n\n"
        "Please send by June 1.\n\nThank you.\n\nBest,\nJ Park\n"
    )
    assert Letter(greeting="Hi").text() == "Hi\n"


def test_a_run_is_marked_only_by_the_words_its_stage_marks():
    """One answer for the clipboard and the preview: stage 2 colours the target
    date alone, stage 3 bolds both dates, stage 4 bolds the consequences too,
    and connective text is never marked."""
    target, filing = Run("June 1", RUN_TARGET), Run("June 8", RUN_DEADLINE_DATE)
    consequences, plain = Run("We cannot file.", RUN_CONSEQUENCES), Run("by")
    seen = {
        stage: [run_emphasis(run, stage_emphasis(stage)) for run in (target, filing, consequences, plain)]
        for stage in (1, 2, 3, 4)
    }
    assert seen[1] == [(False, False)] * 4
    assert seen[2] == [(True, False), (False, False), (False, False), (False, False)]
    assert seen[3] == [(False, True), (False, True), (False, False), (False, False)]
    assert seen[4] == [(False, True), (False, True), (False, True), (False, False)]


def test_a_letter_at_no_stage_is_written_in_the_bodys_own_ink():
    from tracker.page import PALETTE

    assert stage_emphasis(0) == Emphasis() and stage_emphasis(9) == Emphasis()
    assert stage_colour(0) == PALETTE[STAGE_COLOURS[1]] == PALETTE[LETTER_INK["body"]]
    assert stage_colour(4) == PALETTE[STAGE_COLOURS[4]]
    assert HOLD_COLOUR in PALETTE

