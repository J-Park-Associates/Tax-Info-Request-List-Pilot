"""The renderer's scripts, and the names each one takes from another.

The page is eight classic scripts that share one global scope: a top-level
``function``, ``let`` or ``const`` in one is a name every other can read, and
nothing in the language says which do. That is the seam a split of ``app.js``
cuts through (SPEC-architecture D-2), so this file is the JavaScript analogue
of ``test_layers``: it reads which script uses which other script's names and
pins today's answer as data (R3.7), the writes across scripts apart (an
assignment to another script's top-level ``let``, the riskier kind), and the
harness's double of ``app.js`` to what the scripts loaded beside it use, of
``app.js`` and of every script the harness drops when the double stands in
(R3.8, D-8).

**How a use is found.** A script's top-level declarations are the lines that
begin ``function name(``, ``async function name(``, ``let name``, ``const
name``, ``var name`` or ``class name``, with ``$`` a letter as JavaScript has
it (app.js's ``$`` is its ``document.getElementById``). A use is the name as a
whole word in the other script's code - not after a ``.``, and never inside a
string, a template's text, a comment or a regular expression, which
:func:`js_code` blanks first. A name the using script declares itself, at any
depth, is its own and not counted: the pilot's ``el``, ``fill`` and ``show``
and the tour's ``render`` live inside their namespaces, and pages.js's
``active`` is a local. Without that the double would have to define names no
script reads from ``app.js``. The price is that a script which declares a
local and also reads the global of the same name is not seen reading it; none
does today (each such name was read by hand for J3). A parameter or an object
key named like another script's global is still counted, because the match is
by the word; the table says where (``fold``, ``paths``).

The rejected alternative was a JavaScript parser (acorn, as the audit used).
The gate installs nothing for node, and a vendored parser would be a second
large file of someone else's code to keep; the scripts are written plainly
enough that the reader - strings, templates, comments and regular
expressions - is all the claim needs, and its own tests say what it does. It
is :func:`tests.node_harness.js_code`, moved there so every reader of a
script's code reads it one way (SPEC-architecture-p6 R6.1.2); its tests stay
here.

The lists of scripts a claim covers are :data:`tests.node_harness.RENDERER_SCRIPTS`
- the ones ``index.html`` loads - or a named part of it (R3.2), so a part that
named a script the page does not load would be a claim about nothing.

**Before phase 6 splits the scripts** (SPEC-architecture-p6 P6.1, D-5), two
nets go under the moves. A test reads a script by what it claims - the
function, the block, the code as a whole - and names one by its file only
where the claim is about the file, listed in ``FILE_NAMED`` with why; the
named-script guard walks every test file's literals (an ``ast`` walk, so a
script name in a comment or a docstring is not a read) and fails on any other.
And every script the page loads runs in order in one node context, as the
window runs them: a script carved out of ``app.js`` holds declarations only
and loads before it, so a split that moved a statement ahead of the binding
it meets at load fails here, not in the window.
"""

import ast
import json
import re
import subprocess
from functools import cache
from pathlib import Path

import pytest

from tests.node_harness import (
    APP_FAMILY,
    APP_SCRIPTS,
    MAIN_SCRIPTS,
    NODE,
    PILOT_SCRIPTS,
    RENDERER_SCRIPTS,
    REPO,
    SHELL_SCRIPTS,
    js_code,
    read,
    stripped_js,
)

HARNESS = REPO / "pilot" / "harness"


#: A top-level declaration, as R3.7 reads one: at the start of its line.
DECLARATION = re.compile(r"(?m)^(?:(?:async )?function ([\w$]+)\(|(?:let|const|var) ([\w$]+)|class ([\w$]+))")
#: A declaration at any depth: a name the script holds as its own.
OWN = re.compile(r"(?:\bfunction\s+|\b(?:let|const|var)\s+|\bclass\s+)([A-Za-z_$][\w$]*)")
#: A name as a whole word, not a property after a dot, and not the ``$`` of a
#: template's ``${``.
WORD = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)(?![\w${])")


@cache
def code(name: str) -> str:
    return js_code(read(name))


def declared(text: str) -> list[str]:
    """The top-level names a script's code declares, in order."""
    return [next(one for one in found.groups() if one) for found in DECLARATION.finditer(text)]


@cache
def owners() -> dict[str, str]:
    """Every top-level name of the renderer, to the script that declares it."""
    found: dict[str, list[str]] = {}
    for script in RENDERER_SCRIPTS:
        for name in declared(code(script)):
            found.setdefault(name, []).append(script)
    twice = {name: scripts for name, scripts in found.items() if len(scripts) > 1}
    assert twice == {}, twice
    return {name: scripts[0] for name, scripts in found.items()}


def seams() -> dict[tuple[str, str], set[str]]:
    """For each ordered pair (user, owner), the owner's top-level names the
    user's code reads or calls."""
    table: dict[tuple[str, str], set[str]] = {}
    for user in RENDERER_SCRIPTS:
        own = set(OWN.findall(code(user)))
        for word in WORD.findall(code(user)):
            owner = owners().get(word)
            if owner and owner != user and word not in own:
                table.setdefault((user, owner), set()).add(word)
    return table


def writes() -> set[tuple[str, str, str]]:
    """Every (writer, owner, name) where a script assigns to another
    script's top-level ``let``, a field or an item of it included, or
    deletes one, or counts it up or down."""
    lets = {script: set(re.findall(r"(?m)^let ([\w$]+)", code(script))) for script in RENDERER_SCRIPTS}
    found = set()
    for writer in RENDERER_SCRIPTS:
        own = set(OWN.findall(code(writer)))
        for owner, names in lets.items():
            if owner == writer:
                continue
            for name in names - own:
                one = re.escape(name)
                if re.search(rf"(?<![\w$.]){one}(?:\s*(?:\.[\w$]+|\[[^\]\n]*\]))*\s*"
                             rf"(?:[-+*/%&|^]|\*\*|<<|>>>?|&&|\|\||\?\?)?=(?![=>])"
                             rf"|(?<![\w$.])(?:\+\+|--){one}(?![\w$])|(?<![\w$.]){one}\s*(?:\+\+|--)"
                             rf"|\bdelete\s+{one}(?![\w$])", code(writer)):
                    found.add((writer, owner, name))
    return found


#: Today's table (SPEC-architecture J3): for each ordered pair (user, owner),
#: why the user takes the owner's names, and the names. A new cross-script
#: name fails until it is added here on purpose, under a line that says why -
#: a line of its own, or one already here that is its reason; a name no
#: longer used is taken off, so the table stays the page's.
SEAMS = {
    ("app.js", "tooltip.js"): {
        "Every tooltip app.js gives is tooltip.js's (SPEC-shell 13: no title attribute).": """
            setTip
        """,
    },
    ("app.js", "pages.js"): {
        "app.js says a day, a time, a stage, a taxpayer and a request's name as the pages do, routes to a"
        " return the pages' way, and windows its long editor tables at the pages' thresholds (P279).": """
            PAGES_VIRTUAL_FROM PAGES_VIRTUAL_OVER_LEAST pagesDay pagesItemName pagesRoute pagesStage
            pagesTaxpayer pagesTime
        """,
    },
    ("app.js", "sheet.js"): {
        "app.js asks the side sheet what it holds and closes it with its dialogs.": """
            sheetClosed sheetNow sheetRow
        """,
    },
    ("app.js", "shell.js"): {
        "app.js hands the shell its replies, its keys and its pass's progress, and reads the shell's"
        " route, words and Back (SPEC-shell 4: the shell owns the route, the menu and the firm page).": """
            folderName openPath screenWords shellAdopt shellAskFirmLast shellAskFirmNow shellBack
            shellChanged shellFirmProgress shellGo shellKey shellLoadFirm shellNeedsRoot shellProgress
            shellReturn shellReturnStale shellRootSet shellRoute shellStartFailed shellStateArrived
            shellVocabulary shellWords shellWriteLanded shortNotice unanswered
        """,
        "requestRows takes an option named fold: a parameter, counted because the match is by the word.": """
            fold
        """,
    },
    ("app.js", "pilot-content.js"): {
        "About shows the pilot's edition.": """
            PILOT
        """,
    },
    ("pages.js", "app.js"): {
        "The pages draw from app.js's state, vocabulary and per-PC store, word a request as app.js does,"
        " and open its dialogs and writes.": """
            $ acceptFolderName failed fedReturns fill households isSetAside lastState locked notADocument
            openAddReturn openEditor openNewHousehold openUnfile overrideLabel storeRead storeWrite
            syncNotices vocab withdrawAnswer writeBusy
        """,
        "pagesFileLink returns an object with a key named paths: counted because the match is by the word.": """
            paths
        """,
    },
    ("pages.js", "tooltip.js"): {
        "The pages' rows and headings take tooltip.js's tips and place them by its margins.": """
            hideTip setTip setTipIfCut showTipNow TIP_GAP TIP_MARGIN
        """,
    },
    ("pages.js", "sheet.js"): {
        "A row's menu opens the side sheet and presses the sheet's own button for the item.": """
            openCheck openReminder sheetNow sheetPress
        """,
    },
    ("pages.js", "shell.js"): {
        "The pages build with the shell's h() and icons, say its words, and ask its route, menu and firm reply.": """
            folderName h icon openPath screenWords shellAnswer shellEnabled shellFirm shellGo
            shellHousehold shellPopup shellReturn shellRoute shellTurnFirm shortNotice unanswered
        """,
    },
    ("sheet.js", "app.js"): {
        "The side sheet draws app.js's review rows and reminder card inside app.js's dialog stack, and"
        " reads and redraws the return on screen.": """
            $ active applyLock appRouteChanged closeDialog dialogOpener dialogStack drawReminder
            drawReminderReply failed forgetReminderCard isSetAside lastState movedRow notADocument
            openDialog reminderCard reminderCardFor requestClose reviewRow showReturn vocab
        """,
    },
    ("sheet.js", "tooltip.js"): {
        "A name the sheet cuts shows whole in a tooltip.": """
            setTipIfCut
        """,
    },
    ("sheet.js", "pages.js"): {
        "The sheet says its files, drafts, days and reasons as the pages do, and gives focus back to the"
        " page's row.": """
            pagesDay pagesDrafts pagesFiles pagesFocusAt pagesReason pagesWhere
        """,
    },
    ("sheet.js", "shell.js"): {
        "The sheet builds with h(), says the shell's words and reads its route.": """
            FIRM_LEVELS h screenWords shellRoute unanswered
        """,
    },
    ("shell.js", "app.js"): {
        "The shell drives app.js: its state and vocabulary, its calls, notices, lock, pass and dialogs"
        " (SPEC-shell 4); setupDraft is the setup page's draft, which app.js's saveRoot sends.": """
            $ active adoptList appRouteChanged call clearLock clearNotice dialogStack editorDensityChanged
            el engagements failed failureSentence fill forgetSortAnswers households keyedNotice
            lastState locked lockStale markShared notice openAbout openAddReturn openEditor
            openHouseholdEditor openNewHousehold openRoll openSafeguards openSchedule paths
            removeScheduleHere repairSchedule runScan saveRoot scanning setupDraft showReturn stopPass
            storeRead storeWrite takeReply toast toastWord vocab
        """,
    },
    ("shell.js", "tooltip.js"): {
        "The shell's tips, and Escape hiding a showing one first (P130).": """
            hideTip setTip setTipIfCut tipKey
        """,
    },
    ("shell.js", "pages.js"): {
        "The shell routes to the pages and hands them the keys, the menu, the lists and their stored"
        " order and widths.": """
            pagesAdopt pagesClientsAll pagesClientType pagesClosePanel pagesColumnKey pagesDraw
            pagesEnter pagesKey pagesLeave pagesListOf pagesMenu pagesPageAt pagesPanelOpen
            pagesReasonPick pagesResetWidths pagesStoredOrder pagesTab pagesTally
            pagesVirtualMeasureSaid
        """,
    },
    ("shell.js", "sheet.js"): {
        "The menu opens the side sheet's Check and Draft Reminder; a fresh state or a navigation closes it.": """
            closeSheet openCheck openReminder sheetStateArrived
        """,
    },
    ("shell.js", "pilot.js"): {
        "Help > Terms.": """
            PilotTerms
        """,
    },
    ("shell.js", "tour.js"): {
        "Help > Tour.": """
            PilotTour
        """,
    },
    ("pilot.js", "app.js"): {
        "The pilot asks the vocabulary whether its command exists before it records.": """
            vocab
        """,
    },
    ("pilot.js", "tooltip.js"): {
        "The terms card hands a key to the tooltip first, as the shell does (P130).": """
            tipKey
        """,
    },
    ("pilot.js", "pilot-content.js"): {
        "The pilot's own words and edition.": """
            PILOT
        """,
    },
    ("pilot.js", "tour.js"): {
        "The tour starts once the terms are signed, the first time.": """
            PilotTour
        """,
    },
    ("tour.js", "tooltip.js"): {
        "The tour hands a key to the tooltip first (P130).": """
            tipKey
        """,
    },
    ("tour.js", "pilot-content.js"): {
        "The tour's steps and words.": """
            PILOT
        """,
    },
    ("tour.js", "pilot.js"): {
        "The tour builds with the pilot's make() and records that it was seen.": """
            PilotDom PilotRecord
        """,
    },
}

#: Today's writes across scripts (D-2 lists these five): (writer, owner, name).
#: A new one fails; it is the coupling a split must not grow.
WRITES = {
    ("app.js", "shell.js", "shellReturnStale"),   # the read a closing dialog owed is done
    ("app.js", "shell.js", "shellBack"),          # Start goes to the Overview however the page was reached
    ("shell.js", "app.js", "setupDraft"),         # the setup page's fields, which saveRoot sends
    ("shell.js", "pages.js", "pagesPageAt"),      # the page of a list the firm reply drew, or none
    ("shell.js", "pages.js", "pagesClientType"),  # Clients' type picked in the side list
}


def pinned() -> dict[tuple[str, str], list[str]]:
    return {pair: [name for names in reasons.values() for name in names.split()] for pair, reasons in SEAMS.items()}


def test_every_named_part_of_the_renderer_is_inside_the_scripts_the_page_loads():
    """R3.2: each list of scripts a claim covers is the page's own list or a
    part of it, and the app's scripts and the pilot's are the whole of it
    between them."""
    for part in (APP_SCRIPTS, PILOT_SCRIPTS, SHELL_SCRIPTS):
        assert part and set(part) <= set(RENDERER_SCRIPTS), part
        assert len(set(part)) == len(part), part
    assert set(SHELL_SCRIPTS) <= set(APP_SCRIPTS)
    assert sorted((*APP_SCRIPTS, *PILOT_SCRIPTS)) == sorted(RENDERER_SCRIPTS)
    assert "app.js" in APP_SCRIPTS and len(set(RENDERER_SCRIPTS)) == len(RENDERER_SCRIPTS)


def test_the_reader_keeps_code_and_blanks_what_is_not():
    source = "\n".join([
        'const a = "it\'s // not a comment";   // a comment naming shellGo',
        "const b = `x ${call(['list'])} y ${`z ${shellGo}`}`;",
        "/* shellRoute",
        "   in a block */ const c = text.replace(/[/\"']+/g, '') / 2;",
        "if (x) return /shellKey/.test(y);",
    ])
    out = js_code(source)
    assert len(out) == len(source)
    assert out.split("\n") == [
        'const a = "' + " " * 21 + '";' + " " * 30,
        "const b = `  ${call(['    '])}   ${`  ${shellGo}`}`;",       # a template's code is kept
        " " * 13,
        " " * 17 + "const c = text.replace(/" + " " * 6 + "/g, '') / 2;",   # a division after a bracket
        "if (x) return /" + " " * 8 + "/.test(y);",                  # a regular expression after return
    ]


def test_stripped_js_takes_out_the_comments_the_reader_finds_and_nothing_inside_a_string(tmp_path):
    """SPEC-architecture-p6 R6.1.2: stripped_js removes what js_code reads as
    a comment - a block comment to nothing, a line comment with the blank space
    before it, as it always took one (here the blank line and the whole-line
    comment after the template go together) - and keeps a ``//`` or a ``/*``
    inside a string, a template or a regular expression, where the old reader
    cut the template's ``/* this */`` and its second line."""
    script = tmp_path / "made-up.js"
    script.write_text("\n".join([
        'const a = "http://x"; // a comment',
        "/* a block",
        "   comment */ const b = `see /* this */ and",
        "// this, still the template`;",
        "",
        "// a whole-line comment",
        "const c = s.split(/\\/\\//);   // and a trailing one",
        "",
    ]), encoding="utf-8", newline="\n")
    assert stripped_js(script) == "\n".join([
        'const a = "http://x";',
        " const b = `see /* this */ and",
        "// this, still the template`;",
        "const c = s.split(/\\/\\//);",
        "",
    ])


def test_the_reader_reads_every_script_the_page_loads_and_the_double():
    """Every script, and the harness's double of app.js, reads whole: an
    unclosed string, template or regular expression would be an error, and
    the code keeps the script's length and lines. No top-level declaration
    takes a form the table cannot read (a destructuring)."""
    texts = {name: read(name) for name in RENDERER_SCRIPTS}
    texts["app-stub.js"] = (HARNESS / "app-stub.js").read_text(encoding="utf-8")
    for name, text in texts.items():
        out = js_code(text)
        assert len(out) == len(text) and out.count("\n") == text.count("\n"), name
        assert not re.search(r"(?m)^(?:let|const|var) [\[{]", out), name


def test_no_two_scripts_declare_the_same_top_level_name():
    """In one global scope a second top-level ``let`` or ``const`` of a name
    is an error when the page loads, and a second ``function`` silently
    replaces the first."""
    assert owners()


def test_the_names_each_script_takes_from_another_are_todays_table():
    """R3.7, D-2. A pair or a name the table does not hold is a new seam:
    add it to SEAMS on purpose, under a line that says why. A name the table
    holds that no script uses any more is taken off."""
    for pair, reasons in SEAMS.items():
        assert all(why.strip() and names.split() for why, names in reasons.items()), pair
        assert len(pinned()[pair]) == len(set(pinned()[pair])), pair
    found = seams()
    table = {pair: set(names) for pair, names in pinned().items()}
    new = {pair: sorted(names - table.get(pair, set())) for pair, names in found.items() if names - table.get(pair, set())}
    gone = {pair: sorted(names - found.get(pair, set())) for pair, names in table.items() if names - found.get(pair, set())}
    assert new == {}, f"names one script takes from another that SEAMS does not hold: {new}"
    assert gone == {}, f"names SEAMS holds that are no longer used across scripts: {gone}"


def test_the_writes_across_scripts_are_todays_five():
    """D-2: a script that assigns to another script's top-level ``let`` is
    the coupling a split must not grow. A new one fails; one taken away is
    taken off WRITES."""
    assert writes() == WRITES


def the_double_mode() -> tuple[list[str], list[str]]:
    """The scripts the harness loads beside its double of app.js, and the
    ones it drops, read from the server's own page: every script the page
    loads but app.js, which the double replaces, unless a ``replace`` takes
    it out (sheet.js, today). Every ``replace`` in the double's branch is
    read - app.js's, the one that adds the harness's scripts before
    ``</body>``, and the drops - so a drop written another way fails here
    rather than going unseen."""
    serve = (HARNESS / "serve.mjs").read_text(encoding="utf-8")
    double = serve[serve.index('if (mode === "double") {'):serve.index("} else {")]
    assert "html.replace('<script src=\"app.js\"></script>'" in double and "/harness/app-stub.js" in double
    dropped = re.findall(r"""html\.replace\('\s*<script src="([^"]+)"></script>\\n', ""\)""", double)
    assert double.count("html.replace(") == 2 + len(dropped), double
    assert set(dropped) < set(RENDERER_SCRIPTS) and "app.js" not in dropped, dropped
    return [name for name in RENDERER_SCRIPTS if name != "app.js" and name not in dropped], dropped


def el_attributes(text: str) -> list[str]:
    held = text[text.index("const EL_ATTRIBUTES = new Set(["):]
    return re.findall(r'"([\w-]+)"', held[:held.index("]);")])


def test_the_double_defines_every_name_the_scripts_beside_it_use_of_app_js_and_of_the_scripts_it_drops():
    """R3.8, D-8: pilot/harness/app-stub.js is "the contract, written as
    code". It stands in for app.js and for every script the harness drops
    beside it: each of their names the seam table says a script loaded with
    the double uses, the double defines, so no path in the harness throws for
    a name it lacks (pages.js's Check-then-press read sheet.js's sheetNow and
    sheetPress, which it lacked). And it builds with app.js's own attribute
    list, so a node the page may build is one the double builds too."""
    stub = (HARNESS / "app-stub.js").read_text(encoding="utf-8")
    beside, dropped = the_double_mode()
    stood_in_for = {"app.js", *dropped}
    used = set().union(*(names for (user, owner), names in seams().items() if owner in stood_in_for and user in beside))
    missing = sorted(used - set(declared(js_code(stub))))
    assert missing == [], missing
    assert el_attributes(stub) == el_attributes(read("app.js"))


# ── the named-script guard (SPEC-architecture-p6 R6.1.3) ──────────────────
#
# Phase 6 takes app.js, shell.js and main.js apart, so a test that read one by
# its file name would lose the code a move takes out of it, and a claim that
# something is absent would go on passing on code it no longer reads.

#: The sixteen scripts phase 6 creates (SPEC-architecture-p6 section 1), named
#: before they exist so a test that names one fails from the start. Each joins
#: RENDERER_SCRIPTS or MAIN_SCRIPTS in the job that creates it; P6.18 deletes
#: this list once every one has (R6.18.4).
PLANNED = ("api-client.js", "notices.js", "dialogs.js", "reminder-card.js", "review-rows.js", "household.js", "editor.js",
           "schedule.js", "pass.js", "firm-loader.js", "shell-words.js", "logs.js", "last-pass-watch.js", "open-path.js",
           "menu.js", "engine.js")
#: The scripts phase 6 splits whose readers are not yet retargeted: P6.2 takes
#: app.js off this list and P6.3 the other two, then deletes it (R6.2.1, R6.3.1).
NOT_YET = ("app.js", "shell.js", "main.js")
#: The scripts the page loads that phase 6 does not split: a test may name them.
NOT_SPLIT = ("tooltip.js", "pages.js", "sheet.js", "pilot-content.js", "pilot.js", "tour.js")

#: Each place a test names a split script on purpose, to why: the claim is
#: about that file as a file. A place is (test file, function), the function
#: being the outermost ``def`` the literal sits in, ``None`` for module level
#: and ``"*"`` for the whole file. A place that no longer names a split script
#: (or a NOT_YET one) has outlived its claim and fails until it is taken off.
FILE_NAMED: dict[tuple[str, str | None], str] = {
    ("node_harness.py", None):
        "APP_FAMILY is app.js and the scripts listed before it, so it names app.js as the script the family ends at.",
    ("node_harness.py", "_main_scripts"):
        "MAIN_SCRIPTS starts at main.js, the main process's entry (package.json's main), and follows what it requires.",
    ("node_harness.py", "run_menu"):
        "run_menu runs main.js itself under node, as Electron starts it, so it names the entry point.",
    ("test_repo_map.py", "*"):
        "The made-up repositories the map's tests build name their own files, app.js and main.js among them.",
    ("test_renderer_seams.py", None):
        "SEAMS and WRITES are keyed by the scripts that share names, and PLANNED and NOT_YET name the scripts this"
        " guard watches: tables of the page's files, re-derived by each move (SPEC-architecture-p6 section 3).",
    ("test_renderer_seams.py", "the_double_mode"):
        "serve.mjs's double takes app.js out of the page by its file name.",
    ("test_renderer_seams.py", "test_the_double_defines_every_name_the_scripts_beside_it_use_of_app_js_and_of_the_scripts_it_drops"):
        "The double stands in for app.js and builds with app.js's own EL_ATTRIBUTES.",
}


def split_scripts() -> set[str]:
    """Every script phase 6 splits, or creates, whose readers are retargeted."""
    return set(RENDERER_SCRIPTS + MAIN_SCRIPTS + PLANNED) - set(NOT_SPLIT) - set(NOT_YET)


def script_literals(text: str, names: set[str]) -> list[tuple[str | None, str, str, int]]:
    """(function, script, literal, line) for every string literal in a test
    file's code that is the name of one of ``names`` or ends with ``/`` and
    one, in the order of their lines. The function is the outermost ``def``
    around it, its decorators and defaults included; ``None`` at module
    level."""
    found = []

    def visit(node: ast.AST, function: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if function is None and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                named = child.value.rsplit("/", 1)[-1]
                if named in names:
                    found.append((function, named, child.value, child.lineno))
            visit(child, function)

    visit(ast.parse(text), None)
    return sorted(found, key=lambda one: one[3])


def file_named_reads(sources: dict[str, str], split: set[str], not_yet: set[str],
                     listed: dict[tuple[str, str | None], str]) -> tuple[list[str], list[tuple[str, str | None]]]:
    """The literals of ``sources`` (test file to its text) that name a split
    script outside a ``listed`` place, and the listed places that name none
    (a NOT_YET name counts, so a place it still holds has not rotted)."""
    unlisted, held = [], set()
    for file, text in sources.items():
        for function, named, literal, line in script_literals(text, split | not_yet):
            places = {(file, function), (file, "*")} & set(listed)
            held |= places
            if named in split and not places:
                unlisted.append(f"{file}:{line} ({function or 'module level'}) {literal!r}")
    return unlisted, sorted(set(listed) - held, key=str)


def test_no_test_reads_a_script_this_phase_splits_by_its_file_name():
    """R6.1.3, D-5: a test names a script phase 6 splits (or one it will
    create) only where the claim is about that file as a file, listed in
    FILE_NAMED with why; everywhere else a claim reads the code by what it is
    (``js_function``, ``main_function``, ``js_block``, ``lift_line``,
    ``renderer_text``, ``main_text``), so a move cannot take code out from
    under it. And an exemption never outlives its claim: a listed place that
    names no split script fails until it is taken off, so a read added there
    later cannot hide behind it."""
    assert len(set(PLANNED)) == len(PLANNED) == 16 and not set(PLANNED) & set(NOT_SPLIT), PLANNED
    assert set(NOT_YET) <= set(RENDERER_SCRIPTS + MAIN_SCRIPTS) and set(NOT_SPLIT) <= set(RENDERER_SCRIPTS)
    sources = {path.name: path.read_text(encoding="utf-8") for path in sorted((REPO / "tests").glob("*.py"))}
    unlisted, rotted = file_named_reads(sources, split_scripts(), set(NOT_YET), FILE_NAMED)
    assert unlisted == [], f"tests that read a split script by its file name, outside FILE_NAMED: {unlisted}"
    assert rotted == [], f"FILE_NAMED places that no longer name a split script (the claim has rotted): {rotted}"


def test_the_named_script_guard_fails_a_read_outside_file_named_and_a_place_that_has_rotted():
    """The guard itself, on made-up test files and made-up script names."""
    sources = {
        "test_one.py": "TABLE = ('carved.js', 'kept.js')\n\n"
                       "@mark('fixtures/carved.js')\ndef test_named():\n    read('app/carved.js')\n\n"
                       "def test_listed():\n    def inner():\n        read('carved.js')\n\n"
                       "def test_clean():\n    read('kept.js')\n    read('uncarved.js')\n    read('carved.json')\n",
        "test_two.py": "def one():\n    read('carved.js')\n\ndef two():\n    read('src/carved.js')\n\ndef three():\n    read('later.js')\n",
    }
    split, later = {"carved.js"}, {"later.js"}
    every = {("test_one.py", None): "a table", ("test_one.py", "test_named"): "", ("test_one.py", "test_listed"): "",
             ("test_two.py", "*"): "the whole file"}
    # Inside a listed place a literal passes: a module-level table, a function (its decorator and a def nested in
    # it), and every function of a file listed whole.
    assert file_named_reads(sources, split, later, every) == ([], [])
    # Outside one it fails: the name alone or a path ending in it, at module level, in a decorator, in a nested def.
    unlisted, _ = file_named_reads(sources, split, later, {("test_two.py", "*"): ""})
    assert unlisted == ["test_one.py:1 (module level) 'carved.js'", "test_one.py:3 (test_named) 'fixtures/carved.js'",
                        "test_one.py:5 (test_named) 'app/carved.js'", "test_one.py:9 (test_listed) 'carved.js'"]
    # Without its "*" place each function of test_two fails; a not-yet name is never flagged.
    assert file_named_reads({"test_two.py": sources["test_two.py"]}, split, later, {}) == (
        ["test_two.py:2 (one) 'carved.js'", "test_two.py:5 (two) 'src/carved.js'"], [])
    # A listed place that names no split script has rotted, unless a not-yet name still holds it.
    rotted = {**every, ("test_one.py", "test_clean"): "", ("test_three.py", "*"): "", ("test_two.py", "three"): ""}
    assert file_named_reads(sources, split, later, rotted) == ([], [("test_one.py", "test_clean"), ("test_three.py", "*")])


# ── the load test (SPEC-architecture-p6 R6.1.4) ───────────────────────────

#: The page's scripts in one node context, in order, as the window runs its
#: classic scripts: one global scope, so a script that meets a binding a later
#: script makes - a ``let`` it reads, a function it calls - throws here as it
#: would there. What the page provides is a permissive stand-in (any property
#: of one is another, calling or constructing one gives one, a value set on one
#: is kept, and one reads as "" or 0, iterates as empty and is never taken for
#: a promise), with ``document.readyState`` "loading", so the app's start waits
#: for a DOMContentLoaded that never comes. The probe exits once the last
#: script has run (the pilot's timers would hold node open).
LOAD_PROBE = r"""
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const [folder, listed] = process.argv.slice(2);
function standIn(held = {}) {
  return new Proxy(function () {}, {
    get(target, key) {
      if (Object.prototype.hasOwnProperty.call(held, key)) return held[key];
      if (key === Symbol.toPrimitive) return (hint) => (hint === "number" ? 0 : "");
      if (key === Symbol.iterator) return function* () {};
      if (key === "then") return undefined;
      return standIn();
    },
    set(target, key, value) { held[key] = value; return true; },
    apply: () => standIn(),
    construct: () => standIn(),
  });
}
const context = vm.createContext({
  window: standIn(), document: standIn({ readyState: "loading" }), navigator: standIn(), localStorage: standIn(),
  console: new console.Console(process.stderr), setTimeout, clearTimeout, setInterval, clearInterval,
});
const scripts = JSON.parse(listed);
for (const name of scripts) {
  try {
    new vm.Script(fs.readFileSync(path.join(folder, name), "utf8"), { filename: name }).runInContext(context);
  } catch (err) {
    process.stdout.write(`${name} threw while loading: ${(err && err.stack) || err}\n`);
    process.exit(1);
  }
}
process.stdout.write(`${scripts.length} scripts loaded\n`);
process.exit(0);
"""


def load_in_order(folder: Path, scripts: list[str], tmp_path: Path) -> subprocess.CompletedProcess:
    """Run ``scripts`` from ``folder`` in one context, in order (LOAD_PROBE)."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    probe = tmp_path / "load_probe.js"
    probe.write_text(LOAD_PROBE, encoding="utf-8", newline="\n")
    return subprocess.run([NODE, str(probe), str(folder), json.dumps(scripts)], capture_output=True, text=True,
                          encoding="utf-8", timeout=60, check=False)


def test_every_script_the_page_loads_runs_in_order_in_one_scope(tmp_path):
    """R6.1.4: every ``<script src>`` of index.html, the vendored libraries
    too, loads in order in one scope without throwing. A split that put a
    script before the one whose binding it meets at load - a carved-out script
    that ran code, or wiring moved above the function it names - fails here,
    in the suite, rather than in the window."""
    scripts = re.findall(r'<script src="([^"]+)"', read("index.html"))
    assert set(RENDERER_SCRIPTS) < set(scripts)
    done = load_in_order(REPO / "app" / "renderer", scripts, tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout == f"{len(scripts)} scripts loaded\n", done.stdout


def test_a_script_that_meets_a_later_scripts_binding_at_load_fails_the_load_test(tmp_path):
    """The load test on made-up scripts: reading a later script's ``let``, or
    calling a later script's function, as the page loads throws; the same
    scripts in the other order load, so the probe tells the two apart."""
    (tmp_path / "early-let.js").write_text("const early = later + 1;\n", encoding="utf-8")
    (tmp_path / "early-call.js").write_text("start();\n", encoding="utf-8")
    (tmp_path / "late.js").write_text("let later = 1;\nfunction start() { return later; }\n", encoding="utf-8")
    for early, unbound in (("early-let.js", "later"), ("early-call.js", "start")):
        done = load_in_order(tmp_path, [early, "late.js"], tmp_path)
        assert done.returncode == 1 and done.stdout.startswith(f"{early} threw while loading"), done.stdout + done.stderr
        assert f"ReferenceError: {unbound} is not defined" in done.stdout, done.stdout
        assert load_in_order(tmp_path, ["late.js", early], tmp_path).stdout == "2 scripts loaded\n"


#: A top-level statement that declares and runs nothing as the page loads.
DECLARES = re.compile(r"(?:async function|function|class|let|const)\b")

#: After a ``}`` that brings the depth back to 0, a word that starts a new
#: statement: not one that carries the statement on (``} else {``), and not a
#: template's next ``${``, whose code :func:`js_code` keeps.
AFTER_A_BRACE = re.compile(r"(?!(?:else|catch|finally|instanceof|in)\b|\$\{)[A-Za-z_$]")


def top_level_statements(text: str) -> list[tuple[int, str]]:
    """(line, first line) of each top-level statement of a script's code
    (:func:`js_code`'s, so brackets in strings and comments are gone), the
    first line read from where the statement starts. One starts on a line at
    bracket depth 0, either after one that ended (with ``;`` or ``}``) or at
    the line's first column; and within a line, at the code after a ``;`` at
    depth 0, or at a word after a ``}`` that brings the depth back to 0
    (:data:`AFTER_A_BRACE`), so ``const a = 1; init();`` is two statements
    and the second is read."""
    found, depth, open_statement = [], 0, False
    for number, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if depth == 0 and stripped and (not open_statement or not line[0].isspace()):
            found.append((number, stripped))
        for column, one in enumerate(line):
            if one in "([{":
                depth += 1
            elif one in ")]}":
                depth -= 1
            if depth == 0 and one in ";}":
                rest = line[column + 1:].strip()
                if rest and (one == ";" or AFTER_A_BRACE.match(rest)):
                    found.append((number, rest))
        if stripped:
            open_statement = depth > 0 or not stripped.endswith((";", "}"))
    return found


def test_every_script_of_app_js_family_but_app_js_holds_declarations_only():
    """R6.1.4, section 3: a script carved out of app.js loads before it and
    holds only ``function``, ``async function``, ``class``, ``let`` and
    ``const`` declarations at its top level, so nothing in it runs as the page
    loads; every statement that does stays in app.js, the family's last
    script. The reader sees such a statement - in made-up code, where one also
    follows a declaration on its line, and in app.js's own start - so it would
    see one in a carved-out script."""
    made_up = js_code('"use strict";\nfunction a() {\n  b();\n}\nconst c = [\n  1,\n];\nlet d = "}" +\n  2;\n'
                      "class E {}\nasync function f() {}\nif (d) {\n  a();\n} else {\n  b();\n}\nfoo(); // c\n"
                      "const g = 1; h();\nfunction i() {}  j();\nconst k = [\n  1,\n]; l();\n"
                      "const m = `${d} and ${g}`;\n")
    assert [line for _, line in top_level_statements(made_up) if not DECLARES.match(line)] == [
        '"          ";', "if (d) {", "foo();", "h();", "j();", "l();"]
    *carved, keeper = APP_FAMILY
    assert any(not DECLARES.match(line) for _, line in top_level_statements(code(keeper))), keeper
    loose = [f"{script}:{number} {line}" for script in carved for number, line in top_level_statements(code(script))
             if not DECLARES.match(line)]
    assert loose == [], f"statements that run as the page loads, in a script carved out of app.js: {loose}"
