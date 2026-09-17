"""JSON bridge for the desktop app (Electron) — python -m tracker.api <command>.

Commands print a single JSON object to stdout and exit 0, or {"error": ...}
and exit 1. All real logic lives in the tracker package; this module only
serializes it, so the UI can never disagree with the scanner.

Commands:
  list      every engagement under the clients root, plus the vocabulary the app shows
  templates the form catalog and the calendar's default tax year
  create    a new engagement from the wizard's spec (JSON on stdin)
  state     current manifest rows, the index, the one summary, useful paths
  priors    list engagements a new year could be rolled forward from
  rollover  build next year's list from a returning client's prior year
  scan      one pass, exactly as the scheduled run makes it (no draft)
  assign    file one Needs Review document under a request (a person's call)
  check     check_manifest() on demand, problems named by row
  settings / set-root      where the clients live (the settings file beside the app)
  install-schedule         register the daily job for that same folder
  unlock    clear a stale engagement lock (a fresh one is refused)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path

from openpyxl import Workbook, load_workbook

from tracker.locking import STALE_LOCK_SECONDS, clear_stale_lock, lock_status
from tracker import STANDING_RULES
from tracker.manifest import (
    DEFAULT_EXTENSIONS,
    EXPECTED_PATTERN,
    UNSCANNED_LABEL,
    YEAR_MAX,
    YEAR_MIN,
    EngagementInfo,
    ManifestError,
    Override,
    Status,
    check_manifest,
    create_template,
    load_engagement_info,
    load_manifest,
    pending_updates,
    summarize,
    with_pending,
    write_engagement_info,
)
from tracker.registry import RegistryError, discover_engagements, engagement_dirs, engagement_from
from tracker.runner import DRAFT_WEEKDAY, REMINDERS_NEVER, WEEKDAY_NAMES, run_engagement
from tracker.filer import (
    DUPLICATE,
    FILED,
    INDEX_FILENAME,
    NEEDS_REVIEW,
    FilingError,
    assign_review_file,
    file_drops,
    read_index,
)
from tracker.rollover import (
    ORIGIN_PRIOR,
    CARRIED_SHEET,
    carry_engagement_info,
    detect_year,
    next_tax_year,
    roll_forward,
    write_rollover_manifest,
)
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PBC_DIR_NAME,
    REVIEW_DIR_NAME,
    PREPARED_DIR_NAME,
    SHARED_DIR_NAME,
    sanitize_component,
    scaffold_engagement,
)
from tracker.scanner import ScanLockedError, scan_engagement
from tracker.scheduling import (
    INSTALL_HINT,
    DEFAULT_REPEAT_MINUTES,
    DEFAULT_START,
    SCHEDULE_XML_FILENAME,
    TASK_NAME,
    install_task,
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
    KEYWORD_DEFAULT_NOTE,
    PERIOD_PATTERN,
    YEAR_NOTE,
    FORM_TEMPLATES,
    FORM_TYPES,
    base_year,
    default_tax_year,
    item_from_spec,
    shift_item,
    template_items,
)

#: The folder the app runs from (the repository from source, beside the
#: executable when frozen) - the same answer tracker.settings gives.
REPO_ROOT = settings_dir()
def _root() -> Path:
    """The clients root from settings.json - the one place it is kept."""
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


def _engagement_dir(argv: list[str]) -> Path:
    if ENGAGEMENT_FLAG in argv:
        return Path(argv[argv.index(ENGAGEMENT_FLAG) + 1])
    raise ManifestError(f"Pick an engagement first ({ENGAGEMENT_FLAG} <folder>)")


#: How a new engagement is named when nobody types a name. The renderer
#: formats the same pattern, so the wizard's preview and the folder agree.
NAME_PATTERN = "{client} " + PERIOD_PATTERN + " {form}"
ROLLOVER_NAME_PATTERN = "{prior} - {year}"


def form_label(form: str) -> str:
    """``Form 1120-S`` for ``1120S``: the one id -> label map is FORM_TYPES."""
    for entry in FORM_TYPES:
        if entry["id"] == form:
            return entry["label"]
    return f"Form {form}" if form else "Engagement"


def default_engagement_name(client: str, year: int, form: str) -> str:
    return NAME_PATTERN.format(client=client or NEW_CLIENT_PLACEHOLDER, year=year,
                               form=form_label(form)).strip()


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


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
        "decisions": {"filed": FILED, "needs_review": NEEDS_REVIEW, "duplicate": DUPLICATE},
        "default_extensions": ", ".join(DEFAULT_EXTENSIONS),
        "expected_pattern": EXPECTED_PATTERN,
        "period_pattern": PERIOD_PATTERN,
        "origin_prior": ORIGIN_PRIOR,
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
            raise ManifestError(f"Due date must be YYYY-MM-DD, got {due_raw!r}") from None
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


def _engagement_name(requested: str, fallback: str) -> str:
    """A folder name from what the user typed, or the fallback if nothing usable is left."""
    name = sanitize_component(requested.strip())
    return name if any(ch.isalnum() for ch in name) else fallback


def _state(engagement: Path) -> dict:
    manifest_path = engagement / MANIFEST_FILENAME
    deferred = pending_updates(manifest_path)
    items = with_pending(load_manifest(manifest_path), deferred)
    info = load_engagement_info(manifest_path)
    summary = summarize(items)
    return {
        "pending_statuses": len(deferred),
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
        "index": [asdict(e) | {"filed_as": e.filed_as} for e in read_index(engagement / INDEX_FILENAME)],
        "paths": {
            "engagement": str(engagement),
            "shared": str(engagement / SHARED_DIR_NAME),
            "pbc": str(engagement / SHARED_DIR_NAME / PBC_DIR_NAME),
            "prepared": str(engagement / PREPARED_DIR_NAME),
            "index": str(engagement / INDEX_FILENAME),
            "manifest": str(manifest_path),
        },
    }


def _cmd_state(argv: list[str]) -> dict:
    return _state(_engagement_dir(argv))


def _cmd_scan(argv: list[str]) -> dict:
    """One pass over this engagement - the same pass the scheduled job makes.

    Scaffold, check, file, scan, in that order, with the same lock, the same
    error isolation and the same warnings; only the weekly draft is left
    to the scheduled run (or `python -m tracker.reminder`). There is one
    definition of a pass, in tracker.runner, and this is it.
    """
    engagement = _engagement_dir(argv)
    run = run_engagement(engagement_from(engagement), reminders=REMINDERS_NEVER)
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
    except ManifestError as exc:
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
     "due": "YYYY-MM-DD", "items": [{identifier, document, extensions, ...}, ...]}
    year defaults to the most recently ended year; catalog rows are shifted to it.
    client/link/due land on the manifest's Engagement sheet, which is all the
    scheduled run needs - there is no registry to add the engagement to.
    """
    spec = json.loads(sys.stdin.read() or "{}")
    form = str(spec.get("form", "")).strip()
    if form and form not in FORM_TEMPLATES:
        raise ManifestError(f"Unknown tax form type '{form}'")
    client = str(spec.get("client", "") or "").strip()
    # The engagement's tax year: the calendar's default unless chosen.
    try:
        year = int(spec.get("year") or default_tax_year())
    except (TypeError, ValueError):
        raise ManifestError(f"Tax year must be a whole number, got {spec.get('year')!r}") from None
    name = _engagement_name(str(spec.get("name", "")), default_engagement_name(client, year, form))
    engagement = _root() / name
    if engagement.exists():
        raise ManifestError(f"An engagement named '{name}' already exists")

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
        create_template(engagement / MANIFEST_FILENAME, items, info)
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
    if not (prior / MANIFEST_FILENAME).is_file():
        raise ManifestError(f"No manifest found in '{prior_raw}'")

    form = str(spec.get("form", "")).strip()
    template = template_items(form) if form else []

    report = roll_forward(
        prior,
        target_year=spec.get("year") or None,
        template=template,
        include_new=bool(spec.get("include_new")),
    )

    default_name = ROLLOVER_NAME_PATTERN.format(prior=prior.name, year=report.target_year or "next year")
    name = _engagement_name(str(spec.get("name", "")), default_name)
    engagement = _root() / name
    if engagement.exists():
        raise ManifestError(f"An engagement named '{name}' already exists")

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
            "scan_note": scan_note,
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
    root, the Python and the working folder are the ones this app runs
    with, so the job walks exactly the folder the app shows. A frozen build
    has no Python module tree to run the job from and says so.
    """
    if getattr(sys, "frozen", False):
        raise ManifestError(
            "Install the schedule from a Python checkout of the tracker "
            f"({INSTALL_HINT}); the packaged app cannot run the job"
        )
    spec = json.loads(sys.stdin.read() or "{}")
    root = _root()
    start = str(spec.get("start") or DEFAULT_START)
    every = int(spec["every"]) if spec.get("every") not in (None, "") else DEFAULT_REPEAT_MINUTES
    xml_path = settings_path().with_name(SCHEDULE_XML_FILENAME)
    xml_path.write_text(
        task_scheduler_xml(python=sys.executable, root=root, working_dir=REPO_ROOT,
                           start_time=start, repeat_minutes=every),
        encoding="utf-16",
    )
    try:
        command = install_task(xml_path)
    except RuntimeError as exc:
        raise ManifestError(str(exc)) from None
    import platform

    return {
        "installed": platform.system() == "Windows",
        "xml": str(xml_path),
        "command": command,
        "root": str(root),
        "start": start,
        "every": every,
        "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
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
