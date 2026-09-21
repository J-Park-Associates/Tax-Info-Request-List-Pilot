"""JSON bridge for the desktop app (Electron) — python -m tracker.api <command>.

Commands print a single JSON object to stdout and exit 0, or {"error": ...}
and exit 1. All real logic lives in the tracker package; this module only
serializes it, so the UI can never disagree with the scanner.

Commands:
  list      every engagement under the clients root, plus the vocabulary the app shows
  templates the form catalog and the calendar's default tax year
  create    a new engagement from the wizard's spec (JSON on stdin)
  edit      save the request list and the engagement's details from the
            app's editor (JSON on stdin), as one recorded event
  state     the request rows as the record holds them, the index, the
            triaged review queue, the one summary, useful paths
  priors    list engagements a new year could be rolled forward from
  rollover  build next year's list from a returning client's prior year
  scan      one pass, exactly as the scheduled run makes it (no draft)
  assign    file one Needs Review document under a request (a person's call)
  dismiss   record that no request asks for one Needs Review document
  unfile    send one filed document back to Needs Review (a person's call)
  restore   put one moved working copy back where the record put it
  unlearn   take back a keyword a filing taught one request, and re-scan
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

from tracker import STANDING_RULES, ledger, reminder, review, store
from tracker.filer import (
    DUPLICATE,
    FILE_MOVED,
    FILED,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    FilingError,
    assign_review_file,
    dismiss_review_file,
    ensure,
    find_parked,
    moved_to,
    read_index,
    restore_working_copy,
    unfile_document,
)
from tracker.fsio import write_text_atomically
from tracker.locking import STALE_LOCK_SECONDS, clear_stale_lock, lock_status
from tracker.manifest import (
    ANY_EXTENSION,
    COLUMN_HELP,
    COLUMNS,
    DEFAULT_EXTENSIONS,
    EXPECTED_PATTERN,
    ISO_DATE_HINT,
    MIN_EXPECTED_COUNT,
    MIN_SIZE_KB_FLOOR,
    NO_DATE_CHECK,
    NOT_APPLICABLE_LABEL,
    OVERRIDE_REASON_OTHER,
    OVERRIDE_REASONS,
    UNSCANNED_LABEL,
    YEAR_MAX,
    YEAR_MIN,
    ManifestError,
    Override,
    Status,
    check_rules,
    check_tax_year,
    create_engagement,
    item_from_fields,
    load_engagement_info,
    load_manifest,
    rule_as_read,
    save_rules,
    summarize,
    unlearn_keyword,
)
from tracker.page import slug
from tracker.records import (
    CANDIDATE_SEP,
    DATE_FIELDS,
    ENGAGEMENT_EDITABLE,
    ENGAGEMENT_FIELDS,
    ENGAGEMENT_HELP,
    ENGAGEMENT_LABELS,
    EVIDENCE_PLACES,
    EVIDENCE_RULES,
    NO,
    THE_RECORD,
    YES,
    EngagementInfo,
    IndexEntry,
    identifier_key,
    ledger_key,
)
from tracker.registry import RegistryError, discover_engagements, engagement_dirs, engagement_from
from tracker.rollover import (
    ORIGIN_NOT_APPLICABLE,
    ORIGIN_PRIOR,
    UNKNOWN_YEAR_LABEL,
    carry_engagement_info,
    detect_year,
    next_tax_year,
    roll_forward,
    with_default_dates,
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
    last_drafted,
    run_engagement,
    status_report,
    write_status_page,
)
from tracker.scaffold import (
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    SHARED_DIR_NAME,
    assign_folders,
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
    firm_phone,
    product_name,
    set_clients_root,
    set_firm,
    set_firm_phone,
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
    NOT_APPLICABLE_SECTION,
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
#: The three answers to a working copy that is not where the record put it
#: (decision 110), the card they sit on, and the word for a row whose bytes
#: are nowhere under the firm's folder. Nothing is guessed and nothing is
#: preferred: three buttons, one of which is offered only when the copy sits
#: in a request's folder, because "keep it where it is" means nothing
#: anywhere else. The renderer shows these and types none of them.
RESTORE_LABEL = "Put it back"
KEEP_LABEL = "Keep it here"
SEND_TO_REVIEW_LABEL = "Send to review"
MOVED_HEADING = "Moved by hand ({n})"
MOVED_SUMMARY = ("these working copies are not where the record put them; "
                 "choose for each - nothing is guessed")
MOVED_NOWHERE = "nowhere under the firm's folder"
#: The review queue's second rendering (decision 114): the same queue, one
#: card at a time, in the order this module already ships it. Three answers
#: sit on a card - take the top suggestion, open the row in the list where
#: every request is offered (decision 84), or send the card to the back of
#: the deck - and two words label the toggle between the renderings. The
#: heading over the card's suggestion is ``SUGGESTED_HEADING``, the list's
#: own: one queue, one word for a suggestion, and no second word to keep in
#: step with it. ``CARD_POSITION`` is the card's only number, filled by the
#: renderer with the card's place in the deck and the queue's length.
#: Nothing here is a command - both renderings file through ``assign`` - and
#: nothing about the deck is recorded (decision 83). The renderer shows
#: these and types none of them.
ACCEPT_LABEL = "Accept the suggestion"
SKIP_LABEL = "Skip for now"
OPEN_IN_LIST_LABEL = "Pick another request"
CARD_MODE_LABEL = "One at a time"
LIST_MODE_LABEL = "All at once"
CARD_POSITION = "{n} of {total}"
#: What a review command says when it was sent without the row's sequence
#: number (decision 112). The app is drawn from ``state``, which carries one
#: for every row, so a spec without it is a caller acting on no view at all -
#: and an action on no view is exactly what the freshness check exists to
#: refuse. Not a label: the app shows it as it shows any other refusal.
NO_SEQ = "The row's record version was not sent; reload the engagement and try again"
#: Every word the request-list editor shows (decision 104): the button that
#: opens it, its two titles, its buttons, the paste box's hint, the heading
#: over the warnings, what the banner says after a save, and how a keyword a
#: filing taught is shown beside the row - as taught, never as typed. The
#: renderer shows these and types none of them.
EDITOR_OPEN_LABEL = "Edit Request List"
EDITOR_TITLE = "Request list"
EDITOR_ENGAGEMENT_TITLE = "Engagement details"
EDITOR_SAVE_LABEL = "Save"
EDITOR_CANCEL_LABEL = "Cancel"
EDITOR_ADD_LABEL = "Add a request"
EDITOR_REMOVE_LABEL = "Remove"
EDITOR_PASTE_LABEL = "Paste rows"
EDITOR_PASTE_HINT = (
    "Paste rows copied from a spreadsheet: one request per line, cells separated by tabs or "
    "as CSV, in the column order above; a first line that repeats the headings is skipped. "
    "Nothing is recorded until you save."
)
EDITOR_WARNINGS_HEADING = "Worth a look"
RULES_SAVED = "Request list saved: {changed} row(s) changed, {removed} removed"
NOTHING_CHANGED = "Nothing changed; nothing was recorded."
LEARNED_NOTE = "taught by a filing: {keywords}"
#: The button beside each keyword a filing taught, and what the editor says
#: once one is taken back (decision 113). Unlearning is its own event and
#: lands at once - it is not part of Save - so the sentence is in the past
#: tense and says the request was re-scanned, because its rules just moved.
UNLEARN_LABEL = "Unlearn"
UNLEARNED_NOTE = "{keyword} unlearned from {identifier}; the request was re-scanned"
#: What the returning-client page says of last year's set-aside rows, in
#: one line beside the carried and offered counts.
NOT_APPLICABLE_CARRIED = "{n} request(s) not applicable last year - review them in the editor"
#: The settings page's box for the firm's telephone number (decision 117).
#: It sits beside the firm's name because it is the firm's, not one
#: engagement's, and only the final-notice reminder ever says it.
FIRM_PHONE_LABEL = "Firm phone"
FIRM_PHONE_HELP = "named in the final-notice reminder; blank drops that sentence"


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
             "record": THE_RECORD}
    return [{"headline": headline, "detail": detail.format(**names)}
            for headline, detail in STANDING_RULES]


def _vocab() -> dict:
    """Every word and number the renderer shows or compares, from its owner.

    The app never types a status, an override, a decision, a default or a
    sentence pattern of its own: it reads this once and derives everything
    (chip classes from the status key, a set-aside row from the override
    value and its label from the row's year, the parked list from the
    decision value, the picker from candidates).
    """
    return {
        "product": product_name(),
        "firm": firm(),
        "statuses": [{"value": status, "key": _slug(status)} for status in Status.ALL],
        "unscanned_label": UNSCANNED_LABEL,
        "unscanned_key": _slug(UNSCANNED_LABEL),
        "overrides": {"accepted": Override.ACCEPTED, "not_applicable": Override.NOT_APPLICABLE},
        # How a set-aside row is named to a person: the value with the
        # row's year, which travels per item as ``year`` in the state so
        # the renderer computes nothing from the Period's text. The
        # reasons a person may give for Accepted, and the word that opens
        # the box for their own words - which is never itself stored.
        "not_applicable_label": NOT_APPLICABLE_LABEL,
        "override_reasons": list(OVERRIDE_REASONS),
        "override_reason_other": OVERRIDE_REASON_OTHER,
        # The one line the returning-client page adds for last year's
        # set-aside rows, and the origin value it groups them on.
        "origin_not_applicable": ORIGIN_NOT_APPLICABLE,
        "not_applicable_carried": NOT_APPLICABLE_CARRIED,
        # The key a decision is looked up by is the app's handle on it, not
        # the word: NOT_REQUESTED is keyed by the action that writes it,
        # because the renderer may not carry the word "Requested" in any
        # form - it is UNSCANNED_LABEL, a status, and the guard that keeps
        # the app from typing a status of its own reads the whole file.
        # FILE_MOVED is here for the same reason the others are - the app
        # types no decision of its own - and since decision 110 the moved
        # rows have a card of their own, above the review queue, which the
        # state's own ``moved`` list draws.
        "decisions": {"filed": FILED, "needs_review": NEEDS_REVIEW, "duplicate": DUPLICATE,
                      "dismissed": NOT_REQUESTED, "file_moved": FILE_MOVED},
        "review_labels": {"dismiss": DISMISS_LABEL, "dismiss_note": DISMISS_NOTE_HINT,
                          "dismissed_heading": DISMISSED_HEADING, "file": FILE_LABEL,
                          "file_anyway": FILE_ANYWAY_LABEL,
                          "unfile": UNFILE_LABEL, "unfile_note": UNFILE_NOTE_HINT,
                          "filed_heading": FILED_HEADING,
                          "suggested": SUGGESTED_HEADING,
                          "other_requests": OTHER_REQUESTS_HEADING,
                          # Decision 110's card: the three answers, its
                          # heading and summary, and the word for a copy
                          # that is nowhere under the firm's folder.
                          "restore": RESTORE_LABEL, "keep": KEEP_LABEL,
                          "send_to_review": SEND_TO_REVIEW_LABEL,
                          "moved_heading": MOVED_HEADING, "moved_summary": MOVED_SUMMARY,
                          "moved_nowhere": MOVED_NOWHERE,
                          # Decision 114's second rendering of the same
                          # queue: the card's three answers, the toggle's
                          # two words and the position line. The card's
                          # heading over its suggestion is "suggested"
                          # above - one queue, one word for a suggestion.
                          "accept": ACCEPT_LABEL, "skip": SKIP_LABEL,
                          "open_in_list": OPEN_IN_LIST_LABEL,
                          "card_mode": CARD_MODE_LABEL, "list_mode": LIST_MODE_LABEL,
                          "card_position": CARD_POSITION},
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
                   "max_suggestions": review.MAX_SUGGESTIONS,
                   "set_aside_note": review.SET_ASIDE_NOTE},
        "default_extensions": ", ".join(DEFAULT_EXTENSIONS),
        "expected_pattern": EXPECTED_PATTERN,
        "period_pattern": PERIOD_PATTERN,
        "origin_prior": ORIGIN_PRIOR,
        "unknown_year_label": UNKNOWN_YEAR_LABEL,
        "candidate_separator": CANDIDATE_SEP,
        # Every word an evidence line can carry, from the module that owns
        # it: the app labels a rule and a place, and types neither.
        "evidence": {"rules": list(EVIDENCE_RULES), "places": list(EVIDENCE_PLACES)},
        "year_note": YEAR_NOTE,
        "extension_default_note": EXTENSION_DEFAULT_NOTE,
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
        # The one line the app shows for a reminder an ambiguous request
        # holds (decision 115), from the module that holds it.
        "reminder": {"held_line": reminder.HELD_SUMMARY},
        # The settings page's own box for the firm's telephone number
        # (decision 117): its label, the sentence under it, and the number
        # as recorded - so a person who re-points the app at their clients
        # folder does not save a blank over a number they typed once.
        "settings": {"phone_label": FIRM_PHONE_LABEL, "phone_help": FIRM_PHONE_HELP,
                     "phone": firm_phone()},
        # The page a pass regenerates, the three words that say whether the
        # one on disk still describes the engagement, and what the button
        # that opens it says. The app compares nothing itself and types
        # neither label: it shows the words the API sends and derives the
        # chip's class from one of them, exactly as it does a status.
        "view": {"label": VIEW_LABEL, "open": VIEW_OPEN_LABEL, "states": list(VIEW_STATES)},
        # The request list's schema, as the editor draws it: each column's
        # key in the record, its header, and the sentence under the heading.
        "columns": [{"key": field, "label": header, "help": COLUMN_HELP[field]}
                    for header, field in COLUMNS],
        # Every word the editor shows, the engagement fields it lays out
        # (and which of them a person may change), the two yes/no words,
        # the two one-character values, and the floors its number inputs
        # take their minimum from - none of it typed in the page.
        "editor": {
            "open": EDITOR_OPEN_LABEL, "title": EDITOR_TITLE,
            "engagement_title": EDITOR_ENGAGEMENT_TITLE,
            "save": EDITOR_SAVE_LABEL, "cancel": EDITOR_CANCEL_LABEL, "add_row": EDITOR_ADD_LABEL,
            "remove_row": EDITOR_REMOVE_LABEL, "paste": EDITOR_PASTE_LABEL,
            "paste_hint": EDITOR_PASTE_HINT, "warnings_heading": EDITOR_WARNINGS_HEADING,
            "saved": RULES_SAVED, "nothing_changed": NOTHING_CHANGED, "learned_note": LEARNED_NOTE,
            # Taking a taught keyword back is its own event, so it has its
            # own button beside the word and its own sentence afterwards;
            # the renderer types neither (decision 113).
            "unlearn_label": UNLEARN_LABEL, "unlearned_note": UNLEARNED_NOTE,
            "engagement_fields": [
                {"key": f, "label": ENGAGEMENT_LABELS[f], "help": ENGAGEMENT_HELP.get(f, ""),
                 "editable": f in ENGAGEMENT_EDITABLE}
                for _, f in ENGAGEMENT_FIELDS
            ],
            # Which of those fields take a date box. The record answers it
            # (decision 117), so a second date is a date box in the editor
            # without the page learning another field's name.
            "date_fields": list(DATE_FIELDS),
            "yes": YES, "no": NO, "any_extension": ANY_EXTENSION, "no_date_check": NO_DATE_CHECK,
            "minimums": {"expected_count": MIN_EXPECTED_COUNT, "min_size_kb": MIN_SIZE_KB_FLOOR},
            # The folded group the editor keeps the set-aside rows in,
            # headed as the Status Report heads its own (decision 116).
            "set_aside_heading": NOT_APPLICABLE_SECTION,
        },
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
    """The engagement's details as JSON: every field, with dates as ISO text.

    Which fields are dates is the record's answer (``records.DATE_FIELDS``),
    so a date added to the details reaches the app's boxes without a second
    edit here. A blank date travels as "" rather than null, because the
    renderer puts it straight into a date box.
    """
    payload = asdict(info)
    for name in DATE_FIELDS:
        value = getattr(info, name)
        payload[name] = value.isoformat() if value else ""
    return payload


def _info_from_spec(spec: dict, *, carry: EngagementInfo | None = None,
                    blank_clears: bool = False) -> EngagementInfo:
    """The engagement's details: what the wizard or the editor sent, over
    what is carried (last year's details on a rollover, the details as
    recorded on an edit), over the firm default.

    ``blank_clears`` is the editor's rule: a key present with a blank
    value clears the recorded value, and a key absent keeps it - a person
    who empties the Link box means the link to go. The wizard and the
    rollover keep their fallback: a blank there is nothing typed, and the
    carried or default value stands.

    The engagement's name is not written: the folder is the name, and a
    copy in the record would drift the first time the folder was renamed.
    """
    base = carry or EngagementInfo()

    def text(key: str, fallback: str) -> str:
        # One line, whatever was pasted: a detail with a line break inside
        # it would carry that break into the reminder draft's headers.
        def clean(value: object) -> str:
            return " ".join(str(value).split())

        if blank_clears and key in spec:
            return clean(spec[key] or "")
        value = spec.get(key)
        return clean(value) if value not in (None, "") else fallback

    def date(key: str) -> dt.date | None:
        # Which details are dates is the record's answer, so the two are
        # read by one rule and a third would be read by it too.
        typed = str(spec.get(key, "") or "").strip()
        if typed:
            try:
                return dt.date.fromisoformat(typed)
            except ValueError:
                raise ManifestError(
                    f"{ENGAGEMENT_LABELS[key]} must be {ISO_DATE_HINT}, got {typed!r}"
                ) from None
        if blank_clears and key in spec:
            return None
        return getattr(base, key)

    return replace(
        base,
        client=text("client", base.client),
        link=text("link", base.link),
        sender=text("sender", base.sender),
        firm=text("firm", base.firm or firm()),
        reminders=bool(spec.get("reminders", base.reminders)),
        active=bool(spec.get("active", base.active)),
        **{key: date(key) for key in DATE_FIELDS},
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


def _triage_payload(triaged: review.Triage, seqs: dict[str, int]) -> dict:
    """One parked file's shortlist as JSON, in triage order.

    The row itself is already in ``state["index"]``; what travels here is
    the part only :mod:`tracker.review` knows, joined back to that row by
    ``pbc_location`` - the same handle every review command takes. The
    row's sequence number travels here too, beside the row rather than in
    it, so the card a person acts from carries the version of the record
    it was drawn on (decision 112).

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
        "seq": seqs.get(ledger_key(triaged.entry)),
        "shortlist": [asdict(suggestion) for suggestion in triaged.shortlist],
        # The set-aside rows the evidence points at, named with their
        # year's label and never in the shortlist (decision 116).
        "set_aside": [asdict(one) for one in triaged.set_aside],
        "genre": triaged.genre,
        "group": triaged.group,
    }


def _moved_payload(engagement: Path, entries: list[IndexEntry], items,
                   seqs: dict[str, int]) -> list[dict]:
    """Every working copy the record has lost track of, and where it is now.

    Decision 110's card is its own list rather than a fourth column on the
    index: a mislaid copy is the morning's first question and a person
    answers it with three buttons, not by reading a row. Each entry carries
    the row's sequence number (decision 112), the home the record put the
    copy at, where its bytes are now (``None`` for a row whose bytes are
    nowhere under the firm's folder) and - only when the copy sits inside
    some request's folder - which request that is, because "keep it where
    it is" means nothing anywhere else. The folder is matched by
    :func:`tracker.scaffold.assign_folders`, the same answer the filer
    files by, so a wanderer in a subfolder of a request's folder counts as
    that request's and one in the review folder or under no request's
    counts as nobody's.
    """
    folders = assign_folders(engagement / PREPARED_DIR_NAME, [i.identifier for i in items])
    rows = []
    for entry in entries:
        if entry.decision != FILE_MOVED:
            continue
        now = moved_to(entry)
        in_request = ""
        if now:
            where = (engagement / now).parent
            for identifier, claimed in folders.items():
                if any(folder == where or folder in where.parents for folder in claimed):
                    in_request = identifier
                    break
        rows.append({
            "original_name": entry.original_name,
            "pbc_location": entry.pbc_location,
            "seq": seqs.get(ledger_key(entry)),
            "home": entry.prepared_location,
            "now": now,
            "in_request": in_request,
        })
    return rows


def _state(engagement: Path) -> dict:
    root = clients_root()
    # The store is brought up to the record before anything is read, and
    # showing an engagement stays a read - the app shows one a pass is
    # holding, and says so. The rules a person sees here are the ones the
    # record holds: ``items`` with the statuses and the taught keywords
    # laid on, for the table; ``rules`` as stored, for the editor, so a
    # keyword a filing taught is never shown as one somebody typed.
    ensure(engagement)
    items = load_manifest(engagement)
    info = load_engagement_info(engagement)
    summary = summarize(items)
    entries = read_index(engagement)
    conn = store.connect()
    rules = store.rules(conn, engagement) or []
    taught = store.learned_keywords(conn, engagement)      # keyed without case, as the store keys it
    # Which journal line last wrote each index row: the freshness handle the
    # card carries out and a person's action carries back (decision 112).
    seqs = store.document_seqs(conn, engagement)
    view_path = engagement / VIEW_FILENAME
    return {
        # The derived page, and whether it still describes this engagement.
        # Reading the stamp takes no lock and tolerates another program
        # holding it, so showing the engagement stays a read.
        "view": {"state": view_state(engagement), "path": str(view_path)},
        "engagement": _info_payload(info),
        "lock": _lock_payload(engagement),
        "summary": {
            "line": summary.line, "counts": summary.counts, "total": summary.total,
            "received": summary.received, "outstanding": summary.outstanding,
            "not_applicable": summary.not_applicable, "unscanned": summary.unscanned,
        },
        # Each row with the year its own Period gives, so the renderer
        # labels a set-aside row without reading the Period's text.
        "items": [
            asdict(i) | {"received_date": i.received_date.isoformat() if i.received_date else None,
                         "year": i.year}
            for i in items
        ],
        # The person's rows as stored - read the way every reader reads
        # them, so a retired override spelling in an old journal reaches
        # the editor as its successor - the keywords filings taught each
        # row, and the rows the rules cannot act on: what the editor
        # opens on, and what it shows after a save.
        "rules": [rule_as_read(row) for row in rules],
        "learned": {row["identifier"]: list(taught[identifier_key(row["identifier"])])
                    for row in rules if taught.get(identifier_key(row["identifier"]))},
        "warnings": check_rules(items),
        # The index's packed cells travel as data, not as text the app
        # would have to parse: the candidates as a list, the evidence as
        # the record it was written from keyed by candidate identifier,
        # and every working copy's name as a list - one name for nearly
        # every row, and one per request for a page decision 94 filed
        # under several, so the app shows each destination without
        # knowing a separator or how to cut a path. The sequence number
        # rides beside the row and never in it: it is the record's
        # bookkeeping, not a fact about the document, so it reaches the
        # app and nothing else (decision 112).
        "index": [asdict(e) | {"filed_as": e.filed_as, "filed_names": e.filed_names,
                               "candidates": e.candidate_list,
                               "evidence": _evidence_payload(e),
                               "seq": seqs.get(ledger_key(e))}
                  for e in entries],
        # The review queue, triaged: one entry per parked file, its
        # shortlist best-first with the sentence behind each suggestion.
        # There is no `review` command - the card draws from the one state
        # the app already reads - and the manifest and the index are handed
        # to triage() so each is read once for the whole screen.
        "review": [_triage_payload(t, seqs)
                   for t in review.triage(engagement, entries, items=items)],
        # The working copies that are not where the record put them
        # (decision 109 found them; decision 110 is what a person does
        # about them). Their own list, above the review queue in the app.
        "moved": _moved_payload(engagement, entries, items, seqs),
        # The reminder as the record and the rows now stand (decision 115):
        # the requests that hold it - a person decides those before any
        # draft is written - and the day of the last draft. Sorted by the
        # reminder's own triage over the rows already loaded; nothing here
        # reads a draft file, and nothing here drafts (decision 12).
        "reminder": _reminder_payload(engagement, items, entries),
        "paths": {
            "engagement": str(engagement),
            "shared": str(engagement / SHARED_DIR_NAME),
            "pbc": str(engagement / SHARED_DIR_NAME / PBC_DIR_NAME),
            "prepared": str(engagement / PREPARED_DIR_NAME),
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


def _reminder_payload(engagement: Path, items, entries) -> dict:
    """What holds this engagement's reminder, and when it was last drafted.

    The index rows go in because a parked file the client could fix holds
    the request it points at (decision 117), and the card must show the
    same hold the draft day will: the rows are the ones ``state`` has
    already read, so nothing is read twice to answer this.
    """
    _, _, _, held = reminder.triage(items, entries)
    drafted = last_drafted(engagement)
    return {
        "held": [{"identifier": flag.item.identifier, "label": flag.item.label,
                  "reason": flag.reason} for flag in held],
        "last_drafted": drafted.isoformat() if drafted else None,
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
    statuses recorded, so the person is told what happened either way.
    """
    root = clients_root()
    if root is None or not root.is_dir():
        return
    # Broadly, both of them: the pass has already moved the client's files
    # and recorded what it found, so nothing about recording it afterwards
    # may turn a finished pass into an error message in the app.
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

    Scaffold, file, scan, in that order, with the same lock, the same
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


def _cmd_edit(argv: list[str]) -> dict:
    """Save the request list and the engagement's details from the editor.

    JSON on stdin: {"items": [row, ...], "engagement": {...}}. Each row is
    the editor's row, keyed by the column keys ``_vocab()['columns']``
    names: the two numbers as typed, the file types and keywords as a
    comma-separated string or a list, the date pattern blank, ``*`` or a
    regex, the override blank or one of its two values. The rows are
    parsed in order (``item_from_fields``, each refusal naming its row) and
    saved through ``manifest.save_rules``, which validates the list whole
    and records one ``rules_changed`` event of exactly what moved - or
    nothing, when nothing did. ``engagement`` holds only the keys
    ``records.ENGAGEMENT_EDITABLE`` names; any other is refused by name,
    an absent one keeps its recorded value, and one present and blank
    clears it.

    A refusal is the usual error sentence, and nothing is recorded. The
    engagement lock is taken inside the save, so an edit of a folder a
    pass is holding waits on the lock the way a filing does.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    rows = spec.get("items")
    if not isinstance(rows, list):
        raise ManifestError("The editor sent no rows")
    items = [item_from_fields(row if isinstance(row, dict) else {}, where=f"Row {n}")
             for n, row in enumerate(rows, start=1)]
    details = spec.get("engagement") or {}
    for key in details:
        if key not in ENGAGEMENT_EDITABLE:
            raise ManifestError(f"'{key}' is not edited here")
    info = _info_from_spec(details, carry=load_engagement_info(engagement), blank_clears=True)
    saved = save_rules(engagement, items, info)
    state = _state(engagement)
    return {
        "saved": {"changed": list(saved.changed), "removed": list(saved.removed),
                  "engagement": list(saved.info_fields), "recorded": saved.recorded},
        "warnings": state["warnings"],
        "state": state,
    }


def _cmd_unlearn(argv: list[str]) -> dict:
    """Take back a keyword a person's filing taught one request (decision 113).

    JSON spec on stdin: {"identifier": "A01", "keyword": "lender"} - the
    word as the editor shows it, which is the word the record holds. One
    ``keyword_unlearned`` event through ``manifest.unlearn_keyword``; a
    pair nobody taught is refused by name and nothing is recorded.

    Then the re-scan, as ``assign`` does it and for the same reason: the
    request's rules just moved, and a copy that passed only on that word
    should go back to Failed Validation now rather than on Saturday. The
    unlearn and the re-scan each take the engagement lock on their own.

    Unlearning is not part of a save. It lands on its own, so the editor
    hands back the fresh state and keeps whatever the person has typed
    into the rows and not saved yet.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    identifier = str(spec.get("identifier", "")).strip()
    keyword = str(spec.get("keyword", "")).strip()
    if not identifier or not keyword:
        raise ManifestError("Pick the request and the keyword to take back")
    taken = unlearn_keyword(engagement, identifier, keyword)
    scan_note = ""
    try:
        scan_engagement(engagement)
    except ScanLockedError as exc:
        scan_note = f"not re-scanned: {exc}"
    return {
        "unlearned": {
            "identifier": taken.identifier,
            "keyword": taken.keyword,
            "scan_note": scan_note,
        },
        "state": _state(engagement),
    }


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
    client/link/due land in the record as the engagement's details, which is
    all the scheduled run needs - there is no registry to add the engagement
    to, and the catalog the rows came from is recorded there beside them.
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

    # The wizard's dates, or the form's own (decision 117) - a new
    # engagement is on the reminder's ladder from its first draft.
    info = with_default_dates(_info_from_spec(spec), form, year)
    engagement.mkdir(parents=True)
    try:
        # The catalog the wizard chose is recorded in the details: an
        # engagement that cannot say which checklist it came from cannot be
        # checked against it later. The list is validated whole before a
        # line is written, so a bad row leaves nothing behind.
        create_engagement(engagement, items, info, form=form)
        scaffold_engagement(engagement)
    except Exception:
        # Never a half-built engagement, in the folder or in the store.
        _undo_create(engagement)
        raise
    return {"created": name, "state": _state(engagement)}


def _undo_create(engagement: Path) -> None:
    """What a failed create or rollover leaves behind: nothing.

    The folder first, so the name is free again whatever happens next;
    then the store's row, in its own try, because a store that cannot be
    reached at this moment (locked, refused by version) must not replace
    the refusal sentence the person is owed with its own, nor leave the
    folder standing for ``_new_engagement_dir`` to refuse by name. The
    row it could not drop is a ghost ``create_engagement`` forgets on the
    next attempt.
    """
    shutil.rmtree(engagement, ignore_errors=True)
    try:
        store.forget(store.connect(), engagement)
    except Exception:
        pass


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
        items = load_manifest(engagement.path)
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
    if not ledger.path_for(prior).is_file():
        raise ManifestError(f"No record found in '{prior_raw}'")
    # The prior year's rows are read out of the store, so the store has to
    # describe the prior year before roll_forward() asks what never got
    # filed.
    ensure(prior)

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

    # Last year's details, carried by the one rule (tracker.rollover); the
    # wizard's fields go over it. Rolled From is what retires the prior.
    carried = carry_engagement_info(load_engagement_info(prior), rolled_from=str(prior))
    # Last year's deadline did not carry, and this year's is the form's:
    # the rolled engagement starts on the ladder as a new one does.
    info = with_default_dates(_info_from_spec(spec, carry=carried),
                              carried.form or form, report.target_year)
    engagement.mkdir(parents=True)
    try:
        create_engagement(engagement, report.items, info)
        scaffold_engagement(engagement)
    except Exception:
        _undo_create(engagement)
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


def _seq_of(spec: dict) -> int:
    """The row's record version the app sent, refused when it sent none.

    Every review command is made from a card the app drew out of ``state``,
    and every row there carries its own sequence number (decision 112). A
    spec without one is a caller acting against no view of the record, so
    it is refused here rather than passed to the filer, which treats
    ``None`` as "nothing to be stale against" for the scripts and tests
    that genuinely have no view.
    """
    seq = spec.get("seq")
    if seq is None:
        raise ManifestError(NO_SEQ)
    return int(seq)


def _shortlist_now(engagement: Path, original: str) -> list[str]:
    """What the evidence points at for one parked row, this moment.

    Computed here, outside the lock the filer takes, because the filer
    does not import :mod:`tracker.review` - that would be a second
    call-time cycle beside the one deliberate one - and this module is
    above both and already draws the card the person picked from. The row
    is found exactly as the filer will find it (:func:`filer.find_parked`),
    so what is judged is the row that is filed.

    If the row changes between this read and the filer's own under the
    lock, the sequence number the person sent refuses the action and this
    shortlist is never written. The one window left is a rules edit in
    between - which bumps no row's sequence number - and it is
    milliseconds inside one command.
    """
    entries = read_index(engagement)
    entry = entries[find_parked(entries, original, accepting=(FILE_MOVED,))]
    return [s.identifier for s in review.shortlist_for(entry, load_manifest(engagement))]


def _cmd_assign(argv: list[str]) -> dict:
    """File one parked document under a request, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "identifier": "A01", "keyword": "optional",
                         "seq": <the row's record version, as shown>}
    The working copy is filed under the canonical name, the index row is
    rewritten as Filed (attributed to a person), the keyword - if given - is
    added to the request so the next such file routes itself, and the
    engagement is re-scanned so the status reflects it straight away.

    The row is judged against the record it was picked from: ``seq`` is the
    row's own sequence number as the card showed it, and a row rewritten
    since is refused before a file is touched (decision 112). The shortlist
    the evidence points at is computed here, from the same row the filer
    will act on, and handed in, so a pick that overrules it is recorded on
    the row in words.

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
    seq = _seq_of(spec)
    result = assign_review_file(
        engagement, original, identifier, keyword=str(spec.get("keyword", "") or ""),
        seq=seq, shortlist=_shortlist_now(engagement, original),
    )
    # The re-scan puts the request's status right straight away. There is
    # one reason left for it not to (decision 103): another run holds the
    # engagement.
    scan_note = ""
    try:
        scan_engagement(engagement)
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
            "left_in_review": result.left_in_review,
            "overrode_shortlist": result.overrode_shortlist,
            "scan_note": scan_note,
        },
        "state": _state(engagement),
    }


def _cmd_dismiss(argv: list[str]) -> dict:
    """Record that no request asks for one parked document, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "note": "optional",
                         "seq": <the row's record version, as shown>}
    The index row is rewritten as Not Requested (attributed to a person) and
    nothing moves: the working copy stays where it is and the client's
    original is untouched. Filing it afterwards is how the decision is undone.

    ``seq`` is the row as the person saw it and is required (decision 112):
    a row somebody filed or dismissed while the card was open is refused
    with what the record now says.

    There is no re-scan. The document was never filed under a request, so no
    row's status can change; re-scanning would take the lock again and read
    every working copy to prove that.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the file no request asks for")
    result = dismiss_review_file(engagement, original, str(spec.get("note", "") or ""),
                                 seq=_seq_of(spec))
    return {
        "dismissed": {
            "original_name": result.entry.original_name,
            "decision": result.entry.decision,
            "reason": result.entry.reason,
            "prepared_location": result.entry.prepared_location,
        },
        "state": _state(engagement),
    }


def _cmd_unfile(argv: list[str]) -> dict:
    """Send one filed document back to Needs Review, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "note": "optional",
                         "seq": <the row's record version, as shown>}
    The working copy goes back under the client's own name, the index row is
    rewritten Needs Review (attributed to a person, with what it said
    before), and the filer re-scans, so the request the document was
    answering reverts with a regression note in the same breath. The scan
    summary comes back in ``state`` - it is summarize() over the rows the
    re-scan has just left, and there is nowhere else it lives.

    ``seq`` is the row as the person saw it and is required (decision 112):
    a row somebody re-filed in between is a newer filing, and unfiling it
    would undo a decision this person never saw.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the document to send back for review")
    result = unfile_document(engagement, original, str(spec.get("note", "") or ""),
                             seq=_seq_of(spec))
    return {
        "unfiled": {
            "original_name": result.entry.original_name,
            "decision": result.entry.decision,
            "reason": result.entry.reason,
            "prepared_location": result.entry.prepared_location,
            "moved_working_copy": result.moved_working_copy,
            "left_filed": result.left_filed,
            "scan_note": result.scan_note,
        },
        "state": _state(engagement),
    }


def _cmd_restore(argv: list[str]) -> dict:
    """Put one moved working copy back where the record put it (a person's call).

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "seq": <the row's record version, as shown>}
    The bytes return to the path the row's Prepared Location names - the
    wanderer moved home when it still holds them, a copy from the client's
    original when nothing under the firm's folder does - and the row is
    what it was before it wandered. A home already holding the same bytes
    is left as it is and so is the wanderer; a home holding a *different*
    file is never overwritten - that file stays, this document's copy goes
    to review, and the row parks naming both. The row it comes back with
    says which of the four happened.

    ``seq`` is the row as the person saw it and is required (decision 112),
    as it is for the other three: a row the pass rewrote while the card was
    open is refused before a byte is read.
    """
    engagement = _engagement_dir(argv)
    spec = json.loads(sys.stdin.read() or "{}")
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the working copy to put back")
    result = restore_working_copy(engagement, original, seq=_seq_of(spec))
    return {
        "restored": {
            "original_name": result.entry.original_name,
            "decision": result.entry.decision,
            "reason": result.entry.reason,
            "prepared_location": result.entry.prepared_location,
            "moved_home": result.moved_home,
            "copied_from_original": result.copied_from_original,
            "already_home": result.already_home,
            "parked_as": result.parked_as,
            "scan_note": result.scan_note,
        },
        "state": _state(engagement),
    }


def _cmd_settings(argv: list[str]) -> dict:
    """Where the clients live, who the firm is, and where that is written down."""
    root = clients_root()
    return {
        "root": str(root or ""),
        "exists": bool(root and root.is_dir()),
        "firm": firm(),
        "phone": firm_phone(),
        "product": product_name(),
        "settings_path": str(settings_path()),
    }


def _cmd_set_root(argv: list[str]) -> dict:
    """Record the clients root and the firm: JSON {"root": "<folder>", "firm": "...",
    "phone": "..."} on stdin. Once.

    The phone is the firm's own number, said only by the final-notice
    reminder (decision 117). Like the firm's name, a key that is not sent
    leaves what is recorded alone.
    """
    spec = json.loads(sys.stdin.read() or "{}")
    try:
        root = set_clients_root(str(spec.get("root", "")))
    except SettingsError as exc:
        raise ManifestError(str(exc)) from None
    if spec.get("firm") is not None:
        set_firm(str(spec["firm"]))
    if spec.get("phone") is not None:
        set_firm_phone(str(spec["phone"]))
    return {"root": str(root), "firm": firm(), "phone": firm_phone(),
            "settings_path": str(settings_path()),
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
    "restore": _cmd_restore,
    "edit": _cmd_edit,
    "unlearn": _cmd_unlearn,
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
    finally:
        # The store is opened on first use by whatever command needed it;
        # closing it here checkpoints the write-ahead log and takes its two
        # side files with it, so the app's folder is left as it was found.
        store.close()
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
