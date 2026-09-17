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
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import SETTINGS_FILENAME

    ignored = [line.strip() for line in read(".gitignore").splitlines()
               if line.strip() and not line.startswith("#")]
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME, LOG_FILENAME, SCHEDULE_XML_FILENAME, SETTINGS_FILENAME):
        assert ignored.count(name) == 1, name


def test_the_stylesheet_has_a_chip_for_every_status_and_nothing_else():
    from tracker.api import _slug
    from tracker.manifest import Status

    from tracker.manifest import UNSCANNED_LABEL

    css = read("app/renderer/style.css")
    chips = set(re.findall(r"\.chip-([a-z-]+)\s*\{", css))
    assert chips == {_slug(s) for s in Status.ALL} | {_slug(UNSCANNED_LABEL)}


def test_the_renderer_types_no_vocabulary_of_its_own():
    from tracker.filer import DUPLICATE, FILED, NEEDS_REVIEW
    from tracker.manifest import DEFAULT_EXTENSIONS, Override, Status
    from tracker.scheduling import DEFAULT_START

    from tracker.api import _slug
    from tracker.manifest import EXPECTED_PATTERN, UNSCANNED_LABEL, YEAR_MAX, YEAR_MIN
    from tracker.rollover import CARRIED_SHEET
    from tracker.scaffold import PBC_DIR_NAME
    from tracker.settings import EXAMPLE_ROOT

    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    for literal in (*Status.ALL, *Override.ALL, FILED, NEEDS_REVIEW, DUPLICATE, DEFAULT_START,
                    ", ".join(DEFAULT_EXTENSIONS), "looks like", UNSCANNED_LABEL,
                    _slug(UNSCANNED_LABEL), EXPECTED_PATTERN.split("{")[1].split("}")[1].strip()):
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal
        assert literal not in js.replace(f"chip-${{vocab.unscanned_key}}", ""), literal
    for literal in (CARRIED_SHEET, PBC_DIR_NAME, EXAMPLE_ROOT, str(YEAR_MIN), str(YEAR_MAX),
                    UNSCANNED_LABEL):
        assert literal not in html, literal
    assert 'min="' not in html and 'max="' not in html


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
    from tracker.templates import FORM_TYPES

    labels = ", ".join(f["label"].removeprefix("Form ") for f in FORM_TYPES)
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


def test_the_readme_names_the_carried_forward_sheet_the_rollover_writes():
    from tracker.manifest import ENGAGEMENT_SHEET_NAME, SHEET_NAME
    from tracker.rollover import CARRIED_SHEET

    readme = read("README.md")
    assert f"`{CARRIED_SHEET}` sheet" in readme
    for name in re.findall(r"`([A-Z][A-Za-z ]+)` sheet", readme):
        assert name in (CARRIED_SHEET, ENGAGEMENT_SHEET_NAME, SHEET_NAME), name


def test_the_scan_button_label_is_typed_once():
    label = re.search(r'const SCAN_LABEL = "([^"]+)";', read("app/renderer/app.js")).group(1)
    assert label not in read("app/renderer/index.html")
    js = read("app/renderer/app.js")
    assert js.count(f'"{label}"') == 1
    for rel in ("docs/ROADMAP.md", "docs/workflow.md", "README.md"):
        text = read(rel)
        # Prose may name the button, but only by its real label.
        assert "Sort and Scan" not in text and "Sort&Scan" not in text, rel


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


def test_the_readme_engagement_sheet_table_matches_the_fields():
    from tracker.manifest import ENGAGEMENT_FIELDS, ENGAGEMENT_HELP, ENGAGEMENT_NOTES, NO

    readme = read("README.md")
    for label, field in ENGAGEMENT_FIELDS:
        row = next((line for line in readme.splitlines() if line.startswith(f"| {label} |")), None)
        assert row is not None, label
        assert ENGAGEMENT_HELP[field].replace(f"{NO} =", f"`{NO}` =") in row, (label, row)
    for field, note in ENGAGEMENT_NOTES.items():
        assert ENGAGEMENT_HELP[field] == note, field


def test_the_roadmap_schema_table_matches_the_manifest_headers():
    from tracker.manifest import HEADERS

    roadmap = read("docs/ROADMAP.md")
    for header in HEADERS:
        assert f"| {header} |" in roadmap, header


DOCUMENTS = ("README.md", "docs/ROADMAP.md", "docs/workflow.md", "CLAUDE.md")


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


def test_documents_name_only_runtime_files_the_code_owns():
    """Every `something.ext` a document quotes is a file the code names, or a repo file."""
    import subprocess

    from tracker.filer import INDEX_FILENAME, INDEX_PENDING_FILENAME
    from tracker.locking import LOCK_FILENAME
    from tracker.manifest import pending_path
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import LOG_FILENAME
    from tracker.scaffold import MANIFEST_FILENAME, README_NAME
    from tracker.scanner import CACHE_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import SETTINGS_FILENAME

    owned = {CACHE_FILENAME, INDEX_FILENAME, INDEX_PENDING_FILENAME, LOCK_FILENAME,
             pending_path(Path(MANIFEST_FILENAME)).name, DRAFT_FILENAME, NEW_DRAFT_FILENAME,
             LOG_FILENAME, MANIFEST_FILENAME, README_NAME, SCHEDULE_XML_FILENAME, SETTINGS_FILENAME}
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
    repo_files = {Path(t).name for t in tracked} | {t for t in tracked}
    for rel in DOCUMENTS:
        for quoted in re.findall(r"`([^`\s]+\.(?:txt|xml|json|lock|xlsx|log|bat|py|md|js|toml|yml))`", read(rel)):
            name = quoted.split("/")[-1].split("\\")[-1]
            if "<" in quoted or "*" in quoted:
                continue                                  # a pattern, not a file
            assert quoted in repo_files or name in repo_files or name in owned, (rel, quoted)


def test_the_build_output_folder_is_the_one_gitignore_knows():
    out = re.search(r"^set OUT=(\S+)", read("Build App.bat"), re.M).group(1)
    assert f"{out}/" in read(".gitignore")


def test_the_roadmap_names_every_status_in_bold():
    from tracker.manifest import Status

    roadmap = read("docs/ROADMAP.md")
    for value in Status.ALL:
        assert f"**{value}**" in roadmap, value


def test_documents_name_buttons_by_their_labels():
    """A doc may say 'the X button' only for a button the page actually has."""
    html = read("app/renderer/index.html")
    labels = {re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m)).strip()
              for m in re.findall(r"<button[^>]*>(.*?)</button>", html, re.S)}
    js = read("app/renderer/app.js")
    labels |= set(re.findall(r'<button[^>]*>([^<]+)</button>', js))
    labels.add(re.search(r'const SCAN_LABEL = "([^"]+)";', js).group(1))
    labels = {label for label in labels if label and "${" not in label}
    for rel in DOCUMENTS:
        text = read(rel)
        mentions = (re.findall(r"\*\*([^*]+)\*\* button", text) + re.findall(r"\*([^*]+)\* button", text)
                    + re.findall(r"the (?:app's )?([A-Z][A-Za-z &]+?) button", text))
        for name in mentions:
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


def test_every_cli_flag_a_document_names_exists_in_the_code():
    sources = "\n".join(read(str(p.relative_to(REPO))) for p in (REPO / "tracker").glob("*.py"))
    known = set(re.findall(r'"(--[a-z][a-z-]*)"', sources)) | set(re.findall(r"^\w+_FLAG = \"(--[a-z-]+)\"", sources, re.M))
    for rel in DOCUMENTS:
        for flag in set(re.findall(r"(--[a-z][a-z-]*)", read(rel))):
            assert flag in known, (rel, flag)


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
    for label in (module.TESTED_BY, module.EXERCISED_BY, module.NO_TEST_FILE):
        assert f"**{label}**" in text, label
