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
    assert package["productName"] not in read("app/renderer/index.html")
    assert package["productName"] not in read("app/renderer/app.js")
    assert package["productName"] not in read("Build App.bat")


def test_the_frozen_api_name_has_one_home():
    package = json.loads(read("app/package.json"))
    api_name = package["config"]["apiName"]
    assert api_name not in read("app/main.js")          # read from package.json at runtime
    assert api_name not in read("Build App.bat")         # read from package.json at build time
    assert "config.apiName" in read("Build App.bat") and "config.apiName" in read("app/main.js")


def test_ci_tests_the_python_floor_pyproject_declares():
    floor = re.search(r'requires-python\s*=\s*">=([\d.]+)"', read("pyproject.toml")).group(1)
    assert f'python-version: "{floor}"' in read(".github/workflows/ci.yml")


def test_gitignore_knows_every_runtime_file_python_writes_beside_the_app():
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

    css = read("app/renderer/style.css")
    chips = set(re.findall(r"\.chip-([a-z-]+)\s*\{", css))
    assert chips == {_slug(s) for s in Status.ALL} | {"requested"}


def test_the_renderer_types_no_vocabulary_of_its_own():
    from tracker.filer import DUPLICATE, FILED, NEEDS_REVIEW
    from tracker.manifest import DEFAULT_EXTENSIONS, Override, Status
    from tracker.scheduling import DEFAULT_START

    js = read("app/renderer/app.js")
    for literal in (*Status.ALL, *Override.ALL, FILED, NEEDS_REVIEW, DUPLICATE, DEFAULT_START,
                    ", ".join(DEFAULT_EXTENSIONS), "looks like"):
        assert f'"{literal}"' not in js and f"'{literal}'" not in js, literal


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
    from tracker.manifest import ENGAGEMENT_FIELDS

    readme = read("README.md")
    for label, _ in ENGAGEMENT_FIELDS:
        assert f"| {label} |" in readme, label


def test_the_roadmap_schema_table_matches_the_manifest_headers():
    from tracker.manifest import HEADERS

    roadmap = read("docs/ROADMAP.md")
    for header in HEADERS:
        assert f"| {header} |" in roadmap, header
