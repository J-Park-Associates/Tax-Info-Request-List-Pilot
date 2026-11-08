"""The letter's look: the emphasis each stage carries, the letter's shapes
and the HTML the clipboard takes, drawn from a letter and from nothing else.

Each part upholds the decision rows it names:

- **One ladder, one table** (decision 118). :class:`Emphasis` says where a
  stage spends its colour and its weight; :data:`STAGE_EMPHASIS` is the
  ladder (decision 117's four stages) in one place and :data:`STAGE_COLOURS`
  names each rung's colour by its key in :data:`tracker.page.PALETTE`. The
  API ships the same two tables to the app, so the card's preview and the
  body on the clipboard apply one ladder and nothing downstream picks a
  colour. :data:`LETTER_INK` is the letter's own surface and
  :data:`HOLD_COLOUR` the colour a hold is said in.
- **The letter is a shape before it is words** (decision 118).
  :class:`Run`, :class:`Section` and :class:`Letter` are the structure the
  reminder composes; :meth:`Letter.text` is the one place the letter becomes
  text, so the text a person pastes, the clipboard's HTML and the shape the
  app draws its preview from are three renderings of one thing and cannot
  come apart. :func:`run_emphasis` is the one answer to which words of the
  deadline paragraph are marked, read by the HTML and sent to the app
  beside the run itself.
- **The clipboard's body: inline styles only** (decisions 115 and 118).
  :func:`render_text_html` is the body of a draft a person edited by hand
  (their paragraphs, in the letter's own type, with no emphasis to apply),
  and the helpers the reminder's :func:`~tracker.reminder.render_html` is
  built from. Outlook keeps an inline style and drops a style sheet, a class
  and a variable, so every colour is a value out of the palette, there is no
  ``<style>`` block and nothing is fetched. It is rendered when a person asks
  for it and never written to disk.

**Nothing here sends anything** (decision 115). The module imports ``page``
and the standard library: no mail client, no socket, no network module, and
no file is read or written. It does not log.

**Why** ``render_html`` **stays in** ``tracker.reminder``. It is typed by the
reminder's own ``ReminderDraft``, which carries the draft's subject, body
and holds, and this module sits below the reminder (L0): a renderer of a
:class:`Letter` that named the draft would need the reminder, a load-time
import to a higher layer. The reminder imports back by name the shapes,
the ladder's helpers and the colours its own code reads.

**Where it came from** (SPEC-architecture-p5 P5.11, P348; the architecture
audit's C-8). Moved byte for byte out of ``tracker.reminder``, with its
words and comments, so every letter's text and HTML is the same bytes as
before. The reminder had grown to hold the draft's decisions, its record and
its files beside the letter's look; the look is a pure function of a letter
and has no reason to share a file with a hold.

**Why it sits at layer 0.** It reads ``tracker.page`` (its palette, its fonts
and its escape) and the standard library, nothing of the package above that,
and ``tests/test_layers.py`` pins that. The reminder is its caller at the
pass's layer, and the API reads the ladder and the renderers from here
directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tracker import page

# ------------------------------------------------- the ladder of emphasis ----


@dataclass(frozen=True, slots=True)
class Emphasis:
    """Where one stage spends its colour and its weight, and nowhere else.

    Eight flags, all off by default, so a stage that emphasises nothing is
    the empty one. Read by the letter's HTML renderer and shipped to the
    app in the API's vocabulary, so the card's preview and the body on the
    clipboard apply one table rather than two readings of a brief.
    """

    subject_colour: bool = False
    subject_bold: bool = False
    list_colour: bool = False
    list_bold: bool = False
    #: The whole deadline paragraph.
    deadline_colour: bool = False
    #: The two dates inside it - the target and the filing deadline.
    dates_bold: bool = False
    #: The target date alone, which is all stage 2 marks.
    target_colour: bool = False
    #: The final notice's consequences sentence.
    consequences_bold: bool = False


#: Which of :data:`tracker.page.PALETTE`'s colours each stage carries: the
#: toggle's ink in the app, and the letter's one colour. Stage 1's is the
#: body's own ink, so applying it colours nothing - the toggle needs a
#: colour for every rung and the letter needs none at the first, and one
#: table serves both.
STAGE_COLOURS = {1: "slate_600", 2: "gold_800", 3: "warning_600", 4: "danger_600"}
#: What a held reminder is said in: the hold line and the rule beside each
#: held row. Not a rung of the ladder - a hold is not a letter - but the
#: same warning the third rung carries, because it is the same kind of
#: "this needs you" the card is asking for.
HOLD_COLOUR = "warning_600"
#: The letter's own surface, by palette key: the body's ink, the quieter
#: ink its section headings take, and the paper under both.
LETTER_INK = {"body": "slate_600", "muted": "grey_500", "paper": "white"}

#: The ladder, in one place. Stage 4 marks the subject and the list, and
#: inside the deadline paragraph the two dates and the consequences
#: sentence, while the connective text is not: a fully bold paragraph
#: reads as shouting, and the letter is still meant to be respectful.
STAGE_EMPHASIS = {
    1: Emphasis(),
    2: Emphasis(target_colour=True),
    3: Emphasis(deadline_colour=True, dates_bold=True, list_bold=True),
    4: Emphasis(subject_colour=True, subject_bold=True, deadline_colour=True, dates_bold=True,
                consequences_bold=True, list_colour=True, list_bold=True),
}


@dataclass(frozen=True, slots=True)
class Run:
    """One stretch of the deadline paragraph, and what it is.

    ``kind`` is "" for the connective text, or ``target``,
    ``deadline_date`` or ``consequences`` for the three things a stage may
    mark. The runs are cut by formatting the stage's own sentence with
    sentinels around those values and splitting on them - never by looking
    for a date in the finished sentence, which an engagement's name could
    also contain.
    """

    text: str
    kind: str = ""


@dataclass(frozen=True, slots=True)
class Section:
    """One heading of the letter with the request lines under it."""

    heading: str
    items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Letter:
    """The letter as a shape, before it is words on a page (decision 118).

    The text a person pastes and the HTML body that goes on the clipboard
    are two renderings of this one structure, so they cannot say different
    things, and the app's preview is drawn from it as DOM nodes - the page
    is built from data and never from an HTML string. ``intro`` may carry
    its own line breaks (the quiet week's paragraph is written wrapped);
    ``deadline`` is empty when the stage has no such paragraph or the
    engagement has no Due Date to name in it.
    """

    greeting: str
    progress: str = ""
    intro: str = ""
    sections: tuple[Section, ...] = ()
    drop: tuple[str, ...] = ()
    link: str = ""
    deadline: tuple[Run, ...] = ()
    close: str = ""
    signoff: tuple[str, ...] = ()
    stage: int = 0

    @property
    def deadline_text(self) -> str:
        """The deadline paragraph as one sentence again."""
        return "".join(run.text for run in self.deadline)

    def text(self) -> str:
        """The body a person pastes: this structure as plain lines.

        The one place the letter becomes text. Every other rendering -
        the HTML for the clipboard, the app's preview - starts from the
        same fields, so a sentence cannot reach a client in one and not
        the other.
        """
        out: list[str] = [self.greeting, ""]
        if self.progress:
            out += [self.progress, ""]
        if self.intro:
            out += [*self.intro.split("\n"), ""]
        for section in self.sections:
            out += [section.heading, *section.items, ""]
        if self.drop:
            out += list(self.drop)
            if self.link:
                out.append(f"  {self.link}")
            out.append("")
        if self.deadline:
            out += [self.deadline_text, ""]
        if self.close:
            out += [self.close, ""]
        out += list(self.signoff)
        return "\n".join(out).rstrip() + "\n"


#: The three things a stage may mark inside that paragraph.
RUN_TARGET = "target"
RUN_DEADLINE_DATE = "deadline_date"
RUN_CONSEQUENCES = "consequences"


# ------------------------------------------------- the body, as Outlook reads it ----


def stage_emphasis(stage: int) -> Emphasis:
    """What this stage marks. A quiet week marks nothing."""
    return STAGE_EMPHASIS.get(stage, Emphasis())


def stage_colour(stage: int) -> str:
    """The colour this stage carries, as a value (decision 118). A letter
    at no stage is written in the body's own ink, which is stage 1's."""
    return page.PALETTE[STAGE_COLOURS.get(stage, STAGE_COLOURS[1])]


def _styled(tag: str, style: str, inner: str) -> str:
    return f'<{tag} style="{style}">{inner}</{tag}>'


def run_emphasis(run: Run, marks: Emphasis) -> tuple[bool, bool]:
    """Whether one run of the deadline paragraph is coloured, and whether it
    is bold, by the stage's own table.

    One answer, read by the body that goes on the clipboard and sent to the
    app beside the run itself, so the letter and the preview cannot mark
    different words - and so the page never has to know what a kind means.
    """
    colour = run.kind == RUN_TARGET and marks.target_colour
    bold = ((run.kind in (RUN_TARGET, RUN_DEADLINE_DATE) and marks.dates_bold)
            or (run.kind == RUN_CONSEQUENCES and marks.consequences_bold))
    return bool(colour), bool(bold)


def _emphasised(runs: Sequence[Run], marks: Emphasis, colour: str) -> str:
    """The deadline paragraph's runs, each wearing what its stage gives it."""
    out: list[str] = []
    for run in runs:
        text = page.esc(run.text)
        coloured, bold = run_emphasis(run, marks)
        if coloured:
            text = _styled("span", f"color: {colour};", text)
        if bold:
            text = _styled("b", "font-weight: bold;", text)
        out.append(text)
    return "".join(out)


def _paragraph(text: str, style: str) -> str:
    """One paragraph, its own line breaks kept as the breaks they are."""
    inner = "<br />".join(page.esc(line) for line in text.split("\n"))
    return _styled("p", style, inner)


def render_text_html(text: str) -> str:
    """A body somebody wrote by hand, as HTML for the clipboard.

    A draft a person has edited has no :class:`Letter` behind it any more -
    the words are theirs - so there is nothing to put a stage's emphasis
    on and none is put: their paragraphs, in the letter's own type, with
    the same words the plain text carries. Inline styles only, as the
    generated body's are, and nothing fetched.
    """
    ink = page.PALETTE[LETTER_INK["body"]]
    paper = page.PALETTE[LETTER_INK["paper"]]
    out = [f'<div style="font-family: {page.FONT_SANS}; font-size: 15px; line-height: 1.6; '
           f'color: {ink}; background-color: {paper};">']
    for block in text.strip("\n").split("\n\n"):
        if block.strip():
            out.append(_paragraph(block.strip("\n"), "margin: 0 0 14px;"))
    out.append("</div>")
    return "".join(out)


def _with_last(values: Sequence):
    """Each value with whether it is the last one - the only thing the
    letter's spacing needs to know about where it is."""
    total = len(values)
    return [(i == total - 1, value) for i, value in enumerate(values)]
