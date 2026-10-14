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
enough that the reader below - strings, templates, comments and regular
expressions - is all the claim needs, and its own tests say what it does.

The lists of scripts a claim covers are :data:`tests.node_harness.RENDERER_SCRIPTS`
- the ones ``index.html`` loads - or a named part of it (R3.2), so a part that
named a script the page does not load would be a claim about nothing.
"""

import re
from functools import cache

from tests.node_harness import APP_SCRIPTS, PILOT_SCRIPTS, RENDERER_SCRIPTS, REPO, SHELL_SCRIPTS, read

HARNESS = REPO / "pilot" / "harness"

#: A word after which a ``/`` begins a regular expression rather than a division.
_BEFORE_A_REGEX = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void",
                   "throw", "instanceof", "yield", "await"}


def js_code(text: str) -> str:
    """The script's code alone: its comments, the insides of its strings, the
    text of its template literals and its regular expressions blanked to
    spaces, and the code inside a template's ``${...}`` kept. The length and
    every newline are kept, so a place in it is a place in the script.

    A ``/`` begins a regular expression after an operator, an opening
    bracket, a comma or a keyword such as ``return``, and is a division after
    a name, a number or a closing bracket - the rule the scripts are written
    to. An unclosed string, template or regular expression is an error, not a
    guess."""
    out = list(text)
    n = len(text)
    depth = [0]   # open braces at each level of code; a template's ${ opens a level

    def blank(start: int, end: int) -> None:
        for k in range(start, end):
            if out[k] != "\n":
                out[k] = " "

    def template(i: int) -> tuple[int, bool]:
        """From just inside a template's text: past its closing backtick
        (False), or past a ``${`` that opens code inside it (True)."""
        start = i
        while i < n:
            if text[i] == "\\":
                i += 2
            elif text[i] == "`":
                blank(start, i)
                return i + 1, False
            elif text.startswith("${", i):
                blank(start, i)
                return i + 2, True
            else:
                i += 1
        raise ValueError(f"an unclosed template literal at {start}")

    def regex_may_start(i: int) -> bool:
        j = i - 1
        while j >= 0 and text[j] in " \t\r\n":
            j -= 1
        if j < 0 or text[j] in "(,=:[!&|?{};+-*%<>~^":
            return True
        if text[j].isalnum() or text[j] in "_$":
            k = j
            while k >= 0 and (text[k].isalnum() or text[k] in "_$"):
                k -= 1
            return text[k + 1:j + 1] in _BEFORE_A_REGEX
        return False

    i = 0
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif text.startswith("/*", i):
            end = text.index("*/", i + 2) + 2
            blank(i, end)
            i = end
        elif c in "'\"":
            j = i + 1
            while text[j] != c:
                if text[j] == "\n":
                    raise ValueError(f"an unclosed string at {i}")
                j += 2 if text[j] == "\\" else 1
            blank(i + 1, j)
            i = j + 1
        elif c == "`":
            i, opened = template(i + 1)
            if opened:
                depth.append(0)
        elif c == "/" and regex_may_start(i):
            j, in_class = i + 1, False
            while text[j] != "/" or in_class:
                if text[j] == "\n":
                    raise ValueError(f"an unclosed regular expression at {i}")
                if text[j] == "\\":
                    j += 1
                elif text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                j += 1
            blank(i + 1, j)
            i = j + 1
        elif c == "{":
            depth[-1] += 1
            i += 1
        elif c == "}" and depth[-1] == 0 and len(depth) > 1:
            depth.pop()
            i, opened = template(i + 1)
            if opened:
                depth.append(0)
        else:
            if c == "}":
                depth[-1] -= 1
            i += 1
    return "".join(out)


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
