"""The list of engagements a scheduled run works through (component 10).

One ``engagements.yaml`` names every engagement the unattended job should
touch, so adding a client to the nightly run is an edit to one file rather
than a change to a scheduled task. Everything in it is optional except the
path — the defaults block fills in the rest.

::

    root: D:\\OneDrive\\Clients          # relative paths hang off this
    defaults:
      firm: J Park & Associates, CPA
      sender: Jason Park
      reminders: true                   # draft the weekly chase email
    engagements:
      - path: Smith Family 2025
        client: John Smith
        link: https://drive.google.com/drive/folders/abc123
        due: 2026-03-15
      - path: Acme Corp TY2025
        client: Dana Lee
        reminders: false                # this one we chase by phone
      - path: Old Client 2024
        active: false                   # skipped entirely, kept for the record

Loading fails loudly: an unknown key, a missing path, a malformed date or the
same folder listed twice all raise :class:`RegistryError` naming the offending
entry. A scheduled job runs unattended, so a typo that silently skipped a
client would not be noticed until a filing deadline.

Whether an engagement's folder actually exists is *not* checked here. That is
the runner's business, which reports it per engagement and carries on with
the rest — one mistyped path must never stop the other clients' runs.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REGISTRY_FILENAME = "engagements.yaml"

_TOP_LEVEL_KEYS = {"root", "defaults", "engagements"}
_ENGAGEMENT_KEYS = {
    "path", "name", "client", "link", "due", "sender", "firm",
    "reminders", "active",
}
#: Defaults may set anything an engagement can, except its own identity.
_DEFAULT_KEYS = _ENGAGEMENT_KEYS - {"path", "name", "client", "link", "due"}


class RegistryError(Exception):
    """``engagements.yaml`` could not be read or makes no sense."""


@dataclass(frozen=True, slots=True)
class Engagement:
    """One engagement the scheduled run should process."""

    path: Path
    name: str = ""
    client: str = ""
    link: str = ""
    due: dt.date | None = None
    sender: str = ""
    firm: str = ""
    reminders: bool = True
    active: bool = True

    @property
    def label(self) -> str:
        return self.name or self.path.name


@dataclass(slots=True)
class Registry:
    """Every engagement named in one ``engagements.yaml``."""

    source: Path
    root: Path | None = None
    engagements: list[Engagement] = field(default_factory=list)

    @property
    def active(self) -> list[Engagement]:
        return [e for e in self.engagements if e.active]

    def find(self, needle: str) -> list[Engagement]:
        """Engagements whose label or path contains ``needle``, case-insensitively."""
        lowered = needle.lower()
        return [
            e for e in self.engagements
            if lowered in e.label.lower() or lowered in str(e.path).lower()
        ]


# --------------------------------------------------------------- parsing ----


def _reject_unknown(keys: Any, allowed: set[str], where: str) -> None:
    unknown = sorted(set(keys) - allowed)
    if unknown:
        raise RegistryError(
            f"{where}: unknown key(s) {', '.join(unknown)}; "
            f"expected any of {', '.join(sorted(allowed))}"
        )


def _as_bool(value: Any, key: str, where: str) -> bool:
    if isinstance(value, bool):
        return value
    raise RegistryError(f"{where}: {key} must be true or false, got {value!r}")


def _as_str(value: Any, key: str, where: str) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int)):
        return str(value).strip()
    raise RegistryError(f"{where}: {key} must be text, got {value!r}")


def _as_date(value: Any, where: str) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value).strip())
    except ValueError:
        raise RegistryError(
            f"{where}: due must be a date as YYYY-MM-DD, got {value!r}"
        ) from None


def _engagement_from(entry: Any, index: int, defaults: dict, root: Path | None) -> Engagement:
    where = f"engagement #{index}"
    if not isinstance(entry, dict):
        raise RegistryError(f"{where}: expected a mapping, got {entry!r}")
    _reject_unknown(entry.keys(), _ENGAGEMENT_KEYS, where)

    raw_path = _as_str(entry.get("path"), "path", where)
    if not raw_path:
        raise RegistryError(f"{where}: path is required")
    path = Path(raw_path)
    if root is not None and not path.is_absolute():
        path = root / path

    where = f"engagement {raw_path!r}"
    merged = {**defaults, **entry}
    return Engagement(
        path=path,
        name=_as_str(merged.get("name"), "name", where),
        client=_as_str(merged.get("client"), "client", where),
        link=_as_str(merged.get("link"), "link", where),
        due=_as_date(merged.get("due"), where),
        sender=_as_str(merged.get("sender"), "sender", where),
        firm=_as_str(merged.get("firm"), "firm", where),
        reminders=_as_bool(merged.get("reminders", True), "reminders", where),
        active=_as_bool(merged.get("active", True), "active", where),
    )


def load_registry(path: Path | str) -> Registry:
    """Read and validate ``engagements.yaml``."""
    path = Path(path)
    if not path.is_file():
        raise RegistryError(f"no registry at {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RegistryError(f"{path} is not valid YAML: {exc}") from None

    if raw is None:
        raise RegistryError(f"{path} is empty")
    if not isinstance(raw, dict):
        raise RegistryError(f"{path}: expected a mapping at the top level")
    _reject_unknown(raw.keys(), _TOP_LEVEL_KEYS, str(path))

    root_text = _as_str(raw.get("root"), "root", str(path))
    root = Path(root_text) if root_text else None

    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise RegistryError(f"{path}: defaults must be a mapping")
    _reject_unknown(defaults.keys(), _DEFAULT_KEYS, f"{path} defaults")

    entries = raw.get("engagements")
    if not entries:
        raise RegistryError(f"{path}: no engagements listed")
    if not isinstance(entries, list):
        raise RegistryError(f"{path}: engagements must be a list")

    engagements = [
        _engagement_from(entry, i, defaults, root)
        for i, entry in enumerate(entries, start=1)
    ]

    seen: dict[Path, int] = {}
    for i, engagement in enumerate(engagements, start=1):
        first = seen.get(engagement.path)
        if first is not None:
            raise RegistryError(
                f"{path}: engagement #{i} repeats the path of #{first} "
                f"({engagement.path}); it would be processed twice"
            )
        seen[engagement.path] = i

    return Registry(source=path, root=root, engagements=engagements)


def create_registry_template(path: Path | str) -> Path:
    """Write a commented starter ``engagements.yaml``. Never overwrites."""
    path = Path(path)
    if path.exists():
        raise RegistryError(f"Refusing to overwrite existing registry: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Every engagement the scheduled run should process.\n"
        "# Edit this file to add a client; the scheduled task never changes.\n"
        "\n"
        "# root: D:\\OneDrive\\Clients     # relative paths below hang off this\n"
        "\n"
        "defaults:\n"
        "  firm: J Park & Associates, CPA\n"
        "  sender: \n"
        "  reminders: true               # draft the weekly chase email\n"
        "\n"
        "engagements:\n"
        "  - path: Smith Family 2025\n"
        "    client: John Smith\n"
        "    # link: https://drive.google.com/drive/folders/...\n"
        "    # due: 2026-03-15\n"
        "\n"
        "  # - path: Acme Corp TY2025\n"
        "  #   client: Dana Lee\n"
        "  #   reminders: false          # this one we chase by phone\n"
        "  #   active: false             # skip entirely, keep for the record\n",
        encoding="utf-8",
    )
    return path


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check or create engagements.yaml")
    parser.add_argument("registry", nargs="?", default=REGISTRY_FILENAME,
                        help=f"path to the registry (default: {REGISTRY_FILENAME})")
    parser.add_argument("--init", action="store_true",
                        help="write a starter registry instead of checking one")
    ns = parser.parse_args()

    if ns.init:
        try:
            written = create_registry_template(ns.registry)
        except RegistryError as exc:
            raise SystemExit(f"{exc}")
        print(f"Wrote {written}")
        raise SystemExit(0)

    try:
        loaded = load_registry(ns.registry)
    except RegistryError as exc:
        raise SystemExit(f"Registry problem: {exc}")

    print(f"{loaded.source}: {len(loaded.active)} active "
          f"of {len(loaded.engagements)} engagement(s)")
    for engagement in loaded.engagements:
        flags = []
        if not engagement.active:
            flags.append("inactive")
        if not engagement.reminders:
            flags.append("no reminders")
        exists = "" if engagement.path.is_dir() else "  [FOLDER NOT FOUND]"
        suffix = f"  ({', '.join(flags)})" if flags else ""
        print(f"  {engagement.label}{suffix}{exists}")
        print(f"      {engagement.path}")
