"""JSON bridge for the desktop app (Electron) — python -m tracker.api <command>.

Commands print a single JSON object to stdout and exit 0, or {"error": ...}
and exit 1. All real logic lives in the tracker package; this module only
serializes it, so the UI can never disagree with the scanner.

Commands:
  state     current manifest rows, the index, the one summary, useful paths
  priors    list engagements a new year could be rolled forward from
  rollover  build next year's list from a returning client's prior year
  scan      one pass, exactly as the scheduled run makes it (no draft)
  assign    file one Needs Review document under a request (a person's call)
  check     validate the manifest now, with row numbers, instead of at the next scan
  settings / set-root      where the clients live (settings.json beside the app)
  install-schedule         register the daily job for that same folder
  unlock    clear a stale engagement lock (a fresh one is refused)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook

from tracker.locking import clear_stale_lock, lock_status
from tracker.manifest import (
    EngagementInfo,
    ManifestError,
    check_manifest,
    create_template,
    load_engagement_info,
    load_manifest,
    pending_updates,
    summarize,
    with_pending,
    write_engagement_info,
)
from tracker.registry import engagement_dirs, engagement_from
from tracker.runner import REMINDERS_NEVER, run_engagement
from tracker.filer import (
    INDEX_FILENAME,
    FilingError,
    assign_review_file,
    file_drops,
    read_index,
)
from tracker.rollover import detect_year, roll_forward, write_rollover_manifest
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    SHARED_DIR_NAME,
    sanitize_component,
    scaffold_engagement,
)
from tracker.scanner import ScanLockedError, scan_engagement
from tracker.scheduling import install_task, task_scheduler_xml
from tracker.settings import SettingsError, clients_root, set_clients_root, settings_path
from tracker.templates import (  # the catalog; re-exported for the wizard
    FORM_TEMPLATES,
    FORM_TYPES,
    base_year,
    default_tax_year,
    item_from_spec,
    shift_item,
    template_items,
)

# Frozen (PyInstaller) builds live inside the portable package.
if getattr(sys, "frozen", False):
    REPO_ROOT = Path(sys.executable).resolve().parent
else:
    REPO_ROOT = Path(__file__).resolve().parent.parent
#: The firm's name for the very first engagement; after that the wizard
#: copies whatever the newest engagement's sheet says.
DEFAULT_FIRM = "J Park & Associates, CPA"


def _root() -> Path:
    """The clients root from settings.json - the one place it is kept."""
    root = clients_root()
    if root is None:
        raise ManifestError(
            "Tell the app where your clients live first (Settings, or "
            "`python -m tracker.settings <folder>`)"
        )
    return root

# ----------------------------------------------------------------- commands ----


def _engagement_dir(argv: list[str]) -> Path:
    if "--engagement" in argv:
        return Path(argv[argv.index("--engagement") + 1])
    raise ManifestError("Pick an engagement first (--engagement <folder>)")


def _lock_payload(engagement: Path) -> dict | None:
    status = lock_status(engagement)
    if status is None:
        return None
    return {
        "started": status.started,
        "age_minutes": int(status.age_seconds // 60),
        "stale": status.stale,
    }


def _info_payload(info: EngagementInfo) -> dict:
    return {
        "client": info.client, "name": info.name, "link": info.link,
        "due": info.due.isoformat() if info.due else "", "sender": info.sender,
        "firm": info.firm, "reminders": info.reminders, "active": info.active,
        "rolled_from": info.rolled_from,
    }


def _firm_default() -> str:
    """The firm as the newest engagement on disk has it, else the built-in default.

    So the firm's name is typed once, on the first engagement, and copied
    from then on - no constant to keep in step with the sheets.
    """
    root = clients_root()
    if root is not None and root.is_dir():
        for folder in reversed(engagement_dirs(root)):
            try:
                firm = load_engagement_info(folder / MANIFEST_FILENAME).firm
            except ManifestError:
                continue
            if firm:
                return firm
    return DEFAULT_FIRM


def _info_from_spec(
    spec: dict, *, carry: EngagementInfo | None = None, rolled_from: str = ""
) -> EngagementInfo:
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
        due = None   # a new year never inherits last year's deadline
    return EngagementInfo(
        client=text("client", base.client),
        link=text("link", ""),          # a new folder has a new share link
        due=due,
        sender=text("sender", base.sender),
        firm=text("firm", base.firm or _firm_default()),
        reminders=bool(spec.get("reminders", base.reminders)),
        active=True,
        rolled_from=rolled_from,
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
            {
                "identifier": i.identifier,
                "document": i.document,
                "period": i.period,
                "expected_count": i.expected_count,
                "allowed_extensions": list(i.allowed_extensions),
                "required_keywords": list(i.required_keywords),
                "any_keywords": list(i.any_keywords),
                "manual_override": i.manual_override,
                "status": i.status,
                "received_date": i.received_date.isoformat() if i.received_date else None,
                "file_count": i.file_count,
                "validation_notes": i.validation_notes,
            }
            for i in items
        ],
        "index": [
            {
                "received": e.received,
                "original_name": e.original_name,
                "identifier": e.identifier,
                "filed_as": e.filed_as,
                "prepared_location": e.prepared_location,
                "pbc_location": e.pbc_location,
                "decision": e.decision,
                "reason": e.reason,
            }
            for e in read_index(engagement / INDEX_FILENAME)
        ],
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
    error isolation and the same warnings; only the Saturday draft is left
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
    year = default_tax_year()
    return {
        "forms": FORM_TYPES,
        "templates": FORM_TEMPLATES,
        "years": {form: year for form in FORM_TEMPLATES},
        "default_year": year,
    }


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
        return {"engagements": [], "needs_root": True, "root": str(root or "")}
    engagements = [{"name": child.name, "path": str(child)} for child in engagement_dirs(root)]
    return {"engagements": engagements, "needs_root": False, "root": str(root)}


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
    fallback = " ".join(
        part for part in (
            client or "New",
            f"TY{year}",
            f"Form {form}" if form else "Engagement",
        ) if part
    )
    name = _engagement_name(str(spec.get("name", "")), fallback)
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
    """Engagements already on disk that a new year could be rolled from."""
    priors = []
    root = clients_root()
    if root is not None and root.is_dir():
        for child in engagement_dirs(root):
            manifest = child / MANIFEST_FILENAME
            try:
                items = load_manifest(manifest)
                info = load_engagement_info(manifest)
            except ManifestError:
                continue
            priors.append({
                "name": child.name,
                "path": str(child),
                "client": info.client,
                "rolled_from": info.rolled_from,
                "year": detect_year(items),
                "requests": len(items),
                "received": sum(1 for i in items if i.status == "Received"),
            })
    # Say which priors have already been rolled forward, so the wizard can
    # steer the person to the newest year instead of rolling the same
    # prior twice.
    names_by_path = {Path(p["path"]).resolve(): p["name"] for p in priors}
    for prior in priors:
        successor = ""
        if prior["rolled_from"]:
            pass
        for other in priors:
            if other["rolled_from"] and Path(other["rolled_from"]).resolve() == Path(prior["path"]).resolve():
                successor = other["name"]
        prior["superseded_by"] = successor
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

    default_name = f"{prior.name} - {report.target_year}" if report.target_year else f"{prior.name} - next year"
    name = _engagement_name(str(spec.get("name", "")), default_name)
    engagement = _root() / name
    if engagement.exists():
        raise ManifestError(f"An engagement named '{name}' already exists")

    carried = load_engagement_info(prior / MANIFEST_FILENAME)
    # Naming the prior on the new sheet is what retires it (see
    # tracker.registry.mark_superseded); nothing is written to last year.
    info = _info_from_spec(spec, carry=carried, rolled_from=str(prior))
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
        "settings_path": str(settings_path()),
    }


def _cmd_set_root(argv: list[str]) -> dict:
    """Record the clients root: JSON {"root": "<folder>"} on stdin. Once."""
    spec = json.loads(sys.stdin.read() or "{}")
    try:
        root = set_clients_root(str(spec.get("root", "")))
    except SettingsError as exc:
        raise ManifestError(str(exc)) from None
    return {"root": str(root), "settings_path": str(settings_path()),
            "engagements": _cmd_list([])["engagements"]}


def _cmd_install_schedule(argv: list[str]) -> dict:
    """Generate the Task Scheduler job for the configured root and register it.

    JSON on stdin (all optional): {"start": "07:00", "every": 120}. The
    root, the Python and the working folder are the ones this app runs
    with, so the job walks exactly the folder the app shows. A frozen build
    has no Python module tree to run the job from and says so.
    """
    if getattr(sys, "frozen", False):
        raise ManifestError(
            "Install the schedule from a Python checkout of the tracker "
            "(python -m tracker.scheduling --install); the packaged app cannot run the job"
        )
    spec = json.loads(sys.stdin.read() or "{}")
    root = _root()
    start = str(spec.get("start") or "07:00")
    every = int(spec.get("every") or 0)
    xml_path = settings_path().with_name("tax-tracker.xml")
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
