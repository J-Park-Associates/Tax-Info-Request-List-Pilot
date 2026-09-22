"""The markup both of the firm's pages are drawn with, owned once.

The tracker writes two pages a person opens in a browser: the practice-wide
one :mod:`tracker.runner` writes into the clients root (decision 75) and the
per-engagement one :mod:`tracker.view` writes beside the manifest (decision
91). They show different things and they share the parts that are easy to
get subtly wrong, so those parts live here and nowhere else:

- :func:`esc` - **every** value on either page goes through it. A client
  file called like a tag is shown as its name and never rendered as one,
  and there is one escaper to check rather than two to compare.
- :func:`table` - a table with its header row in a ``<thead>`` and its data
  in a ``<tbody>``, so a page that sorts its rows has something to sort and
  a page that does not is no worse for it.
- :func:`page_text` - the lines of a page as the bytes that are written. A
  name NTFS holds is not always one UTF-8 can (a lone surrogate), and a
  page about the firm's clients must not be lost to one client's file name.
- :func:`slug` - a word as a class name, the one way the tracker does it.
- :func:`tolerant_console` - the console made to take what it cannot
  encode. Every command line that prints a client's file or folder name
  calls it first, so a name the console cannot show never turns finished
  work into a traceback (decision 108; the rule was the runner's alone
  before, decision 67).

**Nothing here knows what a page is about.** No engagement, no manifest, no
record: it takes values and gives back markup, which is why it imports
nothing from the package and both pages can import it without a cycle.

**And nothing here fetches anything.** There is no helper for a script tag,
a style sheet link or an image, because a page naming the firm's clients
that reaches the network to render is a page telling somebody else which
firm is reading what. A page's own style is inline, in the module that owns
the page.

**The firm's colours live here too** (decision 118). :data:`PALETTE` and the
two font stacks mirror the design system's tokens, once: the reminder's
HTML body carries them inline because Outlook cannot read a variable, and
the app reads them out of the API rather than typing a colour of its own.
The design system is a folder beside the repository that nothing here may
read at run time - a page that fetched its own colours would be a page
reaching outside the engagement it describes - so this is the mirror, and
a test holds it to the tokens wherever they can be read.
"""

from __future__ import annotations

import html
import sys
from collections.abc import Iterable
from dataclasses import dataclass

#: What a sortable header carries, and what a page's own script looks for.
#: The value is the direction the column is currently sorted in, empty
#: until somebody clicks; a page with no script shows a plain table and the
#: attribute means nothing, which is the point.
SORT_ATTRIBUTE = "data-sort"

#: The firm's colours, by the design system's own primitive names, mirrored
#: here once (decision 118). Each line names the token it mirrors. Nothing
#: downstream writes a colour: the reminder's HTML body reads these because
#: Outlook keeps an inline style and drops a variable, and the desktop app
#: reads them through the API's vocabulary so the renderer types none.
PALETTE: dict[str, str] = {
    "navy_900": "#1B2A4A",      # navy-900, the ink-strong of the light set
    "slate_600": "#3A4660",     # slate-600, ink-body
    "grey_500": "#5C6577",      # grey-500, ink-muted
    "gold_800": "#7A5F16",      # gold-800, ink-accent
    "warning_600": "#8A5A10",   # warning-600
    "danger_600": "#A8362F",    # danger-600
    "cream_50": "#F5F0E8",      # cream-50, surface-page
    "white": "#FFFFFF",         # white, surface-raised
}

#: The two faces a letter is written in, named in full wherever they are
#: used. Not the design system's display faces: an email is read in
#: whatever the reader's mail client has, and neither Outlook nor a phone
#: has the firm's own, so these are the fallbacks the design pass chose on
#: purpose and they are what ships.
FONT_SANS = "Arial, Helvetica, sans-serif"
FONT_SERIF = "Georgia, 'Times New Roman', serif"


def esc(value: object) -> str:
    """One value as page text. Every value on either page goes through here:
    a client's file name is a name, whatever characters it contains."""
    return html.escape(str(value))


def unesc(text: str) -> str:
    """The inverse of :func:`esc`: what a page's own attribute said before
    it was escaped. The one reader of a value this module wrote."""
    return html.unescape(text)


def slug(text: str) -> str:
    """One word as a class name: lower case, anything else a hyphen."""
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


@dataclass(frozen=True, slots=True)
class Cell:
    """One cell that wants a class - a status said as a coloured badge.

    ``badge`` puts the class on a ``<span>`` inside the cell rather than on
    the cell itself, because a word painted as a pill has to be an inline
    box and a table cell cannot be one without taking the row apart. A
    plain string is a plain cell; this is for the few that are not.
    """

    value: object
    class_name: str = ""
    badge: bool = False


@dataclass(frozen=True, slots=True)
class Row:
    """One row that wants a class - a request set aside as not applicable, dimmed."""

    values: tuple[object, ...] = ()
    class_name: str = ""


def _cell(value: object, tag: str, marker: str = "") -> str:
    attributes = marker
    if isinstance(value, Cell):
        inner = esc(value.value)
        if value.badge:
            inner = f'<span class="{esc(value.class_name)}">{inner}</span>'
        elif value.class_name:
            attributes = f' class="{esc(value.class_name)}"{marker}'
    else:
        inner = esc(value)
    return f"<{tag}{attributes}>{inner}</{tag}>"


def cells(values: Iterable[object], tag: str = "td", *, class_name: str = "",
          attribute: str = "") -> str:
    """One ``<tr>`` of cells. ``attribute``, when given, is written empty on
    every cell of the row (the sort marker): a name this module owns and
    never a value from the data."""
    marker = f' {attribute}=""' if attribute else ""
    drawn = "".join(_cell(value, tag, marker) for value in values)
    opened = f'<tr class="{esc(class_name)}">' if class_name else "<tr>"
    return f"{opened}{drawn}</tr>"


def table(columns: Iterable[object], rows: Iterable[Iterable[object] | Row], *,
          sortable: bool = False) -> list[str]:
    """A table, header row in a ``<thead>``, data in a ``<tbody>``.

    ``sortable`` marks the headers for a page whose own script sorts them.
    It adds nothing a browser acts on by itself, so the table is the same
    plain table with scripts off.
    """
    drawn = ["<table>", "<thead>",
             cells(columns, "th", attribute=SORT_ATTRIBUTE if sortable else ""),
             "</thead>", "<tbody>"]
    for row in rows:
        if isinstance(row, Row):
            drawn.append(cells(row.values, class_name=row.class_name))
        else:
            drawn.append(cells(row))
    drawn += ["</tbody>", "</table>"]
    return drawn


def details(summary: str, lines: Iterable[str]) -> list[str]:
    """A folded block: a ``<details>`` whose ``<summary>`` is ``summary``,
    holding ``lines`` of markup already drawn (a :func:`table`, a list).

    A browser folds and unfolds it with no script, so a page with scripts
    off still opens it on a click; the summary is escaped like every value,
    the lines are markup this module drew and are not escaped again.
    """
    return [f"<details><summary>{esc(summary)}</summary>", *lines, "</details>"]


def page_text(lines: Iterable[str]) -> str:
    """The page's lines as the text that is written to disk.

    A name NTFS holds is not always one UTF-8 can (a lone surrogate); the
    page takes what it can write rather than lose a whole page to one
    client's file name, exactly as the run log does.
    """
    joined = "\n".join(lines)
    return joined.encode("utf-8", "backslashreplace").decode("utf-8") + "\n"


def tolerant_console() -> None:
    """The console made to take what it cannot encode, instead of dying on it.

    A report names client files and folders, and the console it lands on
    is not always UTF-8 (the scheduler's, a stock Windows prompt): a name
    it cannot encode - an arrow, a dash, a lone surrogate NTFS holds - is
    written as its escape rather than raised, so finished work (every
    original moved, a record written) never ends in a traceback over how
    it was announced. This is the one home of that guard; every command
    line that prints a client's name calls it before it parses a flag. It
    replaces characters and nothing else: an error is still an error, and
    a UTF-8 console shows the same text it always did. A stream with no
    ``reconfigure`` (a capture, a pipe a test handed in) is left as it is.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
