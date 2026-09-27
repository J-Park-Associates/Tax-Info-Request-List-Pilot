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

from tests.conftest import child_env
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

    Since decision 186 it lives in the tracker's data folder, never in a
    checkout - but a checkout from before it may still hold one, and so
    may the run log. A temp the tracker writes beside a target
    (``fsio.TEMP_SUFFIX``) and the real corpus's expectations file, which
    names the firm's own documents, are ignored too, and none is tracked.
    """
    import fnmatch
    import subprocess

    from tracker.fsio import TEMP_SUFFIX
    from tracker.progress import PASSES_DIRNAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import (
        ERROR_LOG_FILENAME,
        EXPECTATIONS_FILENAME,
        OCR_SCRATCH_DIRNAME,
        SETTINGS_FILENAME,
    )
    from tracker.store import STORE_FILENAME, STORE_SHM_FILENAME, STORE_WAL_FILENAME

    ignored = [line.strip() for line in read(".gitignore").splitlines()
               if line.strip() and not line.startswith("#")]
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME, LOG_FILENAME, STATUS_PAGE_FILENAME,
                 SCHEDULE_XML_FILENAME, SETTINGS_FILENAME,
                 STORE_FILENAME, STORE_WAL_FILENAME, STORE_SHM_FILENAME,
                 # Decision 193: the error log, its rotated copies and the
                 # passes folder, beside the store.
                 ERROR_LOG_FILENAME, f"{ERROR_LOG_FILENAME}.*", PASSES_DIRNAME + "/",
                 f"{OCR_SCRATCH_DIRNAME}/", f"*{TEMP_SUFFIX}", EXPECTATIONS_FILENAME):
        assert ignored.count(name) == 1, name
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.splitlines()
    assert [rel for rel in tracked
            if fnmatch.fnmatch(Path(rel).name, f"*{TEMP_SUFFIX}")
            or Path(rel).name == EXPECTATIONS_FILENAME] == []


def test_the_projects_agent_settings_can_be_committed_and_nothing_else_under_claude():
    """Decision 186: ``.claude/settings.json`` can be tracked, so the
    project's agent settings carry a deny list (a guard rail, not a wall);
    a person's own settings and Claude Code's worktrees stay ignored."""
    import subprocess

    def ignored(rel: str) -> int:
        return subprocess.run(["git", "check-ignore", "-q", "--no-index", rel], cwd=REPO).returncode

    assert ignored(".claude/settings.json") == 1
    assert ignored(".claude/settings.local.json") == 0
    assert ignored(".claude/worktrees/x/y") == 0


def _deny_list_from_the_constants() -> list[str]:
    """The agent deny list, spelled from the constants that own each name
    (decision 186). A folder is never denied by its bare name alone: a
    person's own folders share names like the firm's or ``Clients`` (the
    office's Claude workspace sits in a folder named like the firm's tree,
    and a bare rule for it refused every session its own files - the undoing
    of #133 by #134). So a client folder is named by the tree's shape under
    the clients root - a household, then a year, then a return or the
    inbox - and only a name no person's folder carries (``ocr-scratch``)
    stands alone."""
    from tracker.checkpoint import CHECKPOINT_FILENAME, SET_ASIDE_SUFFIX
    from tracker.content_check import RETIRED_CACHE_FILENAME
    from tracker.layout import CLIENTS_TREE, INBOX_DIR_NAME, OPENED_DIR_NAME, PRIVATE_TREE, RETURN_NAME_PATTERN
    from tracker.ledger import LEDGER_FILENAME
    from tracker.registry import LEGACY_MANIFEST_FILENAME
    from tracker.reminder import DRAFT_FILENAME
    from tracker.runner import LAST_PASS_FILENAME, LOG_FILENAME, PASS_ORDER_FILENAME, STATUS_PAGE_FILENAME
    from tracker.settings import DATA_HOME_NAME, ERROR_LOG_FILENAME, EXPECTATIONS_FILENAME, OCR_SCRATCH_DIRNAME
    from tracker.store import RECOVERED_DIR, STORE_FILENAME, STORE_SHM_FILENAME, STORE_WAL_FILENAME
    from tracker.view import VIEW_FILENAME

    aside = SET_ASIDE_SUFFIX.split("{", 1)[0] + "*"
    stem, ext = DRAFT_FILENAME.rsplit(".", 1)
    year = "[12][0-9][0-9][0-9]"
    a_return = RETURN_NAME_PATTERN.format(form="[0-9]*", client="*")    # every form id begins with a digit
    places = [f"//c/Users/*/AppData/Local/{DATA_HOME_NAME}/**", f"~/.local/state/{DATA_HOME_NAME}/**",
              "//g/Shared drives/**",
              f"//**/{CLIENTS_TREE}/*/{INBOX_DIR_NAME}/**", f"//**/{CLIENTS_TREE}/*/{year}/**",
              f"//**/{PRIVATE_TREE}/*/{year}/{a_return}/**", f"//**/{PRIVATE_TREE}/*/{year}/{OPENED_DIR_NAME}/**",
              f"//**/{OCR_SCRATCH_DIRNAME}/**",
              f"//**/{RECOVERED_DIR}/*__*.jsonl"]    # recover's exports, named by the return's path
    files = [STORE_FILENAME, STORE_WAL_FILENAME, STORE_SHM_FILENAME, STORE_FILENAME + aside,
             CHECKPOINT_FILENAME, CHECKPOINT_FILENAME + "-*", CHECKPOINT_FILENAME + ".*",
             LEDGER_FILENAME, LOG_FILENAME, LOG_FILENAME + ".*", ERROR_LOG_FILENAME, ERROR_LOG_FILENAME + ".*",
             LAST_PASS_FILENAME, LAST_PASS_FILENAME + ".*", PASS_ORDER_FILENAME, f"{stem}*.{ext}",
             STATUS_PAGE_FILENAME, VIEW_FILENAME, EXPECTATIONS_FILENAME, RETIRED_CACHE_FILENAME,
             LEGACY_MANIFEST_FILENAME]
    paths = places + [f"//**/{name}" for name in files]
    return [f"{tool}({path})" for path in paths for tool in ("Read", "Edit")]


def _denied(deny: list[str], path: str) -> bool:
    """Whether a Read rule of ``deny`` matches the absolute ``path`` (``/c/...``),
    read the way the rules are written - gitignore's: ``**/`` any folders,
    ``*`` within one name, ``[...]`` one character of a set - and without
    regard to case, as Windows reads a path, so the test errs toward
    "refused" when it asks that a person's own folder stays readable."""
    for rule in deny:
        if not rule.startswith("Read(//"):
            continue
        pattern, out, i = rule[len("Read(/"):-1], "", 0
        while i < len(pattern):
            if pattern.startswith("**/", i):
                out, i = out + "(?:[^/]*/)*", i + 3
            elif pattern.startswith("/**", i) and i + 3 == len(pattern):
                out, i = out + "/.*", i + 3
            elif pattern[i] == "*":
                out, i = out + "[^/]*", i + 1
            elif pattern[i] == "[":
                end = pattern.index("]", i)
                out, i = out + pattern[i:end + 1], end + 1
            else:
                out, i = out + re.escape(pattern[i]), i + 1
        if re.fullmatch(out, path, flags=re.IGNORECASE):
            return True
    return False


def test_the_agent_deny_list_names_the_data_home_and_every_file_that_names_a_client():
    """Decision 186 (Jason's answer A to its Q1): the project's agent
    settings deny Claude's own file tools, reading and editing alike, the
    data home, the client Shared Drive, a client tree by its shape under the
    clients root, and every file the tracker writes that names a client,
    wherever on the machine it sits - the list equal, rule for rule, to one
    spelled from the constants, so a rule dropped, widened, narrowed or
    respelled fails here; and ``.github/CODEOWNERS`` routes ``/.claude/`` to
    the owner. A guard rail, not a wall (security principle 8): a deny rule
    stops the agent's file tools on the spellings it lists, a shell command
    can still read the file, and the wall is the separate Windows account
    the office's AI tooling runs under."""
    deny = json.loads(read(".claude/settings.json"))["permissions"]["deny"]
    assert deny == _deny_list_from_the_constants()
    owners = [line.split()[0] for line in read(".github/CODEOWNERS").splitlines()
              if line.strip() and not line.startswith("#")]
    assert "/.claude/" in owners, owners      # the list is the owner's to review


def test_the_deny_list_never_refuses_a_persons_own_folder_that_shares_a_client_folders_name():
    """#133 landed a rule for the firm's tree by its bare name, and the
    office's Claude workspace sits in a folder of that same name: every
    session was refused its own START HERE, the Patches folder and the
    checkout, and #134 undid it. So no folder is denied by its name alone:
    a person's folders named like the firm's tree, ``Clients``, the inbox or
    the review folder - with no household, year and return beneath them -
    stay readable, while the same trees in the clients root's shape, on any
    drive, are refused."""
    from tracker.layout import (
        CLIENTS_TREE,
        INBOX_DIR_NAME,
        OPENED_DIR_NAME,
        PREPARED_DIR_NAME,
        PRIVATE_TREE,
        RETURN_NAME_PATTERN,
        REVIEW_DIR_NAME,
    )
    from tracker.store import RECOVERED_DIR

    deny = json.loads(read(".claude/settings.json"))["permissions"]["deny"]
    workspace = f"/c/Users/staff/{PRIVATE_TREE}"
    own = [f"{workspace}/START HERE.md", f"{workspace}/Patches/0001-fix.patch",
           f"{workspace}/Claude/notes/2026/plan.md",
           f"{workspace}/Handoffs/2026/CODE UPDATE - 09-27/notes.md",
           f"{workspace}/Tax-Info-Request-List/tracker/runner.py",
           f"{workspace}/Tax-Info-Request-List/docs/runbook.md",
           f"/c/Users/staff/Documents/{CLIENTS_TREE}/list.txt",
           f"/c/Users/staff/{INBOX_DIR_NAME}/scan.pdf",
           f"/c/Users/staff/Desktop/{REVIEW_DIR_NAME}/todo.txt",
           "/c/Users/staff/Documents/recovered/photo.jpg", "/c/Users/staff/Documents/passes/ticket.pdf"]
    for path in own:
        assert not _denied(deny, path), path
    root = "/e/Firm"
    a_return = RETURN_NAME_PATTERN.format(form="1040", client="Sample Client")
    client = [f"{root}/{CLIENTS_TREE}/Sample Household/{INBOX_DIR_NAME}/W-2.pdf",
              f"{root}/{CLIENTS_TREE}/Sample Household/2025/W-2.pdf",
              f"{root}/{PRIVATE_TREE}/Sample Household/2025/{a_return}/{PREPARED_DIR_NAME}/W-2.pdf",
              f"{root}/{PRIVATE_TREE}/Sample Household/2025/{a_return}/{REVIEW_DIR_NAME}/scan.pdf",
              f"{root}/{PRIVATE_TREE}/Sample Household/2025/{OPENED_DIR_NAME}/letter.pdf",
              f"/c/Tools/tracker/{RECOVERED_DIR}/{PRIVATE_TREE}__Sample Household__2025__"
              f"{a_return}-2026-09-26-120000.jsonl",
              "/g/Shared drives/Any Drive/anything.pdf"]
    for path in client:
        assert _denied(deny, path), path


def test_every_file_beside_the_store_is_ignored_by_git():
    """Decision 159 (the final review's MF1): the checkpoint, the last-pass
    file, recover's exports and a set-aside older store sit beside the
    store, which in a source checkout is this repository - and each holds
    client data or describes one machine. Asked of git itself, by the names
    the code writes, so a pattern that does not match is caught."""
    import subprocess

    from tracker.checkpoint import CHECKPOINT_FILENAME, SET_ASIDE_SUFFIX
    from tracker.fsio import TEMP_SUFFIX
    from tracker.runner import LAST_PASS_FILENAME
    from tracker.store import RECOVERED_DIR, STORE_FILENAME

    aside = STORE_FILENAME + SET_ASIDE_SUFFIX.format(version=15)
    names = [CHECKPOINT_FILENAME, CHECKPOINT_FILENAME + "-wal", CHECKPOINT_FILENAME + "-shm",
             LAST_PASS_FILENAME, f"{LAST_PASS_FILENAME}.1234.abcd{TEMP_SUFFIX}",
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


def test_the_tools_ask_one_rule_whether_a_path_is_inside_the_repository():
    """Decision 185: ``settings.inside_the_app()`` is the one answer to
    "inside the repository", judged by the folder itself as well as its
    spelling; no tool spells the rule a second time."""
    spelled = re.compile(r"is_relative_to\(ROOT\)|ROOT in .*\.parents|== ROOT\b")
    for path in sorted((REPO / "tools").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not spelled.search(text), path.name
    for name in ("backtest.py", "learned_keywords.py"):
        assert "inside_the_app(" in read(f"tools/{name}"), name


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
    # Every word the household's card, the dialog's household step and the
    # misfit list show is the API's too, and so are the two trees and the
    # two patterns the dialog's previews fill (decision 125).
    import tracker.api as api_module

    words = api_module._vocab()
    for literal in (*words["household"].values(), *words["layout"].values()):
        if not isinstance(literal, str):
            continue
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal
        assert f">{literal}<" not in html, literal
    # Decision 142 (its review, R1): every word it adds is the API's - the
    # status of a row nobody asked for, the count beside it, the dialog's
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
             api_module.SET_ASIDE_SECTION.split("{")[0].strip())
    for literal in added:
        assert literal and literal not in js and literal not in html, literal
    for key in ("not_asked_label", "not_asked_key", "ask_the_client", "ask_the_client_note",
                "not_asked_table_label", "roll_template_label", "nothing_asked",
                "new_not_asked_carried", "origin_new"):
        assert f"vocab.{key}" in js, key
    assert "vocab.set_aside.heading" in js and "vocab.editor.yes_no_fields" in js
    # Decision 131: the room's heading and its two sentences are the API's.
    # The renderer fills neither pattern: the set-root reply carries each
    # return's sentences already filled.
    assert set(words["room"]) == {"heading", "short", "parks"}
    for literal in words["room"].values():
        assert literal not in js and literal not in html, literal
        stem = literal.split("{")[0].strip() or literal.split("}")[1].split("{")[0].strip()
        assert stem not in js and stem not in html, stem


def test_the_renderers_one_list_writer_flattens_what_it_is_handed():
    """Half the callers once built a list as "one fixed node, then a mapped
    array", and ``replaceChildren`` turns an array it is handed into the
    text ``[object HTMLOptionElement],...`` instead of its elements - so
    the old list of existing households and the rollover's list of form
    templates each came out holding one option and a line of noise. One
    flatten in the writer, not a rule every call site has to remember; it
    stays for any caller that builds a list that way.
    """
    js = read("app/renderer/app.js")
    body = js.split("function show(id, nodes) {", 1)[1].split("}", 1)[0]
    assert "nodes.flat(" in body, body


# ------------------ decision 196: Roll forward and Add a return ----


def _js_function(js: str, header: str) -> str:
    """One function of ``app.js`` exactly as it is spelled, braces matched."""
    start = js.index(header)
    depth = 0
    for at in range(js.index("{", start + len(header) - 1), len(js)):
        depth += {"{": 1, "}": -1}.get(js[at], 0)
        if depth == 0:
            return js[start:at + 1]
    raise AssertionError(f"{header} in app.js has no closing brace")


def test_the_renderer_keeps_no_hidden_household_choice():
    """D1 was a household picked on one page into a variable the roll page
    never read. The wizard is gone whole, and with it every place a
    household could be chosen except the card being looked at: the one
    household a new return is added to by path is set from that card, and
    only there."""
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    for name in ("chosenHousehold", "rollFor", "rollHousehold", "priorsOfHousehold",
                 "openWizard"):
        assert not re.search(rf"\b{name}\b", js), name
    assert 'call(["priors"]' not in js
    for ident in ("hh-existing", "ro-household", "ro-year", "wiz-prior", "wp-new-client",
                  "wf-back", 'btn-new"'):
        assert ident not in js and ident not in html, ident
    assigned = re.findall(r"\baddingTo = ([^;]+);", js)
    assert len(assigned) == 4, assigned          # the declaration, and the three below
    opening = _js_function(js, "async function openAddReturn(hh) {")
    fresh = _js_function(js, "async function openNewHousehold() {")
    closing = _js_function(js, "function closeNewReturn() {")
    assert re.findall(r"\baddingTo = ([^;]+);", opening) == ["hh.path"]
    assert re.findall(r"\baddingTo = ([^;]+);", fresh) == ["null"]
    assert re.findall(r"\baddingTo = ([^;]+);", closing) == ["null"]
    assert "let addingTo = null;" in js


def _a_household(name: str, year: int) -> dict:
    """A fabricated household payload as ``state.household`` carries it:
    two returns of the open year, one already rolled on, one retired."""
    home = f"/fabricated/{name}"
    def one(label, **more):
        return {"label": f"{name} {year} {label}", "path": f"{home}/{year}/{label}", "year": year,
                "active": True, "superseded_by": None, "rollable": True, "form": "1040",
                "people": [f"{label} person"], **more}
    return {"name": name, "path": home, "open_years": [year], "roll_year": year + 1,
            "returns": [one("1040 - One"), one("1120S - Two", form="1120S"),
                        one("1040 - Rolled", superseded_by="later", rollable=False),
                        one("1040 - Retired", active=False, rollable=False)]}


def test_roll_forward_rolls_the_household_on_screen_and_names_no_other(tmp_path):
    """The roll call is one pure function of the household on screen: run
    as written, with another household's choices left over, it names only
    the household it was handed - its open-year return, its ticked returns,
    the year the card named - and nothing when no roll is offered."""
    import shutil
    import subprocess

    import tracker.api as api_module

    js = read("app/renderer/app.js")
    body = _js_function(js, "function rollHouseholdCall(hh, choice) {")
    # The static half, which always runs: the one roll call is built here,
    # and this function reads nothing but what it is handed.
    assert js.count('"roll-household"') == 1 and '"roll-household"' in body
    for name in ("households", "active", "lastState", "document", "$("):
        assert not re.search(rf"(?<![\w.]){re.escape(name)}", body), name

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it); the roll call's source is still held by name")
    here, there = _a_household("Alpha Household", 2026), _a_household("Beta Household", 2026)
    a_ticked, a_unticked = here["returns"][0]["path"], here["returns"][1]["path"]
    b_first = there["returns"][0]["path"]
    script = tmp_path / "roll_call.js"
    script.write_text(
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
        "const vocab = { engagement_flag: input.flag };\n"
        f"{body}\n"
        "const choice = (c) => c && { household: c.household, unticked: new Set(c.unticked),\n"
        "                              forms: new Map(c.forms) };\n"
        "process.stdout.write(JSON.stringify(input.cases.map(\n"
        "  ([hh, c]) => rollHouseholdCall(hh, choice(c)))));\n",
        encoding="utf-8", newline="\n")
    leftover = {"household": there["path"], "unticked": [a_ticked], "forms": [[b_first, "1065"]]}
    own = {"household": here["path"], "unticked": [a_unticked], "forms": [[a_ticked, "1040"]]}
    cases = [[here, leftover], [here, own], [{**here, "roll_year": None}, own]]
    done = subprocess.run([node, str(script)], capture_output=True, text=True, encoding="utf-8",
                          input=json.dumps({"flag": api_module.ENGAGEMENT_FLAG, "cases": cases}),
                          timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    with_leftover, with_own, offered_none = json.loads(done.stdout)

    open_year = [r["path"] for r in here["returns"] if r["rollable"]]
    for argv, spec in (with_leftover, with_own):
        assert argv[:2] == ["roll-household", api_module.ENGAGEMENT_FLAG]
        assert argv[2] in open_year
        assert spec["year"] == here["roll_year"]
        assert all(one["prior"] in open_year for one in spec["returns"])
        assert "Beta" not in json.dumps([argv, spec])
    # Beta's leftover untick and pick are nobody's here: every open-year
    # return is ticked, each with its own recorded form.
    assert with_leftover[1]["returns"] == [{"prior": a_ticked, "form": "1040"},
                                           {"prior": a_unticked, "form": "1120S"}]
    # Alpha's own untick leaves that return out, to be retired by the API.
    assert with_own[1]["returns"] == [{"prior": a_ticked, "form": "1040"}]
    assert offered_none is None


def test_the_card_hands_the_roll_call_the_household_it_shows_and_no_other(tmp_path):
    """D1 at the caller: the card's roll button builds its call from the
    household on screen, and from nothing else in reach. Run as written,
    with another household first in the list the page holds, it hands
    ``rollHouseholdCall`` the household on screen - and nothing at all
    when no household is on screen."""
    import shutil
    import subprocess

    js = read("app/renderer/app.js")
    body = _js_function(js, "async function rollFromCard() {")
    # The static half: one call site, in this function, fed from the state
    # the card was drawn from, and no list of households or returns read.
    calls = [m.start() for m in re.finditer(r"(?<!function )\brollHouseholdCall\(", js)]
    assert len(calls) == 1 and "rollHouseholdCall(" in body, calls
    assert "const hh = lastState && lastState.household;" in body
    for name in ("households", "engagements"):
        assert not re.search(rf"\b{name}\b", body), name

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it); the caller's source is still held by name")
    here, there = _a_household("Alpha Household", 2026), _a_household("Beta Household", 2026)
    script = tmp_path / "roll_caller.js"
    script.write_text(
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
        "const vocab = { household: {} };\n"
        "const handed = [];\n"
        "let lastState = null;\n"
        "const households = input.households;\n"
        "const engagements = input.households.map((hh) => ({ path: hh.returns[0].path }));\n"
        "function gatherRollChoice(hh) { return { household: hh.path, unticked: new Set(),\n"
        "                                         forms: new Map() }; }\n"
        "function rollHouseholdCall(hh, choice) {\n"
        "  handed.push([hh.path, choice.household]); return null; }\n"
        f"{body}\n"
        "(async () => {\n"
        "  for (const shown of input.shown) { lastState = { household: shown }; await rollFromCard(); }\n"
        "  process.stdout.write(JSON.stringify(handed));\n"
        "})();\n",
        encoding="utf-8", newline="\n")
    done = subprocess.run([node, str(script)], capture_output=True, text=True, encoding="utf-8",
                          input=json.dumps({"households": [there, here],
                                            "shown": [here, None, there]}),
                          timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == [[here["path"], here["path"]],
                                       [there["path"], there["path"]]]


def test_the_roll_fold_says_what_unticking_does_and_a_paused_card_offers_neither_entry():
    """The retire-on-untick sentence (decision 126) is drawn inside the
    fold, beside the ticks and before the button, naming the year; the
    fold is hidden whenever the API offers no roll (a paused household
    among them), and Add a return is hidden while the household is paused
    (decision 188), because then the pause is the work."""
    js = read("app/renderer/app.js")
    fold = _js_function(js, "function renderRollFold(hh) {")
    assert 'fold.classList.toggle("hidden", !hh.roll_year);' in fold
    note = fold.index('fill(words.rollover_unticked, { year })')
    assert fold.index('className: "roll-tick"') < note < fold.index('id: "btn-roll"')
    card = _js_function(js, "function renderHousehold(state) {")
    assert "renderRollFold(hh);" in card
    assert '$("btn-add-return").classList.toggle("hidden", Boolean(pause.sentence));' in card
    assert "const pause = hh.pause || {};" in card


#: The words decision 196 adds under ``vocab.household``.
ROLL_AND_ADD_KEYS = ("roll_forward_to", "roll_ticked", "roll_intro", "roll_no_template",
                     "roll_done", "roll_carried", "roll_unfiled", "roll_retired_line",
                     "roll_forms_unloaded", "add_return", "add_return_title", "new_intro",
                     "form_step_title", "form_step_note", "change_form", "change_household",
                     "items_title", "create_return", "return_created", "empty_root")


def test_every_word_of_roll_forward_add_a_return_and_new_household_is_the_apis():
    """Every visible word of the roll fold, Add a return and New household
    comes from the API's vocabulary: each is read by its key, none is typed
    in the renderer or the page, and the wizard's own typed words are gone
    from the app and from the docs that walked a person through it."""
    import tracker.api as api_module

    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    words = api_module._vocab()["household"]
    assert "existing" not in words
    for key in ROLL_AND_ADD_KEYS:
        assert isinstance(words[key], str) and words[key], key
        assert f"vocab.household.{key}" in js or f"words.{key}" in js, key
        literal = words[key]
        stem = literal.split("{")[0].strip()
        if stem:
            for quoted in (f'"{stem}', f"'{stem}", f"`{stem}", f">{stem}"):
                assert quoted not in js and quoted not in html, (key, quoted)
        else:
            # A text that opens on a placeholder is typed, when it is, after
            # a `${...}` inside a template string: its words after the first
            # placeholder are looked for bare.
            bare = literal.split("}")[1].split("{")[0].strip()
            assert bare not in js and bare not in html, (key, bare)
    for typed in ("New Engagement", "Create Engagement", "Roll Forward<", "returning client",
                  "No engagements under",
                  "No template — carry", "return(s) rolled into", "request(s) carried",
                  "file(s) sent last year were never filed"):
        assert typed not in js and typed not in html, typed
    for doc in ("docs/runbook.md", "README.md", "docs/workflow.md"):
        assert "New Engagement" not in read(doc), doc


def test_a_refused_create_stays_in_the_dialog():
    """A refused create - 188's duplicate household name among them - is
    shown in the dialog's own note, where it stays until a field is edited
    or the dialog closed, so nothing typed is lost; a toast would vanish."""
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    body = _js_function(js, "async function createEngagement() {")
    caught = body.split("} catch (err) {", 1)[1].split("} finally {", 1)[0]
    # A1's split (decision 196, the restack review's S2): a refusal stays in
    # the dialog, in failureSentence's words; anything else is a notice.
    refusal, other = caught.split("} else {", 1)
    assert 'if (err.failure && err.failure.kind === "refused") {' in refusal, caught
    assert '$("ne-note").textContent = failureSentence(err);' in refusal, caught
    assert other.strip().startswith("failed(err);"), caught
    assert "err.message" not in caught and "toast(" not in caught, caught
    assert '<p id="ne-note" class="rem-hold hidden" role="alert"></p>' in html


def test_a_refused_create_is_said_in_the_dialog_and_a_locked_one_is_a_notice(tmp_path):
    """A1's split, run as written (decision 196, the restack review's S2):
    ``createEngagement``'s refusal lands in the dialog's note in the API's
    sentence and raises no notice; a locked create lands in the notices
    area and leaves the note alone; an error of the page's own is said by
    its class there, never its text."""
    harness = """
const classes = () => { const on = new Set(["hidden"]);
  return { remove: (c) => on.delete(c), contains: (c) => on.has(c) }; };
const page = { "tmpl-list": { querySelectorAll: () => [] }, "ne-create": { disabled: false },
               "ne-note": { textContent: "", classList: classes() } };
const $ = (id) => page[id] || { value: "" };
const templates = [];
const customItems = [{ identifier: "X01", document: "Letter from the county" }];
const wizardPeople = [];
const selectedForm = "1040";
const householdSpec = () => ({});
const personSpec = (p) => p;
const call = async () => { throw THROWN; };
const toast = (text) => { throw new Error(`toasted: ${text}`); };
const vocab = { nothing_asked: "", shell: { page_error: "Own error ({kind})." } };
const fill = (text, values) => text.replace("{kind}", values.kind);
const done = { notices: [], logged: 0 };
const window = { tracker: { logError: () => { done.logged += 1; } } };
const notice = (failure) => done.notices.push([failure.sentence, failure.kind]);
createEngagement().then(() => process.stdout.write(JSON.stringify({
  ...done, note: page["ne-note"].textContent, shown: !page["ne-note"].classList.contains("hidden"),
  enabled: !page["ne-create"].disabled })));
"""
    headers = ("async function createEngagement() {", "function failed(err, retry) {",
               "function failureSentence(err) {")

    def thrown(sentence: str, kind: str) -> str:
        return (f"Object.assign(new Error({json.dumps(sentence)}), {{ failure: "
                f"{{ sentence: {json.dumps(sentence)}, kind: {json.dumps(kind)}, identifier: null }} }})")

    refused = "A household of that name is already on the list (fabricated)."
    seen = _run_renderer(tmp_path, "create_refused", headers, harness.replace("THROWN", thrown(refused, "refused")))
    assert seen == {"notices": [], "logged": 0, "note": refused, "shown": True, "enabled": True}
    locked = "Another pass holds this household (fabricated)."
    seen = _run_renderer(tmp_path, "create_locked", headers, harness.replace("THROWN", thrown(locked, "locked")))
    assert seen == {"notices": [[locked, "locked"]], "logged": 0, "note": "", "shown": False, "enabled": True}
    seen = _run_renderer(tmp_path, "create_own", headers,
                         harness.replace("THROWN", 'new TypeError("x is undefined at C:/private")'))
    assert seen == {"notices": [["Own error (TypeError).", "failed"]], "logged": 1, "note": "",
                    "shown": False, "enabled": True}


def test_new_households_refusal_leads_back_to_the_name_field_with_everything_typed_kept():
    """188's duplicate-name refusal is read on the request list, and its
    advice is to change the household's name. New household's request list
    carries the way back to the name field, and Continue returns to the list
    as it was left: neither clears a field, the form, the ticks or the
    people. Add a return has no household step, so it has no such button."""
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    assert '<button id="wi-household" class="wiz-back hidden"></button>' in html
    assert "vocab.household.change_household" in js
    chosen = _js_function(js, "function chooseForm(formId) {")
    assert '$("wi-household").classList.toggle("hidden", Boolean(addingTo));' in chosen
    back = js.split('$("wi-household").addEventListener("click", () => {', 1)[1].split("});", 1)[0]
    assert 'showStep("household");' in back and '$("hh-name").focus();' in back, back
    assert "renderHouseholdStep" not in back and "chooseForm" not in back, back
    assert ('$("wh-next").addEventListener("click", () => showStep(selectedForm ? "items" : "form"));'
            in js)


def test_a_catalog_that_will_not_load_is_said_in_the_roll_fold_and_the_page_is_drawn():
    """The roll fold's form pick needs the catalog; a ``templates`` call that
    fails is said there, in the API's words, and the card is drawn all the
    same. No pick is drawn then, so the roll keeps each return's recorded
    form instead of sending "no template" for every one."""
    js = read("app/renderer/app.js")
    # Start-up loads the catalog once (decision 194: a switch reads the
    # state alone, so the catalog is not read again on every click).
    starting = _js_function(js, "async function bootstrap(preferPath) {")
    guarded = starting.split("try {\n      await loadForms();\n    } catch (err) {", 1)
    assert len(guarded) == 2, starting
    # Said in the words a notice would use: a page error by its class alone
    # (principle 7), never its message.
    assert guarded[1].lstrip().startswith("formsUnloaded = failureSentence(err);"), guarded[1]
    assert "err.message" not in guarded[1].split("}", 1)[0], guarded[1]
    fold = _js_function(js, "function renderRollFold(hh) {")
    said = fold.index("fill(words.roll_forms_unloaded, { reason: formsUnloaded })")
    assert fold.index("formsUnloaded\n") < said < fold.index('className: "roll-form-pick"')
    assert 'formsUnloaded = "";' in _js_function(js, "async function loadForms() {")


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

    from tracker.checkpoint import CHECKPOINT_FILENAME
    from tracker.filer import README_LOCK_FILENAME
    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME, RACE_LOCK_FILENAME
    from tracker.registry import LEGACY_MANIFEST_FILENAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LAST_PASS_FILENAME, LOG_FILENAME, PASS_ORDER_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scaffold import README_NAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import ERROR_LOG_FILENAME, SETTINGS_FILENAME
    from tracker.store import STORE_FILENAME
    from tracker.view import VIEW_FILENAME

    assert LEGACY_MANIFEST_FILENAME in RETIRED_FILES
    owned = {LEDGER_FILENAME, LOCK_FILENAME, DRAFT_FILENAME, NEW_DRAFT_FILENAME,
             LOG_FILENAME, STATUS_PAGE_FILENAME, README_NAME, README_LOCK_FILENAME,
             SCHEDULE_XML_FILENAME, SETTINGS_FILENAME, STORE_FILENAME, VIEW_FILENAME,
             PASS_ORDER_FILENAME, ERROR_LOG_FILENAME,
             # Decision 159: the checkpoint, the scheduled pass's own note, the race's lock.
             CHECKPOINT_FILENAME, LAST_PASS_FILENAME, RACE_LOCK_FILENAME}
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
                   "checkpoint", "locking")
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


# ========== decision 193: replies never go quiet, and a pass can be watched ==========

#: main.js run by node against a stand-in for Electron whose ``tracker-cmd``
#: handler is kept and called, with ``child_process.spawn`` pointed at a
#: scripted fake tracker (``_FAKE_TRACKER``) - a real child process, so the
#: shell's reading of stdout, its kill and its stderr are the real code.
_SHELL_HARNESS = r"""
const Module = require("module");
const realSpawn = require("child_process").spawn;
const realFs = require("fs");
const [mainJs, fake, calls] = process.argv.slice(2);
let handler = null;
const sent = [];
const electron = {
  app: { isPackaged: false, requestSingleInstanceLock: () => true, quit() {}, on() {},
         whenReady: () => new Promise(() => {}) },
  BrowserWindow: class {}, Menu: { setApplicationMenu() {} },
  ipcMain: { handle(name, fn) { if (name === "tracker-cmd") handler = fn; } },
  shell: {}, dialog: {},
};
const load = Module._load;
Module._load = function (request, ...rest) {
  if (request === "electron") return electron;
  if (request === "child_process") {
    return { spawn: (cmd, args, opts) => process.env.FAKE_SPAWN_FAILS
      ? realSpawn("/no/such/tracker-for-this-test", [], opts)
      : realSpawn(process.execPath, [fake, ...args], { ...opts, cwd: undefined }) };
  }
  if (request === "fs") return { ...realFs, existsSync: () => true };
  return load.call(this, request, ...rest);
};
require(mainJs);
const event = { sender: { send: (channel, message) => sent.push({ channel, message }) } };
(async () => {
  const out = [];
  for (const args of JSON.parse(calls)) {
    const began = Date.now();
    const reply = await handler(event, args, undefined);
    out.push({ args, reply, ms: Date.now() - began });
  }
  // The shell appends a failed child's stderr without waiting on it; give
  // that write its moment before the harness ends.
  setTimeout(() => {
    process.stdout.write(JSON.stringify({ out, sent }));
    process.exit(0);
  }, 500);
})();
"""

#: The fake tracker: what each command prints, as the real API would.
_FAKE_TRACKER = r"""
const given = process.argv.slice(2);
const command = given[given.indexOf("tracker.api") + 1];
const say = (o) => process.stdout.write(JSON.stringify(o) + "\n");
const line = (fields) => say({ progress: { v: 1, pass: 4242, at: "2026-01-02T03:04:05", ...fields } });
if (command === "list") {
  say({ vocab: { commands: ["list", "scan", "state", "templates", "priors"],
                 engagement_flag: "--engagement",
                 shell: { error_log: process.env.FAKE_LOG } } });
} else if (command === "scan") {
  line({ event: "started", limit_seconds: 7200, households: 1 });
  line({ event: "household", household: "Sample Household", n: 1, of: 1 });
  line({ event: "file", step: "sort", name: "W-2 Sample.pdf", household: "Sample Household" });
  say({ run: { filed: 1 }, warnings: [] });
} else if (command === "state") {
  line({ event: "started", limit_seconds: 1, households: 1 });
  line({ event: "household", household: "Sample Household", n: 1, of: 1 });
  line({ event: "file", step: "scan", name: "A01", household: "Sample Household" });
  setTimeout(() => {}, 60000);
} else if (command === "templates") {
  process.stderr.write("Traceback: a fabricated message naming Sample Client's folder\n");
  process.exit(1);
}
"""


def _run_the_shell(tmp_path, calls, **env):
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it)")
    harness = tmp_path / "shell_harness.js"
    harness.write_text(_SHELL_HARNESS, encoding="utf-8", newline="\n")
    fake = tmp_path / "fake_tracker.js"
    fake.write_text(_FAKE_TRACKER, encoding="utf-8", newline="\n")
    done = subprocess.run([node, str(harness), str(REPO / "app" / "main.js"), str(fake),
                           json.dumps(calls)],
                          capture_output=True, text=True, encoding="utf-8", timeout=120, check=False,
                          env=child_env(**{"FAKE_LOG": str(tmp_path / "tracker-errors.log"), **env}))
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_shell_passes_progress_lines_on_and_keeps_the_last_line_as_the_reply(tmp_path):
    ran = _run_the_shell(tmp_path, [["list"], ["scan", "--engagement", "/sample/return"]])
    scan = ran["out"][1]
    assert scan["reply"] == {"run": {"filed": 1}, "warnings": []}
    progress = [m["message"] for m in ran["sent"] if m["channel"] == "tracker-progress"]
    assert [m["progress"]["event"] for m in progress] == ["started", "household", "file"]
    assert all(m["args"] == ["scan", "--engagement", "/sample/return"] for m in progress)


def test_the_shells_kill_follows_the_limit_the_pass_reported_and_says_where_it_was(tmp_path):
    import tracker.api as api

    ran = _run_the_shell(tmp_path, [["list"], ["state", "--engagement", "/sample/return"]])
    killed = ran["out"][1]
    assert killed["ms"] < 20_000, "the kill follows limit_seconds, not the thirty minutes"
    reply = killed["reply"]
    assert reply["killed"] is True and reply["failure"]["kind"] == "failed"
    assert reply["error"] == reply["failure"]["sentence"]
    assert reply["error"] == (api.SHELL_KILLED.format(minutes=1) + " "
                              + api.SHELL_KILLED_AT.format(household="Sample Household", name="A01"))
    assert reply["progress"]["name"] == "A01"


def test_the_shell_never_puts_stderr_on_screen_and_appends_it_to_the_error_log(tmp_path):
    import tracker.api as api

    ran = _run_the_shell(tmp_path, [["list"], ["templates"]])
    reply = ran["out"][1]["reply"]
    assert reply["error"] == api.SHELL_NO_REPLY.format(code=1)
    assert reply["failure"]["kind"] == "failed" and "fabricated" not in json.dumps(reply)
    logged = (tmp_path / "tracker-errors.log").read_text(encoding="utf-8")
    assert "a fabricated message naming Sample Client's folder" in logged


def test_with_no_error_log_the_shell_says_stderr_in_the_reply_and_writes_no_file(tmp_path):
    """The rebase review of 186 (MF2): with no data home the API names no
    error log, and the shell never builds one beside the program or in the
    settings folder - a failed command's stderr is said in its own reply,
    and no file is written anywhere."""
    import tracker.api as api
    from tracker.settings import ERROR_LOG_FILENAME

    ran = _run_the_shell(tmp_path, [["list"], ["templates"]], FAKE_LOG="")
    reply = ran["out"][1]["reply"]
    stderr = "Traceback: a fabricated message naming Sample Client's folder\n"
    sentence = api.SHELL_NO_REPLY.format(code=1) + "\n\n" + api.SHELL_NO_LOG.format(stderr=stderr)
    assert reply["error"] == sentence and reply["failure"]["sentence"] == sentence
    assert reply["failure"]["kind"] == "failed"
    assert not (REPO / ERROR_LOG_FILENAME).exists()
    assert not list(tmp_path.rglob(ERROR_LOG_FILENAME))


def test_a_failed_spawn_is_said_by_its_code(tmp_path):
    import tracker.api as api

    ran = _run_the_shell(tmp_path, [["list"]], FAKE_SPAWN_FAILS="1")
    reply = ran["out"][0]["reply"]
    assert reply["error"] == api.SHELL_COULD_NOT_START.format(code="ENOENT")
    assert "/no/such" not in reply["error"] and reply["failure"]["kind"] == "failed"


def test_the_progress_key_is_typed_once_per_language_and_the_error_log_only_by_the_api():
    from tracker.progress import PROGRESS_KEY
    from tracker.settings import ERROR_LOG_FILENAME

    main_js = read("app/main.js")
    assert f'const PROGRESS_KEY = "{PROGRESS_KEY}";' in main_js
    assert main_js.count(f'"{PROGRESS_KEY}"') == 1
    # The log's path is the API's, and the shell never builds one of its own
    # (the rebase review of 186, MF2): its name is not in the shell at all.
    assert ERROR_LOG_FILENAME not in main_js
    assert "vocab.shell" in main_js and "said.error_log" in main_js


def test_the_shells_default_words_are_the_apis_word_for_word():
    import tracker.api as api

    main_js = read("app/main.js")

    def default(name):
        head = main_js.split(f"let {name} =", 1)[1].split(";\n", 1)[0]
        return "".join(re.findall(r'"([^"]*)"', head))

    assert default("killed") == api.SHELL_KILLED
    assert default("killedAt") == api.SHELL_KILLED_AT
    assert default("noReply") == api.SHELL_NO_REPLY
    assert default("couldNotStart") == api.SHELL_COULD_NOT_START
    assert default("couldNotSend") == api.SHELL_COULD_NOT_SEND
    assert default("noLog") == api.SHELL_NO_LOG
    shell = api._vocab()["shell"]
    assert (shell["killed"], shell["killed_at"], shell["no_reply"], shell["could_not_start"]) == (
        api.SHELL_KILLED, api.SHELL_KILLED_AT, api.SHELL_NO_REPLY, api.SHELL_COULD_NOT_START)


def test_the_notice_buttons_are_the_apis_labels_word_for_word():
    import tracker.api as api

    html = read("app/renderer/index.html")
    template = html.split('<template id="notice-buttons">', 1)[1].split("</template>", 1)[0]
    buttons = dict(re.findall(r'data-act="([a-z]+)">([^<]+)</button>', template))
    assert buttons == api.NOTICE_LABELS
    assert api._vocab()["notices"]["labels"] == api.NOTICE_LABELS


def test_no_failure_is_toasted():
    js = read("app/renderer/app.js")
    assert "toast(err" not in js
    assert "throw new Error(result.error)" not in js


def test_every_draw_after_an_await_goes_through_renderFor():
    js = read("app/renderer/app.js")
    calls = [m.start() for m in re.finditer(r"(?<![\w.])render\(", js)]
    body = js.split("function renderFor(view, state) {", 1)[1].split("\n}\n", 1)[0]
    definition = js.index("function render(state)")
    inside = js.index("function renderFor(view, state) {")
    assert [at for at in calls if at != definition + len("function ")] == \
        [inside + len("function renderFor(view, state) {") + body.index("render(")]
    assert "view !== viewGeneration" in body
    # The shown return changes in one place, and every change bumps the view.
    assert len(re.findall(r"(?<![\w.])(?<!let )(?<!const )active = ", js)) == 1
    # Since decision 194 a switch is showReturn, which selects before it asks.
    assert "showReturn(button.dataset.path)" in js and "showReturn(e.target.value)" in js
    show = js.split("async function showReturn(path) {", 1)[1].split("\n}\n", 1)[0]
    assert show.index("const view = select(path)") < show.index("call(")


def test_the_reminder_card_is_never_hidden_on_an_error():
    js = read("app/renderer/app.js")
    body = js.split("async function loadReminder() {", 1)[1].split("\n}\n", 1)[0]
    caught = body.split("} catch (err) {", 1)[1]
    assert '"hidden"' not in caught
    assert "vocab.reminder.unreadable" in caught and "failed(err" in caught
    # One card from either source (decision 194): the not-yet line and the
    # sentence saying why a card could not be composed are drawn on it.
    assert "drawReminderReply(result)" in body
    drawn = js.split("function drawReminderReply(reply) {", 1)[1].split("\n}\n", 1)[0]
    assert "reply.not_yet" in drawn and "reply.unreadable" in drawn and '"hidden"' not in drawn


def test_every_reply_warning_becomes_a_notice():
    js = read("app/renderer/app.js")
    body = js.split("async function call(args, payload, { ofAnother = false } = {}) {", 1)[1].split("\n}\n", 1)[0]
    assert "result.warnings" in body and "warningNotices(" in body
    assert "throw new TrackerError(" in body
    assert "warningNotices(result.pass_warnings" in js


def test_a_failed_first_list_is_a_notice_with_retry_needing_no_vocabulary():
    js = read("app/renderer/app.js")
    start = js.split("async function bootstrap(preferPath) {", 1)[1].split("\n}\n", 1)[0]
    assert "failed(err, () => bootstrap(preferPath))" in start
    # The notice draws its buttons from the static template and reads the
    # vocabulary only for a repeat count, and only when there is one.
    draw = js.split("function drawNotice(entry) {", 1)[1].split("\n}\n", 1)[0]
    assert "entry.count > 1 && vocab" in draw and "noticeButton" in draw
    button = js.split("function noticeButton(act) {", 1)[1].split("\n}\n", 1)[0]
    assert '$("notice-buttons").content' in button and "vocab" not in button


def test_the_lock_notice_types_no_sentence_and_polls_only_while_a_lock_shows():
    js = read("app/renderer/app.js")
    for name in ("function renderLock(state) {", "function showLock(lock) {"):
        body = js.split(name, 1)[1].split("\n}\n", 1)[0]
        literals = re.findall(r'"([^"]*)"|`([^`]*)`', body)
        assert not [lit for pair in literals for lit in pair if " " in lit.strip()], name
    assert "Sort & Scan will wait" not in js and "will wait for it" not in js
    assert js.count('call(["watch"') == 1 and 'withEng("watch")' not in js
    watch = js.split("function watchLock(lock) {", 1)[1].split("\n}\n", 1)[0]
    assert 'call(["watch", vocab.engagement_flag, target])' in watch
    assert "vocab.lock.watch_seconds" in watch and "view !== viewGeneration" in watch
    # It watches the lock it was given (the review's S1), not the shown return.
    assert "const target = lock.engagement || active;" in watch
    show = js.split("function showLock(lock) {", 1)[1].split("\n}\n", 1)[0]
    assert "watchLock(lock)" in show and "stopLockWatch()" in show
    assert "words.running_other" in show


def test_the_shell_sends_on_only_the_channels_the_preload_listens_to():
    sent = set(re.findall(r'event\.sender\.send\("([a-z-]+)"', read("app/main.js")))
    heard = set(re.findall(r'ipcRenderer\.on\("([a-z-]+)"', read("app/preload.js")))
    assert sent == heard == {"tracker-progress"}


# ------------------------------------------ decision 193: the review's fixes ----

#: The renderer's lock functions, lifted out of app.js as they are and driven
#: with fake timers and a fake API (the review's M1 probe, kept as a claim).
_LOCK_HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(sig) { const i = src.indexOf(sig); const j = src.indexOf("\n}\n", i); return src.slice(i, j + 3); }
const parts = ["function select(path) {", "function lockStarted(lock) {", "function showLock(lock) {",
  "function applyLock() {", "function setLocked(on) {", "function stopLockWatch() {",
  "function watchLock(lock) {"].map(grab);
const intervals = []; const held = { A: true, B: true }; const asked = [];
const node = () => ({ classList: { toggle() {}, add() {}, remove() {} }, textContent: "",
                      querySelectorAll: () => [], dataset: {} });
const nodes = {};
const body = `
let active = "A"; let viewGeneration = 0; let locked = false; let lockWatch = null; let lockWatched = null;
const vocab = { engagement_flag: "--engagement",
  lock: { running: "r", running_other: "o", on: "o", greyed: "g", left_behind: "l", watch_seconds: 5,
          buttons_back: "back" } };
const LOCKED_BUTTONS = []; const LOCKED_CARDS = [];
const $ = (id) => (nodes[id] ||= node());
const fill = (p) => p;
async function call(args) { asked.push(args[2]); return { lock: held[args[2]] ? lockOf(args[2]) : null }; }
const lockOf = (path) => ({ started: "", host: "h", stale: false, engagement: path, label: path });
function notice() {}
function refresh() {}
function failed() {}
const setInterval = (fn) => { intervals.push(fn); return intervals.length; };
const clearInterval = (id) => { if (id) intervals[id - 1] = null; };
${parts.join("\n")}
return { select, showLock, lockOf, get locked() { return locked; }, get watching() { return lockWatched; } };`;
const api = new Function("nodes", "node", "intervals", "held", "asked", body)(nodes, node, intervals, held, asked);
(async () => {
  const tick = async () => { for (const fn of intervals.slice()) if (fn) await fn(); };
  api.showLock(api.lockOf("A"));
  await tick();
  api.select("B");
  api.showLock(api.lockOf("B"));
  await tick();
  held.B = false;
  await tick();
  const afterB = { locked: api.locked, watching: api.watching };
  api.showLock(api.lockOf("C"));     // a sibling's lock reported while B is shown
  held.C = true;
  await tick();
  process.stdout.write(JSON.stringify({ asked, afterB, sibling: api.watching }));
})();
"""


def test_a_switch_between_two_locked_returns_watches_the_second_and_gives_its_buttons_back(tmp_path):
    """The review's M1: the watch of the return left behind used to keep the
    second from starting its own, and then stopped itself - the second
    return stayed greyed after its pass let go. And S1: the watch asks
    about the folder the lock was reported in, not the shown return."""
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it)")
    harness = tmp_path / "lock_harness.js"
    harness.write_text(_LOCK_HARNESS, encoding="utf-8", newline="\n")
    done = subprocess.run([node, str(harness), str(REPO / "app" / "renderer" / "app.js")],
                          capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    ran = json.loads(done.stdout)
    assert ran["asked"][:3] == ["A", "B", "B"], ran
    assert ran["afterB"] == {"locked": False, "watching": None}, "B's buttons back, its watch done"
    assert ran["sibling"] == "C" and ran["asked"][-1] == "C", "the lock it was given is watched"


def test_the_editors_failures_are_notices_too():
    """Every editor catch says one sentence, in the editor and as a notice:
    ``failed``'s, never an error's own text (principle 7; the restack
    review's M1)."""
    js = read("app/renderer/app.js")
    for name in ("async function saveEditor() {", "async function renameRequest() {",
                 "async function unlearnKeyword(identifier, keyword) {"):
        body = js.split(name, 1)[1].split("\n}\n", 1)[0]
        assert 'editorNote(failed(err), "err");' in body, name
        assert "err.message" not in body, name


def test_an_errors_own_message_is_read_only_where_failureSentence_logs_it():
    """UX principle 7, by shape: the one place app.js reads a caught error's
    message is ``failureSentence``, which sends it to the error log."""
    js = read("app/renderer/app.js")
    inside = _js_function(js, "function failureSentence(err) {")
    outside = js.replace(inside, "")
    assert inside.count(".message") == 1 and "window.tracker.logError(" in inside
    assert re.search(r"\.message\b", outside) is None


def test_every_word_a_scan_reply_is_said_in_is_the_apis():
    import tracker.api as api

    js = read("app/renderer/app.js")
    body = js.split("function scanSummary(result) {", 1)[1].split("\n}\n", 1)[0]
    words = api._vocab()["scan"]
    for key, literal in words.items():
        assert f"words.{key}" in body or f"vocab.scan.{key}" in js, key
        stem = literal.split("{")[0].strip()
        assert " " not in stem or stem not in js, literal
    assert "Scanning" not in js and "Pass complete" not in js and "Nothing done" not in js


def test_an_error_of_the_page_or_the_shell_is_said_by_class_and_its_message_only_logged():
    import tracker.api as api

    js = read("app/renderer/app.js")
    body = js.split("function failureSentence(err) {", 1)[1].split("\n}\n", 1)[0]
    assert "vocab.shell.page_error" in body and "window.tracker.logError(" in body
    assert "sentence: String(" not in body
    failing = js.split("function failed(err, retry) {", 1)[1].split("\n}\n", 1)[0]
    assert "const sentence = failureSentence(err);" in failing and "err.message" not in failing
    main_js = read("app/main.js")
    run = main_js[main_js.index("function runTracker"):]
    run = run[:run.index("\n}\n")]
    assert "shellFailure(fill(couldNotSend" in run and "`The app could not send" not in run
    assert "err.message" not in run.split("keepInLog(", 1)[0]
    assert 'ipcMain.handle("log-error"' in main_js
    assert api._vocab()["shell"]["page_error"] == api.PAGE_ERROR


# ============= one spawn per click (decision 194) ===========================


def _body(js: str, head: str) -> str:
    return js.split(head, 1)[1].split("\n}\n", 1)[0]


def _handler(js: str, head: str) -> str:
    return js.split(head, 1)[1].split("\n});\n", 1)[0]


def test_switching_returns_is_one_state_call():
    """A switch is one process: ``showReturn`` asks ``state`` and nothing
    else, the three places a person switches and a refusal all go through
    it, and the list is read once, at start-up (and again only after the
    clients folder is set, R8)."""
    js = read("app/renderer/app.js")
    show = _body(js, "async function showReturn(path) {")
    assert show.count("call(") == 1 and 'call(["state", ' in show
    for head in ('$("household-returns").addEventListener("click", (e) => {',
                 '$("eng-select").addEventListener("change", (e) => {',
                 '$("household-roll").addEventListener("click", async (e) => {'):
        handler = _handler(js, head)
        if "reviewPeople(" in handler:       # the roll fold's people button (S4)
            handler += _body(js, "async function reviewPeople(path) {")
        assert "showReturn(" in handler, head
        for other in ("refresh(", "bootstrap(", "loadReminder(", "call("):
            assert other not in handler, (head, other)
    refused = _body(js, "async function refused(err, btn) {")
    assert "showReturn(active)" in refused and "bootstrap(" not in refused
    assert "refresh(" not in js
    assert js.count('call(["list"])') == 1
    assert 'call(["list"])' in _body(js, "async function loadEngagements(preferPath, asked) {")
    calls = [m.start() for m in re.finditer(r"(?<![\w.])bootstrap\(", js)]
    assert len(calls) == 4        # its definition, its own Retry, saveRoot and start-up
    assert "await bootstrap();" in _body(js, "async function saveRoot() {")
    assert js.rstrip().endswith("bootstrap();")


def test_the_reminder_card_is_drawn_from_state():
    """The card arrives with the state (decision 194): ``renderReminder``
    draws ``state.reminder_card``, and the ``reminder`` command is called
    from one place, reached only from the stage toggle, a refused approve
    and the one branch that keeps a rung a person moved (R3)."""
    js = read("app/renderer/app.js")
    card = _body(js, "function renderReminder(state) {")
    assert "drawReminderReply(state.reminder_card" in card
    assert "reminderStage !== null" in card and "loadReminder()" in card
    assert js.count('withEng("reminder")') == 1
    assert 'withEng("reminder")' in _body(js, "async function loadReminder() {")
    heads = ("function renderReminder(state) {", "async function approveReminder() {",
             '$("reminder-stages").addEventListener("click"')
    callers = [m.start() for m in re.finditer(r"(?<![\w.])(?<!function )loadReminder\(", js)]
    places = sorted(max((js[:at].rfind(head), head) for head in heads)[1] for at in callers)
    assert places == sorted(heads)


def test_the_editor_opens_on_the_state_on_screen():
    """D13: the editor opens on the state already drawn for this return,
    with no refetch; a save is still judged by the list's head (160)."""
    js = read("app/renderer/app.js")
    body = _body(js, "async function openEditor() {")
    assert "lastState.paths.engagement === active" in body
    assert body.index("lastState") < body.index("call(")
    assert "head: editorState.list_head" in _body(js, "async function saveEditor() {")


def test_every_editor_write_whose_reply_carries_state_redraws_through_renderFor():
    """The editor opens on the state on screen (D13), so each editor write
    that answers with a state redraws the page from it - an unlearned
    keyword never comes back on the next open (the review's S2)."""
    js = read("app/renderer/app.js")
    for head in ("async function unlearnKeyword(identifier, keyword) {",
                 "async function renameRequest() {", "async function saveEditor() {"):
        body = _body(js, head)
        assert "const view = viewGeneration;" in body and "renderFor(view, result.state)" in body, head


def test_a_warning_about_another_return_is_said_under_its_label():
    """The hand-over picker reads another return's state; what that reply
    warns is about that return, so it is said under its label in the API's
    format and never as if about the return shown (the review's S1)."""
    import tracker.api as api

    js = read("app/renderer/app.js")
    handover = _body(js, "async function loadHandOverRequests() {")
    assert "{ ofAnother: true }" in handover
    head = "async function call(args, payload, { ofAnother = false } = {}) {"
    body = _body(js, head)
    assert "vocab.notices.about" in body and "labelOfState(result)" in body
    assert js.count("ofAnother: true") == 1
    assert api._vocab()["notices"]["about"] == api.NOTICE_ABOUT
    assert set(re.findall(r"{(\w+)}", api.NOTICE_ABOUT)) == {"label", "sentence"}


# ------------------------------- statuses in a preparer's words (d200) ----


def _typed(word: str, text: str) -> bool:
    """Is ``word`` written into ``text`` as a word of its own - quoted, or
    as an element's whole text - rather than said in a comment's prose?"""
    return any(form in text for form in (f'"{word}"', f"'{word}'", f"`{word}`", f">{word}<"))


def test_the_renderer_types_no_status_label():
    """Decision 200: every label and sentence the app shows for a row's
    status, every side and the Set aside headings reach the page through
    the API's vocabulary, and the renderer and the page type none."""
    from tracker import reminder, view
    from tracker.manifest import STATUS_LABELS

    js = read("app/renderer/app.js")
    # A column heading is not a status: the Received column holds a date.
    html = re.sub(r"<th[^>]*>[^<]*</th>", "", read("app/renderer/index.html"))
    for text in (js, html):
        for shown in STATUS_LABELS.values():
            assert not _typed(shown.label, text), shown.label
            assert shown.sentence not in text, shown.sentence
        for side in reminder.SIDES:
            assert not _typed(side.label, text), side.label
            assert side.sentence not in text, side.sentence
        assert view.SET_ASIDE_SECTION.split("{")[0].strip() not in text
        assert view.SET_ASIDE_GROUP not in text
    assert "vocab.labels" in js and "vocab.reminder.sides" in js
    assert "vocab.set_aside.heading" in js and "vocab.set_aside.group" in js


def test_the_renderer_types_no_override_word():
    """The row's override is its label on the side line (decision 200), not
    a typed "override:" after the Period. A key such as ``manual_override:``
    is the record's field name, not a word shown."""
    assert re.search(r"(?<!\w)override:", read("app/renderer/app.js"), re.IGNORECASE) is None


# A document just large enough for app.js's own el(): elements keep their
# children in order, and a child that is not an element becomes text, as a
# browser's append() makes it. Each drawn tree comes back as JSON.
_DOM_SHIM = """
class Node {}
class Text extends Node { constructor(data) { super(); this.data = data; } }
class Element extends Node {
  constructor(tag) { super(); this.tag = tag; this.className = ""; this.dataset = {};
                     this.attributes = {}; this.childNodes = []; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  append(...nodes) { for (const n of nodes) this.childNodes.push(n instanceof Node ? n : new Text(String(n))); }
  replaceChildren(...nodes) { this.childNodes = []; this.append(...nodes); }
  addEventListener() {}
}
const document = { createElement: (tag) => new Element(tag), activeElement: null };
const tree = (n) => n instanceof Text ? n.data
  : { tag: n.tag, className: n.className, attributes: n.attributes, children: n.childNodes.map(tree) };
"""


def _run_renderer(tmp_path, name: str, headers: tuple[str, ...], script: str):
    """Run ``script`` under node with app.js's own ``el()`` (and its
    attribute list) and the named
    functions exactly as written, against :data:`_DOM_SHIM`; what the
    script writes to stdout comes back parsed. Skipped where node is not
    on PATH (CI installs it)."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it)")
    js = read("app/renderer/app.js")
    start = js.index("const EL_ATTRIBUTES = new Set([")
    allowed = js[start:js.index("]);", start) + 3]
    bodies = "\n".join([allowed] + [_js_function(js, header) for header in (
        "function el(tag, attrs = {}, ...children) {", *headers)])
    path = tmp_path / f"{name}.js"
    path.write_text(f"{_DOM_SHIM}\n{bodies}\n{script}\n", encoding="utf-8", newline="\n")
    done = subprocess.run([node, str(path)], capture_output=True, text=True, encoding="utf-8",
                          timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _texts(node) -> list[str]:
    """Every text in a drawn tree, in order."""
    if isinstance(node, str):
        return [node]
    return [text for child in node["children"] for text in _texts(child)]


def test_the_editor_set_aside_fold_draws_each_group_as_elements(tmp_path):
    """The editor's Set aside fold, drawn by ``renderEditorRows`` as
    written through the real ``el()``, holds each group's heading and its
    rows' box as elements - never the text "[object ...]" that an array of
    [heading, box] pairs handed to ``el()`` unflattened becomes, which left
    every set-aside row out of the editor."""
    drawn = _run_renderer(tmp_path, "editor_fold", (
        "function renderEditorRows() {", "function setAsideHeading(group) {",
        "function fill(pattern, values) {"), """
const NOT_ASKED_GROUP = "not asked";
const vocab = { columns: [], set_aside: { heading: "Set aside ({n})", group: "{label} ({n})" },
                editor: { plain_columns: [], routing_columns: [], routing_all: "", routing_help: "" } };
const editorState = { learned: {} };
const editorFolds = new Map();
const editorRowIsCustom = () => false;
const editorRowFoldOpen = () => false;
const showEveryFold = () => {};
const editorRows = [
  { identifier: "A01", group: "" },
  { identifier: "B01", group: NOT_ASKED_GROUP },
  { identifier: "C01", group: "Not Applicable in TY2025" },
];
const editorGroupKey = (row) => row.group;
const editorRowYear = () => 2025;
const unlearnKeyword = () => {};
function requestRows(box, rows) { for (const row of rows) box.append(el("div", { className: "row" }, row.identifier)); }
function setAsideGroups(rows) {
  return rows.map((row) => ({ label: row.group, sentence: "A fabricated sentence.", rows: [row] }));
}
const page = { "ed-rows": document.createElement("div") };
const $ = (id) => page[id];
renderEditorRows();
process.stdout.write(JSON.stringify(tree(page["ed-rows"])));
""")
    above, active, fold = drawn["children"]
    assert above["className"] == "editor-actions"   # the routing toggle (decision 201)
    assert fold["tag"] == "details" and fold["className"] == "ed-set-aside"
    assert [child["tag"] if isinstance(child, dict) else child for child in fold["children"]] == [
        "summary", "div", "div", "div", "div"]
    assert not any("[object" in text for text in _texts(drawn))
    assert [box["children"][0]["children"] for box in fold["children"][2::2]] == [["B01"], ["C01"]]
    assert _texts(active) == ["A01"]


def _class_names(node) -> list[str]:
    """Every ``className`` in a drawn tree, in order."""
    if isinstance(node, str):
        return []
    return [node["className"]] + [name for child in node["children"] for name in _class_names(child)]


def test_the_plain_view_draws_one_box_per_column_and_a_custom_rows_document_in_the_plain_part(
        tmp_path):
    """Decision 201: ``requestRows`` with the fold, run as written, draws
    one box for every column of every row across the plain part and the
    fold - none twice, none lost - and a custom row's Document with the
    plain boxes, because nothing else names it; a catalog row's Document
    is in the fold."""
    drawn = _run_renderer(tmp_path, "plain_view", (
        "function requestRows(container, rows, { columns, onChange, onRemove, onTakeBack, "
        "learned = {}, keyed = true, fold = null }) {",), """
const vocab = { editor: { routing: "Routing", routing_help: "How it is recognised.", remove_row: "Remove" },
                triage: { identifier_separator: " - " } };
const keys = ["identifier", "document", "required_keywords", "expected_count", "asked"];
const columns = keys.map((key) => ({ key, label: key, help: "" }));
const drawnBoxes = [];
function cellInput(row, column) {
  drawnBoxes.push([row.identifier, column.key]);
  return el("span", { className: `cell-${column.key}` });
}
const rows = [{ identifier: "A01", document: "W-2", custom: false },
              { identifier: "X01", document: "Letter from the county", custom: true }];
const box = document.createElement("div");
requestRows(box, rows, { columns, onChange: () => {}, onRemove: () => {}, keyed: false, fold: {
  plain: ["expected_count", "asked"], routing: ["identifier", "document", "required_keywords"],
  custom: (row) => row.custom, isOpen: () => false, setOpen: () => {} } });
process.stdout.write(JSON.stringify({ boxes: drawnBoxes, tree: tree(box) }));
""")
    keys = ["identifier", "document", "required_keywords", "expected_count", "asked"]
    assert sorted(map(tuple, drawn["boxes"])) == sorted((row, key) for row in ("A01", "X01") for key in keys)
    [table] = drawn["tree"]["children"]
    catalog_plain, catalog_fold, custom_plain, custom_fold = table["children"][1]["children"]
    cells = {name: [c[len("cell-"):] for c in _class_names(part) if c.startswith("cell-")]
             for name, part in (("catalog_plain", catalog_plain), ("catalog_fold", catalog_fold),
                                ("custom_plain", custom_plain), ("custom_fold", custom_fold))}
    assert cells == {"catalog_plain": ["expected_count", "asked"],
                     "catalog_fold": ["identifier", "document", "required_keywords"],
                     "custom_plain": ["document", "expected_count", "asked"],
                     "custom_fold": ["identifier", "required_keywords"]}


def test_a_notice_for_a_numeric_identifier_outlines_that_request_and_no_editor_row(tmp_path):
    """Since decision 193 ``data-row`` is the row a notice names, so
    ``requestRows`` keeps each row's index in ``data-index`` instead: a
    notice for request "2", run through ``outlineRefused`` as written,
    outlines the request table's row "2" and never the editor's or the
    wizard's third row (the restack review's S1)."""
    js = read("app/renderer/app.js")
    drawing = _js_function(js, "function requestRows(container, rows, { columns, onChange, onRemove, "
                               "onTakeBack, learned = {}, keyed = true, fold = null }) {")
    assert "row:" not in drawing and "dataset.row" not in drawing
    seen = _run_renderer(tmp_path, "outline_numeric", (
        "function requestRows(container, rows, { columns, onChange, onRemove, onTakeBack, "
        "learned = {}, keyed = true, fold = null }) {", "function outlineRefused() {"), """
Object.defineProperty(Element.prototype, "classList", { get() {
  const node = this;
  return { toggle(name, on) {
    const names = new Set(node.className.split(" ").filter(Boolean));
    if (on) names.add(name); else names.delete(name);
    node.className = [...names].join(" ");
  } };
} });
const vocab = { editor: { routing: "Routing", routing_help: "", remove_row: "Remove" },
                triage: { identifier_separator: " - " } };
const columns = ["identifier", "document", "expected_count"].map((key) => ({ key, label: key, help: "" }));
const cellInput = () => el("span", {});
const columnsByKey = (keys) => columns.filter((c) => keys.includes(c.key));
const rows = [{ identifier: "A01", document: "W-2" }, { identifier: "B01", document: "1099-INT" },
              { identifier: "C01", document: "1098" }];
const table = el("tr", { dataset: { row: "2" } });
const editor = document.createElement("div");
requestRows(editor, rows, { columns, onChange: () => {}, onRemove: () => {}, fold: {
  plain: ["expected_count"], routing: ["identifier", "document"], custom: () => false,
  isOpen: () => false, setOpen: () => {} } });
const wizard = document.createElement("div");
requestRows(wizard, rows, { columns, onChange: () => {}, onRemove: () => {}, keyed: false });
const all = [];
const walk = (n) => { if (n instanceof Element) { all.push(n); n.childNodes.forEach(walk); } };
[table, editor, wizard].forEach(walk);
document.querySelectorAll = (selector) => all.filter((n) => selector === "[data-row]" && "row" in n.dataset);
const notices = [{ identifier: "2" }];
outlineRefused();
const outlined = (root) => { const found = []; const look = (n) => { if (n instanceof Element) {
  if (n.className.split(" ").includes("refused")) found.push(n.dataset.index ?? n.dataset.row);
  n.childNodes.forEach(look); } }; look(root); return found; };
process.stdout.write(JSON.stringify({ table: outlined(table), editor: outlined(editor),
                                      wizard: outlined(wizard),
                                      indexed: all.filter((n) => n.tag === "tr" && "index" in n.dataset).length }));
""")
    assert seen == {"table": ["2"], "editor": [], "wizard": [], "indexed": 9}


# The dialogs' guard as written: the registry, the snapshot, the dirty test
# and requestClose, against a page of plain stand-ins.
_DIALOG_GUARD = ("const DIALOGS = {", "function snapshotOf(id) {", "function isDirty(id) {",
                 "function rebaseline(id, keys) {", "function unsavedBar(id) {",
                 "function requestClose(id) {")
_DIALOG_PAGE = """
const vocab = { dialogs: { unsaved: "Unsaved.", keep_editing: "Keep", discard: "Discard" } };
const classes = (...names) => { const on = new Set(names);
  return { contains: (c) => on.has(c), add: (c) => on.add(c), remove: (c) => on.delete(c),
           toggle: (c, force) => { if (force ?? !on.has(c)) on.add(c); else on.delete(c); } }; };
const bar = { classList: classes("hidden"), parts: {},
              querySelector(sel) { return this.parts[sel] ||= { textContent: "", focus() {} }; } };
const page = new Map();
const $ = (id) => {
  if (!page.has(id)) page.set(id, { value: "", textContent: "", classList: classes(), focus() {},
                                    querySelector: () => bar, querySelectorAll: () => [] });
  return page.get(id);
};
const dialogSnapshot = {};
const dialogKept = {};
const closed = [];
const closeDialog = (id) => closed.push(id);
const keepEditing = () => {};
let editorRows = [];
let details = {};
const engagementFromFields = () => details;
let editorFeeds = [];
let handingOver = null;
const closeNewReturn = () => {};
"""


def _dialog_guard(tmp_path, name: str, headers: tuple[str, ...], script: str):
    return _run_renderer(tmp_path, name, (*_DIALOG_GUARD, *headers), _DIALOG_PAGE + script)


def test_closing_the_editor_closes_it_clean_and_raises_the_bar_on_a_changed_row_or_detail(tmp_path):
    """F-T-7, run as written: ``requestClose`` on an editor nothing moved in
    closes it; one whose rows moved, or whose details alone moved, shows
    the unsaved bar and stays open."""
    seen = _dialog_guard(tmp_path, "dialog_close", (), """
const wizardModel = () => null;
const outcome = () => ({ closed: closed.splice(0), bar: !bar.classList.contains("hidden") });
const results = {};
editorRows = [{ identifier: "A01", document: "W-2" }]; details = { client: "Pat" };
dialogSnapshot.editor = snapshotOf("editor");
requestClose("editor"); results.clean = outcome();
editorRows[0].document = "W-2s"; requestClose("editor"); results.row = outcome();
bar.classList.add("hidden"); editorRows[0].document = "W-2"; details.client = "Pat Lee";
requestClose("editor"); results.detail = outcome();
process.stdout.write(JSON.stringify(results));
""")
    assert seen["clean"] == {"closed": ["editor"], "bar": False}
    assert seen["row"] == {"closed": [], "bar": True}
    assert seen["detail"] == {"closed": [], "bar": True}


def test_picking_a_form_is_not_unsaved_work_but_typing_after_it_is(tmp_path):
    """Decision 201: picking a form fills its defaults in, which is not the
    person's typing - ``chooseForm`` as written leaves New household clean;
    a box typed in afterwards makes it dirty."""
    seen = _dialog_guard(tmp_path, "choose_form", (
        "function chooseForm(formId) {", "function wizardModel() {", "function fill(pattern, values) {"), """
Object.assign(vocab, { household: { items_title: "{form} requests" }, ask_the_client: "Ask",
                       ask_the_client_note: "Note" });
const forms = [{ id: "1040", label: "1040", who: "Individuals" }];
const templatesByForm = { "1040": [{ identifier: "A01" }] };
let selectedForm = null, templates = [], customItems = [], nameIsAuto = false, wizardPeople = [];
const defaultYear = 2026, addingTo = null;
let ticks = [];
$("tmpl-list").querySelectorAll = () => ticks;
const householdContact = () => "Pat Lee";
const syncNameDefault = () => { $("ne-name").value = "1040 - Pat Lee"; };
const blankPerson = () => ({ kind: "taxpayer", name: "", own: false, proposed: [] });
const labelPeopleBlock = () => {}, renderPeople = () => {}, refreshProposals = () => {};
const renderTemplateList = () => { ticks = [{ checked: true }]; };
const renderCustomRows = () => {}, showStep = () => {};
dialogSnapshot.modal = snapshotOf("modal");
chooseForm("1040");
const picked = isDirty("modal");
$("ne-due").value = "2027-04-15";
process.stdout.write(JSON.stringify({ picked, typed: isDirty("modal") }));
""")
    assert seen == {"picked": False, "typed": True}


def test_a_refused_save_opens_every_fold_and_keeps_the_editor_open(tmp_path):
    """Decision 201, R5, run as written: a refusal names a row and a column,
    so ``saveEditor``'s refusal opens every fold, says the API's sentence
    in the editor and does not close it. Decision 193: the refusal arrives
    as the tracker's envelope and is also a notice, in the same sentence;
    an error of the page's own is said in both places by its class alone,
    its message only logged (principle 7)."""
    headers = ("async function saveEditor() {", "function failed(err, retry) {",
               "function failureSentence(err) {")
    harness = """
const page = { "ed-save": { disabled: false } };
const $ = (id) => page[id];
const withEng = (command) => [command];
const call = async () => { throw THROWN; };
const editorRows = [], editorState = { list_head: "h" };
const engagementFromFields = () => ({});
const viewGeneration = 0;
const vocab = { shell: { page_error: "Own error ({kind})." } };
const fill = (text, values) => text.replace("{kind}", values.kind);
const done = { folds: 0, notes: [], notices: [], logged: 0, closed: [] };
const window = { tracker: { logError: () => { done.logged += 1; } } };
const notice = (failure) => done.notices.push([failure.sentence, failure.kind]);
const showEveryFold = () => { done.folds += 1; };
const editorNote = (text, cls) => done.notes.push([text, cls]);
const closeDialog = (id) => done.closed.push(id);
const renderFor = () => { throw new Error("a refused save draws nothing"); };
const banner = () => {};
saveEditor().then(() => process.stdout.write(JSON.stringify(done)));
"""
    sentence = "Row A01: a fabricated refusal"
    refusal = (f"Object.assign(new Error({json.dumps(sentence)}), {{ failure: "
               f"{{ sentence: {json.dumps(sentence)}, kind: \"refused\", identifier: \"A01\" }} }})")
    seen = _run_renderer(tmp_path, "save_refused", headers, harness.replace("THROWN", refusal))
    assert seen == {"folds": 1, "notes": [[sentence, "err"]], "notices": [[sentence, "refused"]],
                    "logged": 0, "closed": []}
    own = _run_renderer(tmp_path, "save_own_error", headers,
                        harness.replace("THROWN", 'new TypeError("x is undefined at C:/private")'))
    assert own == {"folds": 1, "notes": [["Own error (TypeError).", "err"]],
                   "notices": [["Own error (TypeError).", "failed"]], "logged": 1, "closed": []}


def test_edit_request_list_says_so_when_the_state_is_still_another_returns(tmp_path):
    """The review's S4, on decision 194's model: when the state read for
    the editor is still another return's - a switch landed while it was
    read - Edit Request List puts the API's sentence in the banner and
    opens nothing - never a button that does nothing."""
    from tracker import api

    seen = _run_renderer(tmp_path, "open_editor", ("async function openEditor() {",), f"""
const vocab = {{ editor: {{ not_this_return: {json.dumps(api.EDITOR_NOT_THIS_RETURN)} }} }};
const active = "/root/J Park & Associates/Lee/2026/1040 - Pat Lee";
const other = {{ paths: {{ engagement: "/root/J Park & Associates/Lee/2026/1120S - Lee LLC" }} }};
let lastState = other, editorState = null;
const done = {{ called: [], banners: [], opened: [], failed: 0 }};
const withEng = (command) => [command, "--engagement", active];
const call = async (args) => {{ done.called.push(args[0]); return other; }};
const failed = () => {{ done.failed += 1; }};
const banner = (text, cls) => done.banners.push([text, cls]);
const openDialog = (id) => done.opened.push(id);
openEditor().then(() => process.stdout.write(JSON.stringify(done)));
""")
    assert seen == {"called": ["state"], "banners": [[api.EDITOR_NOT_THIS_RETURN, "err"]],
                    "opened": [], "failed": 0}


#: The roll fold's people button, run as written: the real ``showReturn``,
#: ``select`` and ``renderFor`` with the call, the draw and the editor faked.
_PEOPLE_HEADERS = ("function select(path) {", "function renderFor(view, state) {",
                   "async function showReturn(path) {", "async function reviewPeople(path) {")
_PEOPLE_HARNESS = """
const vocab = { engagement_flag: "--engagement" };
const clicked = "/root/J Park & Associates/Lee/2026/1040 - Pat Lee";
const other = "/root/J Park & Associates/Lee/2026/1120S - Lee LLC";
let active = other, viewGeneration = 0;
const done = { called: 0, failed: 0, opened: [] };
const stopLockWatch = () => {}, renderEngagements = () => {}, render = () => {};
const applyLock = () => {}, outlineRefused = () => {};
const failed = () => { done.failed += 1; };
const openEditor = () => { done.opened.push(active); };
const call = async (args) => { done.called += 1; READ };
reviewPeople(clicked).then(() => process.stdout.write(JSON.stringify(done)));
"""


def test_the_roll_folds_people_button_opens_the_editor_only_on_the_read_it_asked_for(tmp_path):
    """The rebase review's S4, decision 194 and 193's late-reply rule: the
    people button is one ``state`` call and the editor on it. A failed read
    is one notice and no second call; a switch during the read opens no
    editor, never another return's."""
    def run(name, read):
        return _run_renderer(tmp_path, name, _PEOPLE_HEADERS,
                             _PEOPLE_HARNESS.replace("READ", read))

    drawn = "return { paths: { engagement: args[2] } };"
    assert run("people_ok", drawn) == {"called": 1, "failed": 0, "opened": [
        "/root/J Park & Associates/Lee/2026/1040 - Pat Lee"]}
    assert run("people_failed", 'throw new Error("a fabricated failure");') == {
        "called": 1, "failed": 1, "opened": []}
    assert run("people_switched", f"select(other); {drawn}") == {
        "called": 1, "failed": 0, "opened": []}


def test_the_roll_banner_says_a_failed_retirement_and_turns_warn(tmp_path):
    """The rebase review's S5, decision 159: when every ticked return
    rolled and a retirement then failed, the API's own sentence is a line
    of the card's roll banner and the banner is a warning, not a success."""
    from tracker import api
    from tracker.rollover import ROLLOVER_NOT_RETIRED

    warning = ROLLOVER_NOT_RETIRED.format(year=2027, rolled="1040 - Pat Lee",
                                          retired="none", left="1120S - Lee LLC",
                                          why="a fabricated failure")
    words = api._vocab()
    seen = _run_renderer(tmp_path, "roll_banner", (
        "function fill(pattern, values) {", "async function rollFromCard() {"), f"""
const vocab = {json.dumps({key: words[key] for key in (
    "household", "people", "origin_not_applicable", "origin_new",
    "not_applicable_carried", "new_not_asked_carried")})};
const state = {{ paths: {{ engagement: "/root/J Park & Associates/Lee/2027/1040 - Pat Lee" }} }};
let lastState = {{ household: {{ path: "/root/J Park & Associates/Lee" }} }}, rollChoice = null;
const done = {{ banners: [], failed: 0 }};
const button = {{ disabled: false, open: true }};
const $ = () => button;
const gatherRollChoice = () => ({{}});
const rollHouseholdCall = () => [["roll-household"], {{}}];
const call = async () => ({{ target_year: 2027, state, rolled: [{{ label: "1040 - Pat Lee",
  carried: [], unfiled_last_year: [], warnings: [] }}], retired: [], skipped: [],
  warning: {json.dumps(warning)} }});
const adoptList = () => {{}}, renderFor = () => {{}}, renderEngagements = () => {{}};
const select = () => 1;
const failed = () => {{ done.failed += 1; }};
const banner = (text, cls) => done.banners.push([text, cls]);
rollFromCard().then(() => process.stdout.write(JSON.stringify(done)));
""")
    assert seen["failed"] == 0
    [(text, cls)] = seen["banners"]
    assert warning in text.split("\n") and cls == "warn"


def _side_lines(tmp_path, labels: dict, items: list[dict]) -> list:
    """``sideLine`` as written, for each of ``items``, with the tracker's
    own sides and the label table given."""
    from tracker import reminder

    sides = [{"key": side.key, "label": side.label} for side in reminder.SIDES]
    return _run_renderer(tmp_path, "side_line", (
        "function sideLine(item) {", "function isSetAside(override) {"), f"""
const vocab = {{ labels: {json.dumps(labels)}, reminder: {{ sides: {json.dumps(sides)} }},
                overrides: {{ not_applicable: "Not Applicable" }} }};
const items = {json.dumps(items)};
process.stdout.write(JSON.stringify(items.map((item) => {{ const line = sideLine(item); return line && tree(line); }})));
""")


def _titles(node) -> list[str]:
    """Every ``title`` - a tooltip - in a drawn tree."""
    if isinstance(node, str):
        return []
    own = [node["attributes"]["title"]] if "title" in node["attributes"] else []
    return own + [title for child in node["children"] for title in _titles(child)]


def test_the_side_sentence_is_text_beside_the_chip_and_never_a_tooltip(tmp_path):
    """Decision 200: whose move a row is, in bold, and the row's own
    sentence as a text child of the same line - on the page for a person
    to read, never moved into a ``title`` to hover for."""
    from tracker import reminder

    items = [{"identifier": side.key, "side": side.key, "manual_override": "",
              "side_sentence": f"{side.sentence} (fabricated row)"} for side in reminder.SIDES]
    lines = _side_lines(tmp_path, {}, items)
    for side, item, line in zip(reminder.SIDES, items, lines, strict=True):
        assert line["className"] == "req-side"
        bold, gap, sentence = line["children"]
        assert bold == {"tag": "span", "className": "side", "attributes": {}, "children": [side.label]}
        assert (gap, sentence) == (" ", item["side_sentence"])
        assert _titles(line) == []


def test_an_accepted_rows_side_word_is_the_label_tables_not_the_records(tmp_path):
    """An Accepted row has no side; its line says the label table's word
    for the override and that label's sentence. Relabelled in the table,
    the line follows the table, not the word the record keeps."""
    labels = {"Accepted": {"key": "Accepted", "label": "Signed off (fabricated)",
                           "sentence": "A fabricated sentence for the accepted row."}}
    [line] = _side_lines(tmp_path, labels, [{"identifier": "A01", "side": None, "side_sentence": "",
                                             "manual_override": "Accepted"}])
    bold, gap, sentence = line["children"]
    assert bold["children"] == ["Signed off (fabricated)"]
    assert (gap, sentence) == (" ", "A fabricated sentence for the accepted row.")
    assert "Accepted" not in _texts(line)


def test_the_runbook_status_table_is_the_label_table():
    """The runbook's two columns - what the record says, what the app shows
    - are the tracker's one table, row for row, in its order. Not
    Applicable's label is said with <year>, as the README spells it. The
    sides table beneath it is ``reminder.SIDES``, word and sentence, in
    triage's order, so neither can drift from what the app shows."""
    from tracker import reminder
    from tracker.manifest import STATUS_LABELS

    runbook = read("docs/runbook.md")
    section = runbook.split("### What the record says, and what the app shows", 1)[1]
    lines = section.split("| The record says | The app shows |\n|---|---|\n", 1)[1].splitlines()
    rows = lines[:next(i for i, line in enumerate(lines) if not line.startswith("|"))]
    assert rows == [f"| **{word}** | {shown.label.replace('{year}', '<year>')} - {shown.sentence} |"
                    for word, shown in STATUS_LABELS.items()]
    assert "TY<year>" in read("README.md")
    lines = section.split("| Whose move | The sentence beside it |\n|---|---|\n", 1)[1].splitlines()
    sides = lines[:next(i for i, line in enumerate(lines) if not line.startswith("|"))]
    assert sides == [f"| **{side.label}** | {side.sentence} |" for side in reminder.SIDES]


# ------------------ decision 201: the editor opens on what a preparer touches ----


_DIALOG_IDS = re.compile(r'<div id="([a-z-]+)" class="modal-overlay')


def _registry(js: str) -> set[str]:
    """The ids the one dialog registry names, at its top level."""
    block = js.split("const DIALOGS = {", 1)[1].split("\n};\n", 1)[0]
    return set(re.findall(r'^  "?([a-z-]+)"?: \{', block, flags=re.MULTILINE))


def test_every_dialog_is_in_the_one_registry_and_closes_through_one_guard():
    """D10: every ``.modal-overlay`` in the page is in ``DIALOGS``, and no
    code but ``closeDialog`` hides one - and none but ``openDialog`` shows
    one - so no dialog can close its own way again."""
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    ids = set(_DIALOG_IDS.findall(html))
    assert ids == {"editor", "household-modal", "handover-modal", "modal"}
    assert _registry(js) == ids
    for ident in ids:
        assert f'$("{ident}").classList.add("hidden")' not in js, ident
        assert f'$("{ident}").classList.remove("hidden")' not in js, ident
        assert f'$("{ident}").classList.toggle("hidden"' not in js, ident
    closing = _js_function(js, "function closeDialog(id) {")
    opening = _js_function(js, "function openDialog(id, first) {")
    assert '$(id).classList.add("hidden");' in closing
    assert 'overlay.classList.remove("hidden");' in opening
    rest = js.replace(closing, "").replace(opening, "")
    assert '$(id).classList.add("hidden")' not in rest and "overlay.classList" not in rest


def test_escape_and_an_overlay_click_reach_every_dialog_the_same_way():
    """One keydown handler on the document sends Escape to ``requestClose``
    for the topmost dialog; a click on any dialog's dim is the same call;
    and every Cancel button makes it too."""
    js = read("app/renderer/app.js")
    assert js.count('document.addEventListener("keydown"') == 1
    handler = js.split('document.addEventListener("keydown", (e) => {', 1)[1].split("\n});", 1)[0]
    assert 'e.key === "Escape"' in handler and "requestClose(id);" in handler
    assert "trapTab(e, id);" in handler
    assert js.count('"Escape"') == 1
    overlay = js.split("for (const id of Object.keys(DIALOGS)) {", 1)[1].split("\n}\n", 1)[0]
    assert "if (e.target === $(id)) requestClose(id);" in overlay
    assert not re.search(r"e\.target === \$\(\"[a-z-]+\"\)", js)
    for button, dialog in (("hh-edit-cancel", "household-modal"), ("ho-cancel", "handover-modal"),
                           ("ed-cancel", "editor"), ("wh-cancel", "modal"), ("wf-cancel", "modal"),
                           ("ne-cancel", "modal")):
        assert f'$("{button}").addEventListener("click", () => requestClose("{dialog}"));' in js, button


def test_every_dialog_opens_with_focus_inside_and_gives_it_back():
    """``openDialog`` remembers what had focus and puts it on a control
    inside; Tab is kept inside while it is open; ``closeDialog`` gives it
    back. Every opener goes through it."""
    js = read("app/renderer/app.js")
    opening = _js_function(js, "function openDialog(id, first) {")
    assert "dialogOpener[id] = document.activeElement;" in opening
    assert "target.focus();" in opening and "DIALOGS[id].first()" in opening
    closing = _js_function(js, "function closeDialog(id) {")
    assert "const back = dialogOpener[id];" in closing and "back.focus();" in closing
    for opener, ident in (("async function openEditor() {", "editor"),
                          ("function openHouseholdEditor() {", "household-modal"),
                          ("async function openHandOver(original, seq) {", "handover-modal"),
                          ("async function openAddReturn(hh) {", "modal"),
                          ("async function openNewHousehold() {", "modal")):
        assert f'openDialog("{ident}")' in _js_function(js, opener), opener
    registry = js.split("const DIALOGS = {", 1)[1].split("\n};\n", 1)[0]
    assert registry.count("first: () =>") == 4
    trap = _js_function(js, "function trapTab(e, id) {")
    assert "e.preventDefault();" in trap and "first.focus();" in trap and "last.focus();" in trap


def test_escape_never_discards_unsaved_work():
    """F-T-7: while the unsaved bar is showing, every way of asking to close
    means Keep editing; a dialog with changes raises the bar and does not
    close; and the bar's discard button is the only way from it to
    ``closeDialog``."""
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    asking = _js_function(js, "function requestClose(id) {")
    showing, rest = asking.split("keepEditing(id);", 1)
    assert 'bar && !bar.classList.contains("hidden")' in showing and "closeDialog" not in showing
    clean, dirty = rest.split("if (!isDirty(id)) {", 1)[1].split("}", 1)
    assert "closeDialog(id);" in clean
    assert "closeDialog" not in dirty and 'bar.querySelector(".dlg-keep").focus();' in dirty
    assert "closeDialog" not in _js_function(js, "function keepEditing(id) {")
    assert js.count('.dlg-discard")') == 2          # its words, and its one listener
    assert 'bar.querySelector(".dlg-discard").addEventListener("click", () => closeDialog(id));' in js
    assert 'bar.querySelector(".dlg-keep").addEventListener("click", () => keepEditing(id));' in js
    # Every dialog a person types in carries the bar; the hand-over is two
    # picks and never dirty.
    assert html.count('class="dlg-unsaved banner warn hidden" role="alert"') == 3
    assert "model: null," in js.split("const DIALOGS = {", 1)[1].split('"handover-modal": {', 1)[1]
    # Acts recorded at once move the snapshot: the rename renames it.
    assert "for (const row of dialogSnapshot.editor.rows)" in _js_function(js, "async function renameRequest() {")


def test_the_editor_opens_on_the_state_on_screen_with_every_fold_closed():
    """D13 on decision 194's model: the editor opens on ``lastState`` - the
    reply the page is showing - and reads ``state`` only for a return a
    switch has not landed on yet, one call; each open starts with every
    fold closed, and the save is still judged by ``list_head``."""
    js = read("app/renderer/app.js")
    body = _js_function(js, "async function openEditor() {")
    assert body.count("call(") == 1 and 'call(withEng("state"))' in body
    assert "? { ...lastState }" in body and body.index("lastState") < body.index("call(")
    assert "refresh(" not in body
    assert body.index("editorFolds.clear();") < body.index("renderEditorRows();")
    assert "head: editorState.list_head" in _js_function(js, "async function saveEditor() {")


def test_no_text_box_is_named_only_by_its_placeholder():
    """D11: a placeholder is gone the moment somebody types. The renderer
    types no placeholder of its own; the keyword, spelling and note boxes
    are each built inside a visible label, by one builder each; and the
    setup card's three boxes sit inside labels in the page."""
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    assert 'placeholder: "' not in js
    assert "keyword to learn" not in js.lower() and "Keyword to add to the request" not in js
    for cls, builder in (("r-keyword", "function keywordBox() {"),
                         ("r-note", "function noteBox(words) {"),
                         ("r-spelling", "function teachSpelling(triage, people) {")):
        assert js.count(f'className: "{cls}"') == 1, cls
        body = _js_function(js, builder)
        label = body.split('el("label", { className: "field', 1)[1]
        assert f'className: "{cls}"' in label, cls
    assert len(re.findall(r"\bkeywordBox\(\)", js)) == 4        # the builder and its three places
    for ident in ("phone-input", "firm-input", "root-input"):
        assert re.search(rf'<label class="field">\s*<span id="[a-z]+-label"></span>\s*<input id="{ident}"', html), ident
        tag = re.search(rf'<input id="{ident}"[^>]*>', html).group(0)
        assert "placeholder=" not in tag and "aria-label=" not in tag, tag


def test_the_issuer_action_has_one_call_site():
    """Decision 201: the list's row and the deck's card add the issuer
    through one function, as filing has one (decision 114) - the page
    sends the row, its version, the list's version and the name, and no
    identifier or row of its own."""
    js = read("app/renderer/app.js")
    assert js.count('withEng("add-issuer-and-file")') == 1
    assert len(re.findall(r"\baddIssuerAndFile\(", js)) == 3     # the definition and its two callers
    sent = re.search(r'call\(withEng\("add-issuer-and-file"\), \{(.*?)\}\)', js, re.S).group(1)
    assert set(re.findall(r"(\w+):", sent)) == {"original", "seq", "head", "issuer"}


def test_each_step_of_the_new_return_dialog_names_the_dialog_by_its_own_heading():
    """196's review N5, carried into decision 201: New household opens on
    its household step, where the form step's heading is hidden, so the
    dialog is named by the heading of whichever step it shows."""
    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    assert ('const STEP_HEADINGS = { household: "household-title", form: "form-title", '
            'items: "items-title" };') in js
    step = _js_function(js, "function showStep(step) {")
    assert "setAttribute(\"aria-labelledby\", STEP_HEADINGS[step])" in step
    for heading in ("household-title", "form-title", "items-title"):
        assert f'<h3 id="{heading}"></h3>' in html, heading
