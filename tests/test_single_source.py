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
    assert api.ENGAGEMENT_FLAG not in js
    assert "vocab.engagement_flag" in js


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
    assert f"Install Python {floor}+" in read("Start App.bat")
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
    from tracker.api import _slug
    from tracker.manifest import UNSCANNED_LABEL, Status

    css = read("app/renderer/style.css")
    chips = set(re.findall(r"\.chip-([a-z-]+)\s*\{", css))
    assert chips == {_slug(s) for s in Status.ALL} | {_slug(UNSCANNED_LABEL)}


def test_the_stylesheet_has_a_class_for_every_view_state():
    """Decision 89: the chip's class is derived from the word the API sends,
    so a state with no class would show as unstyled text and a class with no
    state would be a word the page invented."""
    from tracker.view import VIEW_STATES

    css = read("app/renderer/style.css")
    assert set(re.findall(r"\.view-([a-z-]+)\s*\{", css)) == set(VIEW_STATES)


def test_the_renderer_types_no_vocabulary_of_its_own():
    """Every word Python owns reaches the page through the API's vocabulary:
    the statuses, the overrides, the decisions, the defaults, the ten
    headers of the request list, the yes/no words, the one-character
    values, the year bounds and the editor's floors - none is typed in the
    renderer, so the app cannot disagree with the tracker about a word."""
    from tracker.api import _slug
    from tracker.filer import DUPLICATE, FILED, NEEDS_REVIEW, NOT_REQUESTED
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
    from tracker.scaffold import PBC_DIR_NAME
    from tracker.scheduling import DEFAULT_START
    from tracker.settings import EXAMPLE_ROOT

    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    for literal in (*Status.ALL, *Override.ALL, FILED, NEEDS_REVIEW, DUPLICATE, NOT_REQUESTED,
                    DEFAULT_START,
                    ", ".join(DEFAULT_EXTENSIONS), "looks like", UNSCANNED_LABEL,
                    _slug(UNSCANNED_LABEL), EXPECTED_PATTERN.split("{")[1].split("}")[1].strip()):
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal
        assert literal not in js.replace("chip-${vocab.unscanned_key}", ""), literal
    for literal in (*HEADERS, YES, NO, ANY_EXTENSION):
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal
    # The dashboard's own table heads its columns in plain English, so the
    # one-word headers are not looked for in the page; the two-word ones
    # are the list's alone.
    for literal in (PBC_DIR_NAME, EXAMPLE_ROOT, str(YEAR_MIN), str(YEAR_MAX),
                    UNSCANNED_LABEL, *[h for h in HEADERS if " " in h]):
        assert literal not in html, literal
    assert 'min="' not in html and 'max="' not in html


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
        assert f"**{value}**" in text or f"**{Override.ACCEPTED} / {Override.WAIVED}**" in text, value


def test_the_roadmap_schema_table_lists_the_status_and_override_values():
    from tracker.manifest import Override, Status

    roadmap = read("docs/ROADMAP.md")
    status_row = next(line for line in roadmap.splitlines() if line.startswith("| Status |"))
    assert status_row.rstrip(" |").split("|")[-1].strip() == " / ".join(Status.ALL)
    override_row = next(line for line in roadmap.splitlines() if line.startswith("| Manual Override |"))
    for value in Override.ALL:
        assert f"`{value}`" in override_row, value


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
    """The list is the ten columns a person edits (decision 103), and the
    schema table is those ten and no others: a row left in it for a column
    the machine stopped writing is a column somebody will go looking for."""
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
#: The log never deletes: rows 1 to 103 name these files, and decisions 102
#: to 104 retired them. A document may name one only in the log or in a
#: sentence about the past (the runbook's legacy paragraph names the old
#: request list, which is allowed by this set).
RETIRED_FILES = {"_manifest.xlsx", "_index.xlsx", "_manifest.pending.json", "_index.pending.json",
                 "_index.migrated.xlsx", "_index.pending.migrated.json",
                 "_manifest.pending.migrated.json"}


def test_documents_name_only_runtime_files_the_code_owns():
    """Every `something.ext` a document quotes is a file the code names, a
    repo file, or one of the files the log retired (``RETIRED_FILES``)."""
    import subprocess

    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME
    from tracker.registry import LEGACY_MANIFEST_FILENAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scaffold import README_NAME
    from tracker.scanner import CACHE_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import SETTINGS_FILENAME
    from tracker.store import STORE_FILENAME
    from tracker.view import VIEW_FILENAME

    assert LEGACY_MANIFEST_FILENAME in RETIRED_FILES
    owned = {CACHE_FILENAME, LEDGER_FILENAME, LOCK_FILENAME, DRAFT_FILENAME, NEW_DRAFT_FILENAME,
             LOG_FILENAME, STATUS_PAGE_FILENAME, README_NAME,
             SCHEDULE_XML_FILENAME, SETTINGS_FILENAME, STORE_FILENAME, VIEW_FILENAME}
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
    repo_files = {Path(t).name for t in tracked} | {t for t in tracked}
    for rel in DOCUMENTS:
        for quoted in re.findall(r"`([^`\s]+\.(?:txt|xml|jsonl|json|lock|xlsx|log|bat|py|md|js|toml|yml|db))`", read(rel)):
            name = quoted.split("/")[-1].split("\\")[-1]
            if "<" in quoted or "*" in quoted:
                continue                                  # a pattern, not a file
            assert quoted in repo_files or name in repo_files or name in owned or name in RETIRED_FILES, (rel, quoted)


def test_the_build_output_folder_is_the_one_gitignore_knows():
    out = re.search(r"^set OUT=(\S+)", read("Build App.bat"), re.M).group(1)
    assert f"{out}/" in read(".gitignore")


def test_every_dependency_is_pinned_exactly():
    # A build made next month must freeze the same code as one made today.
    for rel in ("requirements.txt", "requirements-build.txt"):
        for line in read(rel).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r "):
                continue
            assert re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][A-Za-z0-9.]*", line), (rel, line)
    package = json.loads(read("app/package.json"))
    for name, version in package["devDependencies"].items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), (name, version)
    lock = json.loads(read("app/package-lock.json"))
    for name, version in package["devDependencies"].items():
        assert lock["packages"][f"node_modules/{name}"]["version"] == version, name


def test_the_build_is_made_from_what_is_committed():
    ignored = [line.strip() for line in read(".gitignore").splitlines()]
    assert "*.spec" not in ignored and "app/package-lock.json" not in ignored
    assert "npm ci" in read("Build App.bat") and "npm ci" in read("Start App.bat")
    assert "npm install" not in read("Build App.bat") and "npm install" not in read("Start App.bat")
    build = read("Build App.bat")
    assert "requirements-build.txt" in build and "api_entry.spec" in build
    assert "pip install pyinstaller" not in build            # pinned in requirements-build.txt
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
    from tracker.api import (
        EDITOR_ADD_LABEL,
        EDITOR_CANCEL_LABEL,
        EDITOR_OPEN_LABEL,
        EDITOR_PASTE_LABEL,
        EDITOR_REMOVE_LABEL,
        EDITOR_SAVE_LABEL,
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
               EDITOR_REMOVE_LABEL, EDITOR_PASTE_LABEL}
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


def test_tree_diagrams_show_catalog_folders_as_the_scaffold_names_them():
    from tracker.scaffold import folder_name_for
    from tracker.templates import FORM_TEMPLATES, TY, item_from_spec

    folders = {folder_name_for(item_from_spec(spec)) for rows in FORM_TEMPLATES.values() for spec in rows}
    for rel in DOCUMENTS:
        for line in re.findall(r"([A-Z]\d{2} - [^/\n]+?)/", read(rel)):
            assert line in folders, (rel, line)
        for line in read(rel).splitlines():
            if "──" not in line:
                continue                                  # only the tree diagrams
            for period in re.findall(r"\bTY\d{4}\b", line):
                assert period == TY, (rel, period)


def _known_flags() -> set[str]:
    """Every ``--flag`` the package and the tools define, by literal or by ``*_FLAG`` constant."""
    modules = [*(REPO / "tracker").glob("*.py"), *(REPO / "tools").glob("*.py")]
    sources = "\n".join(read(str(p.relative_to(REPO))) for p in modules)
    return (set(re.findall(r'"(--[a-z][a-z-]*)"', sources))
            | set(re.findall(r"^\w+_FLAG = \"(--[a-z-]+)\"", sources, re.M)))


def test_the_command_center_manifest_names_real_commands_and_admits_no_sending():
    """automation.manifest.json is argv the Command Center runs verbatim, so it is pinned here."""
    from tracker.runner import LOG_FLAG

    data = json.loads(read("automation.manifest.json"))
    safety = data["safety"]
    assert safety["auto_send"] is False
    assert safety["money_movement"] is False
    if safety.get("scheduled"):
        assert re.match(r"^\d{4}-\d{2}-\d{2} ", safety["scheduled_exception"]), "a dated exception"
    known = _known_flags()
    for action in data["actions"]:
        argv = action["command"]
        assert argv[0] == "python", action["id"]
        if argv[1] == "-m":
            assert (REPO / (argv[2].replace(".", "/") + ".py")).is_file(), argv[2]
            rest = argv[3:]
        else:
            assert (REPO / argv[1]).is_file(), argv[1]
            rest = argv[2:]
        for token in rest:
            if token.startswith("--") and token != "--":
                assert token in known, (action["id"], token)
        if LOG_FLAG in argv:
            assert action["kind"] == "authorize", "a pass that writes is authorized, never previewed"


def test_every_cli_flag_a_document_names_exists_in_the_code():
    from tracker.runner import REMINDER_MODES

    known = _known_flags()
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


def test_documents_name_the_engagement_folders_as_the_scaffold_does():
    """Every `Something/` a document quotes as a folder is one the scaffold names."""
    from tracker.scaffold import PBC_DIR_NAME, PREPARED_DIR_NAME, REVIEW_DIR_NAME, SHARED_DIR_NAME

    folders = {SHARED_DIR_NAME, PBC_DIR_NAME, PREPARED_DIR_NAME, REVIEW_DIR_NAME}
    for rel in (*DOCUMENTS, "docs/repo-map.curated.json"):
        for quoted in re.findall(r"`((?:[A-Z][A-Za-z]+/)+)`", read(rel)):
            for part in quoted.rstrip("/").split("/"):
                assert part in folders, (rel, quoted)
        for word in re.findall(r"\b([A-Z][a-z]+)/", read(rel)):
            if word in ("Shared", "Prepared", "PBC", "Prepared"):
                assert word in folders, (rel, word)


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
    from tracker.scanner import CACHE_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import SETTINGS_FILENAME
    from tracker.view import VIEW_FILENAME

    owned = {CACHE_FILENAME, LEDGER_FILENAME, LOCK_FILENAME,
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
                   "view", "ledger", "validators")
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

    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME
    from tracker.manifest import Override, Status
    from tracker.registry import LEGACY_MANIFEST_FILENAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME
    from tracker.scaffold import (
        PBC_DIR_NAME,
        PREPARED_DIR_NAME,
        README_NAME,
        REVIEW_DIR_NAME,
        SHARED_DIR_NAME,
    )
    from tracker.scanner import CACHE_FILENAME
    from tracker.settings import SETTINGS_FILENAME
    from tracker.store import STORE_FILENAME
    from tracker.view import VIEW_FILENAME

    values = {LEDGER_FILENAME, LOCK_FILENAME, DRAFT_FILENAME, NEW_DRAFT_FILENAME,
              LOG_FILENAME, LEGACY_MANIFEST_FILENAME, README_NAME, REVIEW_DIR_NAME, CACHE_FILENAME,
              SETTINGS_FILENAME, STORE_FILENAME, VIEW_FILENAME,
              f"{SHARED_DIR_NAME}/", f"{PBC_DIR_NAME}/", f"{PREPARED_DIR_NAME}/"}
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
