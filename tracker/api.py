"""JSON bridge for the desktop app (Electron) — python -m tracker.api <command>.

Commands print a single JSON object to stdout and exit 0, or {"error": ...}
and exit 1. All real logic lives in the tracker package; this module only
serializes it, so the UI can never disagree with the scanner.

Commands:
  list      every engagement under the clients root, plus the vocabulary the app shows
  templates the form catalog and the calendar's default tax year
  create    a new engagement from the wizard's spec (JSON on stdin)
  state     current manifest rows, the index, the triaged review queue, the
            one summary, useful paths
  priors    list engagements a new year could be rolled forward from
  rollover  build next year's list from a returning client's prior year
  scan      one pass, exactly as the scheduled run makes it (no draft)
  assign    file one Needs Review document under a request (a person's call)
  dismiss   record that no request asks for one Needs Review document
  unfile    send one filed document back to Needs Review (a person's call)
  check     check_manifest() on demand, problems named by row
  settings / set-root      where the clients live (the settings file beside the app)
  install-schedule         register the daily job for that same folder
  unlock    clear a stale engagement lock (a fresh one is refused)
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path

from tracker import STANDING_RULES, review
from tracker.content_check import EVIDENCE_PLACES, EVIDENCE_RULES
from tracker.filer import (
    _CANDIDATE_SEP,
    DUPLICATE,
    FILED,
    INDEX_FILENAME,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    FilingError,
    IndexEntry,
    assign_review_file,
    dismiss_review_file,
    read_index,
    unfile_document,
)
from tracker.locking import STALE_LOCK_SECONDS, clear_stale_lock, lock_status
from tracker.manifest import (
    DEFAULT_EXTENSIONS,
    EXPECTED_PATTERN,
    ISO_DATE_HINT,
    UNSCANNED_LABEL,
    YEAR_MAX,
    YEAR_MIN,
    EngagementInfo,
    ManifestError,
    Override,
    Status,
    check_manifest,
    check_tax_year,
    create_template,
    load_engagement_info,
    load_manifest,
    pending_updates,
    summarize,
    with_pending,
    write_engagement_info,
    write_text_atomically,
)
from tracker.page import slug
from tracker.registry import RegistryError, discover_engagements, engagement_dirs, engagement_from
from tracker.rollover import (
    CARRIED_SHEET,
    ORIGIN_PRIOR,
    UNKNOWN_YEAR_LABEL,
    carry_engagement_info,
    detect_year,
    next_tax_year,
    roll_forward,
    write_rollover_manifest,
)
from tracker.runner import (
    DRAFT_WEEKDAY,
    LOG_FILENAME,
    REMINDERS_NEVER,
    STATUS_PAGE_FILENAME,
    WEEKDAY_NAMES,
    EngagementRun,
    RunReport,
    append_log,
    run_engagement,
    status_report,
    write_status_page,
)
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    SHARED_DIR_NAME,
    sanitize_component,
    scaffold_engagement,
)
from tracker.scanner import ScanLockedError, scan_engagement
from tracker.scheduling import (
    DEFAULT_REPEAT_MINUTES,
    DEFAULT_START,
    SCHEDULE_XML_ENCODING,
    SCHEDULE_XML_FILENAME,
    TASK_NAME,
    install_task,
    is_scheduling_host,
    task_scheduler_xml,
)
from tracker.settings import (
    EXAMPLE_ROOT,
    SET_ROOT_HINT,
    SettingsError,
    clients_root,
    firm,
    product_name,
    set_clients_root,
    set_firm,
    settings_dir,
    settings_path,
)
from tracker.templates import (  # the catalog; re-exported for the wizard
    EXTENSION_DEFAULT_NOTE,
    FORM_LABEL_PATTERN,
    FORM_TEMPLATES,
    FORM_TYPES,
    KEYWORD_DEFAULT_NOTE,
    PERIOD_PATTERN,
    YEAR_NOTE,
    base_year,
    default_tax_year,
    item_from_spec,
    require_form,
    shift_item,
    template_items,
)
from tracker.view import (
    VIEW_FILENAME,
    VIEW_LABEL,
    VIEW_OPEN_LABEL,
    VIEW_STATES,
    view_state,
)

log = logging.getLogger("tracker.api")

#: The folder the app runs from (the repository from source, beside the
#: executable when frozen) - the same answer tracker.settings gives.
REPO_ROOT = settings_dir()
def _root() -> Path:
    """The clients root from the settings file - the one place it is kept."""
    root = clients_root()
    if root is None:
        raise ManifestError(
            f"Tell the app where your clients live first (Settings, or `{SET_ROOT_HINT}`)"
        )
    return root

# ----------------------------------------------------------------- commands ----


#: The one flag the app passes: which engagement a command is about.
ENGAGEMENT_FLAG = "--engagement"
#: What a new client is called in the name preview before a name is typed.
NEW_CLIENT_PLACEHOLDER = "New"
#: What the Needs Review card calls the decisions a person makes there and
#: on what is already filed, and what it asks them for. The renderer shows
#: these; it types none of them.
DISMISS_LABEL = "Not requested"
DISMISS_NOTE_HINT = "why nothing asks for it (optional)"
DISMISSED_HEADING = "Not requested ({n})"
FILE_LABEL = "File it"
FILE_ANYWAY_LABEL = "File it anyway"
UNFILE_LABEL = "Unfile"
UNFILE_NOTE_HINT = "why it is coming back (optional)"
FILED_HEADING = "Filed documents ({n})"
#: How the picker divides itself: the triaged shortlist first, under the
#: first heading, then every other request under the second. The two are
#: headings, not decisions - a person may still pick anything on the list.
SUGGESTED_HEADING = "Suggested"
OTHER_REQUESTS_HEADING = "Other requests"


def _new_engagement_dir(name: str) -> Path:
    """Where a new engagement goes, refused if the folder is already there
    or if ``name`` would put it anywhere but straight under the root."""
    root = _root()
    engagement = root / name
    if engagement.resolve().parent != root.resolve():
        raise ManifestError(f"'{name}' is not a folder name")
    if engagement.exists():
        raise ManifestError(f"An engagement named '{name}' already exists")
    return engagement


def _engagement_dir(argv: list[str]) -> Path:
    """The engagement a command is about: ``ENGAGEMENT_FLAG <folder>``.

    A flag with nothing after it, or an empty folder, gets the same sentence
    as no flag at all (it used to be a bare IndexError). Once a clients root
    is set, the folder must lie under it: the app only ever names folders
    the root listed, so anything else is a mistake, not a request.
    """
    hint = f"Pick an engagement first ({ENGAGEMENT_FLAG} <folder>)"
    if ENGAGEMENT_FLAG not in argv:
        raise ManifestError(hint)
    position = argv.index(ENGAGEMENT_FLAG) + 1
    given = argv[position].strip() if position < len(argv) else ""
    if not given:
        raise ManifestError(hint)
    return _under_root(Path(given))


def _under_root(folder: Path) -> Path:
    """``folder`` if it lies under the clients root, else a ManifestError.

    Checked whenever a root is *set*, whether or not the folder it names is
    reachable right now: an unplugged drive is not a licence to read from
    anywhere. Resolved on both sides, so ``..``, a junction out of the root
    and a case difference are all seen for what they are.
    """
    root = clients_root()
    if root is not None:
        try:
            folder.resolve().relative_to(root.resolve())
        except ValueError:
            raise ManifestError(f"{folder} is not under the clients root {root}") from None
    return folder


#: How a new engagement is named when nobody types a name. The renderer
#: formats the same pattern, so the wizard's preview and the folder agree.
NAME_PATTERN = "{client} " + PERIOD_PATTERN + " {form}"
ROLLOVER_NAME_PATTERN = "{prior} - {year}"


def form_label(form: str) -> str:
    """``Form 1120-S`` for ``1120S``: the one id -> label map is FORM_TYPES."""
    for entry in FORM_TYPES:
        if entry["id"] == form:
            return entry["label"]
    return FORM_LABEL_PATTERN.format(form=form) if form else "Engagement"


def default_engagement_name(client: str, year: int, form: str) -> str:
    return NAME_PATTERN.format(client=client or NEW_CLIENT_PLACEHOLDER, year=year,
                               form=form_label(form)).strip()


#: A word as a class name, from the module that owns how the firm's pages
#: spell one, so a status chip in the app and a status badge on the view
#: are classed the same way by the same code.
_slug = slug


def standing_rules() -> list[dict]:
    """The package's standing rules with the folder names filled in."""
    names = {"shared": SHARED_DIR_NAME, "pbc": PBC_DIR_NAME, "review": REVIEW_DIR_NAME,
             "index": INDEX_FILENAME}
    return [{"headline": headline, "detail": detail.format(**names)}
            for headline, detail in STANDING_RULES]


def _vocab() -> dict:
    """Every word and number the renderer shows or compares, from its owner.

    The app never types a status, an override, a decision, a default or a
    sentence pattern of its own: it reads this once and derives everything
    (chip classes from the status key, waived from the override value, the
    parked list from the decision value, the picker from candidates).
    """
    return {
        "product": product_name(),
        "firm": firm(),
        "statuses": [{"value": status, "key": _slug(status)} for status in Status.ALL],
        "unscanned_label": UNSCANNED_LABEL,
        "unscanned_key": _slug(UNSCANNED_LABEL),
        "overrides": {"accepted": Override.ACCEPTED, "waived": Override.WAIVED},
        # The key a decision is looked up by is the app's handle on it, not
        # the word: NOT_REQUESTED is keyed by the action that writes it,
        # because the renderer may not carry the word "Requested" in any
        # form - it is UNSCANNED_LABEL, a status, and the guard that keeps
        # the app from typing a status of its own reads the whole file.
        "decisions": {"filed": FILED, "needs_review": NEEDS_REVIEW, "duplicate": DUPLICATE,
                      "dismissed": NOT_REQUESTED},
        "review_labels": {"dismiss": DISMISS_LABEL, "dismiss_note": DISMISS_NOTE_HINT,
                          "dismissed_heading": DISMISSED_HEADING, "file": FILE_LABEL,
                          "file_anyway": FILE_ANYWAY_LABEL,
                          "unfile": UNFILE_LABEL, "unfile_note": UNFILE_NOTE_HINT,
                          "filed_heading": FILED_HEADING,
                          "suggested": SUGGESTED_HEADING,
                          "other_requests": OTHER_REQUESTS_HEADING},
        # Every word tracker.review gives the card, from the module that
        # owns it: what is said when the evidence suggests nothing, the one
        # separator between an identifier and what follows it (the reason
        # sentence and the picker's entries both use it), the words each
        # evidence place is named by - the record travels raw in the index,
        # so anything labelling a place labels it from here - and the cap
        # the shortlist's length keeps.
        "triage": {"nothing_suggested": review.NOTHING_SUGGESTED,
                   "identifier_separator": review.IDENTIFIER_SEPARATOR,
                   "places": dict(review.PLACE_WORDS),
                   "max_suggestions": review.MAX_SUGGESTIONS},
        "default_extensions": ", ".join(DEFAULT_EXTENSIONS),
        "expected_pattern": EXPECTED_PATTERN,
        "period_pattern": PERIOD_PATTERN,
        "origin_prior": ORIGIN_PRIOR,
        "unknown_year_label": UNKNOWN_YEAR_LABEL,
        "candidate_separator": _CANDIDATE_SEP,
        # Every word an evidence line can carry, from the module that owns
        # it: the app labels a rule and a place, and types neither.
        "evidence": {"rules": list(EVIDENCE_RULES), "places": list(EVIDENCE_PLACES)},
        "year_note": YEAR_NOTE,
        "extension_default_note": EXTENSION_DEFAULT_NOTE,
        "carried_sheet": CARRIED_SHEET,
        "pbc_dir": PBC_DIR_NAME,
        "name_pattern": NAME_PATTERN,
        "rollover_name_pattern": ROLLOVER_NAME_PATTERN,
        "new_client_placeholder": NEW_CLIENT_PLACEHOLDER,
        "year_min": YEAR_MIN,
        "year_max": YEAR_MAX,
        "example_root": EXAMPLE_ROOT,
        "engagement_flag": ENGAGEMENT_FLAG,
        "commands": sorted(COMMANDS),
        "rules": standing_rules(),
        "schedule": {
            "start": DEFAULT_START,
            "every": DEFAULT_REPEAT_MINUTES,
            "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
            "task_name": TASK_NAME,
        },
        "keyword_default_note": KEYWORD_DEFAULT_NOTE,
        # The page a pass regenerates, the three words that say whether the
        # one on disk still describes the engagement, and what the button
        # that opens it says. The app compares nothing itself and types
        # neither label: it shows the words the API sends and derives the
        # chip's class from one of them, exactly as it does a status.
        "view": {"label": VIEW_LABEL, "open": VIEW_OPEN_LABEL, "states": list(VIEW_STATES)},
    }


def _lock_payload(engagement: Path) -> dict | None:
    status = lock_status(engagement)
    if status is None:
        return None
    return {
        "started": status.started,
        "age_minutes": int(status.age_seconds // 60),
        "stale": status.stale,
        "stale_after_minutes": STALE_LOCK_SECONDS // 60,
    }


def _info_payload(info: EngagementInfo) -> dict:
    """The Engagement sheet as JSON: every field, with dates as ISO text."""
    payload = asdict(info)
    payload["due"] = info.due.isoformat() if info.due else ""
    return payload


def _info_from_spec(spec: dict, *, carry: EngagementInfo | None = None) -> EngagementInfo:
    """The Engagement sheet for a new engagement: what the wizard sent, over
    what last year's sheet said (rollover), over the firm default.

    The engagement's name is not written: the folder is the name, and a
    copy on the sheet would drift the first time the folder was renamed.
    """
    base = carry or EngagementInfo()

    def text(key: str, fallback: str) -> str:
        value = spec.get(key)
        return str(value).strip() if value not in (None, "") else fallback

    due_raw = str(spec.get("due", "") or "").strip()
    if due_raw:
        try:
            due = dt.date.fromisoformat(due_raw)
        except ValueError:
            raise ManifestError(f"Due date must be {ISO_DATE_HINT}, got {due_raw!r}") from None
    else:
        due = base.due
    return replace(
        base,
        client=text("client", base.client),
        link=text("link", base.link),
        due=due,
        sender=text("sender", base.sender),
        firm=text("firm", base.firm or firm()),
        reminders=bool(spec.get("reminders", base.reminders)),
    )


def _tax_year(given, default: int | None = None) -> int | None:
    """The tax year a spec asks for: a whole number within the bounds the
    wizard shows (``YEAR_MIN``..``YEAR_MAX``), or ``default`` when none
    was given. The renderer's number box only suggests the bounds."""
    if given in (None, ""):
        return default
    try:
        year = int(given)
    except (TypeError, ValueError):
        raise ManifestError(f"Tax year must be a whole number, got {given!r}") from None
    return check_tax_year(year)


def _engagement_name(requested: str, fallback: str) -> str:
    """A folder name from what the user typed, or the fallback if nothing usable is left."""
    name = sanitize_component(requested.strip())
    return name if any(ch.isalnum() for ch in name) else sanitize_component(fallback)


def _evidence_payload(entry: IndexEntry) -> dict[str, list[dict]]:
    """One index row's Evidence cell as JSON: candidate -> what was found.

    Parsed here, by the one parser that owns the cell's shape
    (:func:`tracker.content_check.parse_evidence`), so the renderer never
    splits a string of the tracker's on separators of its own.
    """
    return {identifier: [asdict(evidence) for evidence in found]
            for identifier, found in entry.evidence_record.items()}


def _triage_payload(triaged: review.Triage) -> dict:
    """One parked file's shortlist as JSON, in triage order.

    The row itself is already in ``state["index"]``; what travels here is
    the part only :mod:`tracker.review` knows, joined back to that row by
    ``pbc_location`` - the same handle every review command takes.

    ``reason`` ships **whole, with its leading identifier**, exactly as
    :class:`tracker.review.Suggestion` built it. One owner: review.py
    writes the sentence and nothing downstream re-assembles it from
    ``identifier`` and a separator of its own. The identifier travels
    beside it as data too, because that is what ``assign`` is given, and a
    caller must never have to read it back out of a sentence.
    """
    return {
        "original_name": triaged.entry.original_name,
        "pbc_location": triaged.entry.pbc_location,
        "shortlist": [asdict(suggestion) for suggestion in triaged.shortlist],
        "genre": triaged.genre,
        "group": triaged.group,
    }


def _state(engagement: Path) -> dict:
    manifest_path = engagement / MANIFEST_FILENAME
    root = clients_root()
    # Showing the engagement is a read: nothing is moved, not even a sidecar
    # that cannot be parsed - the next real run is what moves it aside.
    deferred = pending_updates(manifest_path, quarantine=False)
    items = with_pending(load_manifest(manifest_path), deferred)
    info = load_engagement_info(manifest_path)
    summary = summarize(items)
    entries = read_index(engagement / INDEX_FILENAME, quarantine=False)
    view_path = engagement / VIEW_FILENAME
    return {
        "pending_statuses": len(deferred),
        # The derived page, and whether it still describes this engagement.
        # Reading the stamp takes no lock and tolerates another program
        # holding it, so showing the engagement stays a read.
        "view": {"state": view_state(engagement), "path": str(view_path)},
        "engagement": _info_payload(info),
        "lock": _lock_payload(engagement),
        "summary": {
            "line": summary.line, "counts": summary.counts, "total": summary.total,
            "received": summary.received, "outstanding": summary.outstanding,
            "waived": summary.waived, "unscanned": summary.unscanned,
        },
        "items": [
            asdict(i) | {"received_date": i.received_date.isoformat() if i.received_date else None}
            for i in items
        ],
        # The index's packed cells travel as data, not as text the app
        # would have to parse: the candidates as a list, the evidence as
        # the record it was written from keyed by candidate identifier,
        # and every working copy's name as a list - one name for nearly
        # every row, and one per request for a page decision 94 filed
        # under several, so the app shows each destination without
        # knowing a separator or how to cut a path.
        "index": [asdict(e) | {"filed_as": e.filed_as, "filed_names": e.filed_names,
                               "candidates": e.candidate_list,
                               "evidence": _evidence_payload(e)}
                  for e in entries],
        # The review queue, triaged: one entry per parked file, its
        # shortlist best-first with the sentence behind each suggestion.
        # There is no `review` command - the card draws from the one state
        # the app already reads - and the manifest and the index are handed
        # to triage() so each is read once for the whole screen.
        "review": [_triage_payload(t)
                   for t in review.triage(engagement, items=items, entries=entries)],
        "paths": {
            "engagement": str(engagement),
            "shared": str(engagement / SHARED_DIR_NAME),
            "pbc": str(engagement / SHARED_DIR_NAME / PBC_DIR_NAME),
            "prepared": str(engagement / PREPARED_DIR_NAME),
            "index": str(engagement / INDEX_FILENAME),
            "manifest": str(manifest_path),
            # The one a person is meant to open. Named here as well as
            # above because the shell opens only paths this map holds.
            "view": str(view_path),
            # The practice's page, not this engagement's: it lives in the
            # clients root. Reported here because the shell opens only the
            # paths the API has named, and a person looking at one
            # engagement is one click from the whole practice.
            "status": str(root / STATUS_PAGE_FILENAME) if root else "",
        },
    }


def _cmd_state(argv: list[str]) -> dict:
    return _state(_engagement_dir(argv))


def _record_pass(run: EngagementRun) -> None:
    """Leave the record the scheduled run leaves: a line in the run log and
    the practice's status page, both in the clients root.

    The app's button makes the same pass as the job, so it must leave the
    same trace - a pass with no record is a pass nobody can check
    afterwards, and a page that is a night old is one nobody believes. The
    page is redrawn from every engagement under the root, because it is
    about the practice and not about the engagement that was just run.

    Neither takes a lock or touches an engagement, and neither failing is
    allowed to fail the pass: the files have already been moved and the
    manifest written, so the person is told what happened either way.
    """
    root = clients_root()
    if root is None or not root.is_dir():
        return
    # Broadly, both of them: the pass has already moved the client's files
    # and written the manifest, so nothing about recording it afterwards may
    # turn a finished pass into an error message in the app.
    try:
        append_log(root / LOG_FILENAME, RunReport(today=dt.date.today(),
                                                  reminders=REMINDERS_NEVER, runs=[run]))
    except Exception as exc:
        log.warning("Could not write %s (%s)", LOG_FILENAME, exc)
    try:
        write_status_page(root, status_report(discover_engagements(root), passed=[run]))
    except Exception as exc:
        log.warning("Could not write %s (%s)", STATUS_PAGE_FILENAME, exc)


def _cmd_scan(argv: list[str]) -> dict:
    """One pass over this engagement - the same pass the scheduled job makes.

    Scaffold, check, file, scan, in that order, with the same lock, the same
    error isolation and the same warnings; only the weekly draft is left
    to the scheduled run (or `python -m tracker.reminder`). There is one
    definition of a pass, in tracker.runner, and this is it - including the
    record it leaves behind (:func:`_record_pass`).
    """
    engagement = _engagement_dir(argv)
    run = run_engagement(engagement_from(engagement), reminders=REMINDERS_NEVER)
    _record_pass(run)
    payload = {
        "run": {
            "ok": run.ok,
            "error": run.error,
            "skipped": run.skipped,
            "filed": run.filed,
            "review": run.review,
            "waiting": run.waiting,
            "file_errors": run.file_errors,
            "warnings": run.warnings,
            "index_deferred": run.index_deferred,
            "manifest_deferred": run.manifest_deferred,
            "statuses": run.statuses,
            "outstanding": run.outstanding,
        },
    }
    try:
        payload["state"] = _state(engagement)
    except ManifestError:
        if run.error:
            raise ManifestError(run.error) from None
        raise
    return payload


def _cmd_templates(argv: list[str]) -> dict:
    """The catalog, plus the tax year a new engagement is for by default."""
    return {"forms": FORM_TYPES, "templates": FORM_TEMPLATES, "default_year": default_tax_year()}


def _cmd_check(argv: list[str]) -> dict:
    """Say now what the next scan would fail on, and what it would let slide."""
    engagement = _engagement_dir(argv)
    result = check_manifest(engagement / MANIFEST_FILENAME)
    return {"ok": result.ok, "problems": result.problems, "warnings": result.warnings}


def _cmd_unlock(argv: list[str]) -> dict:
    """Clear a stale engagement lock. A fresh one is refused with how long to wait."""
    engagement = _engagement_dir(argv)
    status = clear_stale_lock(engagement)
    return {"cleared": True, "age_minutes": int(status.age_seconds // 60),
            "state": _state(engagement)}


def _cmd_list(argv: list[str]) -> dict:
    """Every engagement under the root - the same discovery the scheduled run uses."""
    root = clients_root()
    if root is None or not root.is_dir():
        return {"engagements": [], "needs_root": True, "root": str(root or ""), "vocab": _vocab()}
    engagements = [{"name": child.name, "path": str(child)} for child in engagement_dirs(root)]
    return {"engagements": engagements, "needs_root": False, "root": str(root), "vocab": _vocab()}


def _cmd_create(argv: list[str]) -> dict:
    """Create a new engagement from a JSON spec on stdin:
    {"name": "...", "form": "1040", "year": 2026, "client": "...", "link": "...",
     "due": <ISO_DATE_HINT>, "items": [{identifier, document, extensions, ...}, ...]}
    year defaults to the most recently ended year; catalog rows are shifted to it.
    client/link/due land on the manifest's Engagement sheet, which is all the
    scheduled run needs - there is no registry to add the engagement to, and
    the catalog the rows came from is recorded there beside them.
    """
    spec = json.loads(sys.stdin.read() or "{}")
    form = str(spec.get("form", "")).strip()
    if form:
        require_form(form)
    client = str(spec.get("client", "") or "").strip()
    # The engagement's tax year: the calendar's default unless chosen.
    year = _tax_year(spec.get("year"), default_tax_year())
    name = _engagement_name(str(spec.get("name", "")), default_engagement_name(client, year, form))
    engagement = _new_engagement_dir(name)

    items = [item_from_spec(s) for s in spec.get("items", [])]
    if not items:
        raise ManifestError("Select at least one request item")
    # The wizard sends catalog rows as written (the base year); shift them
    # to the engagement's year so TY2025 does not get asked for in 2027.
    base = base_year(form) if form else None
    if base:
        items = [shift_item(item, year - base) for item in items]

    info = _info_from_spec(spec)
    engagement.mkdir(parents=True)
    try:
        # The catalog the wizard chose is recorded on the sheet: an
        # engagement that cannot say which checklist it came from cannot be
        # checked against it later.
        create_template(engagement / MANIFEST_FILENAME, items, info, form=form)
        scaffold_engagement(engagement)  # validates the manifest too
    except Exception:
        shutil.rmtree(engagement, ignore_errors=True)  # never leave a half-built one
        raise
    return {"created": name, "state": _state(engagement)}


def _cmd_priors(argv: list[str]) -> dict:
    """Engagements already on disk that a new year could be rolled from.

    The same discovery the scheduled run uses, so what the wizard offers
    and what the job walks are one list; superseded_by comes from it too.
    """
    root = clients_root()
    if root is None or not root.is_dir():
        return {"priors": []}
    try:
        registry = discover_engagements(root)
    except RegistryError:
        return {"priors": []}
    priors = []
    for engagement in registry.engagements:
        if engagement.problem:
            continue
        items = load_manifest(engagement.path / MANIFEST_FILENAME)
        year = detect_year(items)
        priors.append({
            "name": engagement.path.name,
            "path": str(engagement.path),
            "client": engagement.client,
            "rolled_from": engagement.rolled_from,
            "superseded_by": engagement.superseded_by,
            "year": year,
            "next_year": next_tax_year(year) if year else None,
            "requests": len(items),
            "received": summarize(items).received,
        })
    return {"priors": priors}


def _cmd_rollover(argv: list[str]) -> dict:
    """Build next year's engagement from a returning client's prior one.

    JSON spec on stdin: {"prior": "<path or name>", "name": "...",
                         "form": "1040", "year": 2026, "include_new": false}
    Prior-year data wins on every field it specifies; the form template only
    fills blanks. Rows the client has never had are offered, not added.
    """
    spec = json.loads(sys.stdin.read() or "{}")
    prior_raw = str(spec.get("prior", "")).strip()
    if not prior_raw:
        raise ManifestError("Pick the engagement to roll forward")
    prior = Path(prior_raw)
    if not prior.is_absolute():
        prior = _root() / prior_raw
    prior = _under_root(prior)
    if not (prior / MANIFEST_FILENAME).is_file():
        raise ManifestError(f"No manifest found in '{prior_raw}'")

    form = str(spec.get("form", "")).strip()
    template = template_items(form) if form else []

    report = roll_forward(
        prior,
        target_year=_tax_year(spec.get("year")),
        template=template,
        include_new=bool(spec.get("include_new")),
    )

    default_name = ROLLOVER_NAME_PATTERN.format(prior=prior.name, year=report.target_year or UNKNOWN_YEAR_LABEL)
    name = _engagement_name(str(spec.get("name", "")), default_name)
    engagement = _new_engagement_dir(name)

    # Last year's sheet, carried by the one rule (tracker.rollover); the
    # wizard's fields go over it. Rolled From is what retires the prior.
    carried = carry_engagement_info(load_engagement_info(prior / MANIFEST_FILENAME),
                                    rolled_from=str(prior))
    info = _info_from_spec(spec, carry=carried)
    engagement.mkdir(parents=True)
    try:
        write_rollover_manifest(engagement / MANIFEST_FILENAME, report)
        write_engagement_info(engagement / MANIFEST_FILENAME, info)
        scaffold_engagement(engagement)
    except Exception:
        shutil.rmtree(engagement, ignore_errors=True)
        raise

    return {
        "created": name,
        "rollover": {
            "prior": prior.name,
            "prior_year": report.prior_year,
            "target_year": report.target_year,
            "carried": [
                {"identifier": r.item.identifier, "document": r.item.document,
                 "origin": r.origin, "note": r.note}
                for r in report.rolled
            ],
            "offered": [
                {"identifier": r.item.identifier, "document": r.item.document,
                 "note": r.note}
                for r in report.offered
            ],
            "unfiled_last_year": report.unfiled_last_year,
            "carried_sheet": CARRIED_SHEET,
        },
        "state": _state(engagement),
    }


def _cmd_assign(argv: list[str]) -> dict:
    """File one parked document under a request, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "identifier": "A01", "keyword": "optional"}
    The working copy is filed under the canonical name, the index row is
    rewritten as Filed (attributed to a person), the keyword - if given - is
    added to the request so the next such file routes itself, and the
    engagement is re-scanned so the status reflects it straight away.

    The filing and the re-scan each take the engagement lock on their own.
    A scheduled pass that slips in between only files and scans the same
    folder under the same lock, so nothing is lost; one lock held across
    both would be a second locking rule for no gain.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    original = str(spec.get("original", "")).strip()
    identifier = str(spec.get("identifier", "")).strip()
    if not original or not identifier:
        raise ManifestError("Pick the file and the request it belongs to")
    result = assign_review_file(
        engagement, original, identifier, keyword=str(spec.get("keyword", "") or "")
    )
    scan_note = ""
    try:
        scan = scan_engagement(engagement)
        if not scan.written:
            scan_note = "manifest open in Excel; status update saved to the sidecar"
    except ScanLockedError as exc:
        scan_note = f"not re-scanned: {exc}"
    return {
        "assigned": {
            "original_name": result.entry.original_name,
            "identifier": result.entry.identifier,
            "filed_as": result.entry.filed_as,
            "prepared_location": result.entry.prepared_location,
            "moved_review_copy": result.moved_review_copy,
            "keyword": result.keyword,
            "keyword_note": result.keyword_note,
            "index_deferred": result.index_deferred,
            "left_in_review": result.left_in_review,
            "scan_note": scan_note,
        },
        "state": _state(engagement),
    }


def _cmd_dismiss(argv: list[str]) -> dict:
    """Record that no request asks for one parked document, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "note": "optional"}
    The index row is rewritten as Not Requested (attributed to a person) and
    nothing moves: the working copy stays where it is and the client's
    original is untouched. Filing it afterwards is how the decision is undone.

    There is no re-scan. The document was never filed under a request, so no
    row's status can change; re-scanning would take the lock again and read
    every working copy to prove that.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the file no request asks for")
    result = dismiss_review_file(engagement, original, str(spec.get("note", "") or ""))
    return {
        "dismissed": {
            "original_name": result.entry.original_name,
            "decision": result.entry.decision,
            "reason": result.entry.reason,
            "prepared_location": result.entry.prepared_location,
            "index_deferred": result.index_deferred,
        },
        "state": _state(engagement),
    }


def _cmd_unfile(argv: list[str]) -> dict:
    """Send one filed document back to Needs Review, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "note": "optional"}
    The working copy goes back under the client's own name, the index row is
    rewritten Needs Review (attributed to a person, with what it said
    before), and the filer re-scans, so the request the document was
    answering reverts with a regression note in the same breath. The scan
    summary comes back in ``state`` - it is summarize() over the rows the
    re-scan has just left, and there is nowhere else it lives.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the document to send back for review")
    result = unfile_document(engagement, original, str(spec.get("note", "") or ""))
    return {
        "unfiled": {
            "original_name": result.entry.original_name,
            "decision": result.entry.decision,
            "reason": result.entry.reason,
            "prepared_location": result.entry.prepared_location,
            "moved_working_copy": result.moved_working_copy,
            "left_filed": result.left_filed,
            "index_deferred": result.index_deferred,
            "scan_note": result.scan_note,
        },
        "state": _state(engagement),
    }


def _cmd_settings(argv: list[str]) -> dict:
    """Where the clients live, and where that is written down."""
    root = clients_root()
    return {
        "root": str(root or ""),
        "exists": bool(root and root.is_dir()),
        "firm": firm(),
        "product": product_name(),
        "settings_path": str(settings_path()),
    }


def _cmd_set_root(argv: list[str]) -> dict:
    """Record the clients root and the firm: JSON {"root": "<folder>", "firm": "..."} on stdin. Once."""
    spec = json.loads(sys.stdin.read() or "{}")
    try:
        root = set_clients_root(str(spec.get("root", "")))
    except SettingsError as exc:
        raise ManifestError(str(exc)) from None
    if spec.get("firm") is not None:
        set_firm(str(spec["firm"]))
    return {"root": str(root), "firm": firm(), "settings_path": str(settings_path()),
            "engagements": _cmd_list([])["engagements"]}


def _cmd_install_schedule(argv: list[str]) -> dict:
    """Generate the Task Scheduler job for the configured root and register it.

    JSON on stdin (all optional): {"start": "HH:MM", "every": minutes},
    defaulting to tracker.scheduling's DEFAULT_START / DEFAULT_REPEAT_MINUTES. The
    root and the working folder are the ones this app runs with, so the job
    walks exactly the folder the app shows. From a source checkout the job
    is the Python this API runs under; in the packaged app it is this same
    executable in runner mode (api_entry.py, RUNNER_MODE_FLAG), which needs
    none of the environment the shell gives the API.
    """
    spec = json.loads(sys.stdin.read() or "{}")
    root = _root()
    start = str(spec.get("start") or DEFAULT_START)
    every = int(spec["every"]) if spec.get("every") not in (None, "") else DEFAULT_REPEAT_MINUTES
    frozen = bool(getattr(sys, "frozen", False))
    working_dir = Path(sys.executable).resolve().parent if frozen else REPO_ROOT
    xml_path = settings_path().with_name(SCHEDULE_XML_FILENAME)
    write_text_atomically(
        xml_path,
        task_scheduler_xml(python=sys.executable, root=root, working_dir=working_dir,
                           start_time=start, repeat_minutes=every, frozen=frozen),
        encoding=SCHEDULE_XML_ENCODING,
    )
    try:
        command = install_task(xml_path)
    except RuntimeError as exc:
        raise ManifestError(str(exc)) from None
    return {
        "installed": is_scheduling_host(),
        "xml": str(xml_path),
        "command": command,
        "root": str(root),
        "start": start,
        "every": every,
        "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
        "frozen": frozen,
    }


COMMANDS = {
    "state": _cmd_state,
    "priors": _cmd_priors,
    "rollover": _cmd_rollover,
    "scan": _cmd_scan,
    "templates": _cmd_templates,
    "list": _cmd_list,
    "create": _cmd_create,
    "assign": _cmd_assign,
    "dismiss": _cmd_dismiss,
    "unfile": _cmd_unfile,
    "check": _cmd_check,
    "unlock": _cmd_unlock,
    "settings": _cmd_settings,
    "set-root": _cmd_set_root,
    "install-schedule": _cmd_install_schedule,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(json.dumps({"error": f"usage: tracker.api {'|'.join(COMMANDS)}"}))
        return 1
    try:
        payload = COMMANDS[argv[0]](argv[1:])
    except (ManifestError, ScanLockedError, FilingError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    except Exception as exc:  # surface anything else as JSON, not a traceback
        print(json.dumps({"error": f"{exc.__class__.__name__}: {exc}"}))
        return 1
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
