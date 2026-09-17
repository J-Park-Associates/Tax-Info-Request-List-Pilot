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
schedule is generated from the same value (``python -m tracker.scheduling``
without ``ROOT_FLAG`` reads it too).

Deliberately tiny: one JSON object (the clients root and the firm's name),
read and written whole, atomic on write. There is no second setting to drift.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tracker.manifest import TEMP_SUFFIX

SETTINGS_FILENAME = "settings.json"
#: The keys inside it.
KEY_CLIENTS_ROOT = "clients_root"
KEY_FIRM = "firm"
#: How a person is told to set the root without the app.
SET_ROOT_HINT = "python -m tracker.settings <folder>"
#: The clients-root example every prompt and document shows.
EXAMPLE_ROOT = r"D:\OneDrive\Clients"
ENV_SETTINGS_DIR = "TRACKER_SETTINGS_DIR"
#: The Electron shell passes package.json's productName; from source the
#: same file is read directly. There is no second copy of the product name.
ENV_PRODUCT_NAME = "TRACKER_PRODUCT_NAME"
PACKAGE_JSON = Path(__file__).resolve().parent.parent / "app" / "package.json"


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
    except (OSError, json.JSONDecodeError) as exc:
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


def _write(data: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + TEMP_SUFFIX)
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)


def set_firm(name: str) -> str:
    """Record the firm's name beside the clients root."""
    data = _read()
    data[KEY_FIRM] = str(name).strip()
    _write(data)
    return data[KEY_FIRM]


def set_clients_root(root: Path | str) -> Path:
    """Record ``root`` as the clients root. It must already be a folder.

    Creating it here would turn a typo into an empty "clients" folder that
    the run walks for ever and finds nothing in.
    """
    root = Path(str(root).strip())
    if not root.is_dir():
        raise SettingsError(f"not a folder: {root}")
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
            raise SystemExit(str(exc))
    else:
        root = clients_root()
        print(f"clients root: {root or '(not set)'}  ({settings_path()})")
