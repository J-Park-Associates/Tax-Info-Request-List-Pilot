"""The supply-chain lock: every package the firm installs, by version and by hash.

Decision 191. ``requirements*.txt`` pin what the tracker imports by name, and
decision 137 pinned the whole tree under them - but a pin names a version,
not a file. A wheel replaced on PyPI or on a mirror at a version already
pinned would have installed without a word. A hash is the only thing that
stops that, so every package is now installed from a **lock file** that
names, for each pin, the SHA-256 of **every** file PyPI publishes for that
version (each platform's wheel and the sdist). One lock therefore serves
Linux CI, Windows CI and the Windows build, and ``pip install
--require-hashes`` refuses both a file whose hash is not listed and a
package the lock does not name at all - which is what proves the lock holds
the whole tree.

The four locks, and what installs each:

* ``requirements.lock`` - the whole tree of ``requirements.txt`` (runtime
  and the test tools). CI, ``Setup.bat`` and the build install it.
* ``requirements-build.lock`` - PyInstaller and what it pulls in that
  ``requirements.lock`` does not already hold. ``Build App.bat`` installs it
  together with ``requirements.lock``.
* ``requirements-nodeps.lock`` - ``rapidocr`` alone, installed with
  ``--no-deps`` after the tree (decision 169, R-11).
* ``requirements-gpu.lock`` - the NVIDIA pack, installed with ``--no-deps``
  by ``Build GPU Pack.bat`` (decision 169, ruling 2).

The tree was already resolved (decision 137), so the honest change was to
hash that tree, not to re-resolve it. *Rejected:* ``pip-tools`` and ``uv pip
compile`` - each re-resolves, would move pins nobody chose to move, and is
one more tool the firm would have to trust; ``pip-audit`` - one more package
to lock and trust, for what one OSV request does. So this is the standard
library only.

The commands, none of which the app or the scheduled pass ever runs:

* ``hash`` fills every lock line's hashes from PyPI's JSON API (network;
  a maintainer's command, after a pin moves).
* ``check`` proves the locks agree with the ``requirements*.txt`` pins and
  that every line carries a hash (no network; the suite runs it).
* ``stamp <venv>`` / ``verify <venv>`` - ``Setup.bat`` records the hash of
  each lock (and of ``app/package-lock.json``) in the private environment it
  made; ``Start App.bat`` refuses to start, in one sentence, when the locks
  have changed since, because the launcher never installs anything.
* ``audit`` asks OSV about every pin in the four locks and every package in
  ``app/package-lock.json`` (network; the weekly workflow). It also enforces
  the native-engine cadence: ``NATIVE_ENGINES`` below.

``tracker/`` never imports this module: the fourth standing rule keeps the
network out of the tracker, and ``hash`` and ``audit`` are network commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Each lock and the human-edited file of direct pins it locks. The direct
#: pins of the ``.txt`` (its own ``name==version`` lines, not its ``-r``
#: includes) must each appear in the lock at the same version and marker.
LOCK_FILES: dict[str, str] = {
    "requirements.lock": "requirements.txt",
    "requirements-build.lock": "requirements-build.txt",
    "requirements-nodeps.lock": "requirements-nodeps.txt",
    "requirements-gpu.lock": "requirements-gpu.txt",
}
#: The Electron install, stamped beside the locks: ``Setup.bat`` runs
#: ``npm ci`` from it, so a changed one means Setup must run again too.
NPM_LOCK = "app/package-lock.json"
#: What ``stamp`` writes inside the private environment.
STAMP_NAME = "tracker-lock.json"

#: The two packages that bundle a native engine which parses client files:
#: Pillow's image codecs and pypdfium2's PDFium. A parser of hostile input
#: in C is where an advisory lands, so their cadence is stated rather than
#: left to chance: reviewed with the weekly Dependabot PR, bumped within 7
#: days of an advisory (the audit names it) and at least every
#: ``STALE_DAYS`` days when a newer release exists (the audit fails).
NATIVE_ENGINES = ("pillow", "pypdfium2")
STALE_DAYS = 90

#: The GUI build of OpenCV, which rapidocr's metadata asks for and the app
#: never ships (decision 169, R-11): the headless build is pinned instead.
GUI_OPENCV = "opencv-python"

PYPI_RELEASE = "https://pypi.org/pypi/{name}/{version}/json"
PYPI_PROJECT = "https://pypi.org/pypi/{name}/json"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
#: OSV's own ceiling on one querybatch request.
OSV_BATCH_SIZE = 1000

#: The two sentences the launcher shows. Both name Setup.bat, because
#: running it is the one thing a person at the machine can do about either.
NOT_SET_UP = ("The app's private Python is not set up on this computer. "
              "Run Setup.bat once (it needs the internet), then start the app again.")
CHANGED = ("The package list changed since Setup ran on this computer. "
           "Run Setup.bat again, then start the app again.")

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)\s*(?:;\s*(.+?))?\s*$")
_HASH = re.compile(r"^--hash=sha256:([0-9a-f]{64})$")

#: ``fetch(url, body)``: the parsed JSON answer to a GET (``body`` None) or a
#: POST of ``body`` as JSON. Injected by the tests; the network otherwise.
Fetch = Callable[[str, "dict | None"], dict]


class LockError(Exception):
    """A lock that cannot be read, or a source that did not answer."""


def normalise(name: str) -> str:
    """A distribution's name as pip compares them (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _logical_lines(text: str) -> list[str]:
    """The file's lines with backslash continuations joined, as pip reads them."""
    lines: list[str] = []
    pending = ""
    for raw in text.splitlines():
        if raw.rstrip().endswith("\\") and not raw.lstrip().startswith("#"):
            pending += raw.rstrip()[:-1] + " "
            continue
        lines.append(pending + raw)
        pending = ""
    if pending:
        lines.append(pending)
    return lines


def _parse_requirement(line: str, where: str) -> tuple[str, str, str, list[str]]:
    """``name==version[; marker] --hash=sha256:...`` as (name, version, marker, hashes)."""
    head, *options = re.split(r"\s+(?=--)", line.strip())
    pin = _PIN.match(head)
    if not pin:
        raise LockError(f"{where}: not a name==version pin: {head!r}")
    hashes = []
    for option in options:
        found = _HASH.match(option.strip())
        if not found:
            raise LockError(f"{where}: not a --hash=sha256:<64 hex> option: {option.strip()!r}")
        hashes.append(found.group(1))
    return pin.group(1), pin.group(2), pin.group(3) or "", hashes


def read_lock(path: Path) -> list[tuple[str, str, str, list[str]]]:
    """Every pin in a lock file, as (name, version, marker, hashes), in file order."""
    pins = []
    for number, line in enumerate(_logical_lines(path.read_text(encoding="utf-8")), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pins.append(_parse_requirement(stripped, f"{path.name} line {number}"))
    return pins


def direct_pins(path: Path) -> list[tuple[str, str, str]]:
    """A requirements file's own ``name==version[; marker]`` lines (not its ``-r`` includes)."""
    pins = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name, version, marker, _hashes = _parse_requirement(line, path.name)
        pins.append((name, version, marker))
    return pins


def check(repo: Path = ROOT) -> list[str]:
    """Every way the locks disagree with themselves or the pins; empty when they hold."""
    problems: list[str] = []
    seen: dict[tuple[str, str], tuple[str, str]] = {}      # (name, marker) -> (version, lock)
    for lock_name, source in LOCK_FILES.items():
        lock_path = repo / lock_name
        if not lock_path.is_file():
            problems.append(f"{lock_name} is missing")
            continue
        try:
            pins = read_lock(lock_path)
        except LockError as exc:
            problems.append(str(exc))
            continue
        locked = set()
        for name, version, marker, hashes in pins:
            key = (normalise(name), marker)
            locked.add((key[0], version, marker))
            if not hashes:
                problems.append(f"{lock_name}: {name}=={version} carries no hash")
            if key[0] == GUI_OPENCV:
                problems.append(f"{lock_name}: {name} is the GUI build of OpenCV, which the app never ships")
            if key in seen:
                other_version, other_lock = seen[key]
                problems.append(f"{lock_name}: {name} is pinned again (at {other_version} in {other_lock})"
                                + (f" under the marker {marker}" if marker else ""))
            else:
                seen[key] = (version, lock_name)
        source_path = repo / source
        if not source_path.is_file():
            problems.append(f"{source} is missing (its lock is {lock_name})")
            continue
        try:
            wanted = direct_pins(source_path)
        except LockError as exc:
            problems.append(str(exc))
            continue
        for name, version, marker in wanted:
            if (normalise(name), version, marker) not in locked:
                problems.append(f"{source} pins {name}=={version}" + (f"; {marker}" if marker else "")
                                + f" and {lock_name} does not")
    return problems


# ------------------------------------------------------------ stamp / verify ----


def _fingerprint(repo: Path) -> dict[str, str]:
    """The SHA-256 of each lock and of the npm lock, by repository path."""
    return {name: hashlib.sha256((repo / name).read_bytes()).hexdigest()
            for name in (*LOCK_FILES, NPM_LOCK) if (repo / name).is_file()}


def stamp(venv: Path, repo: Path = ROOT) -> Path:
    """Record, inside the private environment, which locks it was made from."""
    if not venv.is_dir():
        raise LockError(f"{venv} is not a folder: make the environment first")
    target = venv / STAMP_NAME
    target.write_text(json.dumps({"files": _fingerprint(repo)}, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return target


def verify(venv: Path, repo: Path = ROOT) -> str | None:
    """The launcher's sentence when the environment is not the locks' own; None when it is."""
    target = venv / STAMP_NAME
    try:
        recorded = json.loads(target.read_text(encoding="utf-8")).get("files")
    except (OSError, ValueError, AttributeError):
        return NOT_SET_UP
    return None if recorded == _fingerprint(repo) else CHANGED


# ----------------------------------------------------------------- network ----


def fetch_json(url: str, body: dict | None = None) -> dict:
    """GET (or POST ``body`` as JSON to) ``url``; the parsed answer, or a LockError naming it."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="GET" if body is None else "POST",
                                     headers={"Content-Type": "application/json",
                                              "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return json.loads(answer.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise LockError(f"{url} did not answer with JSON: {exc}") from None


def _render(name: str, version: str, marker: str, hashes: list[str]) -> str:
    head = f"{name}=={version}" + (f"; {marker}" if marker else "")
    return " \\\n".join([head, *(f"    --hash=sha256:{digest}" for digest in hashes)])


def hash_locks(repo: Path = ROOT, fetch: Fetch = fetch_json) -> list[str]:
    """Rewrite every lock's hashes from PyPI: every file published for each pin.

    Comments, blank lines, the order of the pins and their markers are
    kept; only the hash options are replaced. Returns the locks written.
    """
    written = []
    for lock_name in LOCK_FILES:
        path = repo / lock_name
        out: list[str] = []
        for number, line in enumerate(_logical_lines(path.read_text(encoding="utf-8")), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                out.append(line.rstrip())
                continue
            name, version, marker, _old = _parse_requirement(stripped, f"{lock_name} line {number}")
            release = fetch(PYPI_RELEASE.format(name=name, version=version), None)
            digests = sorted({file["digests"]["sha256"] for file in release.get("urls", [])})
            if not digests:
                raise LockError(f"PyPI lists no files for {name}=={version} ({lock_name})")
            out.append(_render(name, version, marker, digests))
        path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
        written.append(lock_name)
    return written


def _npm_packages(repo: Path) -> list[tuple[str, str]]:
    """(name, version) of every package ``app/package-lock.json`` installs."""
    lock = json.loads((repo / NPM_LOCK).read_text(encoding="utf-8"))
    found = set()
    for key, entry in lock.get("packages", {}).items():
        if not key or entry.get("link") or "version" not in entry:
            continue                                       # the app itself, or a link
        found.add((entry.get("name") or key.rsplit("node_modules/", 1)[-1], entry["version"]))
    return sorted(found)


def _published(release_files: list[dict]) -> date | None:
    times = [file.get("upload_time_iso_8601") or file.get("upload_time") for file in release_files]
    times = [t for t in times if t]
    if not times:
        return None
    return min(datetime.fromisoformat(t.replace("Z", "+00:00")).date() for t in times)


def audit(repo: Path = ROOT, fetch: Fetch = fetch_json, today: date | None = None) -> list[str]:
    """Every known advisory against a pin, and every native engine left stale; empty when clean."""
    today = today or date.today()
    python = sorted({(normalise(name), version)
                     for lock_name in LOCK_FILES
                     for name, version, _marker, _hashes in read_lock(repo / lock_name)})
    queries = ([("PyPI", name, version) for name, version in python]
               + [("npm", name, version) for name, version in _npm_packages(repo)])
    findings: list[str] = []
    for start in range(0, len(queries), OSV_BATCH_SIZE):
        chunk = queries[start:start + OSV_BATCH_SIZE]
        answer = fetch(OSV_BATCH, {"queries": [
            {"package": {"name": name, "ecosystem": ecosystem}, "version": version}
            for ecosystem, name, version in chunk]})
        results = answer.get("results", [])
        if len(results) != len(chunk):
            raise LockError(f"OSV answered {len(results)} results for {len(chunk)} queries")
        for (ecosystem, name, version), result in zip(chunk, results, strict=True):
            for vuln in result.get("vulns") or []:
                findings.append(f"{vuln['id']}: {name} {version} ({ecosystem})")

    pinned = dict(python)
    for engine in NATIVE_ENGINES:
        if engine not in pinned:
            findings.append(f"{engine} is a native engine and no lock pins it")
            continue
        project = fetch(PYPI_PROJECT.format(name=engine), None)
        newest = project.get("info", {}).get("version")
        if not newest or newest == pinned[engine]:
            continue
        published = _published(project.get("releases", {}).get(newest, []))
        if published and (today - published).days > STALE_DAYS:
            findings.append(f"{engine} {pinned[engine]} is pinned, and {newest} was published "
                            f"{published.isoformat()}, more than {STALE_DAYS} days ago: bump the native engine")
    return findings


# --------------------------------------------------------------------- CLI ----


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python tools/lockfiles.py",
        description="The hash-checked package locks (decision 191).")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hash", help="fill every lock's hashes from PyPI (network)")
    commands.add_parser("check", help="the locks agree with the requirements files, every line hashed")
    for name, text in (("stamp", "record the locks inside a private environment Setup.bat made"),
                       ("verify", "the environment's stamp still matches the locks")):
        command = commands.add_parser(name, help=text)
        command.add_argument("venv", help="the private environment's folder (.venv)")
    commands.add_parser("audit", help="known advisories and stale native engines (network)")
    ns = parser.parse_args(argv)
    try:
        if ns.command == "hash":
            for lock_name in hash_locks(ROOT):
                print(f"{lock_name}: hashed")
            return 0
        if ns.command == "stamp":
            print(f"Stamped {stamp(Path(ns.venv), ROOT)}")
            return 0
        if ns.command == "verify":
            sentence = verify(Path(ns.venv), ROOT)
            if sentence:
                print(sentence, file=sys.stderr)
                return 1
            return 0
        found = check(ROOT) if ns.command == "check" else audit(ROOT)
    except LockError as exc:
        print(f"{ns.command}: {exc}", file=sys.stderr)
        return 1
    for line in found:
        print(line, file=sys.stderr)
    if found:
        return 1
    print(f"{ns.command}: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
