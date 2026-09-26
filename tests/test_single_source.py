"""Every fact that has to cross a language boundary, pinned to its owner.

Python is the source of truth for the tracker's vocabulary and defaults.
Some consumers cannot import Python: the Electron shell, the batch file, CI
config, .gitignore, the stylesheet. Each carries one literal, and this file
is what makes changing the Python owner without the literal a failing test
instead of a silent drift. Nothing here restates a value; every assertion
reads the owner and the consumer and compares them.
"""

import json
import re
from pathlib import Path

import pytest

from tracker.content_check import RETIRED_CACHE_FILENAME

REPO = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_the_electron_shell_uses_the_settings_env_names_python_defines():
    from tracker.settings import ENV_PRODUCT_NAME, ENV_SETTINGS_DIR

    main_js = read("app/main.js")
    assert f"{ENV_SETTINGS_DIR}:" in main_js
    assert f"{ENV_PRODUCT_NAME}:" in main_js


def test_the_product_name_has_one_home():
    from tracker.settings import product_name

    package = json.loads(read("app/package.json"))
    assert product_name() == package["productName"]
    # The renderer and the shell read it at runtime; nothing else types it.
    for rel in ("app/renderer/index.html", "app/renderer/app.js", "app/renderer/style.css",
                "Build App.bat", "Start App.bat", "docs/workflow.md",
                "tracker/settings.py", "tracker/scheduling.py"):
        assert package["productName"] not in read(rel), rel
    # The two documents titled after the product carry it in their title only.
    for rel in ("README.md", "docs/ROADMAP.md"):
        first, _, rest = read(rel).partition("\n")
        assert package["productName"] in first and package["productName"] not in rest, rel


def test_the_version_and_package_name_have_one_home():
    package = json.loads(read("app/package.json"))
    pyproject = read("pyproject.toml")
    assert re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M).group(1) == package["version"]
    assert re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.M).group(1) == package["name"]
    assert re.search(r'^description\s*=\s*"([^"]+)"', pyproject, re.M).group(1) == package["description"]


def test_the_frozen_api_name_has_one_home():
    package = json.loads(read("app/package.json"))
    api_name = package["config"]["apiName"]
    assert api_name not in read("app/main.js")          # read from package.json at runtime
    assert api_name not in read("Build App.bat")         # read from package.json at build time
    assert "config.apiName" in read("Build App.bat") and "config.apiName" in read("app/main.js")
    # The frozen executable's place inside the package: Electron's resources
    # folder, a subfolder named after the API, holding <api>.exe. The shell
    # looks there and the build script copies there.
    assert "resources\\%API%" in read("Build App.bat")
    assert "process.resourcesPath, API_NAME, `${API_NAME}.exe`" in read("app/main.js")


def test_the_shell_and_the_preload_agree_on_every_ipc_channel():
    handled = set(re.findall(r'ipcMain\.handle\("([a-z-]+)"', read("app/main.js")))
    invoked = set(re.findall(r'ipcRenderer\.invoke\("([a-z-]+)"', read("app/preload.js")))
    assert handled == invoked and handled
    # The one channel the shell sends on (decision 209, the review's S7):
    # the launch step finished having run, and the page listens for it.
    sent = set(re.findall(r'const [A-Z_]+_CHANNEL = "([a-z-]+)"', read("app/main.js")))
    heard = set(re.findall(r'ipcRenderer\.on\("([a-z-]+)"', read("app/preload.js")))
    assert sent == heard == {"after-install-done"}
    assert "webContents.send(LAUNCH_DONE_CHANNEL)" in read("app/main.js")
    assert "window.tracker.onAfterInstallDone(" in read("app/renderer/app.js")


def test_the_renderer_calls_only_commands_the_api_has_and_types_no_flag():
    import tracker.api as api

    js = read("app/renderer/app.js")
    called = set(re.findall(r'call\(\["([a-z-]+)"', js)) | set(re.findall(r'withEng\("([a-z-]+)"\)', js))
    assert called <= set(api.COMMANDS), called - set(api.COMMANDS)
    # The four a person presses on a card, each one an API command and none
    # of them a path the page walks itself (decisions 77, 110).
    assert {"assign", "dismiss", "unfile", "restore"} <= called
    assert api.ENGAGEMENT_FLAG not in js
    assert "vocab.engagement_flag" in js


def test_accept_and_file_it_are_one_call_site():
    """Decision 114: Accept on a card is File it on the list, by construction.

    The card takes the top suggestion in one click and the list takes any
    request after reading the whole picker, but the filing underneath is one
    decision, and two places building the ``assign`` call could disagree
    about the keyword, the record version (decision 112) or what is said
    afterwards. One function makes the call and every button reaches it, so
    there is nothing for them to differ about; the same function is what
    Keep it here on a moved copy (decision 110) goes through.

    **One call site per decision**, which since decision 129 is two: a
    hand-over is a different decision from a filing - it closes the row
    here and opens one in the return that takes the document - and it
    reaches the same command with a ``target``. The list and the deck both
    reach *that* through one function too.
    """
    js = read("app/renderer/app.js")
    assert js.count('withEng("assign")') == 2
    assert len(re.findall(r"\bfileRow\(", js)) == 4      # the one definition and its three callers
    # The hand-over's own call site is the only one that names a target,
    # and the two buttons that offer it both reach it.
    assert js.count("target: $(\"ho-return\").value") == 1
    assert len(re.findall(r"\bopenHandOver\(", js)) == 3


def test_the_review_mode_key_is_a_key_and_not_a_word():
    """Decision 114: which rendering a person is on is remembered on the
    machine, under a ``localStorage`` key - nothing about the queue is
    recorded (decision 83). A key is not a word anybody reads, which is why
    the renderer may type it at all, so it must be no word the API says and
    must carry no space."""
    import tracker.api as api

    js = read("app/renderer/app.js")
    key = re.search(r'const REVIEW_MODE_STORAGE_KEY = "([^"]+)";', js).group(1)
    assert key and not re.search(r"\s", key)
    assert key not in {str(word) for word in api._vocab()["review_labels"].values()}


def test_the_shell_runs_only_commands_the_api_has():
    # main.js learns the allowlist from the API's vocabulary; before that it
    # runs exactly one command, the one the renderer calls first, and that
    # command must exist in Python.
    import tracker.api as api

    main_js = read("app/main.js")
    bootstrap = re.search(r'const BOOTSTRAP_COMMAND = "([a-z-]+)";', main_js).group(1)
    assert bootstrap in api.COMMANDS
    first_call = re.search(r'call\(\["([a-z-]+)"\]', read("app/renderer/app.js")).group(1)
    assert first_call == bootstrap
    assert "vocab.commands" in main_js and "vocab.engagement_flag" in main_js
    assert "openable.has(" in main_js                       # opens only paths the API reported
    assert 'proc.on("close", (code)' in main_js             # the exit code is not discarded
    assert "TRACKER_TIMEOUT_MS" in main_js and "proc.kill()" in main_js
    assert "sandbox: true" in main_js and "setWindowOpenHandler" in main_js


def test_the_packaged_app_has_no_console_and_sends_the_api_utf8_it_serialised_first():
    """Decision 176: DevTools in the packaged app is a console from which a
    person at the machine calls the API with any payload; and a payload is
    serialised before the tracker starts, in UTF-8, which is how the API
    reads it (``tracker.api._read_spec``)."""
    main_js = read("app/main.js")
    assert "devTools: !app.isPackaged" in main_js
    run = main_js[main_js.index("function runTracker"):]
    assert run.index("JSON.stringify(payload)") < run.index("spawn(")
    assert 'proc.stdin.write(body, "utf8")' in run


def test_the_packaged_app_has_no_menu_and_the_source_app_runs_its_private_python():
    """Decision 191. The packaged app removes Electron's default menu (E-7)
    before its window is made - the menu carries reload, zoom and the
    developer-tools accelerator. From source, the shell runs the Python
    Setup.bat made, by its full path, never a bare ``python`` from the
    search path, and when that is missing it says so in the lock tool's
    own sentence."""
    from tools.lockfiles import NOT_SET_UP

    main_js = read("app/main.js")
    window = main_js[main_js.index("function createWindow"):]
    assert window.index("if (app.isPackaged) Menu.setApplicationMenu(null);") < window.index("new BrowserWindow(")
    assert re.search(r"const \{ app, BrowserWindow, Menu,", main_js)
    assert 'spawn("python"' not in main_js
    assert 'path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")' in main_js
    assert 'path.join(REPO_ROOT, ".venv", "bin", "python")' in main_js
    sentence = "".join(re.findall(r'"([^"]*)"', main_js.split("const NOT_SET_UP =", 1)[1].split(";", 1)[0]))
    assert sentence == NOT_SET_UP


#: The Electron module main.js is run against in the claim below: an app that
#: answers the single-instance lock as told, and a window that records being
#: brought forward. Every other part of the shell is left real.
_ELECTRON_STUB = r"""
const Module = require("module");
const seen = { asked: false, quit: 0, windows: 0, restored: 0, focused: 0, events: [] };
const handlers = {};
const win = {
  isMinimized: () => true,
  restore() { seen.restored += 1; },
  focus() { seen.focused += 1; },
  loadFile() {},
  webContents: { setWindowOpenHandler() {}, on() {} },
};
const opened = [];
class BrowserWindow {
  constructor() { seen.windows += 1; opened.push(win); return win; }
  static getAllWindows() { return opened; }
}
const electron = {
  app: {
    isPackaged: false,
    requestSingleInstanceLock() { seen.asked = true; return process.argv[3] === "first"; },
    quit() { seen.quit += 1; },
    on(name, fn) { seen.events.push(name); handlers[name] = fn; },
    whenReady: () => Promise.resolve(),
  },
  BrowserWindow, ipcMain: { handle() {} }, shell: {}, dialog: {},
};
const load = Module._load;
Module._load = function (request, ...rest) {
  return request === "electron" ? electron : load.call(this, request, ...rest);
};
require(process.argv[2]);
setImmediate(() => {
  if (handlers["second-instance"]) handlers["second-instance"]();
  process.stdout.write(JSON.stringify(seen));
});
"""


def test_the_app_opens_one_window(tmp_path):
    """A second launch of the app brings the first window forward and opens
    none of its own (decision 160, the audit's B-4): two windows were two
    editors, and the second's save silently reverted the first's.

    The real ``main.js``, run by node against a stand-in for Electron that
    answers the single-instance lock: held by this launch, it opens its one
    window and answers a second launch by restoring and focusing it; held
    by another, it quits before any window is made. Skipped where node is
    not on PATH (CI installs it)."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        import pytest

        pytest.skip("node is not on PATH (CI installs it)")
    harness = tmp_path / "one_window.js"
    harness.write_text(_ELECTRON_STUB, encoding="utf-8", newline="\n")

    def launch(which: str) -> dict:
        done = subprocess.run([node, str(harness), str(REPO / "app" / "main.js"), which],
                              capture_output=True, text=True, encoding="utf-8", timeout=60,
                              check=False)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)

    first = launch("first")
    assert first["asked"] and first["windows"] == 1 and first["quit"] == 0
    assert "second-instance" in first["events"]
    assert first["restored"] == 1 and first["focused"] == 1   # the second launch, answered
    second = launch("second")
    assert second["asked"] and second["quit"] == 1
    assert second["windows"] == 0 and "second-instance" not in second["events"]


def test_the_renderer_builds_the_page_from_data_not_html():
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in js, sink
    assert 'http-equiv="Content-Security-Policy"' in html
    assert "'unsafe-inline'" not in html and "'unsafe-eval'" not in html
    assert not re.search(r"<script[^>]*>[^<]", html)        # no inline script
    assert not re.search(r' on[a-z]+="', html)              # no inline handlers


def test_the_window_colour_is_read_from_the_stylesheet():
    assert re.search(r"--bg:\s*#", read("app/renderer/style.css"))
    main_js = read("app/main.js")
    assert "backgroundColor: pageBackground()" in main_js
    assert not re.search(r'backgroundColor:\s*"#', main_js)


def test_ci_tests_the_python_floor_pyproject_declares():
    floor = re.search(r'requires-python\s*=\s*">=([\d.]+)"', read("pyproject.toml")).group(1)
    assert f'python-version: "{floor}"' in read(".github/workflows/ci.yml")
    # Setup.bat is where a machine's Python is first asked (decision 191).
    assert f"Install Python {floor}+" in read("Setup.bat")
    assert f"sys.version_info < ({floor.replace('.', ', ')})" in read("Setup.bat")
    # Prose says "the floor pyproject.toml declares"; nobody types the number.
    for rel in ("README.md", "docs/ROADMAP.md", "CLAUDE.md", "docs/workflow.md"):
        assert not re.search(r"Python 3\.\d+\+?", read(rel)), rel


def test_gitignore_knows_every_runtime_file_python_writes_outside_the_repo():
    """The store counts, and so do the two files SQLite keeps beside it.

    It lives beside the settings file, which in a source checkout is the
    repository root: a developer who runs the app, or a subprocess test
    that does not name a store of its own, writes one into the tree.
    """
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import SETTINGS_FILENAME
    from tracker.store import STORE_FILENAME, STORE_SHM_FILENAME, STORE_WAL_FILENAME

    ignored = [line.strip() for line in read(".gitignore").splitlines()
               if line.strip() and not line.startswith("#")]
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME, LOG_FILENAME, STATUS_PAGE_FILENAME,
                 SCHEDULE_XML_FILENAME, SETTINGS_FILENAME,
                 STORE_FILENAME, STORE_WAL_FILENAME, STORE_SHM_FILENAME):
        assert ignored.count(name) == 1, name


def test_every_file_beside_the_store_is_ignored_by_git():
    """Decision 159 (the final review's MF1): the checkpoint, the last-pass
    file, recover's exports and a set-aside older store sit beside the
    store, which in a source checkout is this repository - and each holds
    client data or describes one machine. Asked of git itself, by the names
    the code writes, so a pattern that does not match is caught."""
    import subprocess

    from tracker.after_install import RECORD_FILENAME
    from tracker.checkpoint import CHECKPOINT_FILENAME, SET_ASIDE_SUFFIX
    from tracker.fsio import TEMP_SUFFIX
    from tracker.runner import LAST_PASS_FILENAME
    from tracker.store import RECOVERED_DIR, STORE_FILENAME

    aside = STORE_FILENAME + SET_ASIDE_SUFFIX.format(version=15)
    names = [CHECKPOINT_FILENAME, CHECKPOINT_FILENAME + "-wal", CHECKPOINT_FILENAME + "-shm",
             LAST_PASS_FILENAME, f"{LAST_PASS_FILENAME}.1234.abcd{TEMP_SUFFIX}",
             # Decision 209's note of the last after-install run.
             RECORD_FILENAME, f"{RECORD_FILENAME}.1234.abcd{TEMP_SUFFIX}",
             f"{RECOVERED_DIR}/J Park & Associates__Household__2025__Return-2026-09-26-120000.jsonl",
             aside, aside + ".1", aside + "-wal"]
    for name in names:
        asked = subprocess.run(["git", "check-ignore", "--no-index", "-q", name],
                               cwd=REPO, capture_output=True)
        assert asked.returncode == 0, name


def test_gitignore_knows_both_client_trees_and_every_file_written_inside_them():
    """Decision 176: the list above is the files beside the settings file.
    A pass over a client's folder copied into the checkout writes into the
    trees themselves - the record, the lock, the page, the README and what
    was taken out of an email - so each is ignored by the constant that
    names it, and both trees whole."""
    from tracker.filer import README_LOCK_FILENAME
    from tracker.layout import CLIENTS_TREE, OPENED_DIR_NAME, PRIVATE_TREE, README_NAME
    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME
    from tracker.view import VIEW_FILENAME

    ignored = [line.strip() for line in read(".gitignore").splitlines()
               if line.strip() and not line.startswith("#")]
    for name in (f"{CLIENTS_TREE}/", f"{PRIVATE_TREE}/", f"{OPENED_DIR_NAME}/", LEDGER_FILENAME,
                 LOCK_FILENAME, README_LOCK_FILENAME, README_NAME, VIEW_FILENAME):
        assert ignored.count(name) == 1, name


def test_openpyxl_is_imported_only_to_read_a_clients_spreadsheet():
    """Decision 104: nothing Excel remains in the tree but the tier-3 reader
    of a *client's* spreadsheet. ``openpyxl`` stays in requirements.txt for
    that one line, and a guard holds it there."""
    import ast
    import subprocess

    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
    hits = []
    for rel in tracked:
        if not (rel.startswith(("tracker/", "tools/", "app/")) or rel == "api_entry.py"):
            continue
        if rel.endswith(".py"):
            tree = ast.parse(read(rel))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "openpyxl" for a in node.names):
                    hits.append((rel, node.lineno))
                if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "openpyxl":
                    hits.append((rel, node.lineno))
        elif rel.endswith((".js", ".html", ".css", ".json")):
            assert "openpyxl" not in read(rel), rel
    assert len(hits) == 1 and hits[0][0] == "tracker/content_check.py", hits
    source = read("tracker/content_check.py").splitlines()
    start = next(i for i, line in enumerate(source) if line.startswith("def _extract_xlsx("))
    assert start < hits[0][1] - 1, "the one import is inside _extract_xlsx"
    assert any(line.startswith("openpyxl==") for line in read("requirements.txt").splitlines())


def test_the_stylesheet_has_a_chip_for_every_status_and_nothing_else():
    """Every status, the word for a row not yet scanned, and (decision 142)
    the word for a row nobody asked for with nothing in."""
    from tracker.api import _slug
    from tracker.manifest import NOT_ASKED_LABEL, UNSCANNED_LABEL, Status

    css = read("app/renderer/style.css")
    chips = set(re.findall(r"\.chip-([a-z-]+)\s*\{", css))
    assert chips == {_slug(s) for s in Status.ALL} | {_slug(UNSCANNED_LABEL), _slug(NOT_ASKED_LABEL)}


def test_the_stylesheet_has_a_class_for_every_view_state():
    """Decision 89: the chip's class is derived from the word the API sends,
    so a state with no class would show as unstyled text and a class with no
    state would be a word the page invented."""
    from tracker.view import VIEW_STATES

    css = read("app/renderer/style.css")
    assert set(re.findall(r"\.view-([a-z-]+)\s*\{", css)) == set(VIEW_STATES)


def test_the_renderer_types_no_colour():
    """Decision 118: the firm's colours are Python's (``tracker.page.PALETTE``)
    and reach the app through the API's vocabulary, so the renderer looks a
    colour up by the key a stage carries and never writes one. A hex in
    ``app.js`` would be a second copy of the design system's value, in the
    one file the design system cannot check."""
    js = read("app/renderer/app.js")
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", js), "the renderer types no colour"
    assert "vocab.reminder.palette" in js or "words.palette" in js


def test_the_stylesheet_carries_no_stage_colour():
    """Decision 118: the ladder is mirrored once, in the page module. The
    stylesheet reads the four colours as variables the renderer sets from
    the API, so a stage's value written here would be a second mirror
    nothing holds to the tokens."""
    from tracker.page import PALETTE
    from tracker.reminder import HOLD_COLOUR, LETTER_INK, STAGE_COLOURS

    css = read("app/renderer/style.css").lower()
    # The four rungs, the colour a hold is said in and the letter's two inks.
    # Not the paper: white is the app's own card colour and always was.
    for key in {*STAGE_COLOURS.values(), HOLD_COLOUR, LETTER_INK["body"], LETTER_INK["muted"]}:
        assert PALETTE[key].lower() not in css, key
    assert "--stage-ink" in css and "--rem-ink" in css


def test_the_renderer_types_no_vocabulary_of_its_own():
    """Every word Python owns reaches the page through the API's vocabulary:
    the statuses, the overrides, the decisions, the defaults, the
    headers of the request list, the yes/no words, the one-character
    values, the year bounds and the editor's floors - none is typed in the
    renderer, so the app cannot disagree with the tracker about a word."""
    from tracker.api import _slug
    from tracker.filer import DUPLICATE, FILE_MOVED, FILED, NEEDS_REVIEW, NOT_REQUESTED
    from tracker.layout import INBOX_DIR_NAME
    from tracker.manifest import (
        ANY_EXTENSION,
        DEFAULT_EXTENSIONS,
        EXPECTED_PATTERN,
        HEADERS,
        UNSCANNED_LABEL,
        YEAR_MAX,
        YEAR_MIN,
        Override,
        Status,
    )
    from tracker.records import NO, YES
    from tracker.scheduling import DEFAULT_START
    from tracker.settings import EXAMPLE_ROOT

    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    for literal in (*Status.ALL, *Override.ALL, FILED, NEEDS_REVIEW, DUPLICATE, NOT_REQUESTED,
                    FILE_MOVED, DEFAULT_START,
                    ", ".join(DEFAULT_EXTENSIONS), "looks like", UNSCANNED_LABEL,
                    _slug(UNSCANNED_LABEL), EXPECTED_PATTERN.split("{")[1].split("}")[1].strip()):
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal
        assert literal not in js.replace("chip-${vocab.unscanned_key}", ""), literal
    for literal in (*HEADERS, YES, NO, ANY_EXTENSION):
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal
    # The dashboard's own table heads its columns in plain English, so the
    # one-word headers are not looked for in the page; the two-word ones
    # are the list's alone.
    for literal in (INBOX_DIR_NAME, EXAMPLE_ROOT, str(YEAR_MIN), str(YEAR_MAX),
                    UNSCANNED_LABEL, *[h for h in HEADERS if " " in h]):
        assert literal not in html, literal
    assert 'min="' not in html and 'max="' not in html
    # Every word the household's card, the wizard's household step and the
    # misfit list show is the API's too, and so are the two trees and the
    # two patterns the wizard's previews fill (decision 125).
    import tracker.api as api_module

    words = api_module._vocab()
    for literal in (*words["household"].values(), *words["layout"].values()):
        if not isinstance(literal, str):
            continue
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal
        assert f">{literal}<" not in html, literal
    # Decision 142 (its review, R1): every word it adds is the API's - the
    # status of a row nobody asked for, the count beside it, the wizard's
    # heading and note, the folded table's name and heading, the rollover's
    # label and line, the one refusal, the column's help and the rollover's
    # notes. None is typed in the renderer or the page, quoted or not.
    from tracker import rollover
    from tracker.manifest import ALSO_RECEIVED_LABEL, COLUMN_HELP, NOT_ASKED_LABEL

    added = (NOT_ASKED_LABEL, ALSO_RECEIVED_LABEL, api_module.ASK_THE_CLIENT,
             api_module.ASK_THE_CLIENT_NOTE, api_module.NOT_ASKED_TABLE_LABEL,
             api_module.ROLL_TEMPLATE_LABEL, api_module.NOTHING_ASKED, COLUMN_HELP["asked"],
             api_module.NEW_NOT_ASKED_CARRIED.split("{n}")[1].split(" - ")[0].strip(),
             rollover.NEW_NOT_ASKED_NOTE, rollover.NOT_ASKED_NOTE,
             rollover.NOW_ASKED_NOTE.split("{")[0].strip(), '"' + _slug(NOT_ASKED_LABEL) + '"',
             api_module.NOT_ASKED_SECTION.split("{")[0].strip() + " (")
    for literal in added:
        assert literal and literal not in js and literal not in html, literal
    for key in ("not_asked_label", "not_asked_key", "ask_the_client", "ask_the_client_note",
                "not_asked_table_label", "roll_template_label", "nothing_asked",
                "new_not_asked_carried", "origin_new"):
        assert f"vocab.{key}" in js, key
    assert "vocab.editor.not_asked_heading" in js and "vocab.editor.yes_no_fields" in js
    # Decision 131: the room's heading and its two sentences are the API's.
    # The renderer fills neither pattern: the set-root reply carries each
    # return's sentences already filled.
    assert set(words["room"]) == {"heading", "short", "parks"}
    for literal in words["room"].values():
        assert literal not in js and literal not in html, literal
        stem = literal.split("{")[0].strip() or literal.split("}")[1].split("{")[0].strip()
        assert stem not in js and stem not in html, stem


def test_the_renderers_one_list_writer_flattens_what_it_is_handed():
    """Half the callers build a list as "one fixed node, then a mapped
    array", and ``replaceChildren`` turns an array it is handed into the
    text ``[object HTMLOptionElement],...`` instead of its elements - so
    the wizard's list of existing households and the rollover's list of
    form templates each came out holding one option and a line of noise.
    One flatten in the writer, not a rule every call site has to remember.
    """
    js = read("app/renderer/app.js")
    body = js.split("function show(id, nodes) {", 1)[1].split("}", 1)[0]
    assert "nodes.flat(" in body, body
    # And the pattern the flatten exists for is still written this way.
    assert re.search(r'show\("hh-existing", \[\s*\n.*\n\s*households\.map\(', js)


def test_the_renderer_names_no_catalog_of_its_own():
    """Decision 86: the app prints the engagement's form from the state, as
    the catalog keys it. A catalog id typed into the page would be a second
    list of return types to keep in step with tracker.templates."""
    from tracker.templates import FORM_TEMPLATES

    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    for form in FORM_TEMPLATES:
        assert form not in js and form not in html, form
    assert "state.engagement ? state.engagement.form" in js


def test_the_standing_rules_are_worded_once_and_quoted_everywhere():
    """The package words each rule; the app renders it; the documents quote it."""
    import tracker.api as api

    def plain(text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("`", "").replace("*", "").replace("—", "-"))

    documents = {rel: plain(read(rel)) for rel in ("CLAUDE.md", "README.md", "docs/ROADMAP.md")}
    curated = json.loads(read("docs/repo-map.curated.json"))
    rule_nodes = plain(" ".join(node["role"] for key, node in curated["nodes"].items()
                                if key.startswith("rule:")))
    for rule in api.standing_rules():
        for rel, text in documents.items():
            assert rule["headline"] in text, (rel, rule["headline"])
            assert plain(rule["detail"]) in text, (rel, rule["detail"])
        assert rule["headline"] in rule_nodes and plain(rule["detail"]) in rule_nodes, rule["headline"]
    html = read("app/renderer/index.html")
    assert html.count("<div><strong></strong><span></span></div>") == len(api.standing_rules())


def test_the_documents_list_the_forms_the_catalog_has():
    from tracker.templates import FORM_LABEL_PATTERN, FORM_TYPES

    prefix = FORM_LABEL_PATTERN.split("{")[0]
    labels = ", ".join(f["label"].removeprefix(prefix) for f in FORM_TYPES)
    for rel in ("README.md", "docs/ROADMAP.md", "tracker/templates.py"):
        text = re.sub(r"\s+", " ", read(rel))
        for listed in re.findall(r"\((\d{3,4}[^)]*\d{3,4})\)", text):
            assert listed == labels, (rel, listed)


def test_the_workflow_document_names_every_status_and_override():
    from tracker.manifest import Override, Status

    text = read("docs/workflow.md")
    for value in (*Status.ALL, *Override.ALL):
        assert f"**{value}**" in text or f"**{' / '.join(Override.ALL)}**" in text, value


def test_the_roadmap_schema_table_lists_the_status_and_override_values():
    from tracker.manifest import Override, Status

    roadmap = read("docs/ROADMAP.md")
    status_row = next(line for line in roadmap.splitlines() if line.startswith("| Status |"))
    assert status_row.rstrip(" |").split("|")[-1].strip() == " / ".join(Status.ALL)
    override_row = next(line for line in roadmap.splitlines() if line.startswith("| Manual Override |"))
    for value in Override.ALL:
        assert f"`{value}`" in override_row, value


def test_the_retired_override_word_survives_only_in_the_decision_logs_history():
    """Decision 116 retired the override's old second value. The code folds
    it on every read (``Override.RETIRED``) and never writes it; no document,
    docstring, comment, curated note or renderer may still say it, and no
    name may carry it - the decision log's rows are history and are the one
    place it stays, with the row that retired it."""
    import ast

    from tracker.manifest import Override

    [retired] = Override.RETIRED
    assert not hasattr(Override, "WAIVED")
    for rel in ("README.md", "docs/workflow.md", "docs/runbook.md", "docs/storage.md", "CLAUDE.md",
                "docs/repo-map.curated.json", "app/renderer/app.js", "app/renderer/index.html",
                "app/renderer/style.css"):
        assert retired.lower() not in read(rel).lower(), rel
    for path in [*(REPO / "tracker").glob("*.py"), *(REPO / "tools").glob("*.py")]:
        text = path.read_text(encoding="utf-8")
        assert f"{retired.upper()} " not in text and f"{retired.upper()}\n" not in text, path.name
        tree = ast.parse(text)
        prose = [ast.get_docstring(tree) or ""]
        prose += [ast.get_docstring(node) or "" for node in ast.walk(tree)
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        prose += [line.split("#", 1)[1] for line in text.splitlines() if line.lstrip().startswith("#")]
        assert retired.lower() not in "\n".join(prose).lower(), path.name
        for node in ast.walk(tree):
            if isinstance(node, (ast.Name, ast.Attribute, ast.FunctionDef, ast.ClassDef, ast.arg)):
                name = getattr(node, "id", None) or getattr(node, "attr", None) or getattr(node, "name", None) \
                    or getattr(node, "arg", None)
                assert retired.lower() not in (name or "").lower(), (path.name, name)
    # The one literal is the fold's own key, where ``Override`` lives since
    # decision 187 moved it to the record's value rule.
    literals = [node.value for node in ast.walk(ast.parse(read("tracker/records.py")))
                if isinstance(node, ast.Constant) and node.value == retired]
    assert literals == [retired]
    for path in (REPO / "tracker").glob("*.py"):
        if path.name != "records.py":
            assert retired not in path.read_text(encoding="utf-8"), path.name
    # The roadmap: the schema table and the component table say the new value; the
    # decision log's rows are history.
    roadmap = read("docs/ROADMAP.md").splitlines()
    for line in roadmap:
        if retired.lower() in line.lower():
            assert line.startswith("| ") and line.split("|")[1].strip().isdigit(), line[:80]
    # And the tests name the new claim, not the old word.
    for path in (REPO / "tests").glob("test_*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("def test_"):
                assert retired.lower() not in line.lower() or "old_journal" in line, (path.name, line)


def test_the_scan_button_label_is_typed_once():
    label = re.search(r'const SCAN_LABEL = "([^"]+)";', read("app/renderer/app.js")).group(1)
    assert label not in read("app/renderer/index.html")
    js = read("app/renderer/app.js")
    assert js.count(f'"{label}"') == 1
    for rel in ("docs/ROADMAP.md", "docs/workflow.md", "README.md", "docs/repo-map.curated.json"):
        text = read(rel)
        # Prose may name the button, but only by its real label.
        for phrase in re.findall(r"\b([A-Z][a-z]+ (?:&|and) Scan)\b", text):
            assert phrase == label, (rel, phrase)


def test_the_words_for_the_engagements_page_are_pythons_alone():
    """Decision 91: the chip's label and the button that opens the page are
    the API's vocabulary; the renderer shows them and types neither."""
    from tracker.view import VIEW_LABEL, VIEW_OPEN_LABEL

    for rel in ("app/renderer/index.html", "app/renderer/app.js", "app/renderer/style.css"):
        text = read(rel)
        assert VIEW_OPEN_LABEL not in text, rel
        assert VIEW_LABEL not in text, rel


def test_the_example_root_is_the_same_everywhere():
    from tracker.settings import EXAMPLE_ROOT

    for rel in ("README.md", "docs/ROADMAP.md", "docs/workflow.md"):
        text = read(rel)
        for example in re.findall(r"[A-Z]:\\[\w\\ .-]*Clients", text):
            assert example == EXAMPLE_ROOT, (rel, example)


def test_the_api_docstring_lists_exactly_the_commands():
    import tracker.api as api

    listed = set(re.findall(r"^  ([a-z-]+(?: / [a-z-]+)*)\s", api.__doc__, re.M))
    names = {n for entry in listed for n in entry.split(" / ")}
    assert names == set(api.COMMANDS), names ^ set(api.COMMANDS)


def test_the_package_docstring_lists_every_module():
    import tracker

    listed = set(re.findall(r"^- (\w+)\s+:", tracker.__doc__, re.M))
    modules = {p.stem for p in (REPO / "tracker").glob("*.py") if p.stem != "__init__"}
    assert listed == modules, listed ^ modules


def test_the_readme_engagement_details_table_matches_the_fields():
    from tracker.records import ENGAGEMENT_FIELDS, ENGAGEMENT_HELP, ENGAGEMENT_NOTES, NO

    readme = read("README.md")
    for label, field in ENGAGEMENT_FIELDS:
        row = next((line for line in readme.splitlines() if line.startswith(f"| {label} |")), None)
        assert row is not None, label
        assert ENGAGEMENT_HELP[field].replace(f"{NO} =", f"`{NO}` =") in row, (label, row)
    for field, note in ENGAGEMENT_NOTES.items():
        assert ENGAGEMENT_HELP[field] == note, field


def test_the_roadmap_schema_table_lists_exactly_the_manifest_headers():
    """The list is the columns a person edits (``manifest.HEADERS``), and the
    schema table is those and no others: a row left in
    it for a column the machine stopped writing is a column somebody will go
    looking for."""
    from tracker.manifest import HEADERS

    listed = _schema_table("Manifest Schema")
    assert listed == list(HEADERS), listed


def _schema_table(heading: str) -> list[str]:
    """The first cell of every data row of the table under ``heading``."""
    lines = read("docs/ROADMAP.md").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"## {heading}"))
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("#"):
            break
        if line.startswith("|") and not set(line) <= set("|- "):
            rows.append(line.split("|")[1].strip())
    return [cell for cell in rows[1:] if cell]       # drop the header row


DOCUMENTS = ("README.md", "docs/ROADMAP.md", "docs/workflow.md", "docs/runbook.md",
             "docs/storage.md", "CLAUDE.md")


def test_prose_names_no_weekday_but_the_draft_day():
    """Docs may say which day the draft is made, but only the runner's day."""
    from tracker.runner import DRAFT_DAY_NAME, WEEKDAY_NAMES

    sources = [*DOCUMENTS, "docs/repo-map.curated.json", "tracker/__init__.py",
               *(str(p.relative_to(REPO)) for p in (REPO / "tracker").glob("*.py"))]
    quoted_day = "|".join(WEEKDAY_NAMES)
    for rel in sources:
        text = read(rel).lower()
        text = re.sub(rf'"(?:{quoted_day})"', "", text)          # the tuple that defines them
        text = re.sub(rf"--weekday (?:{quoted_day})", "", text)  # a CLI example takes any day
        for day in WEEKDAY_NAMES:
            if day != DRAFT_DAY_NAME:
                assert day not in text, (rel, day)


#: The runtime files the decision log names and the code no longer owns.
#: The log never deletes: rows 1 to 106 name these files, and decisions 102
#: to 104 and 107 retired them. A document may name one only in the log or
#: in a sentence about the past (the runbook's legacy paragraph names the
#: old request list, which is allowed by this set). The verdict cache's
#: file is named by the constant the filer's tidy-up still removes it by.
RETIRED_FILES = {"_manifest.xlsx", "_index.xlsx", "_manifest.pending.json", "_index.pending.json",
                 "_index.migrated.xlsx", "_index.pending.migrated.json",
                 "_manifest.pending.migrated.json", RETIRED_CACHE_FILENAME,
                 "constraints.txt"}   # replaced by the hash-checked locks (decision 191)

#: Repository files the decision log names and a later decision deleted:
#: decision 206 removed the manifest a program outside the app ran, and row 81 still names it
#: because rows are history. Only the log may quote one. The name is
#: assembled at run time so the decision-206 guard does not trip on it here.
DELETED_REPO_FILES = {".".join(("automation", "manifest", "json"))}


def test_documents_name_only_runtime_files_the_code_owns():
    """Every `something.ext` a document quotes is a file the code names, a
    repo file, or one of the files the log retired (``RETIRED_FILES``)."""
    import subprocess

    from tracker.after_install import BUILD_INFO_FILENAME, RECORD_FILENAME
    from tracker.checkpoint import CHECKPOINT_FILENAME
    from tracker.filer import README_LOCK_FILENAME
    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME, RACE_LOCK_FILENAME
    from tracker.registry import LEGACY_MANIFEST_FILENAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LAST_PASS_FILENAME, LOG_FILENAME, PASS_ORDER_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scaffold import README_NAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import SETTINGS_FILENAME
    from tracker.store import STORE_FILENAME
    from tracker.view import VIEW_FILENAME

    assert LEGACY_MANIFEST_FILENAME in RETIRED_FILES
    owned = {LEDGER_FILENAME, LOCK_FILENAME, DRAFT_FILENAME, NEW_DRAFT_FILENAME,
             LOG_FILENAME, STATUS_PAGE_FILENAME, README_NAME, README_LOCK_FILENAME,
             SCHEDULE_XML_FILENAME, SETTINGS_FILENAME, STORE_FILENAME, VIEW_FILENAME,
             PASS_ORDER_FILENAME,
             # Decision 159: the checkpoint, the scheduled pass's own note, the race's lock.
             CHECKPOINT_FILENAME, LAST_PASS_FILENAME, RACE_LOCK_FILENAME,
             # Decision 209: the after-install step's note, and the build's.
             RECORD_FILENAME, BUILD_INFO_FILENAME}
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
    repo_files = {Path(t).name for t in tracked} | {t for t in tracked}
    for rel in DOCUMENTS:
        for quoted in re.findall(r"`([^`\s]+\.(?:txt|xml|jsonl|json|lock|xlsx|log|bat|py|md|js|toml|yml|db))`", read(rel)):
            name = quoted.split("/")[-1].split("\\")[-1]
            if "<" in quoted or "*" in quoted:
                continue                                  # a pattern, not a file
            if rel == "docs/ROADMAP.md" and name in DELETED_REPO_FILES:
                continue                                  # history names what 206 deleted
            assert quoted in repo_files or name in repo_files or name in owned or name in RETIRED_FILES, (rel, quoted)


def test_the_build_output_folder_is_the_one_gitignore_knows():
    out = re.search(r"^set OUT=(\S+)", read("Build App.bat"), re.M).group(1)
    assert f"{out}/" in read(".gitignore")


def test_every_dependency_is_pinned_exactly():
    # A build made next month must freeze the same code as one made today.
    # A pin may carry an environment marker (decision 169, R-11a and R-11b:
    # numpy by Python version, ONNX Runtime by platform); it is still exact.
    for rel in ("requirements.txt", "requirements-build.txt", "requirements-nodeps.txt",
                "requirements-gpu.txt"):
        for line in read(rel).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r "):
                continue
            assert re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][A-Za-z0-9.]*"
                                r"(; (python_version|sys_platform) [<>=!]=? \"[A-Za-z0-9.]+\")?", line), (rel, line)
    package = json.loads(read("app/package.json"))
    for name, version in package["devDependencies"].items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), (name, version)
    lock = json.loads(read("app/package-lock.json"))
    for name, version in package["devDependencies"].items():
        assert lock["packages"][f"node_modules/{name}"]["version"] == version, name


def test_the_build_is_made_from_what_is_committed():
    ignored = [line.strip() for line in read(".gitignore").splitlines()]
    assert "*.spec" not in ignored and "app/package-lock.json" not in ignored
    assert "npm ci" in read("Build App.bat") and "npm ci" in read("Setup.bat")
    assert "npm install" not in read("Build App.bat") and "npm install" not in read("Setup.bat")
    build = read("Build App.bat")
    assert "requirements-build.lock" in build and "api_entry.spec" in build
    assert "pip install pyinstaller" not in build            # pinned in requirements-build.txt, locked by hash
    spec = read("api_entry.spec")
    api_name = json.loads(read("app/package.json"))["config"]["apiName"]
    assert api_name not in spec and "config" in spec and "apiName" in spec
    assert "git rev-parse HEAD" in build and "pip freeze" in build   # BUILD-INFO.txt provenance


def test_the_roadmap_names_every_status_in_bold():
    from tracker.manifest import Status

    roadmap = read("docs/ROADMAP.md")
    for value in Status.ALL:
        assert f"**{value}**" in roadmap, value


def test_documents_name_buttons_by_their_labels():
    """A doc may say 'the X button' only for a button the page actually has."""
    from tracker import reminder
    from tracker.api import (
        ACCEPT_LABEL,
        CARD_MODE_LABEL,
        EDITOR_ADD_LABEL,
        EDITOR_CANCEL_LABEL,
        EDITOR_OPEN_LABEL,
        EDITOR_PASTE_LABEL,
        EDITOR_REMOVE_LABEL,
        EDITOR_SAVE_LABEL,
        KEEP_LABEL,
        LIST_MODE_LABEL,
        OPEN_IN_LIST_LABEL,
        RESTORE_LABEL,
        SCHEDULE_REPAIR_LABEL,
        SEND_TO_REVIEW_LABEL,
        SKIP_LABEL,
        UNLEARN_LABEL,
    )
    from tracker.view import VIEW_OPEN_LABEL

    html = read("app/renderer/index.html")
    labels = {re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m)).strip()
              for m in re.findall(r"<button[^>]*>(.*?)</button>", html, re.S)}
    js = read("app/renderer/app.js")
    labels |= set(re.findall(r'<button[^>]*>([^<]+)</button>', js))
    labels.add(re.search(r'const SCAN_LABEL = "([^"]+)";', js).group(1))
    # Buttons filled in at runtime from a label Python owns: the scan
    # button's, above, the one that opens the engagement's page, and the
    # request-list editor's (decision 104).
    labels.add(VIEW_OPEN_LABEL)
    labels |= {EDITOR_OPEN_LABEL, EDITOR_SAVE_LABEL, EDITOR_CANCEL_LABEL, EDITOR_ADD_LABEL,
               EDITOR_REMOVE_LABEL, EDITOR_PASTE_LABEL, UNLEARN_LABEL}
    # And the three answers to a working copy that is not where the record
    # put it (decision 110), which the workflow names by their labels.
    labels |= {RESTORE_LABEL, KEEP_LABEL, SEND_TO_REVIEW_LABEL}
    # And the card's three answers with the two words the toggle between the
    # review queue's renderings carries (decision 114).
    labels |= {ACCEPT_LABEL, SKIP_LABEL, OPEN_IN_LIST_LABEL, CARD_MODE_LABEL, LIST_MODE_LABEL}
    # And the Reminder card's three, filled in at runtime from the module
    # that owns the draft (decision 118). None of them sends anything.
    labels |= {reminder.COPY_LABEL, reminder.APPROVE_LABEL, reminder.OPEN_DRAFT_LABEL}
    # And the schedule's repair path, filled in from the API (decision 209).
    labels.add(SCHEDULE_REPAIR_LABEL)
    labels = {label for label in labels if label and "${" not in label}
    for rel in (*DOCUMENTS, "docs/repo-map.curated.json"):
        text = read(rel)
        mentions = (re.findall(r"\*\*([^*]+)\*\* button", text) + re.findall(r"\*([^*]+)\* button", text)
                    + re.findall(r"the (?:app's )?([A-Z][A-Za-z &]+?) button", text)
                    + re.findall(r"\*\*([A-Z][A-Za-z ]+)\*\*", text) + re.findall(r"(?<!\*)\*([A-Z][A-Za-z ]+)\*(?!\*)", text))
        for name in mentions:
            # An emphasised phrase that is almost a button label must be the label.
            close = [label for label in labels if label.lower() == name.lower()]
            if close or name.endswith(" button"):
                assert name in labels, (rel, name)


def test_the_stub_and_staging_examples_docs_give_are_the_validators():
    from tracker.validators import _GOOGLE_STUB_EXTENSIONS, _SYNC_STAGING_PREFIX

    for rel in DOCUMENTS:
        text = read(rel)
        for ext in re.findall(r"`\.(g[a-z]+)`", text):
            assert ext in _GOOGLE_STUB_EXTENSIONS, (rel, ext)
        for prefix in re.findall(r"`(\.tmp\.[a-z]+)\*?`", text):
            assert prefix == _SYNC_STAGING_PREFIX, (rel, prefix)


def test_documents_spell_manifest_headers_exactly():
    from tracker.manifest import HEADERS

    for rel in DOCUMENTS:
        text = read(rel)
        for quoted in re.findall(r"`([A-Z][A-Za-z ]+)`", text):
            for header in HEADERS:
                if quoted.lower() == header.lower():
                    assert quoted == header, (rel, quoted)


def test_tree_diagrams_show_catalog_copies_as_the_filer_names_them():
    """Decision 168: a working copy sits in Prepared itself, so a tree
    diagram shows no folder per request, and every working copy it shows
    is named as the filer names a catalog row's copy."""
    from tracker.filer import prepared_name_for
    from tracker.templates import FORM_TEMPLATES, TY, item_from_spec

    items = [item_from_spec(spec) for rows in FORM_TEMPLATES.values() for spec in rows]
    names = {prepared_name_for(item, extension, set())
             for item in items for extension in (item.allowed_extensions or ("pdf",))}
    for rel in DOCUMENTS:
        for line in read(rel).splitlines():
            if "──" not in line:
                continue                                  # only the tree diagrams
            assert not re.search(r"[A-Z]\d{2} - [^/\n]+?/", line), (rel, line)
            for copy in re.findall(r"([A-Z]\d{2} - .+?\.[a-z]{2,4})\b", line):
                assert copy in names, (rel, copy)
            for period in re.findall(r"\bTY\d{4}\b", line):
                assert period == TY, (rel, period)


def _known_flags() -> set[str]:
    """Every ``--flag`` the package and the tools define, by literal or by ``*_FLAG`` constant."""
    modules = [*(REPO / "tracker").glob("*.py"), *(REPO / "tools").glob("*.py")]
    sources = "\n".join(read(str(p.relative_to(REPO))) for p in modules)
    return (set(re.findall(r'"(--[a-z][a-z-]*)"', sources))
            | set(re.findall(r"^\w+_FLAG = \"(--[a-z-]+)\"", sources, re.M)))


#: The removed surface's name in any spelling a document or a line of code
#: could carry it: any case, one word or two, joined by a space, a hard wrap,
#: an underscore or a hyphen - and its manifest's file name the same way.
#: Written as a pattern, so this source does not itself match it.
REMOVED_NAME = re.compile(r"command[\s_-]*center|automation[\s._-]*manifest", re.IGNORECASE)

#: The one place the name may stand outside the log: the guard's own test
#: name, which the SPEC fixes and the generated map lists.
GUARD_NAME = "test_the_command_center_is_gone_from_everything_but_the_decision_log"


def _hits_of_the_removed_name(root: Path, rels: list[str]) -> list[tuple[str, int]]:
    """Every (file, line) under ``root`` where REMOVED_NAME matches, searched
    over each file's whole text so a name wrapped across two lines is found;
    the line is the one the match starts on. The decision log is exempt
    (its rows are history), as is GUARD_NAME; a file missing from the
    working tree or not UTF-8 text is skipped."""
    hits = []
    for rel in rels:
        if rel == "docs/ROADMAP.md":
            continue                                   # decision rows are history
        path = root / rel
        if not path.is_file():
            continue                                   # deleted in the working tree
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue                                   # not a text file
        text = text.replace(GUARD_NAME, "")            # no newline in it: line numbers hold
        hits += [(rel, text.count("\n", 0, match.start()) + 1) for match in REMOVED_NAME.finditer(text)]
    return hits


def test_the_command_center_is_gone_from_everything_but_the_decision_log():
    """Decision 206: the integration a program outside the app ran, and its
    manifest, were removed outright, not corrected - a manifest nobody
    maintains is argv another program runs verbatim, so the shape itself
    goes (no stub, no reserved file). The decision log keeps its rows
    because rows are history; every other tracked file, the generated map
    included, names neither that surface nor its manifest, in any spelling."""
    import subprocess

    # Joined at run time: a literal file name here would be a hit of its own.
    manifest = ".".join(("automation", "manifest", "json"))
    assert not (REPO / manifest).exists(), "the manifest is deleted, not stubbed"

    listed = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True,
                            text=True, check=True).stdout
    tracked = [rel for rel in listed.split("\0") if rel]
    assert tracked, "git ls-files listed nothing - the guard would pass vacuously"
    assert not (hits := _hits_of_the_removed_name(REPO, tracked)), hits


# The probes below spell the name at run time, for the reason the guard does.
_FIRST, _SECOND = "Command", "Center"


def test_the_guard_finds_the_name_hard_wrapped_across_two_lines(tmp_path):
    (tmp_path / "notes.md").write_text(f"A fabricated paragraph about the firm's {_FIRST}\n"
                                       f"{_SECOND}, wrapped the way the docs wrap.\n", encoding="utf-8")
    assert _hits_of_the_removed_name(tmp_path, ["notes.md"]) == [("notes.md", 1)]


def test_the_guard_finds_the_name_as_an_identifier(tmp_path):
    (tmp_path / "x.py").write_text(f"ok = 1\n{_FIRST.lower()}_{_SECOND.lower()} = 2\n", encoding="utf-8")
    assert _hits_of_the_removed_name(tmp_path, ["x.py"]) == [("x.py", 2)]


def test_the_guard_exempts_only_the_log_and_its_own_name(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ROADMAP.md").write_text(f"| 81 | {_FIRST} {_SECOND} |\n", encoding="utf-8")
    (tmp_path / "t.py").write_text(f"def {GUARD_NAME}():\n    pass\n", encoding="utf-8")
    (tmp_path / "other.md").write_text(f"{_FIRST}-{_SECOND}\n", encoding="utf-8")
    assert _hits_of_the_removed_name(tmp_path, ["docs/ROADMAP.md", "t.py", "other.md"]) == [("other.md", 1)]


#: Flags of other programs' command lines that the documents quote, each
#: with why: they are not this package's, so no source defines them.
FOREIGN_FLAGS = {
    "--no-deps": "pip's: the reader's package is installed without its dependencies (decision 169, R-11)",
    "--require-hashes": "pip's: every install checks every file against the lock's SHA-256 (decision 191)",
}


def test_every_cli_flag_a_document_names_exists_in_the_code():
    from tracker.runner import REMINDER_MODES

    known = _known_flags() | set(FOREIGN_FLAGS)
    for rel in DOCUMENTS:
        text = read(rel)
        for flag in set(re.findall(r"(--[a-z][a-z-]*)", text)):
            assert flag in known, (rel, flag)
        for mode in re.findall(r"--reminders[ =]([a-z]+)", text):
            assert mode in REMINDER_MODES, (rel, mode)
        for listed in re.findall(r"--reminders ([a-z]+(?:\\?\|[a-z]+)+)", text):
            assert listed.replace("\\", "").split("|") == list(REMINDER_MODES), (rel, listed)


def test_documents_give_the_settings_hint_the_api_gives():
    from tracker.settings import SET_ROOT_HINT

    for rel in DOCUMENTS:
        for hint in re.findall(r"`(python -m tracker\.settings[^`]*)`", read(rel)):
            assert hint == SET_ROOT_HINT, (rel, hint)


def test_claude_md_explains_the_map_edges_by_their_rendered_names():
    import sys

    sys.path.insert(0, str(REPO / "tools"))
    try:
        import repo_map as module
    finally:
        sys.path.pop(0)
    text = read("CLAUDE.md")
    for label in (module.TESTED_BY, module.EXERCISED_BY, module.NO_TEST_FILE,
                  module.IMPORTS_AT_CALL):
        assert f"**{label}**" in text, label


def test_documents_quote_the_any_value_only_as_the_constants_say_it():
    from tracker.manifest import ANY_EXTENSION, NO_DATE_CHECK

    assert ANY_EXTENSION == NO_DATE_CHECK      # one character means "any / none" in both columns
    for rel in (*DOCUMENTS, "docs/repo-map.curated.json"):
        text = read(rel)
        if "`*`" in text or "'*'" in text:
            assert ANY_EXTENSION == "*", rel   # the docs quote it; the constant had better be it


def test_documents_name_the_engagement_folders_as_the_layout_does():
    """Every `Something/` a document quotes as a folder is one the layout
    names (decision 125). ``Shared`` and ``PBC`` are the layout before it
    and survive only in the decision log's own rows."""
    from tracker.layout import (
        CLIENTS_TREE,
        INBOX_DIR_NAME,
        PREPARED_DIR_NAME,
        PRIVATE_TREE,
        REVIEW_DIR_NAME,
    )

    folders = {CLIENTS_TREE, PRIVATE_TREE, INBOX_DIR_NAME, PREPARED_DIR_NAME, REVIEW_DIR_NAME}

    def a_decision_row(line: str) -> bool:
        """A row of the Decision Log, which is history and says what the
        layout was when that decision was taken."""
        return line.startswith("| ") and line.split("|")[1].strip().isdigit()

    for rel in (*DOCUMENTS, "docs/repo-map.curated.json"):
        for line in read(rel).splitlines():
            if a_decision_row(line):
                continue
            for quoted in re.findall(r"`((?:[A-Z][A-Za-z]+/)+)`", line):
                for part in quoted.rstrip("/").split("/"):
                    assert part in folders, (rel, quoted)
            # The two folder names decision 125 retired live on in the
            # log's own rows and nowhere else.
            assert "Shared/" not in line and "PBC/" not in line, (rel, line[:80])


def test_gitignore_ignores_the_junk_the_validators_ignore():
    from tracker.validators import _IGNORED_NAMES, OFFICE_LOCK_PREFIX

    ignored = {line.strip().lower() for line in read(".gitignore").splitlines()
               if line.strip() and not line.startswith("#")}
    for name in _IGNORED_NAMES:
        assert name.lower() in ignored, name
    assert f"{OFFICE_LOCK_PREFIX}*".lower() in ignored


def test_documents_state_the_naming_pattern_with_the_one_separator():
    from tracker.manifest import LABEL_SEPARATOR

    for rel in (*DOCUMENTS, "docs/repo-map.curated.json"):
        for joiner in re.findall(r"\{Identifier\}(.+?)\{Document\}", read(rel)):
            assert joiner == LABEL_SEPARATOR, (rel, joiner)


def test_tree_diagrams_name_only_runtime_files_the_code_owns():
    """A tree diagram shows the folder as it is: the files the code writes
    and none of the retired ones - a tree is never a sentence about the past."""
    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scaffold import README_NAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import SETTINGS_FILENAME
    from tracker.view import VIEW_FILENAME

    owned = {LEDGER_FILENAME, LOCK_FILENAME,
             DRAFT_FILENAME, NEW_DRAFT_FILENAME,
             LOG_FILENAME, STATUS_PAGE_FILENAME, README_NAME,
             SCHEDULE_XML_FILENAME, SETTINGS_FILENAME, VIEW_FILENAME}
    assert not owned & RETIRED_FILES
    for rel in DOCUMENTS:
        for line in read(rel).splitlines():
            if "──" not in line:
                continue
            for name in re.findall(r"(_[\w.-]+\.(?:xlsx|jsonl|json|txt|lock|log))", line):
                assert name in owned, (rel, name)
        for name in re.findall(r"--out (\S+\.xml)", read(rel)):
            assert name == SCHEDULE_XML_FILENAME, (rel, name)


#: Every command line that prints a client's file or folder name. The
#: guard against a console that cannot encode one is tracker.page's
#: tolerant_console(), and each of these takes it before it parses a flag.
CONSOLE_GUARDED = ("rollover", "filer", "scanner", "registry", "review", "scaffold",
                   "store", "reminder", "runner", "router", "content_check",
                   "view", "ledger", "validators", "names", "containers", "ocr", "door",
                   "checkpoint", "locking", "after_install")
#: The command lines that print no client's name, each with why it is not
#: guarded - so a new command line has to be named in one list or the other.
CONSOLE_EXEMPT = {
    "api": "stdout is the shell's JSON channel, written with ensure_ascii; nothing a console encodes",
    "settings": "prints the firm's own root and settings, never a client's name (decision 97's hold)",
    "scheduling": "prints the task's root and paths, never a client's name",
}


def _command_line_source(module: str) -> str:
    """The source of the module's ``__main__`` block - and, when that block
    only calls ``main()``, of ``main`` itself (the runner's command line is
    a function the frozen entry calls too)."""
    import ast

    text = read(f"tracker/{module}.py")
    tree = ast.parse(text)
    blocks = [node for node in tree.body
              if isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
              and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"]
    assert len(blocks) == 1, module
    source = ast.get_source_segment(text, blocks[0])
    if "main(" in source:
        source += "\n" + "\n".join(
            ast.get_source_segment(text, node) for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main")
    return source


def test_every_command_line_that_prints_a_clients_name_takes_the_tolerant_console_first():
    for module in CONSOLE_GUARDED:
        source = _command_line_source(module)
        guarded_at = source.find("tolerant_console()")
        parses_at = source.find("argparse.ArgumentParser(")
        assert guarded_at != -1, module
        assert parses_at != -1, module
        assert guarded_at < parses_at, module


def test_every_command_line_is_either_guarded_or_exempt_by_name():
    """A command line added tomorrow is named here, guarded or exempt with a
    reason, before the suite is green - so none can slip past the console."""
    import ast

    from tests.test_layers import _is_main_guard

    with_a_command_line = set()
    for path in (REPO / "tracker").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.If) and _is_main_guard(node) for node in tree.body):
            with_a_command_line.add(path.stem)
    assert with_a_command_line == set(CONSOLE_GUARDED) | set(CONSOLE_EXEMPT)
    assert not set(CONSOLE_GUARDED) & set(CONSOLE_EXEMPT)
    for module, reason in CONSOLE_EXEMPT.items():
        assert reason, module
        assert "tolerant_console()" not in _command_line_source(module), module


def test_the_package_prose_names_constants_rather_than_their_values():
    """A docstring or comment may name LEDGER_FILENAME; it may not spell the value."""
    import ast

    from tracker.filer import README_LOCK_FILENAME
    from tracker.layout import (
        CLIENTS_TREE,
        INBOX_DIR_NAME,
        PREPARED_DIR_NAME,
        PRIVATE_TREE,
        README_NAME,
        REVIEW_DIR_NAME,
    )
    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME
    from tracker.manifest import Override, Status
    from tracker.registry import LEGACY_MANIFEST_FILENAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME
    from tracker.settings import SETTINGS_FILENAME
    from tracker.store import STORE_FILENAME
    from tracker.view import VIEW_FILENAME

    values = {LEDGER_FILENAME, LOCK_FILENAME, README_LOCK_FILENAME, DRAFT_FILENAME, NEW_DRAFT_FILENAME,
              LOG_FILENAME, LEGACY_MANIFEST_FILENAME, README_NAME, REVIEW_DIR_NAME,
              RETIRED_CACHE_FILENAME,
              SETTINGS_FILENAME, STORE_FILENAME, VIEW_FILENAME,
              f"{CLIENTS_TREE}/", f"{PRIVATE_TREE}/", f"{INBOX_DIR_NAME}/",
              f"{PREPARED_DIR_NAME}/"}
    quoted = {f"``{v}``" for v in set(Status.ALL) | set(Override.ALL)}
    for path in (REPO / "tracker").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        prose = [ast.get_docstring(tree) or ""]
        prose += [ast.get_docstring(node) or "" for node in ast.walk(tree)
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        prose += [line.split("#", 1)[1] for line in text.splitlines() if line.lstrip().startswith("#")]
        prose_text = "\n".join(prose)
        for token in quoted:
            assert token not in prose_text, (path.name, token)
        for value in values:
            assert value not in prose_text, (path.name, value)


def test_every_review_action_the_renderer_sends_carries_the_rows_seq():
    """Decision 112: a person's action is judged against the record it was
    made on, so every review command the app sends carries the row's own
    sequence number as the card showed it. The API refuses a spec without
    one, which would make a handler that forgot it a button that never
    works - and this is the test that says so before anyone clicks it.
    """
    import tracker.api as api

    js = read("app/renderer/app.js")
    # Two of the three read the row's version where they send it...
    for command in ("dismiss", "unfile"):
        sent = re.search(rf'call\(withEng\("{command}"\), \{{(.*?)\}}\)', js, re.S)
        assert sent, command
        assert "seq:" in sent.group(1), command
        assert "li.dataset.seq" in sent.group(1), command
    # ...and since decision 114 the filing has one call site for the three
    # buttons that make it, so each of them reads the version off the element
    # it was drawn on and hands it to that one function.
    sent = re.search(r'call\(withEng\("assign"\), \{(.*?)\}\)', js, re.S)
    assert sent and "seq" in sent.group(1)
    for handler in ("assignParked", "keepMoved", "acceptCard"):
        body = re.search(rf"async function {handler}\(.*?\n\}}", js, re.S)
        assert body, handler
        assert "fileRow(" in body.group(0) and "dataset.seq" in body.group(0), handler
    # Both row builders put it on the element the handlers read it back from.
    assert js.count("seq: e.seq") == 2
    # And the sentence a refusal shows is the API's, never the renderer's.
    assert api.NO_SEQ not in js


def test_the_feed_editor_picks_a_return_by_index_and_never_takes_a_value_apart():
    """Decision 129: a feed is two fields - a household name and a return
    line - and every real one of both carries spaces. A picker whose option
    value ran the pair together had to take it apart again on a guess, and
    the guess saved a feed nobody typed: recorded, warned unresolved every
    pass, feeding nothing. So the option's value is its index into the list
    the page is showing, and what is added is the object that option was
    drawn from, field for field. The API's own test never reaches the page,
    which is why this is pinned here.
    """
    js = read("app/renderer/app.js")
    render = re.search(r"function renderEditorFeeds\(\) \{.*?\n\}", js, re.S)
    add = re.search(r"function addEditorFeed\(\) \{.*?\n\}", js, re.S)
    assert render and add
    # The option carries its position in the list being drawn...
    assert 'el("option", { value: String(feedChoices.length) }' in render.group(0)
    assert "feedChoices.push({ household: other.name, return_name: one.return_name" \
        in render.group(0)
    # ...and the handler reads that position back and uses the whole object.
    assert "feedChoices[Number(picked)]" in add.group(0)
    # Neither of them splits a value into fields, on any separator.
    for body in (render.group(0), add.group(0)):
        assert ".split(" not in body
    # Where the two fields must be one key - the set of feeds already added,
    # which is a lookup and nothing the page sends - they are keyed as the
    # pair rather than run together with a separator a name might carry.
    assert re.search(r"function feedKey\(household, returnName\) \{\s*"
                     r"return JSON\.stringify\(\[household, returnName\]\);", js)
    # And no separator a source file cannot show: a raw NUL in this file is
    # what made the earlier bug read as a space to everything that looked.
    assert chr(0) not in js


def test_the_pass_and_the_hand_over_file_into_another_household_through_one_function():
    """Decision 132: one act, one shape. A filing into a return - by the
    pass or by a person's hand-over - is that return's filing, written down
    and carried out by ``filer._file_into`` and nothing else, so the two
    roads cannot drift apart again. Decision 129's second machinery is gone
    from the package: nothing carries another record's half of a decision
    (the one place that names the retired key is the store's refusal of
    it), no ``Handed Over`` decision, no sentence cut at a ``_WAS_PREFIX``."""
    filer = read("tracker/filer.py")
    calls = re.findall(r"\b_file_into\(", filer)
    assert len(calls) == 3                          # the definition and its two callers
    assert len(re.findall(r"^def _file_into\(", filer, re.M)) == 1
    body = lambda name: re.search(rf"^def {name}\(.*?(?=^def )", filer, re.S | re.M).group(0)  # noqa: E731
    assert "_file_into(" in body("_file_it") and "_file_into(" in body("hand_over")

    tracker = {path.name: path.read_text(encoding="utf-8")
               for path in (REPO / "tracker").glob("*.py")}
    for name, text in tracker.items():
        assert not re.search(r"\bHANDED_OVER\b", text), name
        assert "_WAS_PREFIX" not in text and "ALSO_IN_KEY" not in text, name
        assert "_also_in_the_other_record" not in text and "INTERRUPTED_ELSEWHERE" not in text, name
        assert "DUPLICATE_OF_HANDED_OVER" not in text, name
    assert sum(text.count('"also_in"') for text in tracker.values()) == 1
    assert 'ALSO_IN = "also_in"' in tracker["store.py"]


def test_documents_quote_the_jobs_command_line_as_the_scheduler_writes_it():
    """Decision 131: the scheduled job names the app's settings folder and
    no clients root. The README shows the job's command line, and it shows
    it exactly as ``tracker.scheduling.runner_arguments`` writes it - so the
    day the line changes, the document is out of step here, not at the
    office."""
    from tracker.runner import SETTINGS_FLAG
    from tracker.scheduling import runner_arguments

    readme = read("README.md")
    job = f"python {runner_arguments('C:' + chr(92) + 'Tools' + chr(92) + 'tax-tracker')}"
    assert job in readme, job
    assert SETTINGS_FLAG in job
    # And nothing still tells a person the scheduler takes a root.
    for rel in ("README.md", "docs/runbook.md"):
        assert "--root" not in read(rel), rel


#: The ROADMAP's decision-log rows are history: they quote what a document
#: used to say, and the log never deletes (decision 184 quotes the very
#: sentences it strikes). The guards below read the log's prose around them.
DECISION_ROW = re.compile(r"^\| \d+ \|.*$", re.MULTILINE)


def read_as_prose(rel: str) -> str:
    text = read(rel)
    return DECISION_ROW.sub("", text) if rel == "docs/ROADMAP.md" else text


NUMBER_WORDS = ("ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                "seventeen", "eighteen", "nineteen", "twenty")


def test_every_document_counts_the_request_lists_columns_as_the_api_does():
    """Decision 184 (the UX council's D2): the request list has as many
    columns as ``manifest.HEADERS`` has headers, and the API hands the app
    that list. The documents had counted ten, eleven and twelve. Wherever a
    document, the page, the code's prose or a test still spells a count of
    the columns a person edits, it is that one. A detector of the known
    phrasings, not of every way to say it."""
    from tracker.manifest import HEADERS

    count = len(HEADERS)
    sources = ["README.md", "docs/runbook.md", "docs/storage.md", "docs/workflow.md",
               "CLAUDE.md", "docs/repo-map.curated.json", "app/renderer/index.html",
               "app/renderer/app.js", "docs/ROADMAP.md",
               *(str(p.relative_to(REPO)) for p in sorted((REPO / "tracker").glob("*.py"))),
               *(str(p.relative_to(REPO)) for p in sorted((REPO / "tests").glob("*.py")))]
    phrasings = (
        r"\b(\w+)\s+(?:accountant\s+)?columns\s+(?:you\s+edit|an\s+accountant\s+edits|a\s+person\s+edits)",
        r"\b(\w+)\s+accountant\s+columns",
        r"person's\s+(\w+)\s+columns",
        r"the\s+(\w+)\s+columns\s+\(:data:`COLUMNS`\)",
        r"the\s+(\w+)\s+headers\s+of\s+the\s+request\s+list",
        r"\bshows\s+(?://\s*)?\w+\s+of\s+the\s+(\w+)",
    )
    counted = 0
    for rel in sources:
        text = read_as_prose(rel)
        for phrasing in phrasings:
            for found in re.finditer(phrasing, text, re.IGNORECASE):
                word = found.group(1).lower()
                if word.isdigit():
                    assert int(word) == count, (rel, found.group(0))
                elif word in NUMBER_WORDS:
                    assert NUMBER_WORDS.index(word) + 10 == count, (rel, found.group(0))
                else:
                    continue
                counted += 1
    assert counted, "no document counts the columns any more; the guard reads nothing"


#: Sentences that sent a careful person to do the dangerous thing (decision
#: 184): open what the tracker refused on the machine signed in to every
#: client's folder, publish a file of unknown origin to a household, or
#: rebuild a refused record as if nothing could be lost.
STRUCK = ("open it yourself", "open it on this machine", "on this machine, and drop",
          "drop any document you find into the client's folder",
          "drop the documents in the client's folder",
          "drop the documents you find in the client's folder",
          "drop a copy in the client's folder", "drop it in the client's folder",
          "the record itself is the truth", "nothing is lost either way",
          "and run `rebuild` — nothing is lost")


def test_no_document_sends_a_person_to_open_a_refused_file_or_publish_a_stray():
    """Decision 184: each struck sentence stays struck, and what replaced it
    - the paragraph on opening a parked file, the section on a document the
    tracker did not file - is said once. It catches these sentences' known
    shapes coming back, not a new one worded differently."""
    for rel in (*DOCUMENTS, "app/renderer/index.html", "app/renderer/app.js",
                "tracker/reasons.py", "Build App.bat"):
        text = read_as_prose(rel).lower()
        for sentence in STRUCK:
            assert sentence not in text, (rel, sentence)
    runbook = read("docs/runbook.md")
    assert runbook.count("**Before you open anything a pass parked.**") == 1
    assert runbook.count("### A document the tracker did not file") == 1


def test_the_one_machine_rule_is_stated_once_as_todays_rule():
    """Decision 184: the one-machine rule is today's rule while the owner
    decides how several machines may write, and it is stated in one place,
    the runbook's section 1, so the day it changes one paragraph changes.
    Nothing tells a person to carry the app to another machine, and nothing
    but the decision log names a viewer mode that does not exist."""
    runbook = read("docs/runbook.md")
    marker = "**One machine per clients root"
    assert runbook.count(marker) == 1
    rule = runbook[runbook.index(marker):].split("\n\n", 1)[0]
    assert "today" in rule and "while the owner decides" in rule, rule
    for rel in (*DOCUMENTS, "Build App.bat"):
        # The one sanctioned "USB" is the place a copy of the store never
        # goes (the review of decision 184, S1).
        text = " ".join(read_as_prose(rel).split()).replace("a USB drive, an email or a chat", "")
        for sentence in ("in the app on another machine", "any Windows laptop", "USB",
                         "Two machines must never both run it"):
            assert sentence not in text, (rel, sentence)
        if rel != "docs/ROADMAP.md":
            assert "viewer mode" not in text.lower(), rel
    readme = read("README.md")
    pointer = readme[readme.index("One machine per clients root"):].split("\n\n", 1)[0]
    assert "(docs/runbook.md)" in pointer, pointer


def test_the_runbook_pastes_the_letter_where_the_copy_button_says():
    """The UX council's D9: the runbook told a person to paste the letter
    into a program the app's button does not name. The program is the last
    word of ``reminder.COPY_LABEL``, so the button and the sentence change
    together."""
    from tracker.reminder import COPY_LABEL

    program = COPY_LABEL.rsplit(" ", 1)[-1]
    pasted = re.findall(r"paste it into (\w+)", read("docs/runbook.md"))
    assert pasted, "the runbook no longer says where the letter is pasted"
    assert set(pasted) == {program}, pasted


def test_the_setup_card_names_no_retired_word():
    """The UX council's D3: decision 104 retired the manifest as a file and
    decision 125 the engagement-per-folder shape; the page that sets up a
    clients root says neither."""
    page = re.sub(r"<!--.*?-->", "", read("app/renderer/index.html"), flags=re.DOTALL)
    assert "manifest" not in page.lower()


def test_the_repository_carries_no_task_for_the_office_computer():
    """Decision 184 (audit F-2): instructions to the office computer go
    through the Handoffs folder, never a file in the repository that an
    agent on that machine would obey. This catches the one known shape
    coming back - a dated local-update file and a CLAUDE.md section
    pointing at it. The real boundary is the separate Windows account the
    agent there runs under, with no Drive sign-in (principle 11), not this
    test."""
    import subprocess

    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                             text=True, check=True).stdout.splitlines()
    assert not [rel for rel in tracked if rel.startswith("docs/local-update-")]
    headings = [line for line in read("CLAUDE.md").splitlines() if line.startswith("#")]
    assert not [line for line in headings if "office computer" in line.lower()], headings


#: Command lines that take a folder argument and do not read it through the
#: door, each with why (decision 188).
DOOR_EXEMPT = {
    "tracker/settings.py": "it records the root, and holds the rule the door asks",
    "tools/backtest.py": "its folder is the firm's sorted documents, never the clients root",
    # Decision 159's race: any folder a person races a test lock in (its own
    # _race.lock, never a return's lock); it reads nothing there and walks
    # nothing - a check of the lock on a drive, not a pass over clients.
    "tracker/locking.py": "its folder is any folder a test lock is raced in; nothing is read or walked",
}


def test_every_command_line_that_takes_a_root_or_a_folder_checks_it():
    """Decision 188 (T17, R11, C-9/E-5): every command line that takes a
    clients root, a household's or a return's folder reads it through the
    one door - ``door.checked_root``, ``door.return_dir`` or
    ``door.household_dir`` - so no command line walks a root the rule
    refuses or reads a folder in the client tree as a return."""
    import ast

    asked = {"checked_root", "return_dir", "household_dir"}
    taking = []
    for path in sorted([*(REPO / "tracker").glob("*.py"), *(REPO / "tools").glob("*.py")]):
        rel = path.relative_to(REPO).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        takes = any(isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value in ("root", "folder", "engagement_dir")
                    for node in ast.walk(tree))
        if not takes:
            continue
        taking.append(rel)
        through = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                      and isinstance(node.func.value, ast.Name) and node.func.value.id == "door"
                      and node.func.attr in asked for node in ast.walk(tree))
        assert through or rel in DOOR_EXEMPT, rel
    assert set(DOOR_EXEMPT) <= set(taking), set(DOOR_EXEMPT) - set(taking)


def test_the_shell_lstats_before_it_opens_and_refuses_a_link_or_a_changed_kind():
    """Decision 188 (T18, E-14): the shell opens a reported path only after
    ``lstat`` says it is no link and still the kind the API reported - a
    folder as a folder, a file as a file - with the kinds and the refusal
    from the API's vocabulary."""
    import tracker.api as api

    main = read("app/main.js")
    opener = main[main.index("async function openPath("):]
    opener = opener[:opener.index("\n}\n")]
    assert opener.index("fs.promises.lstat(") < opener.index("shell.openPath(")
    assert "isSymbolicLink()" in opener and "isDirectory()" in opener and "isFile()" in opener
    assert "vocab.path_kinds" in main and "vocab.shell.not_opened" in main
    assert main.count("shell.openPath(") == 1
    vocab = api._vocab()
    assert vocab["shell"]["not_opened"] == api.SHELL_NOT_OPENED
    assert set(vocab["path_kinds"].values()) == {"folder", "file"}


# ------------------------------------------ one-time steps run themselves ----

#: Where a person is told what to do: the two documents and the two batch
#: files a person double-clicks (decision 209, R5).
ONE_TIME_STEP_DOCUMENTS = ("README.md", "docs/runbook.md", "Setup.bat", "Start App.bat")
#: The first word of a clause that is an instruction to a person.
INSTRUCTIONS = frozenset({"press", "run", "click", "double-click", "type", "open"})
#: What "after installing" may be said with, within three words of "after".
AFTER_WHAT = frozenset({"installing", "upgrading", "install", "upgrade", "setup", "setup.bat"})


def one_time_step_clauses(text: str) -> list[str]:
    """Every clause of ``text`` that tells a person to run a one-time step
    after installing or upgrading - the shape Jason's standing preference
    retires (decision 209): an instruction - the first word of the clause
    or of any comma-separated part of it, so "After upgrading, press X
    once" is one - with the word ``once``, and ``after`` followed within
    three words by installing, upgrading or Setup; or a clause that is
    itself the lead-in "Once, after installing ..." (the review's S1, the
    shape of the base runbook's decision-187 heading). Wrapped lines are
    joined (a ``rem`` prefix and Markdown list and quote markers dropped);
    clauses end at ``.``, ``:``, ``;`` and blank lines."""
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*rem(\s|$)", "", line, flags=re.I)
        line = re.sub(r"^\s*(?:[-*+>]|\d+\.)\s+", "", line)
        lines.append(line.strip())
    joined = "\n".join(lines)
    caught = []
    for paragraph in re.split(r"\n\s*\n", joined):
        for clause in re.split(r"[.:;]", " ".join(paragraph.split())):
            plain = re.sub(r"[*`_(]", "", clause).strip().lower()
            words = plain.split()
            if not words:
                continue
            bare = [word.strip(",)!?\"'") for word in words]
            after = any(word == "after" and set(bare[i + 1:i + 4]) & AFTER_WHAT
                        for i, word in enumerate(bare))
            starts = {part.split()[0] for part in plain.split(",") if part.split()}
            instruction = bool(starts & INSTRUCTIONS) and "once" in bare
            lead_in = bare[0] == "once" and after and bare[1:2] == ["after"]
            if (instruction and after) or lead_in:
                caught.append(clause.strip())
    return caught


@pytest.mark.parametrize(("clause", "caught"), [
    ("Run the store check once after installing.", True),
    ("installed with: **press Install Schedule once after upgrading**, and never", True),
    ("Setup runs it once, after installing.", False),
    ("Press Repair the schedule to register it again.", False),
    ("Run Setup.bat once.", False),
    ("rem Double-click it once after `Setup.bat` finishes.", True),
    ("Open the app once a week after lunch.", False),
    # The review's S1: the base runbook's decision-187 lead-in, and the
    # condition put first.
    ("**Once, after installing the version that holds every record line to the\neditor's bounds** "
     "(decision 187). Run the store check once", True),
    ("After upgrading, press Install Schedule once.", True),
    ("After installing, run the store check once.", True),
])
def test_the_one_time_step_matcher_catches_and_spares(clause, caught):
    assert bool(one_time_step_clauses(clause)) is caught, clause


def test_no_document_tells_a_person_to_run_a_one_time_step():
    """Jason's standing preference (decision 209): any one-time step after
    installing or upgrading is built into installation - Setup, the app's
    launch, the first root saved - never a line telling a person to run it."""
    for rel in ONE_TIME_STEP_DOCUMENTS:
        caught = one_time_step_clauses(read(rel))
        assert not caught, (rel, caught)


def _package_trees():
    """Every module under ``tracker/``, at any depth, parsed."""
    import ast

    for path in sorted((REPO / "tracker").rglob("*.py")):
        yield path.relative_to(REPO).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def test_only_the_lock_asks_the_platform_for_this_computers_name():
    """``platform.node`` is called in ``locking.this_host`` and nowhere else
    under the package (decision 209): the lock line and the designation of
    the computer that runs the schedule normalise one name one way. By the
    syntax tree, at any depth (the review's N7), so ``from platform import
    node`` is caught as surely as ``platform.node()``."""
    import ast

    found = []
    for rel, tree in _package_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "node" and \
                    isinstance(node.value, ast.Name) and node.value.id == "platform":
                found.append(rel)
            if isinstance(node, ast.ImportFrom) and node.module == "platform" and \
                    any(alias.name == "node" for alias in node.names):
                found.append(f"{rel} (from platform import node)")
    assert found == ["tracker/locking.py"], found
    locking = read("tracker/locking.py")
    this_host = locking[locking.index("def this_host"):]
    this_host = this_host[:this_host.index("\ndef ")]
    assert "platform.node" in this_host


def hand_comparisons(source: str) -> list[int]:
    """The lines of ``source`` that compare a name with this computer's by
    hand: ``==``, ``!=``, ``in`` or ``not in`` where one side is a
    ``this_host()`` call, a name bound from one in the same function, or a
    tuple, list or set holding either (the re-review's SF2: 5bb5d3c bound
    ``here = this_host()`` and compared ``named == here``)."""
    import ast

    def calls_this_host(node):
        return isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name) and node.func.id == "this_host"
            or isinstance(node.func, ast.Attribute) and node.func.attr == "this_host")

    tree = ast.parse(source)
    scopes = [tree, *(node for node in ast.walk(tree)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)))]
    found = set()
    for scope in scopes:
        bound = {target.id for node in ast.walk(scope)
                 if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
                 and node.value is not None and calls_this_host(node.value)
                 for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                 if isinstance(target, ast.Name)}

        def is_this_host(node, bound=bound):
            if calls_this_host(node) or isinstance(node, ast.Name) and node.id in bound:
                return True
            return isinstance(node, (ast.Tuple, ast.List, ast.Set)) and \
                any(is_this_host(one, bound) for one in node.elts)

        for node in ast.walk(scope):
            if isinstance(node, ast.Compare) and \
                    any(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for op in node.ops) and \
                    any(is_this_host(side) for side in (node.left, *node.comparators)):
                found.add(node.lineno)
    return sorted(found)


@pytest.mark.parametrize(("source", "caught"), [
    ("ok = named == this_host()", True),
    ("ok = locking.this_host() != named", True),
    # 5bb5d3c's schedule_decision: the name bound first, compared after.
    ("def decide(named):\n    here = this_host()\n    return named == here", True),
    ("ok = named in (this_host(),)", True),
    ("here = this_host()\nok = named not in {here}", True),
    ("line = this_host() + '\\n'", False),
    ("ok = is_this_host(named)", False),
])
def test_the_hand_comparison_matcher_catches_and_spares(source, caught):
    assert bool(hand_comparisons(source)) is caught, source


def test_no_module_compares_a_name_with_this_host_by_hand():
    """Every comparison of a computer's name with this one is decision 159's
    ``locking.is_this_host`` - the one comparison of a host, in any case and
    spacing - never ``== this_host()``, ``!= here`` after ``here =
    this_host()``, or ``in (this_host(),)``. ``this_host()`` stays where
    this computer's name is *written* (the lock line, the designation file,
    a sentence)."""
    found = []
    for path in sorted((REPO / "tracker").rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        for line in hand_comparisons(path.read_text(encoding="utf-8")):
            if rel == "tracker/locking.py" and line in _is_this_host_lines():
                continue            # the one comparison itself
            found.append(f"{rel}:{line}")
    assert found == [], found


def _is_this_host_lines() -> range:
    """The lines of ``locking.is_this_host``, which is the comparison."""
    import ast

    tree = ast.parse(read("tracker/locking.py"))
    [function] = [node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == "is_this_host"]
    return range(function.lineno, function.end_lineno + 1)
