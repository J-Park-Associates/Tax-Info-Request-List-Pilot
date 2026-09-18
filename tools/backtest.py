"""The firm's own already-sorted documents, routed again and scored.

Thirteen adversarial readings tuned the router against fifty blank IRS
forms and ninety-odd typed reconstructions. Neither is a client's
document, and the coverage report says so plainly: most of the catalog's
keywords are reached by nothing in the suite, and most rows have no
document the suite files into them. The firm, meanwhile, has years of
documents a person has already sorted by hand, sitting on the office file
server. Those are the measure. This tool routes them, counts how often
the router lands where the person did, and times the pass - so that a
routing change can be held to a number taken from real paperwork instead
of from forms nobody ever sent.

It is run at the office, against a folder that is never reachable from a
development machine and whose contents never enter the repository. Only
one number comes back: the agreement, recorded in ``BASELINE_PATH``, which
every later routing change must not lower.

**The file's own name is hidden from the router.** A person filing by hand
reads the document; the router, faced with a scan it cannot read, falls
back to the file's name - and the firm names its files after the form and
the client, so a backtest that let the router see the name would be
scoring the firm's own naming discipline, not the routing rules. Each
document is therefore routed through a hard link (a copy where the file
system refuses one) in a scratch folder outside the repository, named
``NEUTRAL_STEM`` plus the document's own extension, with the text read once
and handed to :func:`tracker.router.route_file` as ``text``. The link is
the same bytes, so every tier-2 check - the extension, the size, whether
the PDF opens - still sees the real document.

What that choice costs, said plainly:

- The neutral stem is a real word, and a catalog whose keyword was that
  word would be reached by it. ``tests/test_backtest.py`` pins that no
  keyword in any shipped catalog is.
- Handing the router the text means the router does not read the file
  itself, so the reading is this tool's rather than the router's. It is
  the same call the router would make (:func:`tracker.content_check.extract`
  with OCR withheld), which is also the reading the scanner makes later.
- A document with no text layer is not routed at all: it is its own
  category, because the only evidence left would be the name this tool is
  hiding. With ``OCR_FLAG`` it is routed with nothing supplied, so the
  router reads it, OCRs it, and applies its own stricter rule for OCR
  text - which is the honest measurement of an OCR pass.
- A hard link costs nothing; a copy (another volume, a file system without
  links) costs one read of the document, which lands in that document's
  timing and nowhere else.

What it measures is where the router *would* file each document, and
nothing else: not the names the filer gives working copies, not the
statuses the scanner writes. And the person's filing is the standard, not
the truth - a disagreement is a case to read, not automatically a bug.

Each ``(catalog, year)`` is built once, through ``create_template()`` and
``load_manifest()``, the way ``tests/test_irs_forms.py`` and
``tests/test_real_corpus.py`` build theirs, with the same two rules
lifted: the size floor, because a redacted or scanned document is small,
and the Period's year check, because the engagement year is what the
expectations file gives. Those two lifts have their own tests; leaving
them in would score the year check instead of the routing.

**Nothing identifying leaves this tool.** The report and the console
summary carry counts, identifiers from the catalog, and row numbers from
the expectations file - never a file name, never a folder name below the
corpus root, never a word of a document. A row number is that row's
position among the rows the expectations file lists, counting from one.

::

    python tools/backtest.py run <folder>        # route the corpus and score it
    python tools/backtest.py collect <folder>    # a skeleton expectations file to fill in
    python tools/backtest.py record              # record this report's agreement
    python tools/backtest.py check               # exit 1 if a report is below the baseline
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))   # run as a script: the package and the suite must import

from tracker.content_check import extract  # noqa: E402
from tracker.manifest import RequestItem  # noqa: E402
from tracker.router import route_file  # noqa: E402
from tracker.settings import COLUMN_EXPECTED, EXPECTATIONS_COLUMNS, EXPECTATIONS_FILENAME  # noqa: E402
from tracker.templates import FORM_TYPES, template_items  # noqa: E402
from tracker.validators import extension_of, is_ignored  # noqa: E402

#: The one number this tool commits: the agreement the firm's own
#: documents scored the last time a person ran the backtest at the office.
BASELINE_PATH = ROOT / "docs" / "backtest-baseline.json"
SCHEMA_VERSION = 1
#: Every catalog a row of the expectations file may name.
CATALOGS = tuple(entry["id"] for entry in FORM_TYPES)

#: The name every document is routed under, so the router's by-name
#: fallback can never read the client's name off the file.
NEUTRAL_STEM = "document"
#: How a blank ``expected`` column reads in the report: the document is
#: meant for a person, not for a request.
PARKS = "parks"
#: How many of the slowest documents the report names, by row number.
SLOWEST_COUNT = 10
#: The extra column ``collect`` writes for the person filling the file in:
#: the request folder the firm already filed the document into, which is
#: almost always the answer.
HINT_COLUMN = "hint"
COLLECT_COLUMNS = (*EXPECTATIONS_COLUMNS, HINT_COLUMN)

REPORT_FLAG = "--report"
EXPECTATIONS_FLAG = "--expectations"
OUT_FLAG = "--out"
OCR_FLAG = "--ocr"
CATALOG_FLAG = "--catalog"
YEAR_FLAG = "--year"

#: What the report is, said in the report itself.
REPORT_NOTE = (
    "How often the router files the firm's own documents where a person already filed them. "
    "No file name, no folder name and no word of any document is recorded here."
)
#: What the committed baseline is, said in the baseline itself.
BASELINE_NOTE = (
    "The agreement the firm's own sorted documents scored, measured at the office. "
    "No routing change may lower it."
)
#: The note the file ships with, before anybody has run the backtest.
UNMEASURED_NOTE = (
    "No backtest has been run against the firm's own documents yet, so there is no agreement "
    "to hold a routing change to. Run the backtest at the office and record it."
)
NO_BASELINE = (
    "No agreement is recorded: the owner has not yet run the backtest at the office. "
    "There is no baseline to hold this report to, and an unknown baseline is not a passing one."
)
NOTHING_ROUTED = "This report routed no document at all, so it cannot be held to the recorded baseline."
BELOW_BASELINE = "Agreement is BELOW the baseline: {agreement} now, {baseline} recorded."
AT_BASELINE = "Agreement holds: {agreement} now, {baseline} recorded."
RECORDED = "Recorded {agreement} over {documents} document(s) in {path}."


class BacktestError(Exception):
    """The backtest could not be run, read or scored."""


@dataclass(frozen=True, slots=True)
class Outcome:
    """What became of one row of the expectations file.

    ``row`` is the row's position in that file, counting from one, and is
    the only handle the report ever has on a document.
    """

    row: int
    catalog: str
    expected: str | None      # None: the document is meant to park
    got: str | None           # None: the router parked it, or never read it
    no_text: bool             # no text layer, and OCR was not allowed
    seconds: float


# ------------------------------------------------------------- the corpus ----


def _harness():
    """The suite's own reader of the expectations file, and its catalog builder.

    Imported here rather than at the top, the way ``tools/vocab_report.py``
    imports the suite's placements: the contract between a corpus and the
    code has one owner, and a tool that parsed the file a second way would
    be a second owner of it that could drift.
    """
    from tests.test_real_corpus import catalog_rows, read_expectations

    return catalog_rows, read_expectations


def _document_path(folder: Path, name: str, row: int) -> Path:
    """One row's document, checked to be a real file inside the corpus.

    Named by row number rather than by name: a missing document is a
    person's typo in the expectations file, and this message is the first
    place the name of a client's file would otherwise escape.
    """
    path = (folder / name).resolve()
    if folder.resolve() not in path.parents:
        raise BacktestError(f"row {row} names a path outside the corpus folder")
    if not path.is_file():
        raise BacktestError(f"row {row} names a document that is not in the corpus folder")
    return path


def _linked_under_a_neutral_name(source: Path, scratch: Path, row: int) -> Path:
    """``source``'s bytes under ``NEUTRAL_STEM``, in a folder of their own.

    A hard link where the file system allows one - nothing is read and
    nothing is written - and a copy where it does not (another volume, a
    file system with no links). Either way the router sees the real bytes
    under a name that says nothing, and the folders above it are this
    scratch folder's, never the firm's.
    """
    holder = scratch / str(row)
    holder.mkdir(parents=True, exist_ok=True)
    target = holder / f"{NEUTRAL_STEM}{source.suffix}"
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return target


def route_one(path: Path, rows: list[RequestItem], *, ocr: bool) -> tuple[str | None, bool]:
    """Where the router files ``path``, and whether it had no text layer at all.

    The text is read once, without OCR, and handed to the router; that is
    the reading the scanner makes of the same bytes later, so the two can
    never disagree. A scan is not routed unless OCR is allowed, because
    the only evidence left for it is the file name this tool hides - and
    when OCR is allowed nothing is handed over, so the router does its own
    reading and applies its own stricter rule to OCR's words.
    """
    reading = extract(path, ocr=False)
    if reading.needs_ocr:
        if not ocr:
            return None, True
        return route_file(path, rows).identifier, False
    return route_file(path, rows, text=reading.text).identifier, False


def route_corpus(folder: Path, expectations: Path, *, ocr: bool = False) -> tuple[list[Outcome], float]:
    """Route every row of ``expectations``, and say how long the whole pass took.

    The catalogs and the scratch links live in one temporary folder outside
    the repository, which goes away with the pass.
    """
    catalog_rows, read_expectations = _harness()
    rows = read_expectations(expectations)
    unknown = sorted({catalog for _, catalog, _, _ in rows} - set(CATALOGS))
    if unknown:
        raise BacktestError(f"no such catalog: {', '.join(unknown)}; the catalogs are {', '.join(CATALOGS)}")

    outcomes: list[Outcome] = []
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="backtest-") as scratch_name:
        scratch = Path(scratch_name)
        workspace = scratch / "catalogs"
        workspace.mkdir()
        built: dict = {}
        for row, (name, catalog, year, expected) in enumerate(rows, start=1):
            items = catalog_rows(workspace, catalog, year, built)
            link = _linked_under_a_neutral_name(_document_path(folder, name, row), scratch, row)
            began = time.perf_counter()
            got, no_text = route_one(link, items, ocr=ocr)
            outcomes.append(Outcome(
                row=row, catalog=catalog, expected=expected, got=got,
                no_text=no_text, seconds=time.perf_counter() - began,
            ))
    return outcomes, time.perf_counter() - started


# -------------------------------------------------------------- the score ----


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _key(identifier: str | None) -> str:
    return PARKS if identifier is None else identifier


def _blank_row() -> dict:
    return {"filed_here": 0, "parked": 0, "filed_elsewhere": 0}


def _confusions(counted: Counter) -> list[dict]:
    """(expected, filed, count), commonest first: where to start reading."""
    return [
        {"expected": expected, "got": got, "count": count}
        for (expected, got), count in sorted(counted.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def score(outcomes: list[Outcome], seconds: float) -> dict:
    """The report, as data: pure, so the tests can exercise it without a corpus.

    ``agreement`` is over the documents the router was actually asked
    about - a document with no text layer was never routed and is counted
    apart, so it neither flatters the agreement nor damns it. The shares
    are of the whole corpus, which is the number a person has in mind.
    """
    catalogs: dict[str, dict] = {}
    pairs: dict[str, Counter] = {}
    for outcome in outcomes:
        entry = catalogs.setdefault(outcome.catalog, {
            "documents": 0, "routed": 0, "agreed": 0, "agreement": None,
            "parked": 0, "parked_share": None, "no_text": 0, "no_text_share": None,
            "rows": {}, "confusions": [],
        })
        confusions = pairs.setdefault(outcome.catalog, Counter())
        entry["documents"] += 1
        expected = _key(outcome.expected)
        row = entry["rows"].setdefault(expected, _blank_row())
        if outcome.no_text:
            entry["no_text"] += 1
            continue
        entry["routed"] += 1
        if outcome.got is None:
            # Every document the router sends to a person, whether or not
            # that is where the person filed it: the parked share is how
            # much of a real drop somebody still has to read.
            entry["parked"] += 1
        if outcome.got == outcome.expected:
            entry["agreed"] += 1
            row["filed_here"] += 1
            continue
        confusions[(expected, _key(outcome.got))] += 1
        if outcome.got is None:
            row["parked"] += 1
        else:
            row["filed_elsewhere"] += 1
    for name, entry in catalogs.items():
        entry["agreement"] = _share(entry["agreed"], entry["routed"])
        entry["parked_share"] = _share(entry["parked"], entry["documents"])
        entry["no_text_share"] = _share(entry["no_text"], entry["documents"])
        entry["confusions"] = _confusions(pairs[name])

    documents = len(outcomes)
    routed = sum(e["routed"] for e in catalogs.values())
    agreed = sum(e["agreed"] for e in catalogs.values())
    parked = sum(e["parked"] for e in catalogs.values())
    no_text = sum(e["no_text"] for e in catalogs.values())
    everywhere: Counter = Counter()
    for counted in pairs.values():
        everywhere.update(counted)
    slowest = sorted(outcomes, key=lambda o: (-o.seconds, o.row))[:SLOWEST_COUNT]
    return {
        "schema": SCHEMA_VERSION,
        "note": REPORT_NOTE,
        "documents": documents,
        "routed": routed,
        "agreed": agreed,
        "agreement": _share(agreed, routed),
        "parked": parked,
        "parked_share": _share(parked, documents),
        "no_text": no_text,
        "no_text_share": _share(no_text, documents),
        "catalogs": {name: catalogs[name] for name in sorted(catalogs)},
        "confusions": _confusions(everywhere),
        "timing": {
            "seconds": round(seconds, 3),
            "seconds_per_document": round(seconds / documents, 3) if documents else None,
            "slowest": [{"row": o.row, "seconds": round(o.seconds, 3)} for o in slowest],
        },
    }


def _percent(share: float | None) -> str:
    return "n/a" if share is None else f"{share * 100:.1f}%"


def print_summary(data: dict, out=None) -> None:
    """The report as a person reads it off the console. Names nothing but numbers."""
    write = (out or sys.stdout).write
    timing = data["timing"]
    write(f"{data['documents']} document(s): {data['routed']} routed, "
          f"{data['no_text']} with no text layer ({_percent(data['no_text_share'])}).\n")
    write(f"Agreement: {_percent(data['agreement'])} "
          f"({data['agreed']} of {data['routed']} filed where a person filed them).\n")
    write(f"Parked: {data['parked']} ({_percent(data['parked_share'])} of the corpus).\n")
    write(f"Took {timing['seconds']}s, {timing['seconds_per_document']}s per document.\n")
    write("\nBy catalog:\n")
    for name, entry in data["catalogs"].items():
        write(f"  {name}: {entry['routed']} routed, {_percent(entry['agreement'])} agreement, "
              f"{entry['parked']} parked ({_percent(entry['parked_share'])}), "
              f"{entry['no_text']} with no text layer ({_percent(entry['no_text_share'])})\n")
        for identifier, row in sorted(entry["rows"].items()):
            write(f"      {identifier}: {row['filed_here']} here, {row['parked']} parked, "
                  f"{row['filed_elsewhere']} elsewhere\n")
    write("\nConfusions (expected -> filed), commonest first:\n")
    for pair in data["confusions"]:
        write(f"  {pair['expected']} -> {pair['got']}: {pair['count']}\n")
    if not data["confusions"]:
        write("  none\n")
    write(f"\nSlowest {SLOWEST_COUNT}, by row in the expectations file:\n")
    for slow in timing["slowest"]:
        write(f"  row {slow['row']}: {slow['seconds']}s\n")


# ------------------------------------------------------------- collecting ----


def accepted_extensions(items: list[RequestItem]) -> set[str] | None:
    """Every extension the catalog's rows accept; None where a row accepts any."""
    accepted: set[str] = set()
    for item in items:
        if not item.allowed_extensions:
            return None
        accepted.update(item.allowed_extensions)
    return accepted


def collectable(folder: Path, extensions: set[str] | None, skip: set[Path] | None = None) -> list[Path]:
    """The documents under ``folder`` a catalog would even look at, in a stable order.

    Recursive, because the firm files by request folder and the documents
    are in those folders, and the folder's name is the hint. An
    ``EXPECTATIONS_FILENAME`` kept beside the corpus is a spreadsheet of
    answers, not a client document, and neither is the file being written;
    a catalog that accepts spreadsheets would otherwise list both.
    """
    skip = skip or set()
    found = [
        path for path in folder.rglob("*")
        if path.is_file() and not is_ignored(path)
        and path.name != EXPECTATIONS_FILENAME and path.resolve() not in skip
        and (extensions is None or extension_of(path) in extensions)
    ]
    return sorted(found, key=lambda p: p.relative_to(folder).as_posix())


def write_skeleton(folder: Path, out: Path, catalog: str, year: int) -> int:
    """A row per document, ``COLUMN_EXPECTED`` blank for a person to fill in.

    Refuses to overwrite: the filled-in file is hours of a person's
    reading, and a second ``collect`` after a document arrived would erase
    every answer already given.
    """
    if out.exists():
        raise BacktestError(f"{out} already exists; a filled-in expectations file is never overwritten")
    if catalog not in CATALOGS:
        raise BacktestError(f"no such catalog: {catalog}; the catalogs are {', '.join(CATALOGS)}")
    extensions = accepted_extensions(template_items(catalog, year=year))
    documents = collectable(folder, extensions, skip={out.resolve()})
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLLECT_COLUMNS)
        for path in documents:
            writer.writerow([path.relative_to(folder).as_posix(), catalog, year, "", path.parent.name])
    return len(documents)


# --------------------------------------------------------- the one number ----


def load_report(path: Path) -> dict:
    """One report written by ``run``, checked to be one this tool wrote."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BacktestError(f"no report at {path}; run the backtest first") from None
    except (json.JSONDecodeError, OSError) as exc:
        raise BacktestError(f"could not read {path}: {exc}") from None
    if data.get("schema") != SCHEMA_VERSION:
        raise BacktestError(f"{path} is schema {data.get('schema')!r}, this tool writes {SCHEMA_VERSION}")
    return data


def load_baseline(path: Path | None = None) -> dict:
    path = path or BASELINE_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BacktestError(f"no baseline at {path}") from None
    except (json.JSONDecodeError, OSError) as exc:
        raise BacktestError(f"could not read {path}: {exc}") from None


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=1, sort_keys=True) + "\n").encode("utf-8"))


def record(report_path: Path, baseline_path: Path | None = None, today: date | None = None) -> dict:
    """Make this report's agreement the number every later change is held to."""
    data = load_report(report_path)
    if data["agreement"] is None:
        raise BacktestError(NOTHING_ROUTED)
    baseline = {
        "agreement": data["agreement"],
        "documents": data["routed"],
        "recorded": (today or date.today()).isoformat(),
        "note": BASELINE_NOTE,
    }
    write_json(baseline_path or BASELINE_PATH, baseline)
    return baseline


def check(report_path: Path, baseline_path: Path | None = None, out=None) -> int:
    """0 while the report holds the baseline, 1 below it.

    A baseline of ``None`` is not a passing one and is not a failing one:
    nobody has measured yet, and saying so is the honest answer. Reporting
    an unknown baseline as met would be the report this tool exists to
    prevent.
    """
    write = (out or sys.stdout).write
    data = load_report(report_path)
    baseline = load_baseline(baseline_path)
    recorded = baseline.get("agreement")
    if recorded is None:
        write(f"{NO_BASELINE}\n")
        return 0
    agreement = data["agreement"]
    if agreement is None:
        write(f"{NOTHING_ROUTED}\n")
        return 1
    said = {"agreement": _percent(agreement), "baseline": _percent(recorded)}
    if agreement < recorded:
        write(BELOW_BASELINE.format(**said) + "\n")
        return 1
    write(AT_BASELINE.format(**said) + "\n")
    return 0


# --------------------------------------------------------------------- CLI ----


def _outside_the_repository(path: Path) -> Path:
    """``path``, refused if it would land in the repository.

    A report of the firm's own documents is the firm's, and a file written
    into the tree is a file somebody commits.
    """
    resolved = path.expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise BacktestError(f"{OUT_FLAG} must name a path outside the repository: {resolved}")
    return resolved


def _corpus(folder: str) -> Path:
    path = Path(folder).expanduser()
    if not path.is_dir():
        raise BacktestError(f"not a folder: {path}")
    return path


def _cmd_run(ns: argparse.Namespace) -> int:
    folder = _corpus(ns.folder)
    expectations = Path(ns.expectations).expanduser() if ns.expectations else folder / EXPECTATIONS_FILENAME
    if not expectations.is_file():
        raise BacktestError(f"no expectations file at {expectations}; write one with the collect command")
    outcomes, seconds = route_corpus(folder, expectations, ocr=ns.ocr)
    data = score(outcomes, seconds)
    print_summary(data)
    if ns.out:
        out = _outside_the_repository(Path(ns.out))
        write_json(out, data)
        print(f"\nWrote {out}")
    return 0


def _cmd_collect(ns: argparse.Namespace) -> int:
    out = _outside_the_repository(Path(ns.out))
    written = write_skeleton(_corpus(ns.folder), out, ns.catalog, ns.year)
    print(f"Wrote {written} row(s) to {out}. Fill in {COLUMN_EXPECTED} for each; {HINT_COLUMN} is usually the answer.")
    return 0


def _cmd_record(ns: argparse.Namespace) -> int:
    baseline = record(Path(ns.report).expanduser())
    print(RECORDED.format(agreement=_percent(baseline["agreement"]),
                          documents=baseline["documents"], path=BASELINE_PATH.relative_to(ROOT)))
    return 0


def _cmd_check(ns: argparse.Namespace) -> int:
    return check(Path(ns.report).expanduser())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="route the firm's own documents and score the router")
    run.add_argument("folder", help="the folder holding the firm's sorted documents")
    run.add_argument(EXPECTATIONS_FLAG, default="", help=f"the expectations file (default: {EXPECTATIONS_FILENAME} in the folder)")
    run.add_argument(OUT_FLAG, default="", help="write the report here, outside the repository")
    run.add_argument(OCR_FLAG, action="store_true", help="let the router OCR a document with no text layer")

    collect = sub.add_parser("collect", help="write a skeleton expectations file for a person to fill in")
    collect.add_argument("folder", help="the folder holding the firm's sorted documents")
    collect.add_argument(CATALOG_FLAG, required=True, choices=CATALOGS, help="the catalog these documents are routed against")
    collect.add_argument(YEAR_FLAG, required=True, type=int, help="the engagement year")
    collect.add_argument(OUT_FLAG, required=True, help="write the skeleton here, outside the repository")

    for name, help_text in (("record", "make a report's agreement the committed baseline"),
                            ("check", "exit 1 if a report's agreement is below the baseline")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument(REPORT_FLAG, required=True, help="a report written by the run command")

    ns = parser.parse_args(argv)
    commands = {"run": _cmd_run, "collect": _cmd_collect, "record": _cmd_record, "check": _cmd_check}
    try:
        return commands[ns.command](ns)
    except BacktestError as exc:
        print(f"backtest: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
