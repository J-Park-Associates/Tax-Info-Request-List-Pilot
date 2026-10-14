"""The type checker's gate: no file may have more type errors than the baseline records.

Decision P310 (SPEC-architecture J6, R6.3; the audit's finding E-5). Nine in
ten of the package's functions declare their types and, until this, nothing
checked one: Python has no checker of its own, and ``typing`` only declares.
mypy is the checker, a development tool installed from its own hash-checked
lock (``requirements-dev.lock``) by a person or a session working on the
repository, never by Setup, a build or the app, and never frozen into a
package.

Its first run found a little over two hundred real errors (an optional value used without
a check, a parameter typed ``object`` then read as a record), and fixing them
all before the gate could start would be a refactor of its own. So the gate is
a ratchet: ``docs/typecheck-baseline.json`` records every error each file has
today, and

* ``check`` runs mypy and fails if any file has more errors than its recorded
  count, or a file the baseline records none for gains one. It names the file
  and the errors the baseline does not hold. A file with fewer passes, and the
  summary says so, so the count is lowered on purpose;
* ``update`` rewrites the baseline from a fresh run, and refuses to raise any
  count: it is how a fix is recorded, never how an error is let in. With no
  baseline at all it records the first one.

The pass or fail is by count, file by file. The baseline also keeps each
error's message (without its line number, which moves with every edit above
it), only so that a failure can name which errors are new; a message mypy
rewords, at the same count, is no failure.

What mypy reads is set in ``pyproject.toml``'s ``[tool.mypy]``, and chosen so
the count is the same on every machine the gate runs on - the cloud session,
the Linux CI runner, the office PC - and under both interpreters:

* ``python_version`` is the floor's, so a newer interpreter's syntax is an
  error wherever the check runs;
* ``platform`` is Linux, so a Windows run reads the same code paths as a
  Linux one. Windows-only and Mac-only lines that mypy would read as
  missing carry a narrow ``# type: ignore[attr-defined]`` with the platform
  named, never a file-wide ignore. *Rejected:* a baseline per platform -
  three runs and three baselines, for code the tests on those platforms
  already exercise;
* ``no_site_packages``, so no installed package's own types are read: numpy
  2.5's annotations use syntax the floor's Python does not have, the floor
  and the office install different numpy releases, and a count that changes
  with a package upgrade is no ratchet. The readers' packages are named for
  ``ignore_missing_imports`` instead, and read as untyped;
* a test module a tool imports (``tests.*``) is followed but not counted:
  the check is of ``tracker`` and ``tools``, the files it names.

mypy keeps its cache in ``.mypy_cache`` at the repository's root, a folder it
marks ignored itself.

Standard library only, like the other tools: mypy is run as a child process of
this interpreter (``python -m mypy``), so it is the environment's own. The
suite never runs mypy: ``tests/test_typecheck.py`` hands every command a
made-up reading.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = "docs/typecheck-baseline.json"
#: The checker: the distribution whose version the baseline records, and the
#: module run as ``python -m``.
CHECKER = "mypy"
#: How the checker is installed, said where it is missing or the wrong one.
INSTALL = "pip install --require-hashes -r requirements-dev.lock"
NOT_INSTALLED = f"mypy is not installed in this environment: {INSTALL} (once), then run this again."
#: What the baseline says about itself.
BASELINE_NOTE = ("Every type error each file had when this was written, by python tools/typecheck.py update. "
                 "check fails when a file has more; update refuses to raise a count. Never edit it by hand.")

#: The shape of mypy's output, fixed on the command line so that no setting in
#: pyproject.toml can change what is read here: one line per error, the path as
#: given (relative to the root), no column, no context notes, the code at the
#: end, and the summary line last.
MYPY_FLAGS = ("--hide-error-context", "--hide-column-numbers", "--show-error-codes",
              "--hide-error-code-links", "--no-pretty", "--no-color-output", "--error-summary",
              "--hide-absolute-path")

_ERROR = re.compile(r"^(?P<path>(?:[A-Za-z]:)?[^:\n]+):(?P<line>\d+)(?::\d+)*: error: (?P<message>.+?)\s*$")
_FOUND = re.compile(r"^Found (\d+) errors? in \d+ files? \(checked \d+ source files?\)\s*$", re.M)
_CLEAN = re.compile(r"^Success: no issues found in \d+ source files?\s*$", re.M)

#: ``mypy(root)``: (mypy's version, its exit code, everything it printed).
#: Injected by the tests; the real checker otherwise.
Mypy = Callable[[Path], "tuple[str, int, str]"]


class TypeCheckError(Exception):
    """mypy could not be run or read, or the baseline could not be."""


@dataclass(frozen=True)
class Reading:
    """One run of mypy: its version, and each file's errors as (line, message)."""

    version: str
    errors: dict[str, list[tuple[int, str]]]

    @property
    def total(self) -> int:
        return sum(len(found) for found in self.errors.values())


@dataclass(frozen=True)
class Baseline:
    """The recorded errors: the version that counted them, and each file's messages."""

    version: str
    errors: dict[str, list[str]]

    @property
    def total(self) -> int:
        return sum(len(found) for found in self.errors.values())


def run_mypy(root: Path) -> tuple[str, int, str]:
    """Run this environment's mypy over what ``[tool.mypy]`` names, from ``root``."""
    try:
        version = importlib.metadata.version(CHECKER)
    except importlib.metadata.PackageNotFoundError:
        raise TypeCheckError(NOT_INSTALLED) from None
    done = subprocess.run([sys.executable, "-m", CHECKER, *MYPY_FLAGS], cwd=root, capture_output=True,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=False)
    said = (done.stdout + done.stderr).decode("utf-8", errors="replace")
    return version, done.returncode, said


def read_output(version: str, code: int, output: str) -> Reading:
    """mypy's printed output as a Reading, or a TypeCheckError saying why it cannot be one.

    Exit code 0 is clean and 1 is errors found; anything else (2 is mypy's own:
    a bad setting, a file it cannot parse, a blocking error) stops the check
    with what mypy said. The summary line must agree with the lines counted,
    so a change in mypy's output that this cannot read fails loudly instead of
    reading as fewer errors.
    """
    if code not in (0, 1):
        raise TypeCheckError(f"mypy stopped (exit code {code}) before it could count:\n{output.strip()}")
    errors: dict[str, list[tuple[int, str]]] = {}
    for line in output.splitlines():
        found = _ERROR.match(line)
        if found:
            path = found.group("path").replace("\\", "/")
            errors.setdefault(path, []).append((int(found.group("line")), found.group("message")))
    counted = sum(len(found) for found in errors.values())
    summary = _FOUND.search(output)
    said = int(summary.group(1)) if summary else 0 if _CLEAN.search(output) else None
    if said is None:
        raise TypeCheckError(f"mypy printed no summary line, so its errors cannot be counted:\n{output.strip()}")
    if said != counted or (code == 0) != (counted == 0):
        raise TypeCheckError(f"mypy said {said} errors (exit code {code}) and {counted} could be read "
                             f"from its output:\n{output.strip()}")
    return Reading(version, {path: sorted(found) for path, found in sorted(errors.items())})


def measure(root: Path = ROOT, mypy: Mypy = run_mypy) -> Reading:
    """Run mypy and read what it said."""
    return read_output(*mypy(root))


def load_baseline(root: Path = ROOT) -> Baseline | None:
    """The committed baseline, or None when there is none yet."""
    path = root / BASELINE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise TypeCheckError(f"{BASELINE} cannot be read: {exc}") from None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict) or not isinstance(data.get("mypy"), str) or not all(
            isinstance(found, list) and found and all(isinstance(message, str) for message in found)
            for found in files.values()):
        raise TypeCheckError(f"{BASELINE} is not a baseline this tool wrote: rebuild it with update")
    baseline = Baseline(data["mypy"], {path: list(found) for path, found in files.items()})
    if data.get("total") != baseline.total:
        raise TypeCheckError(f"{BASELINE} says it holds {data.get('total')} errors and lists "
                             f"{baseline.total}: it was edited by hand")
    return baseline


def _errors(count: int) -> str:
    return "1 type error" if count == 1 else f"{count} type errors"


def raised(baseline: Baseline, reading: Reading) -> list[str]:
    """Every file with more errors than the baseline records, each with the errors it does not hold.

    An error is named by its message and every line it is on. Where the
    baseline holds the same message fewer times, the tool cannot tell which
    line is the new one, so it names them all and says how many it holds.
    """
    problems: list[str] = []
    for path, found in reading.errors.items():
        allowed = baseline.errors.get(path, [])
        if len(found) <= len(allowed):
            continue
        heading = f"{path}: {_errors(len(found))}, and the baseline records {len(allowed) or 'none'}"
        held = Counter(allowed)
        lines: dict[str, list[int]] = {}
        for line, message in found:
            lines.setdefault(message, []).append(line)
        new = []
        for message, where in lines.items():
            if len(where) > held[message]:
                said = f"  {path}:{', '.join(str(line) for line in where)}: {message}"
                new.append(said + (f"  (the baseline holds {held[message]} of these)" if held[message] else ""))
        problems.append("\n".join([heading, *new]))
    return problems


def check(root: Path = ROOT, mypy: Mypy = run_mypy) -> tuple[list[str], str]:
    """(every file above the baseline, the summary line); the check passes when the first is empty.

    No baseline, or one counted by another mypy, is a TypeCheckError: a count
    is only comparable with one the same checker made.
    """
    baseline = load_baseline(root)
    if baseline is None:
        raise TypeCheckError(f"there is no {BASELINE} to hold the errors to: python tools/typecheck.py update "
                             "records the first one")
    reading = measure(root, mypy)
    if reading.version != baseline.version:
        raise TypeCheckError(f"{BASELINE} was counted by mypy {baseline.version}, and this environment runs "
                             f"mypy {reading.version}: {INSTALL}")
    problems = raised(baseline, reading)
    files = len(reading.errors)
    summary = f"{_errors(reading.total)} in {files} files, none above the baseline"
    if reading.total < baseline.total:
        summary += (f"; {baseline.total - reading.total} fewer than it records, "
                    "so python tools/typecheck.py update lowers it")
    return problems, summary


def update(root: Path = ROOT, mypy: Mypy = run_mypy) -> tuple[list[str], str]:
    """Rewrite the baseline from a fresh run, unless a count would rise: (problems, summary)."""
    baseline = load_baseline(root)
    reading = measure(root, mypy)
    problems = raised(baseline, reading) if baseline is not None else []
    if problems:
        return problems, ""
    data = {
        "note": BASELINE_NOTE,
        "mypy": reading.version,
        "total": reading.total,
        "files": {path: sorted(message for _line, message in found) for path, found in reading.errors.items()},
    }
    (root / BASELINE).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                                 newline="\n")
    before = "no baseline" if baseline is None else f"{baseline.total} before"
    return [], f"{_errors(reading.total)} in {len(reading.errors)} files recorded ({before})"


# --------------------------------------------------------------------- CLI ----


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python tools/typecheck.py",
        description="Hold every file's type errors to docs/typecheck-baseline.json (decision P310).")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="run mypy; fail if any file has more errors than the baseline records")
    commands.add_parser("update", help="rewrite the baseline from a fresh run, never raising a count")
    ns = parser.parse_args(argv)
    command = check if ns.command == "check" else update
    try:
        problems, summary = command(ROOT, run_mypy)
    except TypeCheckError as exc:
        print(f"{ns.command}: {exc}", file=sys.stderr)
        return 1
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        said = (f"{len(problems)} files have" if len(problems) != 1 else "1 file has") + \
            " more type errors than the baseline records"
        if ns.command == "update":
            said = f"the baseline is left as it was: {said}, and update never raises a count"
        print(f"{ns.command}: {said}", file=sys.stderr)
        return 1
    print(f"{ns.command}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
