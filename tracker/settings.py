"""The one place the app is told where the clients live (component 13).

The desktop app and the scheduled run both need the clients root - the
folder every engagement sits under. It used to exist twice: an environment
variable the Electron shell set for the app (with a stand-in default),
and a path typed on the runner's command line for the job. Nothing tied
them together, so the app could be showing one folder while the schedule
walked another.

Now it is written once, in ``SETTINGS_FILENAME`` beside the app - next to the
packaged executable, or in the repository root when run from source - and
both read it. The app asks for it on first launch and never again; the
scheduled job names this file's folder rather than the root, and reads the
root from here at every run (decision 131), so the root has one home and a
root changed in the app is the root the job walks next.

Deliberately tiny: one JSON object (the clients root, the firm's name and,
since decision 117, the firm's telephone number), read and written whole,
atomic on write. What is here is what belongs to the firm rather than to
an engagement; there is no second copy of any of it to drift.

``ENV_REAL_CORPUS`` sits here for the same reason the clients root does:
it is the other folder outside the repository the code is told about - the
firm's own redacted documents, which the harness and the coverage report
route when it is set and skip when it is not. It is an environment
variable rather than a setting because it belongs to the machine a person
develops on, never to an engagement, and because a run must never depend
on it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tracker.fsio import write_json_atomically

SETTINGS_FILENAME = "settings.json"
#: The keys inside it.
KEY_CLIENTS_ROOT = "clients_root"
KEY_FIRM = "firm"
#: The firm's own telephone number (decision 117). It belongs beside the
#: firm's name for the same reason the name is there: it is the firm's,
#: not one engagement's, and typing it into every client's details would
#: be the same number recorded a hundred times. Only the final-notice
#: reminder says it, and a blank one drops that sentence rather than
#: printing an empty invitation to call.
KEY_FIRM_PHONE = "firm_phone"
#: How a person is told to set the root without the app.
SET_ROOT_HINT = "python -m tracker.settings <folder>"
#: What a command line with no clients root tells a person: the app first,
#: because the packaged app is what the office runs and has no ``python``
#: to type; the command second (decision 131's review).
NO_ROOT_HINT = f"set the clients folder in the app, or run {SET_ROOT_HINT}"
#: The clients-root example every prompt and document shows.
EXAMPLE_ROOT = r"G:\Shared drives\Clients"
ENV_SETTINGS_DIR = "TRACKER_SETTINGS_DIR"
#: The Electron shell passes package.json's productName; from source the
#: same file is read directly. There is no second copy of the product name.
ENV_PRODUCT_NAME = "TRACKER_PRODUCT_NAME"
PACKAGE_JSON = Path(__file__).resolve().parent.parent / "app" / "package.json"
#: The folder of the firm's own redacted documents, outside the repository.
ENV_REAL_CORPUS = "TRACKER_REAL_CORPUS"
#: The file beside them that says where each one belongs, and its columns:
#: the document's own name, the catalog it is routed against, the
#: engagement year, and the identifier it must file under - blank for a
#: document that must park for a person.
EXPECTATIONS_FILENAME = "expectations.csv"
COLUMN_FILE = "file"
COLUMN_CATALOG = "catalog"
COLUMN_YEAR = "year"
COLUMN_EXPECTED = "expected"
EXPECTATIONS_COLUMNS = (COLUMN_FILE, COLUMN_CATALOG, COLUMN_YEAR, COLUMN_EXPECTED)
#: How the ``expected`` column names more than one request: ``A01+A02``
#: means "filed to exactly these, and to nothing else". One document can
#: belong to several when it carries several forms (decision 94), and a
#: harness that could only say one identifier would have had to call the
#: other filing a miss. Blank still means "parks"; a single identifier
#: still means "filed there and nowhere else".
EXPECTED_SEP = "+"


class SettingsError(Exception):
    """The settings file could not be read, or names a folder that is not there."""


def settings_dir() -> Path:
    """Where ``SETTINGS_FILENAME`` lives: beside the app.

    The Electron shell passes the folder in ``ENV_SETTINGS_DIR`` (next to
    the packaged executable). A frozen API without it uses its own folder;
    source checkouts use the repository root.
    """
    override = os.environ.get(ENV_SETTINGS_DIR)
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILENAME


def _read() -> dict:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SettingsError(f"{path} could not be read: {exc}") from None
    if not isinstance(data, dict):
        raise SettingsError(f"{path} should hold one JSON object")
    return data


def clients_root() -> Path | None:
    """The configured clients root, or None when nothing has been set yet."""
    raw = str(_read().get(KEY_CLIENTS_ROOT, "") or "").strip()
    return Path(raw) if raw else None


def firm() -> str:
    """The firm's name as typed once at setup; the wizard's default Firm."""
    return str(_read().get(KEY_FIRM, "") or "").strip()


def firm_phone() -> str:
    """The firm's telephone number, or "" when nobody has set one."""
    return str(_read().get(KEY_FIRM_PHONE, "") or "").strip()


def product_name() -> str:
    """What the app is called, from app/package.json (or the shell's copy of it)."""
    override = os.environ.get(ENV_PRODUCT_NAME)
    if override:
        return override
    try:
        return str(json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["productName"])
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        # A frozen build has no package.json; the shell always passes the
        # name in. Naming the product here would be a second copy of it.
        raise SettingsError(
            f"{ENV_PRODUCT_NAME} is not set and {PACKAGE_JSON.name} is not readable: {exc}"
        ) from exc


def real_corpus_dir() -> Path | None:
    """The folder of the firm's own redacted documents, or None.

    ``ENV_REAL_CORPUS`` names it and it lives outside the repository, so
    an unset variable and a folder that is not there mean the same thing -
    there is nothing to route - and both answer None. Raising instead
    would fail the suite on every machine that has no corpus, CI's
    included; the harness and the report skip on None and say so.
    """
    named = os.environ.get(ENV_REAL_CORPUS, "").strip()
    if not named:
        return None
    folder = Path(named)
    return folder if folder.is_dir() else None


def _write(data: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomically(path, data)


def set_firm(name: str) -> str:
    """Record the firm's name beside the clients root."""
    data = _read()
    data[KEY_FIRM] = str(name).strip()
    _write(data)
    return data[KEY_FIRM]


def set_firm_phone(number: str) -> str:
    """Record the firm's telephone number beside its name.

    Stripped and otherwise taken as typed: a firm writes its own number
    its own way - with an extension, a country code, two numbers - and a
    format this code invented would be a number read out to a client in
    the firm's name that the firm never wrote.
    """
    data = _read()
    data[KEY_FIRM_PHONE] = str(number).strip()
    _write(data)
    return data[KEY_FIRM_PHONE]


def app_dir() -> Path:
    """The app's own folder: the packaged executable's, or the repository
    root when run from source.

    Not :func:`settings_dir`, which the Electron shell may point elsewhere:
    this is where the program itself lives, whatever the settings say.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def system_drive_root() -> Path:
    """The root of the drive the operating system lives on
    (``%SystemDrive%\\``), or ``/`` where there are no drive letters."""
    if os.name == "nt":
        return Path(os.environ.get("SystemDrive", "C:") + os.sep)
    return Path("/")


#: Why a folder is refused as the clients root (decision 137). One sentence
#: per reason, each naming the folder, so a person knows what to choose
#: instead. The walk every two hours, the run log and the status page, and
#: the API's "under the clients root" check all follow the root, so a root
#: that holds the app's own folder would walk it, write into it and accept
#: its files as engagements.
ROOT_IS_SYSTEM_DRIVE = ("{root} is the whole system drive; the tracker would walk all of it. "
                        "Choose the folder the firm keeps its clients in")
ROOT_HOLDS_SETTINGS = ("{root} holds the app's own settings and store ({settings}); "
                       "choose the folder the firm keeps its clients in")
ROOT_INSIDE_SETTINGS = ("{root} is inside the app's settings folder ({settings}); "
                        "choose the folder the firm keeps its clients in")
ROOT_HOLDS_APP = ("{root} holds the app itself ({app}); "
                  "choose the folder the firm keeps its clients in")


def _within(inner: Path, outer: Path) -> bool:
    """Whether ``inner`` is ``outer`` or lies below it, compared as the
    filesystem compares names (without case on Windows)."""
    a = os.path.normcase(os.path.normpath(str(inner)))
    b = os.path.normcase(os.path.normpath(str(outer)))
    if a == b:
        return True
    return a.startswith(b.rstrip(os.sep) + os.sep)


def root_refusal(root: Path, *, settings: Path, app: Path, system: Path) -> str:
    """Why ``root`` may not be the clients root, or ``""`` when it may.

    Pure, so every rule is testable on any machine: ``settings`` is the
    folder holding ``SETTINGS_FILENAME`` (and the store beside it), ``app`` the
    app's own folder, ``system`` the system drive's root. Refused (decision
    137): the system drive's root; the settings folder, any folder that
    holds it, and any folder inside it; the app's folder and any folder
    that holds it. **Another drive's root is allowed**: a letter mapped to
    the clients share (``S:``, a Shared Drive letter) is a real root.
    """
    if _within(system, root) and _within(root, system):
        return ROOT_IS_SYSTEM_DRIVE.format(root=root)
    if _within(settings, root):
        return ROOT_HOLDS_SETTINGS.format(root=root, settings=settings)
    if _within(root, settings):
        return ROOT_INSIDE_SETTINGS.format(root=root, settings=settings)
    if _within(app, root):
        return ROOT_HOLDS_APP.format(root=root, app=app)
    return ""


def set_clients_root(root: Path | str) -> Path:
    """Record ``root`` as the clients root. It must already be a folder.

    Creating it here would turn a typo into an empty "clients" folder that
    the run walks for ever and finds nothing in. And it may not be a folder
    that would swallow the app (decision 137, :func:`root_refusal`): the
    system drive's root, the settings folder or anything around or inside
    it, the app's own folder or anything around it. That replaced a check
    against the working folder, which in the packaged build is whatever
    folder the app happened to be started from.
    """
    typed = str(root).strip()
    if not typed:
        # Path("") is the working folder, which is a folder: a cleared box
        # would record the app's own folder and lose the real one.
        raise SettingsError("no folder given")
    root = Path(typed)
    if not root.is_dir():
        raise SettingsError(f"not a folder: {root}")
    if str(root).rstrip("/") == root.drive:       # "D:" is the drive's current folder to Windows
        root = Path(root.drive + os.sep)
    root = root.resolve()   # the scheduled job and the app do not share a working folder
    refusal = root_refusal(root, settings=settings_dir().resolve(), app=app_dir(),
                           system=system_drive_root())
    if refusal:
        raise SettingsError(refusal)
    data = _read()
    data[KEY_CLIENTS_ROOT] = str(root)
    _write(data)
    return root


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Show or set the clients root")
    parser.add_argument("root", nargs="?", help="the folder the firm keeps its clients in")
    ns = parser.parse_args()
    if ns.root:
        try:
            print(f"clients root: {set_clients_root(ns.root)}  ({settings_path()})")
        except SettingsError as exc:
            raise SystemExit(str(exc)) from None
    else:
        root = clients_root()
        print(f"clients root: {root or '(not set)'}  ({settings_path()})")
