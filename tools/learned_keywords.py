"""What the staff taught the router, in one list: the learned-keyword report.

When a person files a parked document from the review folder they may type a
keyword, and :func:`tracker.manifest.add_any_keyword` writes it into **that
one engagement's** manifest. It is the right place for it - the person is
deciding about this client's document, and the next such file routes itself
here - but it goes nowhere else. Fifty engagements hold fifty private
vocabularies, invisible to each other and to the catalog in
``tracker/templates.py``, which is the only vocabulary the suite tests
(``tests/test_catalog.py``, ``tests/test_irs_forms.py``,
``docs/vocab-coverage.md``). A keyword five clients had to teach separately
is a keyword the catalog is missing, and nobody can see that from inside one
engagement.

This is that list, read once a season: every keyword staff have taught the
router across every engagement under the clients root, grouped by request
row, so the recurring ones become catalog commits the suite then defends.

**It only reads.** No lock is taken (the report is not a pass and must never
queue behind, or block, a scheduled one), no manifest is written, no file is
moved and no unreadable sidecar is quarantined - the readers' ``quarantine=False``,
as the reminder and the rollover pass it. The one thing written is the
optional report file, which is refused inside the repository: client folder
names would otherwise land in a commit.

**What "learned" means, and the soft spot in it.** The Engagement sheet does
not record which form type the engagement was created from, so a manifest row
cannot be compared against *its* catalog. It is compared instead against every
catalog in ``FORM_TYPES`` holding a row with the same Identifier and Document,
and the report names which ones matched; a keyword is learned when the
manifest carries it and no matching catalog row does. Comparing against all of
them is the conservative direction: a keyword any catalog already carries on
that row is not reported, so the list under-reports rather than sending
somebody after a keyword that is already committed. A row no catalog holds at
all is a custom request, listed apart with all of its keywords - those are
candidates for the catalog too, and there is nothing to compare them against.

Keywords are grouped and shown in lower case, because that is how the matcher
reads them: "Trial Balance" typed by one person and "trial balance" by another
are one keyword, and counting them apart would hide exactly the repetition
this report exists to find.

**The counts alone, by default.** An engagement folder name is a client's
name, so the default output carries only how many engagements typed each
keyword; ``--engagements`` names them, for the person deciding whether a
keyword is one client's habit or the firm's. An engagement whose manifest
cannot be read is named either way, with its problem: a report that quietly
skipped it would say the firm has taught nothing where it may have taught
most.

``--lint`` runs each candidate over the fifty-two IRS forms in ``tests/irs/`` the
way ``tools/vocab_report.py`` runs the catalog's own keywords - the same
extraction, the same :func:`tracker.content_check.says`, about thirty seconds -
and reports which forms would say it. Where a form that says it belongs
somewhere else in a matching catalog, the keyword is marked ``would misfile``
and is not a candidate for promotion: committing it would break a placement
the suite already asserts. A custom row has no catalog to disagree with, so
its keywords are only ever reported as said, never as misfiling.

::

    python tools/learned_keywords.py                     # the clients root the settings file names
    python tools/learned_keywords.py "D:\\Clients"       # or one named here
    python tools/learned_keywords.py --engagements       # name the engagements, not just count them
    python tools/learned_keywords.py --lint              # mark the ones that would misfile a known form
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(ROOT), str(ROOT / "tools")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)   # run as a script: the package, the suite and vocab_report must import

from vocab_report import corpus_documents, shipped_catalogs  # noqa: E402

from tracker.content_check import dominant_forms, says  # noqa: E402
from tracker.manifest import (  # noqa: E402
    COL_ANY_KEYWORDS,
    COL_REQUIRED_KEYWORDS,
    ManifestError,
    RequestItem,
    label_for,
    load_manifest,
    pending_updates,
    with_pending,
)
from tracker.registry import SKIP_ROLLED_FORWARD, RegistryError, discover_engagements  # noqa: E402
from tracker.scaffold import MANIFEST_FILENAME  # noqa: E402
from tracker.settings import SET_ROOT_HINT, SettingsError, clients_root, settings_path  # noqa: E402

#: How an engagement the run would no longer chase is flagged where it is named.
FLAG_INACTIVE = "inactive"
#: How a keyword's reach is said, per engagement count and per corpus form.
CARRIED_BY = "{n} engagement(s)"
MISFILE = "would misfile: {form} {placement}"
FILES_AS = "files as {identifier} in the {catalog} catalog"
PARKS = "parks in the {catalog} catalog"
SAID_BY = "said by: {forms}"
#: What a row with no matching catalog row is called, and what is said of it.
CUSTOM_ROW = "no catalog holds this row"
IN_CATALOGS = "in the {catalogs} catalog(s)"
NONE = "- none"


class LearnedKeywordsError(Exception):
    """The report could not be built, or was asked to write where it must not."""


# ------------------------------------------------------------------ inputs ----


def _key(identifier: str, document: str) -> tuple[str, str]:
    """How a request row is matched to a catalog row: its identifier and document, without case."""
    return identifier.strip().lower(), document.strip().lower()


def catalog_index() -> dict[tuple[str, str], dict[str, frozenset[str]]]:
    """Every shipped catalog row as ``(identifier, document) -> catalog -> its keywords``.

    Built the way an engagement gets a catalog - through ``create_template()``
    and ``load_manifest()``, which is what ``shipped_catalogs()`` does - so the
    comparison is against the rows a manifest is actually written with, not
    against the spec dicts behind them.
    """
    index: dict[tuple[str, str], dict[str, frozenset[str]]] = {}
    for form, rows in shipped_catalogs().items():
        for row in rows:
            index.setdefault(_key(row.identifier, row.document), {})[form] = frozenset(keywords_of(row))
    return index


def keywords_of(item: RequestItem) -> list[str]:
    """Both keyword columns of one row, lower-cased, in order, without repeats."""
    seen: dict[str, None] = {}
    for keyword in (*item.required_keywords, *item.any_keywords):
        cleaned = keyword.strip().lower()
        if cleaned:
            seen.setdefault(cleaned)
    return list(seen)


def manifest_rows(folder: Path) -> list[RequestItem]:
    """One engagement's request rows, with any deferred statuses overlaid.

    The overlay changes no keyword - it carries the scanner's columns - but a
    reader of a manifest reads it the way every other reader does, and
    ``quarantine=False`` is the half that matters here: looking must never
    move a sidecar aside.
    """
    manifest = folder / MANIFEST_FILENAME
    return with_pending(load_manifest(manifest), pending_updates(manifest, quarantine=False))


# ------------------------------------------------------------------ report ----


@dataclass(slots=True)
class Row:
    """One request row across every engagement that taught it something."""

    identifier: str
    document: str
    #: The catalogs holding this row; empty for a custom request.
    catalogs: tuple[str, ...] = ()
    #: keyword -> the engagements carrying it, in the order they were walked.
    keywords: dict[str, list[str]] = field(default_factory=dict)
    #: keyword -> what the corpus says about it; only filled by ``--lint``.
    notes: dict[str, list[str]] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return label_for(self.identifier, self.document)

    @property
    def count(self) -> int:
        """How many engagement-keyword pairs this row holds; what it is sorted on."""
        return sum(len(holders) for holders in self.keywords.values())


@dataclass(slots=True)
class Report:
    """Every learned keyword under one clients root."""

    root: Path
    engagements: int = 0
    read: int = 0
    inactive: int = 0
    rolled_forward: int = 0
    rows: list[Row] = field(default_factory=list)
    custom: list[Row] = field(default_factory=list)
    #: (engagement folder, why it could not be read) - never a silent skip.
    problems: list[tuple[str, str]] = field(default_factory=list)
    linted: bool = False

    @property
    def learned(self) -> int:
        return sum(len(row.keywords) for row in self.rows)

    @property
    def custom_keywords(self) -> int:
        return sum(len(row.keywords) for row in self.custom)


def _engagement_label(engagement) -> str:
    """The engagement's folder name, flagged when the run would no longer chase it."""
    if engagement.superseded_by:
        return f"{engagement.path.name} ({SKIP_ROLLED_FORWARD.format(successor=engagement.superseded_by)})"
    if not engagement.active:
        return f"{engagement.path.name} ({FLAG_INACTIVE})"
    return engagement.path.name


def _by_count(row: Row) -> tuple[int, str, str]:
    """Rows in the order the report lists them: the most-taught first, then by row."""
    return -row.count, row.identifier, row.document


def collect(root: Path | str) -> Report:
    """Walk every engagement under ``root`` and gather what its manifest knows and the catalog does not."""
    registry = discover_engagements(root)
    index = catalog_index()
    report = Report(root=Path(registry.source), engagements=len(registry.engagements))
    learned: dict[tuple[str, str], Row] = {}
    custom: dict[tuple[str, str], Row] = {}

    for engagement in registry.engagements:
        if engagement.problem:
            report.problems.append((str(engagement.path), engagement.problem))
            continue
        try:
            rows = manifest_rows(engagement.path)
        except (ManifestError, OSError) as exc:
            report.problems.append((str(engagement.path), str(exc)))
            continue
        report.read += 1
        if engagement.superseded_by:
            report.rolled_forward += 1
        elif not engagement.active:
            report.inactive += 1
        label = _engagement_label(engagement)
        for item in rows:
            key = _key(item.identifier, item.document)
            known = index.get(key)
            if known is None:
                row = custom.setdefault(key, Row(item.identifier, item.document))
                fresh = keywords_of(item)
            else:
                row = learned.setdefault(key, Row(item.identifier, item.document, tuple(sorted(known))))
                carried = frozenset().union(*known.values())
                fresh = [k for k in keywords_of(item) if k not in carried]
            for keyword in fresh:
                holders = row.keywords.setdefault(keyword, [])
                if label not in holders:
                    holders.append(label)

    report.rows = sorted((row for row in learned.values() if row.keywords), key=_by_count)
    report.custom = sorted(custom.values(), key=_by_count)
    return report


# -------------------------------------------------------------------- lint ----


def _placement(where: str | None, catalog: str) -> str:
    return PARKS.format(catalog=catalog) if where is None else FILES_AS.format(identifier=where, catalog=catalog)


def lint(report: Report) -> Report:
    """Mark every candidate the IRS corpus says, and refuse the ones that would misfile.

    The corpus and the reading are ``tools/vocab_report.py``'s: the
    fifty-two forms in ``tests/irs/`` extracted once, then each keyword tested with
    ``says()`` against the whole text, which is how the router and the scanner
    read. A form that says the keyword and belongs elsewhere in one of the
    row's matching catalogs is a placement ``tests/test_irs_forms.py`` already
    asserts, so promoting that keyword would turn a green suite red - or worse,
    would not, and would misfile the form in the field.
    """
    prepared = [(doc, doc.text.lower(), dominant_forms(doc.text)) for doc in corpus_documents()]
    for row in (*report.rows, *report.custom):
        for keyword in row.keywords:
            misfiles: list[str] = []
            said: list[str] = []
            for doc, low, dominant in prepared:
                if not says(low, keyword, dominant):
                    continue
                wrong = [form for form in row.catalogs
                         if form in doc.expected and doc.expected[form] != row.identifier]
                if wrong:
                    misfiles += [MISFILE.format(form=doc.name, placement=_placement(doc.expected[form], form))
                                 for form in wrong]
                else:
                    said.append(doc.name)
            notes = list(misfiles)
            if said:
                notes.append(SAID_BY.format(forms=", ".join(said)))
            row.notes[keyword] = notes
    report.linted = True
    return report


# ---------------------------------------------------------------- markdown ----


def summary_line(report: Report) -> str:
    return (
        f"{report.engagements} engagement(s) · {report.read} read "
        f"({report.inactive} {FLAG_INACTIVE}, {report.rolled_forward} rolled forward) · "
        f"{report.learned} learned keyword(s) on {len(report.rows)} row(s) · "
        f"{report.custom_keywords} keyword(s) on {len(report.custom)} custom row(s) · "
        f"{len(report.problems)} problem(s)"
    )


def _keyword_lines(row: Row, *, engagements: bool) -> list[str]:
    lines = []
    for keyword, holders in sorted(row.keywords.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        note = "; ".join(row.notes.get(keyword, ()))
        lines.append(f"- `{keyword}` — {CARRIED_BY.format(n=len(holders))}" + (f" — {note}" if note else ""))
        if engagements:
            lines += [f"  - {holder}" for holder in holders]
    return lines


def render(report: Report, *, engagements: bool = False) -> str:
    """The report as people read it. ``engagements`` names the folders; the default counts them."""
    lines = [
        "# Learned keywords",
        "",
        f"Keywords a person typed into one engagement's {COL_REQUIRED_KEYWORDS} or {COL_ANY_KEYWORDS} "
        "that no catalog row carrying the same identifier and document carries, grouped by request row. "
        "Nothing was written, moved or locked to make this: the manifests were only read.",
        "",
        f"Clients root: {report.root}",
        "",
        summary_line(report),
        "",
    ]
    if not report.linted:
        lines += ["No keyword here has been run against the IRS forms; a promoted keyword is a catalog "
                  "commit, and the suite is what decides whether it misfiles one.", ""]

    lines += ["## Learned keywords by row", "",
              "Rows first that carry the most. A keyword here is a candidate for "
              "`tracker/templates.py`, where the suite would then defend it.", ""]
    for row in report.rows:
        lines += [f"### {row.label} — {IN_CATALOGS.format(catalogs=', '.join(row.catalogs))}", ""]
        lines += _keyword_lines(row, engagements=engagements)
        lines.append("")
    if not report.rows:
        lines += [NONE, ""]

    lines += ["## Custom rows", "",
              "Requests somebody added by hand, which no catalog knows at all. Every keyword they "
              "carry was typed by a person, so all of them are listed.", ""]
    for row in report.custom:
        lines += [f"### {row.label} — {CUSTOM_ROW}", ""]
        lines += _keyword_lines(row, engagements=engagements)
        lines.append("")
    if not report.custom:
        lines += [NONE, ""]

    lines += ["## Problems", "",
              "Engagements whose manifest could not be read. Whatever they have taught the router is "
              "not in the lists above.", ""]
    lines += [f"- {folder} — {problem}" for folder, problem in report.problems] or [NONE]
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI ----


def out_path(named: str) -> Path:
    """Where the report may be written: anywhere but inside the repository.

    A report names client folders when it is asked to, and a path under the
    tree is one `git add -A` away from a commit that carries them.
    """
    path = Path(named).expanduser()
    resolved = (Path.cwd() / path).resolve() if not path.is_absolute() else path.resolve()
    if resolved == ROOT or resolved.is_relative_to(ROOT):
        raise LearnedKeywordsError(f"refusing to write inside the repository: {resolved}")
    return resolved


def chosen_root(named: str) -> Path:
    """The clients root to walk: the one named, else the settings file's."""
    if named:
        return Path(named)
    configured = clients_root()
    if configured is None:
        raise LearnedKeywordsError(
            f"no clients root given and none in {settings_path()}; set one with: {SET_ROOT_HINT}"
        )
    return configured


def main(argv: list[str] | None = None) -> int:
    # The report prints folder names and the separators this file words its
    # counts with, and a console that is not UTF-8 must not turn a finished
    # report into a traceback, as the runner's does not.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(
        prog="python tools/learned_keywords.py",
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("root", nargs="?", default="",
                        help="the folder the firm keeps its clients in (default: the settings file's)")
    parser.add_argument("--out", default="",
                        help="write the report to this file instead of printing it; never inside the repository")
    parser.add_argument("--engagements", action="store_true",
                        help="name the engagement folders carrying each keyword (they carry client names)")
    parser.add_argument("--lint", action="store_true",
                        help="run each keyword over the IRS forms in tests/irs/ and mark one that would misfile")
    ns = parser.parse_args(argv)

    try:
        target = out_path(ns.out) if ns.out else None
        report = collect(chosen_root(ns.root))
        if ns.lint:
            lint(report)
        text = render(report, engagements=ns.engagements)
    except (LearnedKeywordsError, RegistryError, SettingsError) as exc:
        print(f"learned_keywords: {exc}", file=sys.stderr)
        return 2

    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
        print(f"Wrote {target}\n{summary_line(report)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
