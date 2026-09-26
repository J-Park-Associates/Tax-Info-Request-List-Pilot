"""JSON bridge for the desktop app (Electron) — python -m tracker.api <command>.

Commands print a single JSON object to stdout and exit 0, or {"error": ...,
"failure": ...} and exit 1. All real logic lives in the tracker package; this module only
serializes it, so the UI can never disagree with the scanner.

Commands:
  list      every household, return and left-alone folder under the clients
            root, plus the vocabulary the app shows
  templates the form catalog and the calendar's default tax year
  create    a new return, and its household where it is a new one, from
            the wizard's spec (JSON on stdin)
  edit      save the request list and the engagement's details from the
            app's editor (JSON on stdin), as one recorded event
  edit-household  save the household's members, contact and inbox link
            (JSON on stdin), as one recorded event
  propose-spellings  what a document might print one name as, for a person
            to tick (a read: nothing is recorded)
  state     the request rows as the record holds them, the index, the
            triaged review queue, the one summary, useful paths
  priors    list engagements a new year could be rolled forward from
  rollover  build next year's list from a returning client's prior year
  roll-household  roll every ticked return of a household's open year into
            the next one, and retire the returns left out (JSON on stdin)
  mark-shared  record that the firm has shared this household's folder and
            inbox with the client - the firm's word, dated
  accept-folder-name  record that a paused household (or one return) is now
            called by its folder's name - a person's word, dated (decision 188)
  scan      one pass over this return's household, exactly as the scheduled
            run makes it (no draft)
  reminder  the week's draft as the record and the file now stand, at any
            of the four stages, with the body Outlook wants (never sends)
  approve   make the text the panel showed this week's draft, and record it
  assign    file one Needs Review document under a request (a person's call)
  dismiss   record that no request asks for one Needs Review document
  unfile    send one filed document back to Needs Review (a person's call)
  mark-missing  take one request off what a consolidated statement answers,
            and re-scan (a person's call, decision 146)
  restore   put one moved working copy back where the record put it
  unlearn   take back a keyword a filing taught one request, and re-scan
  rename    give a request another identifier and move its filed documents
            with it, as one recorded act (JSON on stdin)
  settings / set-root      where the clients live (the settings file beside the app)
  install-schedule         register the daily job for that same folder
  unlock    clear a stale engagement lock (a fresh one is refused)
  acknowledge-foreign  a person has looked at the lines another machine wrote
            in one return's record; they stop being named (decision 159)
  watch     whether a pass still holds this return, and where it is (a read
            of the lock and the pass's progress file; no store)
  cancel-pass  ask a running Sort & Scan this app started to stop at its
            next file (JSON on stdin: {"pass": id})

Every reply carries ``warnings``; every error also carries ``failure``
({sentence, kind, seq, identifier}) beside ``error`` (decision 193).
Sort & Scan prints progress lines before its reply (tracker.progress).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import shutil
import sys
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import asdict, replace
from functools import cache
from pathlib import Path
from types import SimpleNamespace

from tracker import (
    STANDING_RULES,
    checkpoint,
    content_check,
    door,
    layout,
    ledger,
    names,
    ocr,
    progress,
    reasons,
    records,
    reminder,
    review,
    store,
)
from tracker.filer import (
    DUPLICATE,
    FILE_MOVED,
    FILED,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    NOT_WAITING,
    ROOM_PARKS,
    ROOM_SHORT,
    FilingError,
    Spelling,
    StaleRowError,
    assign_review_file,
    both_gone,
    dismiss_review_file,
    documents_by_request,
    ensure,
    find_parked,
    hand_over,
    hand_over_copies,
    mark_missing_again,
    marked_missing,
    moved_to,
    read_index,
    refresh_household_readme,
    refuse_a_path_past_the_limit,
    rename_request,
    requests_taking,
    restore_working_copy,
    room_for,
    unfile_document,
    waiting_target,
)
from tracker.fsio import make_new_folders, write_text_atomically
from tracker.households import (
    HOUSEHOLD_PAUSED_YEAR,
    claim_disagrees,
    create_household,
    fed_by,
    household_returns,
    load_household_info,
    open_years,
    pause_of,
    resolve_feeds,
    return_disagrees,
    return_name_taken,
    save_household,
    shared_on,
)
from tracker.layout import (
    CLIENTS_TREE,
    ENGAGEMENT_LABEL_PATTERN,
    INBOX_DIR_NAME,
    MAX_PATH_LENGTH,
    PATH_TOO_LONG,
    PRIVATE_TREE,
    RETURN_NAME_PATTERN,
    client_household_dir,
    household_of,
    inbox_dir_for,
    inbox_of,
    locate,
    originals_dir_for,
    private_household_dir,
    return_dir_for,
    year_of,
)
from tracker.locking import (
    LOCK_FILENAME,
    RUN_TIME_LIMIT_SECONDS,
    STALE_LOCK_SECONDS,
    EngagementLockedError,
    clear_stale_lock,
    engagement_lock,
    is_this_host,
    lock_status,
    pid_alive,
)
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
    NO_LIST_HEAD,
    NOT_APPLICABLE_LABEL,
    NOT_ASKED_LABEL,
    OVERRIDE_REASON_OTHER,
    OVERRIDE_REASONS,
    UNSCANNED_LABEL,
    YEAR_MAX,
    YEAR_MIN,
    ListMoved,
    ManifestError,
    Override,
    Status,
    check_rules,
    check_tax_year,
    create_engagement,
    has_a_document,
    is_idle_unasked,
    item_from_fields,
    item_from_record,
    list_head,
    load_engagement_info,
    load_manifest,
    recorded_rules,
    rule_as_read,
    save_rules,
    status_label,
    summarize,
    unlearn_keyword,
)
from tracker.names import NO_PEOPLE, ONE_WORD_SPELLING, propose_spellings
from tracker.page import PALETTE, slug
from tracker.records import (
    CANDIDATE_SEP,
    DATE_FIELDS,
    ENGAGEMENT_EDITABLE,
    ENGAGEMENT_FIELDS,
    ENGAGEMENT_HELP,
    ENGAGEMENT_LABELS,
    EVIDENCE_PLACES,
    EVIDENCE_RULES,
    FEED_REFUSED,
    HOUSEHOLD_EDITABLE,
    NO,
    PEOPLE_HELP,
    PEOPLE_LABEL,
    PERSON_KIND_LABELS,
    PERSON_KINDS,
    RETURN_NAME_HELP,
    RETURN_NAME_LABEL,
    RULE_FIELDS,
    RULE_FLAG_FIELDS,
    THE_RECORD,
    YES,
    EngagementInfo,
    Feed,
    HouseholdInfo,
    IndexEntry,
    Person,
    identifier_key,
    is_a_spelling,
    ledger_key,
    person_to_json,
)
from tracker.registry import (
    EmptyRoot,
    Engagement,
    Household,
    Registry,
    RegistryError,
    discover_engagements,
    engagement_from,
    households_named,
    mark_superseded,
)
from tracker.registry import (
    held_back as registry_held_back,
)
from tracker.rollover import (
    ORIGIN_NEW,
    ORIGIN_NOT_APPLICABLE,
    ORIGIN_PRIOR,
    UNKNOWN_YEAR_LABEL,
    ReturnPlan,
    RolledNotAllRetired,
    carried_link,
    carry_engagement_info,
    detect_year,
    next_tax_year,
    open_year_returns,
    roll_forward,
    roll_household,
    with_default_dates,
)
from tracker.runner import (
    DRAFT_WEEKDAY,
    LOG_FILENAME,
    LOG_NOT_WRITTEN,
    NOTHING_OUTSTANDING,
    PAGE_NOT_WRITTEN,
    REMINDERS_NEVER,
    STATUS_PAGE_FILENAME,
    WEEKDAY_NAMES,
    EngagementRun,
    RunReport,
    append_log,
    created_on,
    last_draft_day,
    last_drafted,
    last_pass_line,
    reader_start_warning,
    run_household,
    status_report,
    write_status_page,
)
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    assign_files,
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
    ERROR_LOG_FILENAME,
    EXAMPLE_ROOT,
    SET_ROOT_HINT,
    SettingsError,
    app_dir,
    clients_root,
    error_log,
    error_log_path,
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
    NOT_ASKED_SECTION,
    VIEW_FILENAME,
    VIEW_LABEL,
    VIEW_OPEN_LABEL,
    VIEW_STATES,
    view_state,
)

log = logging.getLogger("tracker.api")

# ------------------------------------------------------------ the envelope ----
#
# Every reply carries ``warnings``, and every error one ``failure`` beside
# the unchanged ``error`` string (decision 193). How an error is said is
# decided in one place, :func:`_failure_of`: a refusal the tracker words
# for a person is said in its own sentence; anything else by its class and
# code, and its full text and traceback go only to the local error log.

#: This command's envelope warnings - what a person must see about the
#: reply beyond its result - reset by :func:`main`.
_WARNINGS: list[str] = []
#: The spec :func:`_read_spec` parsed, so a failure can name the row the
#: person clicked; reset by :func:`main`.
_ASKED: dict = {}
#: The command :func:`main` is running, which :func:`_with_list` holds to
#: :data:`LIST_CHANGING` (decision 194's review, S3); set by :func:`main`.
_RUNNING: dict = {"command": ""}

#: The usage line, a refusal like any other (its text is unchanged).
USAGE = "usage: tracker.api {commands}"
#: What an error the tracker did not expect is said as: its class and code,
#: never its message, and where its detail went.
FAILED = ("The tracker hit an error it did not expect ({kind}). What it finished is on the record; "
          "the details are in {log} beside the tracker's database.")
#: The notices' three buttons (decision 193, ruling 12). Static in
#: ``index.html``'s template, pinned to these word for word, because a
#: notice must work when the very first ``list`` fails, before any
#: vocabulary exists.
NOTICE_LABELS = {"retry": "Retry", "look": "Look again", "dismiss": "Dismiss"}


#: A clients root that could not be walked (decision 193): said, never an
#: empty answer that reads as a practice with nothing in it.
PRACTICE_NOT_WALKED = ("The clients folder could not be walked just now, so what needs the whole "
                       f"practice is not shown; the details are in {ERROR_LOG_FILENAME}.")
#: The Reminder card kept on screen when its reminder cannot be read (D7).
REMINDER_UNREADABLE = "This return's reminder could not be read just now; the notice above says why."
#: One return's reminder line on the household card that could not be read.
REMINDER_LINE_UNREADABLE = "{label}: its reminder could not be read ({kind})"
#: A pass that filed and then could not redraw the page (D5): the counts
#: stay, and the app redraws from the record.
STATE_NOT_REDRAWN = ("The pass finished and its counts stand, but the page could not be redrawn "
                     "({kind}); it is drawn again from the record.")
#: Stop asked of a pass this app is not running (ruling 7 and the lane's).
NOTHING_TO_STOP = "There is no pass this app started running to stop; nothing was changed."
#: How often the app asks whether a lock it shows has gone (ruling 10).
LOCK_WATCH_SECONDS = 5
#: The lock notice's words (D4): nothing waits, and nothing needs clearing.
LOCK_RUNNING = "A pass that started at {started} on {host} is holding this return."
#: The same, about a lock that is not the shown return's - a sibling, a fed
#: return or the household (the review's S1): named by its own label.
LOCK_RUNNING_OTHER = "A pass that started at {started} on {host} is holding {label}."
LOCK_ON = "It is on {household}: {name}."
LOCK_GREYED = ("This return's buttons are greyed while it runs and come back by themselves the "
               "moment it lets go.")
LOCK_LEFT_BEHIND = ("A pass that started at {started} on {host} left its lock behind ({minutes} min "
                    "old); it has most likely ended. The next pass replaces it, or clear it here.")
LOCK_CLEARED = "The lock left behind was cleared ({minutes} min old)."
LOCK_BUTTONS_BACK = "The pass let go of this return; its buttons are back."
#: Sort & Scan, watched (decision 193).
PROGRESS_HOUSEHOLD = "{household} ({n} of {of})"
PROGRESS_SORT = "Sorting {name}"
PROGRESS_SCAN = "Checking {name}"
PROGRESS_STOP = "Stop"
PROGRESS_STOPPING = "Stopping after this file\u2026"
#: What the shell says when a child is killed, ends with no reply, or
#: cannot start - learned from here, with pinned defaults for a first
#: start (``app/main.js``).
SHELL_KILLED = ("The pass ran past its limit of {minutes} minutes and was stopped. What it finished "
                "is on the record, and the next pass does the rest.")
SHELL_KILLED_AT = "It was on {household}: {name}."
SHELL_NO_REPLY = "The tracker ended without a reply (exit code {code}); the details are in the error log."
SHELL_COULD_NOT_START = "The tracker could not start ({code})."
SHELL_COULD_NOT_SEND = "The app could not send that to the tracker ({kind}); nothing was changed."
#: An error of the page's own, said by its class; its message goes to the
#: error log through the shell (the review's S5).
PAGE_ERROR = "The app met an error of its own ({kind}); the details are in the error log."
#: What a Sort & Scan reply is said as (the review's S4, decision 42).
SCAN_SCANNING = "Scanning\u2026"
SCAN_NOTHING_DONE = "Nothing done: {why}."
SCAN_PROBLEM = "The pass reported a problem: {error}"
SCAN_COMPLETE = "Pass complete \u2014 {did}.   {summary}"
SCAN_FILED = "filed {n}"
SCAN_REVIEW = "{n} to review"
SCAN_SYNCING = "{n} still syncing"
SCAN_NOT_SORTED = "{n} file(s) could not be sorted"
SCAN_BUT = "But {problems}."
#: A notice said more than once is one notice with a count.
NOTICE_REPEATED = "({n} times)"
#: A warning a reply brought about a return other than the one shown - the
#: hand-over picker's read of its target (decision 194's review, S1): said
#: with that return's label, so no notice reads as about the return shown.
NOTICE_ABOUT = "{label}: {sentence}"


class _Stale(ManifestError):
    """The record moved under a click that is not a row's (decision 193):
    a household accepted from an old page, a draft approved after it
    changed. Said as *stale* - look again - and still a ManifestError."""


def _warn(sentence: str) -> None:
    """Say ``sentence`` in this reply's ``warnings``, once."""
    if sentence and sentence not in _WARNINGS:
        _WARNINGS.append(sentence)


def _failure_of(exc: BaseException) -> dict:
    """The one rule for how an error is said (decision 193, ruling 3):
    ``{"sentence", "kind", "seq", "identifier"}``, plus ``lock`` when
    another pass holds the return. In this order: stale, locked, the
    record's and the store's own failures by class (their text can quote
    a journal line), the tracker's worded refusals, and anything else by
    class."""
    seq = getattr(exc, "seq", None)
    identifier = getattr(exc, "identifier", None)
    if seq is None:
        seq = _ASKED.get("seq")
    if identifier is None:
        identifier = _ASKED.get("original") or _ASKED.get("identifier")
    extra: dict = {}
    if isinstance(exc, (StaleRowError, ListMoved, _Stale)):
        kind, sentence = "stale", str(exc)
    elif isinstance(exc, EngagementLockedError):
        kind, sentence = "locked", str(exc)
        held = getattr(exc, "lock", None)
        extra["lock"] = (_lock_payload(Path(held).parent)
                         if held and Path(held).name == LOCK_FILENAME else None)
    elif isinstance(exc, (store.StoreUnavailable, ledger.RecordNotWritten, ledger.LedgerError)):
        kind, sentence = "failed", FAILED.format(kind=content_check.said_as_class(exc),
                                                 log=ERROR_LOG_FILENAME)
    elif isinstance(exc, (ManifestError, FilingError, door.DoorError, layout.LayoutError,
                          SettingsError, reminder.ReminderError, RegistryError,
                          store.StoreError)):
        kind, sentence = "refused", str(exc)
    else:
        kind, sentence = "failed", FAILED.format(kind=content_check.said_as_class(exc),
                                                 log=ERROR_LOG_FILENAME)
    reply = progress.failure_reply(sentence, kind, seq=seq, identifier=identifier, **extra)
    return reply["failure"]


def _reply_failure(exc: BaseException) -> int:
    failure = _failure_of(exc)
    reply = progress.failure_reply(failure["sentence"], failure["kind"], seq=failure["seq"],
                                   identifier=failure["identifier"], warnings=_WARNINGS,
                                   **{k: v for k, v in failure.items()
                                      if k not in ("sentence", "kind", "seq", "identifier")})
    print(json.dumps(reply))
    return 1

#: The folder the app runs from (the repository from source, beside the
#: executable when frozen) - the same answer tracker.settings gives.
REPO_ROOT = app_dir()
def _root() -> Path:
    """The clients root from the settings file - the one place it is kept -
    held to the settings' rule on every command that reads it (decision
    188, E-13): a root saved before a rule, or one a person has since made
    one level too deep by moving the trees around it, is refused with
    "Clients folder problem: " and the refusal, never walked."""
    if clients_root() is None:
        raise ManifestError(
            f"Tell the app where your clients live first (Settings, or `{SET_ROOT_HINT}`)"
        )
    return door.checked_root()


def _saved_root() -> Path | None:
    """The saved clients root held to the rule, as :func:`_root` holds it,
    or ``None`` where none is saved - for the commands that answer without
    one (the list before a root is chosen, the wizard's priors)."""
    return None if clients_root() is None else door.checked_root()

# ----------------------------------------------------------------- commands ----


#: The one flag the app passes: which engagement a command is about.
ENGAGEMENT_FLAG = "--engagement"
#: Every word the household's card, the wizard's household step and the
#: misfit list show (decision 125). The renderer types none of it: it
#: reads these from the vocabulary, as it reads every other word Python
#: owns.
HOUSEHOLD_HEADING = "Household"
HOUSEHOLD_NAME_LABEL = "Household"
MEMBERS_LABEL = "Shared with (as typed by the firm)"
MEMBERS_HELP = ("who this household's folder is meant to be shared with - the tracker cannot "
                "read Drive's sharing, so this is the firm's own note")
CONTACT_LABEL = "Contact"
CONTACT_HELP = "the greeting name in every return's letter, filled into each return when it is made"
INBOX_LINK_LABEL = "Inbox link"
INBOX_LINK_HELP = "pasted into every return's letter; paste it once the inbox is shared"
OPEN_CLIENT_FOLDER_LABEL = "Open Client Folder"
OPEN_INBOX_LABEL = "Open Inbox"
EDIT_HOUSEHOLD_LABEL = "Edit household"
NEW_HOUSEHOLD_LABEL = "New household"
EXISTING_HOUSEHOLD_LABEL = "Add a return to an existing household"
HOUSEHOLD_RETURNS_HEADING = "Returns this year"
HOUSEHOLD_QUEUE_LINE = "{n} document(s) waiting for a person across this household"
#: The feed list (decision 129): what a drop folder feeds beyond its own
#: household's returns, what a household is fed by, and the two warnings a
#: person reads before they extend either. Every one of them is the API's
#: word and the page types none of them.
FEEDS_LABEL = "Also feeds"
FEEDS_HELP = ("returns in other households this drop folder feeds, by return line; most "
              "households feed only their own")
FEEDS_LINE = "This drop folder also feeds: {listed}"
FED_BY_LINE = "Also fed by the drop folder of: {listed}"
ADD_FEED_LABEL = "Add a return this drop folder feeds"
FEED_WARNING = ("Anyone with access to this drop folder may drop for this return. Its documents "
                "will rest under the folder it lives in, shared with: {members}.")
RETURN_WARNING = ("Everyone with access to this folder will see this return's documents. Add it "
                  "here only if every member may.")
HAND_OVER_LABEL = "File under another return"
#: The two boxes that answer come with their own words rather than borrowing
#: the household heading and the editor's title, which happened to read
#: nearly right and would have drifted the moment either was reworded. What
#: is being picked is a return and then one of that return's requests.
HAND_OVER_RETURN_LABEL = "The return that takes it"
HAND_OVER_REQUEST_LABEL = "Under which request"
#: What the app says once a document has been filed under another return
#: (decision 132): where it went, and that the row here is gone - released,
#: nothing about it kept in this return. Filled by the page with the
#: label and the request the reply carries.
HANDED_OVER_LINE = "Filed under {label} ({identifier}); nothing about it stays here"
#: The one click (decision 204): a document that names the person of a
#: return in another household waits here, and this is the button that
#: hands it over to that return - the requests its list accepted, shown
#: under it, and nothing picked on the page. Filled with the return's label.
FILE_WHERE_IT_WAITS_LABEL = "File it under {label}"
#: What stands in for the members of a household nobody has typed any for.
#: The warning must still say who will see the documents, and "nobody typed
#: yet" is the honest answer - the tracker cannot see Drive's sharing.
NOBODY_TYPED = "nobody typed yet"
#: What a hand-over to a return this drop folder does not feed is refused
#: with. Nothing routes outside the feed list, and a person extends it
#: deliberately or not at all.
NOT_FED = "{label} is not a return this drop folder feeds; add it to the household's feeds first"

MISFITS_HEADING = "Folders the tracker leaves alone"
MISFITS_NOTE = ("Each is listed with the one reason it does not fit the layout; nothing in it "
                "is ever read, moved or renamed.")
TWO_OPEN_YEARS_NOTE = ("Two years are open in this household ({years}); nothing is sorted from "
                       "its inbox until one is retired in the editor")
#: The two grants a person makes in Drive, once per household, and the one
#: thing the tracker can check was done (decision 126). **The tracker
#: cannot see Drive's sharing** - Drive for desktop exposes no permission
#: to a program - so it asks for the grants in words, in order, and
#: records only that a person said they had made them. Shown when a
#: household's first return is made, and on the household's card until
#: somebody presses *Mark as shared*. The renderer types none of it.
SHARING_CHECKLIST = (
    "Share the household folder, {client_folder}, with the client as Viewer.",
    "Share {inbox} with the client as Contributor.",
    "Paste the inbox's link into the household's Inbox link, then press Mark as shared.",
)
SHARING_HEADING = "Before the client can drop anything"
MARK_SHARED_LABEL = "Mark as shared"
SHARED_ON_LINE = "Marked as shared on {day} by the firm"
NOT_YET_SHARED_LINE = "Not yet marked as shared"
SHARING_NOTE = ("The tracker cannot see Drive's sharing. The two grants are the firm's to make, once; "
                "the year folders are view-only through the household folder, and nothing is ever re-shared.")
#: Why *Mark as shared* refuses: the inbox's link is the one part of the
#: three the tracker can see was done, so it is the one part it insists on.
SHARE_LINK_FIRST = "paste the inbox's link into the household first"
#: What the returning-client page says under its checklist of returns, so
#: nobody unticks a return expecting it to sit still (decision 126).
ROLLOVER_UNTICKED_NOTE = ("A return left unticked is retired for {year}: it is set inactive and "
                          "stops being chased. Tick it later and roll it on its own if that changes.")
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
#: Decision 146: the button beside each request a filed consolidated
#: statement answers without a copy, and the words that introduce them.
MARK_MISSING_LABEL = "Mark {identifier} missing"
ALSO_ANSWERS_LABEL = "also answers"
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
#: in the firm's folder under a name that belongs to a request (decision
#: 168), because "keep it where it is" means nothing anywhere else. The renderer shows these and types none of them.
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
#: What a save is told of a row carrying a key that is no column this
#: version knows (decision 160): a newer window's row, or a mistake. Refused
#: rather than dropped, because a column dropped on the way in is exactly
#: the silent loss a save must not make.
UNKNOWN_COLUMN = "Row {n}: '{key}' is not a column this version knows; close the app and open it again"
#: What a save is told when it would take a request that holds filed
#: documents off the list - removed, or respelt, which to a save is the same
#: (decision 160, the audit's D-7). The documents would be orphaned under a
#: folder no request names, and the letter and the README would ask the
#: client again. The rename carries them; unfiling them frees the request.
HOLDS_DOCUMENTS = ("{identifier} holds {n} filed document(s), so a save cannot take it off the list "
                   "or give it another identifier: to stop asking for it, set it Not Applicable "
                   "instead of removing it; to change its identifier, use Rename below the list, "
                   "which moves its documents with it")
#: The editor's rename (decision 160): its fold's title, the sentence under
#: it, the two boxes' labels, its button, and what it says once done. It
#: lands at once, on its own - not part of Save - so the rows typed and not
#: saved stay in front of the person.
RENAME_TITLE = "Rename a request"
RENAME_HINT = ("Gives a request another identifier and moves its filed documents with it, at once. "
               "Changing an identifier in the list and saving is refused while the request holds "
               "documents; a change of case alone is saved in the list.")
RENAME_FROM_LABEL = "Request"
RENAME_TO_LABEL = "New identifier"
RENAME_LABEL = "Rename"
RENAMED_NOTE = "{old} renamed {new}; {moved} working copy(ies) moved with it and the request was re-scanned"
RENAME_LEFT_NOTE = "left in the old folder because no row names them: {left}"
#: What the returning-client page says of last year's set-aside rows, in
#: one line beside the carried counts.
NOT_APPLICABLE_CARRIED = "{n} request(s) not applicable last year - review them in the editor"
#: And of the catalog rows the client never had, added as not asked
#: (decision 142, rewording decision 9: they used to be offered, not added).
NEW_NOT_ASKED_CARRIED = ("{n} catalog row(s) this client never had added as not asked - "
                         "a document for one files there; set Asked in the editor to ask for it")
#: The wizard's heading over the catalog's checkboxes, and the sentence
#: under it (decision 142): a tick is a request the client is asked for
#: and reminded of; every row is on the return either way.
ASK_THE_CLIENT = "Ask the client"
#: The name the app's folded table of not-asked rows is read out by, and
#: the returning-client page's label over the template pick (decision 142).
NOT_ASKED_TABLE_LABEL = "Requests not asked for"
ROLL_TEMPLATE_LABEL = "Form template (fills blanks, adds the rows this client never had as not asked)"
ASK_THE_CLIENT_NOTE = ("Every row is on the return. A ticked row is asked for and reminded; "
                       "an unticked one is never asked for, but a document that arrives for "
                       "it is filed there.")
#: The settings page's box for the firm's telephone number (decision 117).
#: It sits beside the firm's name because it is the firm's, not one
#: engagement's, and only the final-notice reminder ever says it.
FIRM_PHONE_LABEL = "Firm phone"
FIRM_PHONE_HELP = "named in the final-notice reminder; blank drops that sentence"

# ---- the people block (decision 128) ----------------------------------------
#: Every word the wizard's and the editor's People block shows. The record
#: owns the heading and what the list is for (``records.PEOPLE_LABEL`` and
#: ``PEOPLE_HELP``) and :mod:`tracker.names` owns the two refusals; these
#: are the block's own controls, and the page types none of them.
PERSON_KIND_LABEL = "Who"
PERSON_NAME_LABEL = "Name"
SPELLINGS_LABEL = "Spellings documents use"
SPELLINGS_HELP = ("ticked spellings are what a page is matched against; untick one a document "
                  "never prints, and add any the app did not propose")
ADD_PERSON_LABEL = "Add a person"
REMOVE_PERSON_LABEL = "Remove"
#: The box for a spelling the app did not propose takes one per line: a
#: comma is part of the very form a document prints (``Park, John``), so
#: splitting on one would turn the form a person typed into two one-word
#: spellings and then refuse both.
OWN_SPELLING_HINT = "another spelling, one per line"
REVIEW_PEOPLE_LABEL = "Review people"
#: Said once after a household rolls forward: the people carried unchanged
#: and are worth one look (decision 128). Nothing blocks on it - strict
#: parking is the safety net.
PEOPLE_ROLLED_NOTE = "{n} return(s) rolled; review each return's people once"
#: The card's offer beside a page that named nobody, and what the box asks
#: for. Pre-filled with nothing: the person types what the page shows.
TEACH_SPELLING_LABEL = "Teach this spelling"
TEACH_SPELLING_HINT = "the name as this page prints it"


def _folder_name(value: object, what: str) -> str:
    """One household or return name from what a person typed (``what`` is
    ``household`` or ``return``), or the refusal that says why.

    A household and a return are each **one** folder name: the layout puts
    them where they go (decision 125), and the layout's one name rule
    (decision 188, ``layout.checked_name``) says what one may be - the
    same sentence wherever a name is typed: the wizard, a new return, a
    rolled return's new name, a feed.
    """
    try:
        return layout.checked_name(value, what)
    except layout.LayoutError as exc:
        raise ManifestError(str(exc)) from None


def _new_return_dir(root: Path, household: str, year: int, return_name: str,
                    items: list | None = None) -> Path:
    """Where a new return goes: ``<root>/<private tree>/<household>/<year>/<return>``.

    Refused when the household or the return is not a single folder name,
    when the year is outside the bounds the wizard shows, when a return of
    that name already exists for that household and year, and when the
    deepest working copy the list implies would pass what Windows will
    open (§3.9.1 of decision 125): a folder made today that cannot hold a
    filed document in February is a failure at a filing deadline, and the
    refusal names the length so a person knows what to shorten.
    """
    household = _folder_name(household, "household")
    return_name = _folder_name(return_name, "return")
    year = check_tax_year(int(year))
    engagement = return_dir_for(root, household, year, return_name)
    # Unique by the layout's key within the household-year (decision
    # 188), so a look-alike of a return already there is that return.
    if (taken := return_name_taken(engagement.parent, return_name)) is not None:
        raise ManifestError(
            f"A return named '{taken}' already exists for {household} {year}")
    refuse_a_path_past_the_limit(engagement, items or [])
    return engagement


#: What creating a household says when a folder of that name is already
#: there and holds no record (decision 137, M1): the tracker did not make
#: it, so it is a misfit, and a misfit is left alone. Refused before
#: anything is written.
HOUSEHOLD_NOT_OURS = ("A folder named '{name}' is already there and the tracker did not make it. "
                      "Choose another name, or move that folder aside first. Nothing was changed.")
def _engagement_dir(argv: list[str]) -> Path:
    """The engagement a command is about: ``ENGAGEMENT_FLAG <folder>``.

    A flag with nothing after it, or an empty folder, gets the same sentence
    as no flag at all (it used to be a bare IndexError). The folder must lie
    under the clients root, and **a clients root must be set** (decision
    137): the app only ever names folders the root listed, so anything else
    is a mistake, not a request, and with no root there is nothing to be
    under. It must also be a return by its place in the layout - four
    levels down, under a year - so a year or a household folder is refused
    rather than read one level too high.
    """
    hint = f"Pick an engagement first ({ENGAGEMENT_FLAG} <folder>)"
    if ENGAGEMENT_FLAG not in argv:
        raise ManifestError(hint)
    position = argv.index(ENGAGEMENT_FLAG) + 1
    given = argv[position].strip() if position < len(argv) else ""
    if not given:
        raise ManifestError(hint)
    return _return_dir(given)


def _return_dir(given: str | Path) -> Path:
    """The return a path the app sent names, rebuilt from the checked
    clients root and its own names (``door.return_dir``, decisions 176 and
    188) - a folder in the client tree, a year or a household folder, and
    anything outside the root are refused with the layout's sentence."""
    return door.return_dir(given, root=_root())


def _household_dir(given: str | Path) -> Path:
    """The household a path the app sent names (``door.household_dir``)."""
    return door.household_dir(given, root=_root())


#: What a command is told when the app's JSON is not one object.
NOT_A_SPEC = "The app sent something that is not a JSON object; nothing was changed"


def _read_spec() -> dict:
    """The JSON object the app wrote on stdin, read as UTF-8 bytes.

    main.js writes ``JSON.stringify(payload)``, which leaves every letter
    outside ASCII as it is, and Node writes a string to a pipe as UTF-8.
    Python reads a pipe as text in the machine's ANSI code page, so on the
    firm's Windows machine ``sys.stdin.read()`` turned the ``ñ`` of
    ``Muñoz`` into ``Ã±`` - in a household folder the client is shared -
    and refused ``Á`` outright. The bytes are read and decoded here, the
    one reading of stdin, so no command depends on the code page. A
    stream with no bytes under it (a test's ``StringIO``) is read as the
    text it already is.
    """
    stream = sys.stdin
    raw = stream.buffer.read().decode("utf-8") if hasattr(stream, "buffer") else stream.read()
    spec = json.loads(raw or "{}")
    if not isinstance(spec, dict):
        raise ManifestError(NOT_A_SPEC)
    # Kept for the failure envelope: the row a click was about (decision 193).
    _ASKED.update(spec)
    return spec


def default_return_name(form: str, client: str) -> str:
    """How a return folder is named when nobody types a name: the form
    first, the client after (``layout.RETURN_NAME_PATTERN``).

    The catalog's own id, not its label - ``1040 - John & Maria Park``,
    which is the name the same return keeps every year (decision 125). The
    renderer fills the same pattern for its preview, so the box and the
    folder agree.
    """
    return layout.normalised_name(sanitize_component(
        RETURN_NAME_PATTERN.format(form=form, client=client or "New client").strip()
    ))


#: A word as a class name, from the module that owns how the firm's pages
#: spell one, so a status chip in the app and a status badge on the view
#: are classed the same way by the same code.
_slug = slug


def _stages() -> list[dict]:
    """The reminder's four rungs as the app draws them (decision 118): the
    number, the name the stage carries, the key its colour has in the
    palette, and where that stage spends its emphasis. The renderer looks
    the colour up and applies the flags; it decides neither."""
    return [{"number": stage.number, "name": stage.name,
             "colour": reminder.STAGE_COLOURS[stage.number],
             "emphasis": asdict(reminder.STAGE_EMPHASIS[stage.number])}
            for stage in reminder.STAGES]


def standing_rules() -> list[dict]:
    """The package's standing rules with the folder names filled in."""
    names = {"inbox": INBOX_DIR_NAME, "review": REVIEW_DIR_NAME, "record": THE_RECORD}
    return [{"headline": headline, "detail": detail.format(**names)}
            for headline, detail in STANDING_RULES]


#: The heading the root dialog lists the returns short of room under, after
#: a person sets the clients root (decision 131).
ROOM_HEADING = "Returns short of room under this root"


#: What each key of a return's ``paths`` names: a folder or a file
#: (decision 188, E-14). The shell ``lstat``s a path before it opens it and
#: refuses a link, or a path that is no longer the kind reported.
PATH_KINDS: dict[str, str] = {
    "engagement": "folder", "inbox": "folder", "originals": "folder", "client_folder": "folder",
    "household": "folder", "prepared": "folder", "view": "file", "draft": "file", "status": "file",
}
#: What the shell says when a reported path is no longer what it was.
SHELL_NOT_OPENED = "That is no longer the folder or file the tracker reported; nothing was opened."


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
        # What a row nobody asked for is called while nothing has arrived
        # for it (decision 142), and the chip class it is drawn with.
        "not_asked_label": NOT_ASKED_LABEL,
        "not_asked_key": _slug(NOT_ASKED_LABEL),
        # The wizard's heading over the catalog's ticks, and its sentence.
        "ask_the_client": ASK_THE_CLIENT,
        "ask_the_client_note": ASK_THE_CLIENT_NOTE,
        "not_asked_table_label": NOT_ASKED_TABLE_LABEL,
        # The one refusal of a list nobody is asked for (R6), which the
        # wizard also says before it calls.
        "nothing_asked": NOTHING_ASKED,
        "roll_template_label": ROLL_TEMPLATE_LABEL,
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
        # The catalog rows a rollover added as not asked (decision 142),
        # grouped on their origin value.
        "origin_new": ORIGIN_NEW,
        "new_not_asked_carried": NEW_NOT_ASKED_CARRIED,
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
                          "mark_missing": MARK_MISSING_LABEL,
                          "also_answers": ALSO_ANSWERS_LABEL,
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
                          "card_position": CARD_POSITION,
                          # Decision 129's answer, beside the other three:
                          # a parked document handed to a return this drop
                          # folder feeds, own or fed, and the two boxes
                          # that answer it - which return, and which of
                          # that return's requests.
                          "hand_over": HAND_OVER_LABEL,
                          "hand_over_return": HAND_OVER_RETURN_LABEL,
                          "hand_over_request": HAND_OVER_REQUEST_LABEL,
                          # And what the page says once it is done
                          # (decision 132): the row here is released.
                          "handed_over": HANDED_OVER_LINE,
                          # Decision 204's one click: a row that names
                          # another household's person, filed where it
                          # waits, with nothing picked on the page.
                          "file_where_it_waits": FILE_WHERE_IT_WAITS_LABEL},
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
        # The name tier's words (decision 128), from the two modules that
        # own them: the three kinds of person, the labels each is shown
        # under, the two refusals, and what the card says and offers where
        # a page named nobody. The page types none of them.
        "people": {
            "label": PEOPLE_LABEL,
            "help": PEOPLE_HELP,
            "kinds": [{"value": kind, "label": PERSON_KIND_LABELS[kind]} for kind in PERSON_KINDS],
            "kind_label": PERSON_KIND_LABEL,
            "name_label": PERSON_NAME_LABEL,
            "spellings_label": SPELLINGS_LABEL,
            "spellings_help": SPELLINGS_HELP,
            "add": ADD_PERSON_LABEL,
            "remove": REMOVE_PERSON_LABEL,
            "own_spelling": OWN_SPELLING_HINT,
            "one_word": ONE_WORD_SPELLING,
            "none_yet": NO_PEOPLE,
            "review_people": REVIEW_PEOPLE_LABEL,
            "rolled_note": PEOPLE_ROLLED_NOTE,
            "outcomes": {"confirmed": names.NAME_CONFIRMED, "other": names.NAME_VETOED,
                         "absent": names.NAME_ABSENT},
            "teach": TEACH_SPELLING_LABEL,
            "teach_hint": TEACH_SPELLING_HINT,
        },
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
        # The shape of the clients root, from the module that owns it
        # (decision 125): the two trees, the one inbox, and the two
        # patterns the wizard's previews fill.
        "layout": {
            "clients_tree": CLIENTS_TREE,
            "private_tree": PRIVATE_TREE,
            "inbox": INBOX_DIR_NAME,
            "return_name_pattern": RETURN_NAME_PATTERN,
            "engagement_label_pattern": ENGAGEMENT_LABEL_PATTERN,
        },
        # Every word the household's card, the wizard's household step and
        # the misfit list show. The page types none of them.
        "household": {
            "heading": HOUSEHOLD_HEADING,
            "name_label": HOUSEHOLD_NAME_LABEL,
            "members_label": MEMBERS_LABEL,
            "members_help": MEMBERS_HELP,
            "contact_label": CONTACT_LABEL,
            "contact_help": CONTACT_HELP,
            "link_label": INBOX_LINK_LABEL,
            "link_help": INBOX_LINK_HELP,
            "return_name_label": RETURN_NAME_LABEL,
            "return_name_help": RETURN_NAME_HELP,
            "open_client_folder": OPEN_CLIENT_FOLDER_LABEL,
            "open_inbox": OPEN_INBOX_LABEL,
            "edit": EDIT_HOUSEHOLD_LABEL,
            "new": NEW_HOUSEHOLD_LABEL,
            "existing": EXISTING_HOUSEHOLD_LABEL,
            "returns_heading": HOUSEHOLD_RETURNS_HEADING,
            "queue_line": HOUSEHOLD_QUEUE_LINE,
            "misfits_heading": MISFITS_HEADING,
            "misfits_note": MISFITS_NOTE,
            "two_open_years": TWO_OPEN_YEARS_NOTE,
            "editable": list(HOUSEHOLD_EDITABLE),
            # The sharing checklist and the firm's dated word about it
            # (decision 126). The page shows these and types none of them;
            # the three lines themselves arrive filled, in `checklist`.
            "sharing_heading": SHARING_HEADING,
            "sharing_note": SHARING_NOTE,
            "mark_shared": MARK_SHARED_LABEL,
            "shared_on_line": SHARED_ON_LINE,
            "not_yet_shared_line": NOT_YET_SHARED_LINE,
            # And the one line the returning-client page needs of its own:
            # what unticking a return does to it.
            "rollover_unticked": ROLLOVER_UNTICKED_NOTE,
            # The feed list (decision 129): what this drop folder also
            # feeds, who feeds it, the word that adds one, and the two
            # warnings a person reads before extending either. The page
            # shows them and types none of them.
            "feeds_label": FEEDS_LABEL,
            "feeds_help": FEEDS_HELP,
            "feeds_line": FEEDS_LINE,
            "fed_by_line": FED_BY_LINE,
            "add_feed": ADD_FEED_LABEL,
            "feed_warning": FEED_WARNING,
            "return_warning": RETURN_WARNING,
            "nobody_typed": NOBODY_TYPED,
            # A paused household (decision 188): the one action and its help.
            "accept_folder_name": ACCEPT_FOLDER_NAME_LABEL,
            "accept_folder_name_help": ACCEPT_FOLDER_NAME_HELP,
        },
        "year_min": YEAR_MIN,
        "year_max": YEAR_MAX,
        "example_root": EXAMPLE_ROOT,
        "engagement_flag": ENGAGEMENT_FLAG,
        "commands": sorted(COMMANDS),
        # What each path the API reports is (decision 188, E-14): the shell
        # opens one only while it is still that kind of thing and no link.
        "path_kinds": PATH_KINDS,
        # The shell's own sentences (decision 193), learned here with pinned
        # defaults in main.js for a first start, and the error log it appends
        # a failed child's stderr to: beside the tracker's database, a path
        # the shell never builds itself.
        "shell": {"not_opened": SHELL_NOT_OPENED, "killed": SHELL_KILLED,
                  "killed_at": SHELL_KILLED_AT, "no_reply": SHELL_NO_REPLY,
                  "could_not_start": SHELL_COULD_NOT_START,
                  "could_not_send": SHELL_COULD_NOT_SEND, "page_error": PAGE_ERROR,
                  "error_log": str(error_log_path())},
        # The lock notice (decision 193, D4): when, where, and - on this
        # machine - which file; nothing waits and nothing needs clearing.
        "lock": {"running": LOCK_RUNNING, "running_other": LOCK_RUNNING_OTHER, "on": LOCK_ON, "greyed": LOCK_GREYED,
                 "left_behind": LOCK_LEFT_BEHIND, "cleared": LOCK_CLEARED,
                 "buttons_back": LOCK_BUTTONS_BACK, "watch_seconds": LOCK_WATCH_SECONDS},
        # What a Sort & Scan reply is said as (decision 193's review, S4).
        "scan": {"scanning": SCAN_SCANNING, "nothing_done": SCAN_NOTHING_DONE,
                 "problem": SCAN_PROBLEM, "complete": SCAN_COMPLETE, "filed": SCAN_FILED,
                 "review": SCAN_REVIEW, "syncing": SCAN_SYNCING, "not_sorted": SCAN_NOT_SORTED,
                 "but": SCAN_BUT},
        # Sort & Scan, watched, and its Stop (decision 193).
        "progress": {"household": PROGRESS_HOUSEHOLD, "sort": PROGRESS_SORT,
                     "scan": PROGRESS_SCAN, "stop": PROGRESS_STOP,
                     "stopping": PROGRESS_STOPPING},
        # The notices area's one word of its own; its buttons are static in
        # index.html (NOTICE_LABELS), because a notice must work before any
        # vocabulary has arrived.
        "notices": {"repeated": NOTICE_REPEATED, "about": NOTICE_ABOUT,
                    "labels": dict(NOTICE_LABELS)},
        "rules": standing_rules(),
        "schedule": {
            "start": DEFAULT_START,
            "every": DEFAULT_REPEAT_MINUTES,
            "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
            "task_name": TASK_NAME,
        },
        # The room a return has under the clients root (decision 131): the
        # two sentences the return's page, the warnings and the set-root
        # reply fill - ROOM_SHORT as information, ROOM_PARKS as a warning
        # (the lead's L-1) - and the heading the root dialog lists them
        # under. The renderer types none.
        "room": {"short": ROOM_SHORT, "parks": ROOM_PARKS, "heading": ROOM_HEADING},
        "keyword_default_note": KEYWORD_DEFAULT_NOTE,
        # Every word and colour the Reminder card shows (decisions 115 and
        # 118), from the module that owns the draft. The card types none of
        # it: the four stages with the palette key each carries and where
        # each spends its emphasis, the palette those keys name, the
        # colour a hold is said in and the three the letter's own surface
        # takes. A hex never reaches the renderer or the stylesheet.
        "reminder": {
            "held_line": reminder.HELD_SUMMARY,
            "inbox_held_line": reminder.INBOX_HELD_SUMMARY,
            "heading": reminder.REMINDER_HEADING,
            "stage_group": reminder.STAGE_GROUP_LABEL,
            "subject_prefix": reminder.SUBJECT_PREFIX,
            "copy": reminder.COPY_LABEL,
            "approve": reminder.APPROVE_LABEL,
            "open_draft": reminder.OPEN_DRAFT_LABEL,
            "last_drafted_line": reminder.LAST_DRAFTED_LINE,
            "never_drafted_line": reminder.NEVER_DRAFTED_LINE,
            "approved_line": reminder.APPROVED_LINE,
            "edited_by_hand": reminder.EDITED_BY_HAND,
            "stage_toggle_hint": reminder.STAGE_TOGGLE_HINT,
            "copied": reminder.COPIED_NOTE,
            "set_aside_line": reminder.SET_ASIDE_LINE,
            "not_yet": reminder.REMINDER_NOT_YET,
            "unreadable": REMINDER_UNREADABLE,
            "line_unreadable": REMINDER_LINE_UNREADABLE,
            "nothing_to_send": NOTHING_OUTSTANDING,
            "stages": _stages(),
            "palette": dict(PALETTE),
            "hold_colour": reminder.HOLD_COLOUR,
            "letter_ink": dict(reminder.LETTER_INK),
        },
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
            # The rename (decision 160), its own act beside the list, as
            # unlearning is; every word here, none in the renderer.
            "rename_title": RENAME_TITLE, "rename_hint": RENAME_HINT,
            "rename_from": RENAME_FROM_LABEL, "rename_to": RENAME_TO_LABEL,
            "rename": RENAME_LABEL, "renamed_note": RENAMED_NOTE, "rename_left_note": RENAME_LEFT_NOTE,
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
            # And where they stop: the record's own bounds (decision 187),
            # so the page never offers a number the store's gate refuses.
            "maximums": {"expected_count": records.MAX_EXPECTED_COUNT,
                         "min_size_kb": records.MAX_SIZE_KB},
            # The folded group the editor keeps the set-aside rows in,
            # headed as the Status Report heads its own (decision 116).
            "set_aside_heading": NOT_APPLICABLE_SECTION,
            # The folded group of rows nobody asked for (decision 142),
            # headed as the Status Report heads its own, and the columns
            # that are a yes/no pick rather than a box - so the editor
            # sends each back as the record holds it.
            "not_asked_heading": NOT_ASKED_SECTION,
            # The app's request table folds the same rows the same way,
            # closed, under the same heading.
            "yes_no_fields": [key for _, key in COLUMNS if key in RULE_FLAG_FIELDS],
        },
    }


def _lock_payload(engagement: Path) -> dict | None:
    """The engagement's lock as the app's notice says it (decision 193):
    when the pass started, on which machine, and - for a live pass on this
    machine - the household and the file it is on, from its progress file.
    Reads the lock file and that one small file; opens no store."""
    status = lock_status(engagement)
    if status is None:
        return None
    this_machine = is_this_host(status.host)
    running = None
    if this_machine and status.pid.isdigit() and pid_alive(status.pid):
        running = progress.read_latest(store.store_path().parent, int(status.pid))
    return {
        "started": status.started,
        "age_minutes": int(status.age_seconds // 60),
        "stale": status.stale,
        "stale_after_minutes": STALE_LOCK_SECONDS // 60,
        "host": status.host,
        "this_machine": this_machine,
        "pass": running,
        "engagement": str(engagement),
        # How a person reads the folder the lock is in (the review's S1): a
        # return by its label, a household by its name - from the path, so
        # no store is opened.
        "label": _lock_label(engagement),
    }


def _lock_label(folder: Path) -> str:
    """A locked folder as a person reads it: the return's label, or the
    household's folder name. From the layout's names alone."""
    folder = Path(folder)
    if layout.year_of(folder) is not None:
        return layout.label_for(layout.household_name_of(folder), layout.year_of(folder), folder.name)
    return folder.name


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
    # The people through their own writer, so the editor's block gets the
    # shape it sends back (decision 128).
    payload["people"] = [person_to_json(one) for one in info.people]
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
            # The record's own date rule (decision 187): a real calendar date
            # in the years the store's gate admits, never one it refuses.
            if records.date_problem(typed):
                raise ManifestError(
                    f"{ENGAGEMENT_LABELS[key]} must be {ISO_DATE_HINT}, got {typed!r}"
                )
            return dt.date.fromisoformat(typed)
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
        people=_people_from_spec(spec["people"]) if "people" in spec else base.people,
        **{key: date(key) for key in DATE_FIELDS},
    )


def _people_from_spec(sent: object) -> tuple[Person, ...]:
    """The return's people as the wizard and the editor's block send them:
    a list of ``{kind, name, spellings}`` (decision 128).

    Every refusal is by name and in the words their one owner gives them:
    a kind nothing knows, a name nobody typed, a spelling of one word
    (:data:`tracker.names.ONE_WORD_SPELLING`). Nothing is inferred here -
    the app *proposes* spellings through ``propose-spellings`` and a person
    ticks them, and what arrives is what they ticked.
    """
    if not isinstance(sent, list):
        raise ManifestError(f"{PEOPLE_LABEL} must be a list of people")
    people: list[Person] = []
    for one in sent:
        if not isinstance(one, dict):
            raise ManifestError(f"{PEOPLE_LABEL} must be a list of people")
        kind = str(one.get("kind", "") or "").strip()
        if kind not in PERSON_KINDS:
            raise ManifestError(f"'{kind}' is not one of {', '.join(PERSON_KINDS)}")
        name = " ".join(str(one.get("name", "") or "").split())
        if not name:
            raise ManifestError(f"Every person needs a name ({PERSON_KIND_LABELS[kind]})")
        spellings: list[str] = []
        for spelling in one.get("spellings") or []:
            spelling = " ".join(str(spelling).split())
            if not spelling:
                continue
            if not is_a_spelling(spelling):
                raise ManifestError(ONE_WORD_SPELLING)
            if spelling not in spellings:
                spellings.append(spelling)
        people.append(Person(kind=kind, name=name, spellings=tuple(spellings)))
    return tuple(people)


def _placed(info: EngagementInfo, household: str, year: int, return_name: str) -> EngagementInfo:
    """The details with the three the layout records (decision 125): where
    this return sits and what it is called.

    Written at creation and at rollover from the folders they name, and
    never editable afterwards - the folders are the names, and the record
    is what wins when somebody renames one.
    """
    return replace(info, household=household, tax_year=year, return_name=return_name)


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


def _evidence_payload(entry: IndexEntry) -> dict[str, list[dict]]:
    """One index row's Evidence cell as JSON: candidate -> what was found.

    Parsed here, by the one parser that owns the cell's shape
    (:func:`tracker.content_check.parse_evidence`), so the renderer never
    splits a string of the tracker's on separators of its own.
    """
    return {identifier: [asdict(evidence) for evidence in found]
            for identifier, found in entry.evidence_record.items()}


def _triage_payload(triaged: review.Triage, seqs: dict[str, int],
                    waiting: tuple[dict | None, str] = (None, "")) -> dict:
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

    Each suggestion carries ``name`` - what the page said about whose
    document this is, as ``{"outcome", "spelling", "label"}`` or null
    (decision 128) - so the card can offer *Teach this spelling* where the
    page named nobody without deciding anything of its own.

    ``waits_for`` is the one click (decision 204) for a row that names the
    person of a return in another household, resolved by
    :func:`_waiting_payload` - ``{target, label, requests, answers}``, or
    null - and ``waits_for_refused`` the sentence that stands in for it
    where the claim no longer resolves.
    """
    offer, refused = waiting
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
        "waits_for": offer,
        "waits_for_refused": refused,
    }


def _waiting_payload(engagement: Path, entry: IndexEntry,
                     fed: Callable[[], dict[Path, str]]) -> tuple[dict | None, str]:
    """What one click on a parked row would do (decision 204), or why it
    offers none.

    Only a row whose Waits For cell holds a claim is asked. The claim is
    resolved against the feed list (:func:`_fed_returns`, the one list a
    hand-over may name) by the filer's own comparison, and each request it
    names is held to the taking list by the filer's own check - so the
    card is offered exactly where the click would go through, and refused
    in the click's own words where it would not: :data:`NOT_FED` with the
    claim's return name, the request's refusal, or the taking return's
    want of room (:func:`tracker.filer.hand_over_copies`, the click's own
    naming). ``fed`` is asked only when a row waits, so a queue with none
    costs nothing.

    Only a row the click would take is offered - still parked, with
    ``NAMED_ACROSS_HOUSEHOLDS`` as its reason, the condition the filer's
    refusal holds it to (the review's S-3) - so a claim on any other row
    draws no button.
    """
    claim = entry.waiting_for
    if (claim is None or entry.decision != NEEDS_REVIEW
            or not reasons.NAMED_ACROSS_HOUSEHOLDS.matches(entry.reason)):
        return None, ""
    returns = fed()
    target = waiting_target(claim, returns)
    if target is None:
        return None, NOT_FED.format(label=claim.return_name)
    try:
        items = {item.identifier: item for item in load_manifest(target)}
        wanted = requests_taking(items, claim.identifiers)
        hand_over_copies(target, wanted, items, locate(engagement, entry.pbc_location), entry.digest)
    except (FilingError, ManifestError) as exc:
        return None, str(exc)
    return {
        "target": str(target),
        "label": returns[target],
        "requests": [{"identifier": item.identifier, "document": item.document} for item in wanted],
        "answers": [identifier for identifier, _ in records.parse_answers(claim.answers)
                    if identifier in items],
    }, ""


def _moved_payload(engagement: Path, entries: list[IndexEntry], items,
                   seqs: dict[str, int]) -> list[dict]:
    """Every working copy the record has lost track of, and where it is now.

    Decision 110's card is its own list rather than a fourth column on the
    index: a mislaid copy is the morning's first question and a person
    answers it with three buttons, not by reading a row. Each entry carries
    the row's sequence number (decision 112), the home the record put the
    copy at, where its bytes are now (``None`` for a row whose bytes are
    nowhere under the firm's folder) and - only when the copy sits directly
    in the firm's folder under a name that belongs to a request - which
    request that is, because "keep it where it is" means nothing anywhere
    else. The name is matched by :func:`tracker.scaffold.assign_files`, the
    same answer the filer and the scan read (decision 168), so a wanderer
    renamed ``A02 - ...`` beside the other copies is offered to A02, and
    one in the review folder, in a folder a person made or under a name no
    request's identifier begins counts as nobody's.

    Decision 157: ``gone`` says the row's copy and its original are both
    gone (``filer.both_gone``), and ``identifier`` is the row's own request -
    the card offers such a row **Mark missing** (the API's ``mark-missing``
    with the row's own identifier) instead of three answers that would each
    refuse: there is nothing to put back. A row a person has already marked
    missing (``filer.marked_missing``) is answered, and is not listed.
    """
    owned = assign_files(engagement / PREPARED_DIR_NAME, [i.identifier for i in items])
    rows = []
    for entry in entries:
        if entry.decision != FILE_MOVED or marked_missing(entry):
            continue
        now = moved_to(entry)
        in_request = ""
        if now:
            where = locate(engagement, now)
            in_request = next((identifier for identifier, paths in owned.items() if where in paths), "")
        rows.append({
            "original_name": entry.original_name,
            "pbc_location": entry.pbc_location,
            "seq": seqs.get(ledger_key(entry)),
            "home": entry.prepared_location,
            "now": now,
            "in_request": in_request,
            "gone": both_gone(entry),
            "identifier": entry.identifier,
        })
    return rows


def _root_of(engagement: Path) -> Path:
    """The clients root this return sits under, positionally: the layout
    says a return is four levels below it and nothing else is a return."""
    return engagement.parents[3]


def _originals_of(engagement: Path) -> Path:
    """The folder the client sees for this return's year.

    The record's year where it carries one, the year folder's name where
    it does not - the record wins over a folder somebody renamed, and a
    return whose year nobody recorded is answered with its own folder's
    parent so the app still has a path to offer.
    """
    try:
        recorded = load_engagement_info(engagement).tax_year
    except ManifestError:
        recorded = None
    year = recorded if recorded is not None else year_of(engagement)
    if year is None:
        return client_household_dir(_root_of(engagement), household_of(engagement).name)
    return originals_dir_for(_root_of(engagement), household_of(engagement).name, year)


def _sharing_checklist(root: Path, household: str) -> dict:
    """The two grants and the paste, as a person does them, with this
    household's own folders named (decision 126).

    Filled here and nowhere else: the page shows the lines it is handed,
    so the folder a person is told to share is the folder the tracker
    would read, character for character.
    """
    client_folder = client_household_dir(root, household)
    return {
        "heading": SHARING_HEADING,
        "lines": [line.format(client_folder=client_folder,
                              inbox=inbox_dir_for(root, household))
                  for line in SHARING_CHECKLIST],
        "note": SHARING_NOTE,
    }


def _return_reminder(path: Path, today: dt.date, label: str = "") -> dict:
    """One return's reminder state for the household card (decision 128):
    when it was last drafted, whether this week's draft is approved, how
    many requests are holding it, and how many files wait unsorted in the
    household's inbox (decision 133, counted by the reminder's own
    :func:`tracker.reminder.unsorted_in_inbox`).

    Four numbers and two dates - never a word of the letter. The card
    puts them into the sentences the Reminder card already uses
    (``vocab.reminder``'s ``last_drafted_line``, ``approved_line``,
    ``never_drafted_line`` and ``held_line``), so the returns of a
    household stand side by side in the words their own panel uses and the
    page types nothing new. A return whose record this read cannot open
    still draws the card, but says so (decision 193): ``unreadable`` on
    the line, and a warning on the reply, by class; the full text goes to
    the error log.
    """
    blank = {"last": None, "approved": None, "held": 0, "unsorted": 0}
    try:
        items = load_manifest(path)
        entries = read_index(path)
        _, _, held = reminder.triage(items, entries)
        last = reminder.last_draft_event(path, carrying=ledger.FILE_KEY)
        approved = reminder.last_approved_event(path)
        in_force = reminder.is_approved_this_week(
            path, path / reminder.DRAFT_FILENAME,
            since=last_draft_day(today, DRAFT_WEEKDAY))
        unsorted = reminder.unsorted_in_inbox(path)
    except Exception as exc:                 # the card still draws, and says so
        kind = content_check.said_as_class(exc)
        log.warning("A reminder line could not be read (%s)", kind, exc_info=True)
        _warn(REMINDER_LINE_UNREADABLE.format(label=label or path.name, kind=kind))
        return {**blank, "unreadable": True, "kind": kind}
    return {
        "last": ({"date": ledger.day_of(str(last.get(ledger.AT_KEY, ""))).isoformat(),
                  "stage": last.get(reminder.STAGE_KEY) or 0} if last else None),
        "approved": ({"date": ledger.day_of(str(approved.get(ledger.AT_KEY, ""))).isoformat(),
                      "stage": approved.get(reminder.STAGE_KEY) or 0}
                     if approved and in_force else None),
        "held": len(held),
        "unsorted": unsorted,
    }


def _the_practice() -> Registry | None:
    """One walk of the clients root, or ``None`` where it cannot be walked
    (decision 129).

    **The one walk a click makes, and only *Run now* makes it** (decision
    192): :func:`_cmd_scan` walks once and hands this registry to the pass
    and to the practice page it redraws. Showing a return walks nothing -
    the card resolves its feeds over the households they name
    (:func:`_feed_payload`). A root that is unset, gone or unreadable
    answers with nothing rather than failing the pass - and one that could
    not be walked says so (decision 193, :data:`PRACTICE_NOT_WALKED`).
    """
    root = _saved_root()
    try:
        return discover_engagements(root) if root and root.is_dir() else None
    except EmptyRoot:
        return None
    except RegistryError as exc:
        log.warning("The clients root could not be walked (%s)", content_check.said_as_class(exc),
                    exc_info=True)
        _warn(PRACTICE_NOT_WALKED)
        return None


def _feed_payload(household_dir: Path, years: list[int]) -> tuple[list[dict], list[dict]]:
    """What this drop folder also feeds, and whose drop folders feed it
    (decision 129).

    Each feed is the household and the return line as a person recorded
    them - so the editor sends back exactly what it was shown - with the
    return it resolves to this year, or the sentence saying it resolves to
    nothing. ``fed_by`` is the other direction, for the destination's own
    card: who else may drop for a return that lives here.

    **Nothing is walked** (decision 192). The feeds are resolved by
    :func:`resolve_feeds`, unchanged, over
    :func:`tracker.registry.households_named` - the households the feed
    list names and no other, read fresh, because the hand-over and the
    waiting row's click check their target through this same resolution
    before they write, and a write is never answered from a cache. A
    household with no feed, which is nearly every household, reads no
    other folder at all. ``fed_by`` needs every household's feed list,
    which only a walk or the store holds, so it is the store's
    (:func:`_fed_by_payload`): a display, which may lag a feed added on
    another computer. A private tree that cannot be listed answers the
    feeds with nothing rather than failing the card.
    """
    try:
        info = load_household_info(household_dir)
    except ManifestError:
        info = HouseholdInfo()
    fed = _fed_by_payload(household_dir)
    year = years[0] if len(years) == 1 else None
    found: list[Engagement] = []
    said: list[str] = []
    if info.feeds and year is not None:
        try:
            practice = households_named(household_dir.parent, [one.household for one in info.feeds])
        except RegistryError as exc:
            log.warning("The feeds could not be resolved (%s)", content_check.said_as_class(exc),
                        exc_info=True)
            _warn(PRACTICE_NOT_WALKED)
            return ([{"household": one.household, "return_name": one.return_name,
                      "label": "", "path": "", "warning": PRACTICE_NOT_WALKED}
                     for one in info.feeds], fed)
        found, said = resolve_feeds(household_dir, info.feeds, year, practice)
    by_line = {(one.info.household or one.household_path.name, one.info.return_name or one.path.name):
               one for one in found}
    unresolved = iter(said)
    feeds = []
    for one in info.feeds:
        match = next((found_one for key, found_one in by_line.items()
                      if layout.name_key(key[0]) == layout.name_key(one.household)
                      and layout.name_key(key[1]) == layout.name_key(one.return_name)), None)
        feeds.append({
            "household": one.household, "return_name": one.return_name,
            "label": match.label if match else "",
            "path": str(match.path) if match else "",
            "warning": "" if match else next(unresolved, ""),
        })
    return feeds, fed


#: What *Fed by* says in place of a household whose stored record this
#: computer could not read (decision 192): a name in the line's own list,
#: so the card says it without a word of its own, and the class alone -
#: an exception's text can name a client's folder (security principle 7).
FED_BY_UNREADABLE = "a household whose record this computer could not read ({kind})"


def _fed_by_payload(household_dir: Path) -> list[dict]:
    """The households whose drop folders feed a return of this one, from
    the store's household rows as they stand (decision 192).

    The question needs every household's feed list, and a card may not
    walk the practice to learn it; every walk tops the rows up, so this
    answers as of the last time this computer listed the clients or ran a
    pass - a feed added on another computer is named here after the next
    of those (the runbook says so). Removed elsewhere, the feeder stays
    named until then: over-telling, the safe direction for a disclosure
    line. No write reads it.

    Each match is held to the walk's own tests before it is shown: a
    household position under this household's own private tree, a name
    the layout accepts, and a journal that is still there (one ``stat``,
    never a read) - so a folder renamed aside or a record removed is not
    named from a row the store still holds. With no saved root there is
    nothing to place the rows under and the answer is nobody.

    **One row the store cannot read costs its own household, never every
    card** (decision 192, the review's S1). The rows are read in one
    query; where that fails, each household under this private tree is
    read from the store on its own, in its own guard, and a household that
    still cannot be read is left out and said in its place
    (:data:`FED_BY_UNREADABLE`, by class; the class is logged). A card
    must not fail on its disclosure line, and a line that leaves a
    household out in silence would tell nobody it did.
    """
    root = _saved_root()
    if root is None:
        return []
    faults = (store.StoreError, ValueError, TypeError)
    unreadable: list[str] = []
    built: list[Household] = []
    try:
        conn = store.connect()
        built = [Household(path=root.joinpath(*key.split("/")), info=info)
                 for key, info in store.households(conn)]
    except faults as exc:
        log.warning("fed_by: the store's households could not be read at once (%s)",
                    type(exc).__name__)
        try:
            conn = store.connect()
            with os.scandir(household_dir.parent) as entries:
                folders = sorted(Path(entry.path) for entry in entries if entry.is_dir())
        except (*faults, OSError) as again:
            log.warning("fed_by: nothing could be read one by one (%s)", type(again).__name__)
            unreadable.append(type(again).__name__)
            folders = []
        for folder in folders:
            try:
                info = store.household_info(conn, folder)
            except faults as one:
                log.warning("fed_by: one household's stored record could not be read (%s)",
                            type(one).__name__)
                unreadable.append(type(one).__name__)
                continue
            if info is not None:
                built.append(Household(path=folder, info=info))
    shown = [one for one in fed_by(SimpleNamespace(households=built), household_dir)
             if layout.place_of(root, one.path).kind == layout.HOUSEHOLD
             and one.path.parent == household_dir.parent
             and layout.segment_problem(one.path.name) is None
             and ledger.path_for(one.path).is_file()]
    fed = [{"name": one.name, "path": str(one.path), "members": list(one.info.members)}
           for one in sorted(shown, key=lambda one: one.path.name.lower())]
    if unreadable:
        fed.append({"name": FED_BY_UNREADABLE.format(kind=unreadable[0]), "path": "", "members": []})
    return fed


#: The app's action on a paused household (decision 188, R6) and its help.
ACCEPT_FOLDER_NAME_LABEL = "Accept the folder's name"
ACCEPT_FOLDER_NAME_HELP = ("records that this household (or this return) is now called by its folder's "
                           "name; nothing is moved or renamed")
#: Why the app does not accept a folder's name.
YEAR_NOT_ACCEPTED = ("This return's folder sits under a year its record does not hold. Move it back "
                     "under the year its record says. Nothing was changed.")
ORIGINALS_UNDER_OLD_NAME = ("The originals of this household rest under its client folder of the old "
                            "name. Give the folder back the name its record holds; a household is "
                            "not renamed this season. Nothing was changed.")
#: What an accept drawn from a household page that has since changed is told.
ACCEPT_STALE = ("The household's record changed since this page was drawn; nothing was changed. "
                "Look at it again.")
#: What an accept on a household that is not paused is told.
NOT_PAUSED = "This household's folders and its record agree; there is nothing to accept."


def _household_seq(household_dir: Path) -> int:
    """The household record's version as a page shows it: its line count."""
    return len(ledger.read_events(household_dir))


def _pause_payload(household_dir: Path, info: HouseholdInfo, returns: list) -> dict:
    """Why the household is paused, and what accepting would record: the
    household's own name when its record claims another, else the first
    return whose claims disagree (decision 188)."""
    readable = [one for one in returns if not one.problem]
    sentence = pause_of(household_dir, info, [(one.path, one.info) for one in readable])
    # A year is never accepted (ruling 9.3): the card shows the sentence and
    # no button, rather than a button that can only be refused (review S3).
    if not sentence or sentence == HOUSEHOLD_PAUSED_YEAR:
        return {"sentence": sentence, "scope": "", "engagement": "", "seq": None}
    household_claim = claim_disagrees(info.name, household_dir.name) or any(
        claim_disagrees(one.info.household, household_dir.name) for one in readable)
    which = next((one.path for one in readable if return_disagrees(one.path, one.info)), None)
    scope = "household" if household_claim else "return"
    return {"sentence": sentence, "scope": scope,
            "engagement": str(which or (readable[0].path if readable else "")),
            "seq": _household_seq(household_dir)}


def _household_payload(engagement: Path) -> dict:
    """The household this return belongs to, as the app's card shows it.

    Its own record (the members a person typed, the contact, the link),
    the years still open across it, every return under it with its label,
    and how many documents are waiting for a person across the open year's
    returns - one number for the household, because the queue a person
    works is the household's and not one return's.

    And the feed list both ways (decision 129): the return lines in other
    households this drop folder also feeds, each resolved to this year's
    return or said to resolve to nothing, and the households whose drop
    folders feed a return here.

    Each open-year return also carries its reminder's state
    (:func:`_return_reminder`, decision 128), so the letters stand side by
    side. There is still **one letter per return** and the Reminder card
    is still the surface a person approves from: this is a line, never a
    send, and never a bundle.
    """
    today = dt.date.today()
    household_dir = household_of(engagement)
    try:
        info = load_household_info(household_dir)
        marked = shared_on(household_dir)
    except ManifestError:
        info = HouseholdInfo()
        marked = None
    # The household's own returns, retired among themselves: a rollover
    # names its prior by path and a prior is always in the same household,
    # so the whole practice does not have to be walked to know which of
    # these years is finished with.
    returns = mark_superseded([engagement_from(folder)
                               for folder in household_returns(household_dir)])
    # A Rolled From naming nothing, said on the return it is about
    # (decision 193): the registry's own sentence, not only its CLI's.
    for one in returns:
        if one.path == engagement and one.warning:
            _warn(one.warning)
    years = open_years(returns)
    queue = sum(
        sum(1 for entry in read_index(one.path) if entry.decision == NEEDS_REVIEW)
        for one in returns if one.active and one.tax_year in years
    )
    feeds, fed = _feed_payload(household_dir, years)
    pause = _pause_payload(household_dir, info, returns)
    return {
        # Why the pass touches nothing of this household, and what a person
        # may accept (decision 188): the card draws the sentence and the
        # one button, and sends back the seq it was drawn from.
        "pause": pause,
        "name": household_dir.name,
        "path": str(household_dir),
        "members": list(info.members),
        "contact": info.contact,
        "link": info.link,
        "feeds": feeds,
        "fed_by": fed,
        "open_years": years,
        "returns": [
            {"label": one.label, "path": str(one.path),
             "year": one.tax_year if one.tax_year is not None else year_of(one.path),
             "return_name": one.info.return_name or one.path.name,
             "active": one.active, "superseded_by": one.superseded_by,
             "reminder": (_return_reminder(one.path, today, one.label)
                          if one.active and one.tax_year in years else None)}
            for one in returns
        ],
        "queue": queue,
        # The firm's own dated word that this household was shared, and
        # the checklist until it is given (decision 126). Nothing in the
        # pass reads either: the tracker cannot see Drive's sharing and
        # must not make filing wait on what it cannot check.
        "shared_on": marked.isoformat() if marked else None,
        "checklist": None if marked else _sharing_checklist(
            _root_of(engagement), household_dir.name),
    }


def _rule_for_the_editor(row) -> dict:
    """One stored rule as ``state`` hands it out: read as every reader reads
    it (``rule_as_read``), with a row that accepts any file type saying so
    with the star, ``["*"]``.

    The record holds "any" as an empty list, but a person's blank means the
    default types (``parse_extensions``), and ``edit`` reads what it is sent
    as a person's row. So ``[]`` sent back unchanged became pdf, xlsx, csv
    and the save recorded a change nobody made (decision 145). The star is
    what the editor already sends for such a row, and it is how "any" has
    always had to be said; a blank typed in the editor still means the
    default types.
    """
    rule = rule_as_read(row)
    if not rule["allowed_extensions"]:
        rule["allowed_extensions"] = [ANY_EXTENSION]
    return rule


def _state(engagement: Path) -> dict:
    root = _saved_root()
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
    # The room this return has under the clients root (decision 131),
    # measured from the list already loaded - no second read - so a person
    # opening a return sees the number without waiting for a pass.
    room = room_for(engagement, items)
    # The household payload, built once (decision 192): the card and the
    # feed list a waiting row is offered from are drawn from the same one.
    household = _household_payload(engagement)
    # The feed list, read once and only if a parked row waits for another
    # household (decision 204).
    fed_once = cache(lambda: _fed_returns(engagement, household))
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
            "also_received": summary.also_received, "not_asked": summary.not_asked,
        },
        # Each row with the year its own Period gives, so the renderer
        # labels a set-aside row without reading the Period's text, and
        # the word its status is shown as - "Not asked" for a row nobody
        # asked for with nothing in (decision 142) - so it types none.
        "items": [
            asdict(i) | {"received_date": i.received_date.isoformat() if i.received_date else None,
                         "year": i.year, "status_label": status_label(i),
                         # Decision 142, the designer's ruling on the build:
                         # a row nobody asked for folds away in the request
                         # table only while no document at all is in it; the
                         # editor regroups a row live from ``has_document``.
                         "has_document": has_a_document(i), "not_asked_idle": is_idle_unasked(i),
                         # The short name the row's copies go by
                         # (decision 144): its own, or the one its document
                         # derives - the editor's placeholder for a blank.
                         "short_name": i.short_name}
            for i in items
        ],
        # The person's rows as stored - read the way every reader reads
        # them, so a retired override spelling in an old journal reaches
        # the editor as its successor - the keywords filings taught each
        # row, and the rows the rules cannot act on: what the editor
        # opens on, and what it shows after a save - each in the form
        # ``edit`` reads back as the same rule (``_rule_for_the_editor``).
        "rules": [_rule_for_the_editor(row) for row in rules],
        # The version of the list and the details the editor opens on
        # (decision 160): a save hands it back, and one made from any other
        # version is refused rather than taking another window's save back.
        "list_head": list_head(engagement),
        "learned": {row["identifier"]: list(taught[identifier_key(row["identifier"])])
                    for row in rules if taught.get(identifier_key(row["identifier"]))},
        # A request that cannot receive is a warning; a return merely short
        # of room is not (the lead's L-1): its names are cut to fit and
        # everything files, so the figure is information on its page.
        "warnings": check_rules(items) + (
            [ROOM_PARKS.format(count=room.parks)] if room.parks else []),
        "room": {"need": room.need, "least": room.least, "floor": room.floor,
                 "short": room.short, "parks": room.parks, "limit": room.limit},
        "room_note": ROOM_SHORT.format(short=room.short) if room.short else "",
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
                               "answered": [identifier for identifier, _ in e.answered],
                               "evidence": _evidence_payload(e),
                               "seq": seqs.get(ledger_key(e))}
                  for e in entries],
        # The review queue, triaged: one entry per parked file, its
        # shortlist best-first with the sentence behind each suggestion.
        # There is no `review` command - the card draws from the one state
        # the app already reads - and the manifest and the index are handed
        # to triage() so each is read once for the whole screen.
        "review": [_triage_payload(t, seqs, _waiting_payload(engagement, t.entry, fed_once))
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
        # The Reminder card itself, at the record's stage (decision 194):
        # exactly what the ``reminder`` command answers, so a switch or a
        # write is one reply and the card cannot disagree with the table.
        # The command stays for the stage toggle alone.
        "reminder_card": _reminder_said(engagement),
        # The household this return belongs to (decision 125): its own
        # record, the years still open across it, its returns and the one
        # queue a person works. The card is drawn from this and types
        # nothing of its own.
        "household": household,
        "paths": {
            "engagement": str(engagement),
            # The household's one inbox and the folder the client sees for
            # the year, both in the tree a client is shared. The shell
            # opens only the paths this map holds, so the two buttons that
            # open them are named here.
            "inbox": str(inbox_of(engagement)),
            "originals": str(_originals_of(engagement)),
            "client_folder": str(client_household_dir(_root_of(engagement),
                                                      household_of(engagement).name)),
            "household": str(household_of(engagement)),
            "prepared": str(engagement / PREPARED_DIR_NAME),
            # The one a person is meant to open. Named here as well as
            # above because the shell opens only paths this map holds.
            "view": str(view_path),
            # The week's draft, so the Reminder card's quiet button can
            # open it (decision 118). Named here for the same reason the
            # two above are: the shell opens only the paths this map
            # holds, and the card names no path of its own.
            "draft": str(engagement / reminder.DRAFT_FILENAME),
            # The practice's page, not this engagement's: it lives in the
            # clients root. Reported here because the shell opens only the
            # paths the API has named, and a person looking at one
            # engagement is one click from the whole practice.
            "status": str(root / STATUS_PAGE_FILENAME) if root else "",
        },
    }


def _room_sentences(room) -> list[str]:
    """What the reply to setting the root says about one return's room
    (decision 131), filled: the figure it is short by, as information, and
    the requests that cannot receive, as the warning they are."""
    said = [ROOM_SHORT.format(short=room.short)] if room.short else []
    return said + ([ROOM_PARKS.format(count=room.parks)] if room.parks else [])


def _reminder_payload(engagement: Path, items, entries) -> dict:
    """What holds this engagement's reminder, and when it was last drafted.

    The index rows go in because a parked file the client could fix holds
    the request it points at (decision 117), and the card must show the
    same hold the draft day will: the rows are the ones ``state`` has
    already read, so nothing is read twice to answer this.
    """
    _, _, held = reminder.triage(items, entries)
    drafted = last_drafted(engagement)
    return {
        "held": _held_rows(held),
        "unsorted": reminder.unsorted_in_inbox(engagement),
        "last_drafted": drafted.isoformat() if drafted else None,
    }


def _held_rows(held) -> list[dict]:
    """The requests that hold a reminder, as the card names them: the
    identifier on its own, the document beside it, the whole label for
    anything that wants one line, and the reason the hold was put on it.
    The identifier travels apart from the label because the card sets it
    in its own type, and a page cutting an identifier off a label would be
    a page parsing a sentence Python wrote."""
    return [{"identifier": flag.item.identifier, "document": flag.item.document,
             "label": flag.item.label, "reason": flag.reason} for flag in held]


def _refresh_readmes(*engagements: Path) -> None:
    """Rewrite the client README of each household these returns are in,
    once each (decision 130): after an action that creates or edits a
    return or changes a document's row, what the client reads is current
    at once rather than at the next pass. A hand-over across households
    names both. Never raises - :func:`filer.refresh_household_readme`
    says a failure by class in this reply's warnings (decision 193) and
    logs it in full - and is reached only after the action succeeded, so
    a refused action refreshes nothing."""
    for household_dir in dict.fromkeys(household_of(Path(one)) for one in engagements):
        refresh_household_readme(household_dir, said=_WARNINGS)


def _cmd_state(argv: list[str]) -> dict:
    return _state(_engagement_dir(argv))


def _record_pass(runs: list[EngagementRun] | EngagementRun,
                 warnings: list[str] | None = None, *, registry: Registry | None) -> list[str]:
    """Leave the record the scheduled run leaves: a line in the run log and
    the practice's status page, both in the clients root.

    The app's button makes the same pass as the job, so it must leave the
    same trace - a pass with no record is a pass nobody can check
    afterwards, and a page that is a night old is one nobody believes. The
    page is redrawn from every engagement under the root, because it is
    about the practice and not about the engagement that was just run -
    drawn from the walk the pass made, ``registry``: one walk per *Run
    now* (decision 192). With no walk (``None``: the root could not be
    walked, and the pass was refused for it) the log line is still
    written and the page is not, which the reply says.

    Neither takes a lock or touches an engagement, and neither failing is
    allowed to fail the pass: the files have already been moved and the
    statuses recorded, so the person is told what happened either way -
    **in the reply** (decision 189): the sentence for each that failed is
    returned, because stderr is what the app discards when the reply
    parses. ``warnings`` are the pass's own sentences, logged and put on
    the page as the scheduled pass puts its own.
    """
    every = [runs] if isinstance(runs, EngagementRun) else list(runs)
    said = list(warnings or [])
    root = _saved_root()
    if root is None or not root.is_dir():
        return []
    failed: list[str] = []
    # Broadly, both of them: the pass has already moved the client's files
    # and recorded what it found, so nothing about recording it afterwards
    # may turn a finished pass into an error message in the app.
    try:
        append_log(root / LOG_FILENAME, RunReport(today=dt.date.today(), reminders=REMINDERS_NEVER,
                                                  runs=every, warnings=said))
    except Exception as exc:
        log.warning("Could not write %s (%s)", LOG_FILENAME, exc)
        failed.append(LOG_NOT_WRITTEN.format(kind=exc.__class__.__name__))
    if registry is None:
        log.warning("Could not write %s (%s)", STATUS_PAGE_FILENAME, RegistryError.__name__)
        failed.append(PAGE_NOT_WRITTEN.format(kind=RegistryError.__name__))
        return failed
    try:
        write_status_page(root, status_report(registry, passed=every, warnings=said + failed))
    except Exception as exc:
        log.warning("Could not write %s (%s)", STATUS_PAGE_FILENAME, exc)
        failed.append(PAGE_NOT_WRITTEN.format(kind=exc.__class__.__name__))
    return failed


def _cmd_scan(argv: list[str]) -> dict:
    """One pass over this return's **household** - the same pass the
    scheduled job makes.

    Scaffold, sort the household's one inbox, scan, in that order, with
    the same locks, the same error isolation and the same warnings; only
    the weekly draft is left to the scheduled run (or `python -m
    tracker.reminder`). There is one definition of a pass, in
    tracker.runner, and this is it - including the record it leaves behind
    (:func:`_record_pass`).

    **The reply carries what the pass said** (decision 189): ``run`` is the
    asked return, ``household`` is every other return of the household the
    pass touched (its error, skip and warnings), and ``pass_warnings`` are
    the pass's own - the reader's path, a reader that could not start, the
    card, and a run log or page that could not be written. Nothing the
    pass said is left on stderr alone.

    **The whole inbox, always** (decision 125). One folder feeds every
    return of the household, so Run now on one return sorts all of it;
    sorting a share of a pile nobody sorted is not a thing the tracker can
    honestly do. The reply is about the return that was asked for.

    **And the whole feed list with it** (decision 129). The practice is
    walked once and handed down, and the page is drawn from the same walk
    (decision 192), so the returns this drop folder feeds in other
    households are judged, locked and filed into here exactly as the
    scheduled pass does it: without the walk the same trial balance would
    file under the co-owned LLC on the schedule and park at home on Run
    now, which is two definitions of a pass and one of them wrong. Since
    decision 132 the pass cannot be called without the walk at all: a root
    that cannot be walked is refused by the runner in one sentence
    (``tracker.runner.NO_PRACTICE``), which is this reply's ``error``, and
    nothing is sorted.

    **Watched, and stoppable** (decision 193). Before its reply the pass
    prints one progress line per household and per file or request
    (:mod:`tracker.progress`), the first carrying the run limit the
    shell's kill follows, and keeps the latest in its progress file beside
    the tracker's database. ``pass`` is its id, which **Stop** names
    (``cancel-pass``); a stopped household says so in ``run.cancelled``
    and its warnings. A redraw that fails after the pass keeps the counts
    (D5): ``state`` is null, and the warning says so.
    """
    engagement = _engagement_dir(argv)
    household_dir = household_of(engagement)
    watch = progress.Watch(store.store_path().parent, emit=_emit,
                           limit_seconds=RUN_TIME_LIMIT_SECONDS)
    outcome = "failed"
    try:
        watch.say("started", started=dt.datetime.now().isoformat(timespec="seconds"),
                  households=1)
        returns = mark_superseded([engagement_from(folder)
                                   for folder in household_returns(household_dir)]) \
            or [engagement_from(engagement)]
        practice = _the_practice()
        runs = run_household(household_dir, returns, reminders=REMINDERS_NEVER, registry=practice,
                             watch=watch)
        outcome = ("stopped" if any(one.cancelled for one in runs)
                   else "out_of_time" if any(one.out_of_time for one in runs) else "finished")
    finally:
        watch.close(outcome)
    run = next((one for one in runs if one.engagement.path == engagement),
               EngagementRun(engagement=engagement_from(engagement)))
    # Said once, as the pass's own (decisions 150, 169 and 189).
    pass_warnings = [w for w in (ocr.reader_path_warning(), reader_start_warning()) if w]
    if ocr_session := ocr.current_session():
        pass_warnings.extend(ocr_session.warnings())
    pass_warnings.extend(_record_pass(runs, pass_warnings, registry=practice))
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
            "cancelled": run.cancelled,
            "label": run.engagement.label,
        },
        "household": [
            {"label": one.engagement.label, "ok": one.ok, "error": one.error,
             "skipped": one.skipped, "warnings": one.warnings}
            for one in runs if one is not run
        ],
        "pass_warnings": pass_warnings,
        "pass": watch.pass_id,
    }
    held = next((one.locked_at for one in runs if one.locked_out and one.locked_at), None)
    if held is not None:
        payload["lock"] = _lock_payload(held)
    try:
        payload["state"] = _state(engagement)
    except Exception as exc:
        # Filed, then could not redraw (D5), whatever the redraw raised - a
        # ManifestError included (the review's M2): the counts are the
        # pass's and stand, ``run.error`` already says what the pass met,
        # and the page is drawn again from the record by the app.
        kind = content_check.said_as_class(exc)
        log.warning("The page could not be redrawn after a pass (%s)", kind, exc_info=True)
        payload["state"] = None
        _warn(STATE_NOT_REDRAWN.format(kind=kind))
    # The list from the pass's own walk, which adds none (decision 194, R7):
    # how a folder made by hand reaches the app's picker. No walk, no list.
    return _with_list(payload, practice) if practice is not None else payload


def _emit(line: str) -> None:
    """A progress line on stdout, flushed at once, so the shell hears it
    while the pass runs rather than at its end."""
    sys.stdout.write(line)
    sys.stdout.flush()


def _cmd_watch(argv: list[str]) -> dict:
    """Whether a pass still holds this return, and where it is (decision
    193): the lock file and the pass's progress file, and nothing else - no
    store, no journal. The app asks it every ``LOCK_WATCH_SECONDS`` while a
    live lock shows, and brings the buttons back on the first ``null``.

    The folder is the one the lock was reported in - a return, or a
    household folder under the root (the review's S1) - each checked by
    the one door."""
    try:
        folder = _engagement_dir(argv)
    except (ManifestError, door.DoorError, layout.LayoutError):
        at = argv.index(ENGAGEMENT_FLAG) + 1 if ENGAGEMENT_FLAG in argv else len(argv)
        if at >= len(argv) or not argv[at].strip():
            raise
        folder = _household_dir(argv[at].strip())
    return {"lock": _lock_payload(folder)}


def _cmd_cancel_pass(argv: list[str]) -> dict:
    """Ask a running pass this app started to stop at its next file
    (decision 193). JSON on stdin: ``{"pass": <id>}``, the id its progress
    lines carry. Refused (:data:`NOTHING_TO_STOP`) unless that pass is
    live and may be stopped from here; the scheduled pass never may."""
    spec = _read_spec()
    pass_id = spec.get("pass")
    if not isinstance(pass_id, int) or isinstance(pass_id, bool) or pass_id <= 0 \
            or not progress.ask_to_stop(store.store_path().parent, pass_id):
        raise ManifestError(NOTHING_TO_STOP)
    return {"stopping": True}


def _cmd_templates(argv: list[str]) -> dict:
    """The catalog, plus the tax year a new engagement is for by default."""
    return {"forms": FORM_TYPES, "templates": FORM_TEMPLATES, "default_year": default_tax_year()}


def _cmd_propose_spellings(argv: list[str]) -> dict:
    """What a document might print one name as, for a person to tick.

    JSON spec on stdin: ``{"name": "John A. Park", "kind": "taxpayer"}``
    -> ``{"spellings": [...]}``. A **read**:
    no folder is touched, no lock taken and nothing recorded, because a
    proposal is not a decision - what a return matches on is what somebody
    ticked and the wizard or the editor then saves with the rest of the
    details (decision 128).

    The twenty-third command, and the only one the wizard calls while
    somebody is still typing.
    """
    spec = _read_spec()
    kind = str(spec.get("kind", "") or "").strip()
    if kind not in PERSON_KINDS:
        raise ManifestError(f"'{kind}' is not one of {', '.join(PERSON_KINDS)}")
    return {"spellings": list(propose_spellings(str(spec.get("name", "") or ""), kind))}


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

    **The rows the same way** (decision 160, the audit's E2). A key a row
    leaves out keeps what the record holds for the row of that identifier
    (:func:`_as_recorded`), so an older window or build that knows fewer
    columns does not reset the ones it does not know - a short name
    blanked, a request set not asked put back in the client's letter. A key
    that is no column this version knows is refused (:data:`UNKNOWN_COLUMN`).
    ``head`` is the version of the list the editor was opened on
    (``state``'s ``list_head``); a save made from any other version, or
    naming none, is refused under the lock before anything is compared
    (``manifest.save_rules``). A request that holds filed documents may not
    leave the list - removed, or respelt other than by case - and the save
    says so (:data:`HOLDS_DOCUMENTS`); the ``rename`` command carries them.

    A refusal is the usual error sentence, and nothing is recorded. The
    engagement lock is taken inside the save, so an edit of a folder a
    pass is holding waits on the lock the way a filing does.
    """
    engagement = _engagement_dir(argv)
    spec = _read_spec()
    rows = spec.get("items")
    if not isinstance(rows, list):
        raise ManifestError("The editor sent no rows")
    head = spec.get("head")
    if not isinstance(head, str) or not head.strip():
        raise ManifestError(NO_LIST_HEAD)
    recorded = recorded_rules(engagement)
    exact = {str(rule["identifier"]): rule for rule in recorded}
    folded = {identifier_key(str(rule["identifier"])): rule for rule in recorded}
    items = []
    for n, row in enumerate(rows, start=1):
        row = row if isinstance(row, dict) else {}
        for key in row:
            if key not in _ROW_KEYS:
                raise ManifestError(UNKNOWN_COLUMN.format(n=n, key=key))
        identifier = str(row.get("identifier") or "").strip()
        held = exact.get(identifier) or folded.get(identifier_key(identifier))
        items.append(item_from_fields(_as_recorded(row, held), where=f"Row {n}"))
    _refuse_a_list_nobody_is_asked_for(items)
    details = spec.get("engagement") or {}
    for key in details:
        if key not in ENGAGEMENT_EDITABLE:
            raise ManifestError(f"'{key}' is not edited here")
    info = _info_from_spec(details, carry=load_engagement_info(engagement), blank_clears=True)
    _refuse_a_changed_row_past_the_limit(engagement, items)
    # The documents-held check reads the index, which a pass writes: it
    # runs inside the save's own lock, so a filing cannot land between it
    # and the write (decision 160).
    saved = save_rules(engagement, items, info, head=head,
                       check=lambda: _refuse_taking_away_documents(engagement, recorded, items))
    _refresh_readmes(engagement)
    state = _state(engagement)
    reply = {
        "saved": {"changed": list(saved.changed), "removed": list(saved.removed),
                  "engagement": list(saved.info_fields), "recorded": saved.recorded},
        # The editor's rule warnings are ``state.warnings``; the reply's own
        # ``warnings`` is the envelope's, with one meaning (decision 193).
        "state": state,
    }
    # ``active`` is the one field saved here that the list shows - the
    # feed picker reads it - so only a save that changed it walks (R6,
    # decision 194).
    return _with_list(reply) if "active" in saved.info_fields else reply


#: The keys a row the editor sends may carry (decision 160): the columns of
#: ``records.RULE_FIELDS`` - the two the person never types included,
#: because ``state`` hands them out and a caller sends the rows back - and
#: ``extensions``, the name the wizard has always sent the file types by.
_ROW_KEYS = frozenset(RULE_FIELDS) | {"extensions"}


def _as_recorded(row: dict, recorded: dict | None) -> dict:
    """``row`` with every column it leaves out taken from ``recorded``, the
    record's row of the same identifier (decision 160): absent means
    unchanged, as it does for the details. A row the record does not hold
    is a new request and takes the defaults, as before.

    ``recorded`` is in the form ``state`` hands a rule out
    (:func:`_rule_for_the_editor`), which :func:`item_from_fields` reads
    back as the same rule. Three keys are not columns a person keeps on
    their own: ``row`` is the position, which the save numbers from the
    list's order; the file types sent as ``extensions`` are the file types;
    and ``date_pattern_derived`` is what the save decided of the date
    pattern, so it is kept only with the pattern it describes - when the
    row leaves the pattern out too, or sends back exactly the pattern the
    record holds. A pattern the person typed is theirs, derived or not.
    """
    if recorded is None:
        return row
    filled = dict(row)
    for key, value in _rule_for_the_editor(recorded).items():
        if key in row or key == "row":
            continue
        if key == "allowed_extensions" and "extensions" in row:
            continue
        if key == "date_pattern_derived" and "date_pattern" in row and \
                str(row["date_pattern"] or "").strip() != str(recorded.get("date_pattern") or "").strip():
            continue
        filled[key] = value
    return filled


def _refuse_taking_away_documents(engagement: Path, recorded: list[dict], items: list) -> None:
    """Refuse a save that would take a request holding filed documents off
    the list (decision 160, the audit's D-7): the first such request, by
    name and count (:data:`HOLDS_DOCUMENTS`). Compared without case, so a
    respelling by case alone keeps the request and is saved. Called by
    ``manifest.save_rules`` under the engagement lock, after the list's
    version is checked - so ``recorded`` is the list as it still stands."""
    kept = {identifier_key(item.identifier) for item in items}
    held = documents_by_request(engagement, [item_from_record(rule) for rule in recorded])
    for rule in recorded:
        key = identifier_key(str(rule["identifier"]))
        if key not in kept and held.get(key):
            raise ManifestError(HOLDS_DOCUMENTS.format(identifier=rule["identifier"], n=held[key]))


#: What a row is compared on to say the editor changed it (decision 131):
#: the four things a working copy's path is made of.
_PATH_FIELDS = ("identifier", "document", "period", "allowed_extensions")


def _refuse_a_changed_row_past_the_limit(engagement: Path, items: list) -> None:
    """The editor's save keeps creation's standard for the rows it changes
    (decision 131).

    A row whose identifier, document, period or file types differ from the
    stored list, and every new row, is measured as creation measures a
    list (``filer.room_for``); one whose canonical working copy would pass
    what Windows opens refuses the save with creation's own sentence, and
    nothing is recorded - the person shortens the label and saves again.
    A row the person did not touch is never refused: it is already in the
    room the page and the banner report, so shortening one label is never
    trapped by another. A row set Not Applicable is not measured, as
    creation does not measure it, and neither is a row nobody asked for
    (decision 142); a row a person has just set Asked is measured, because
    it is now a request creation would have measured.
    """
    stored = {item.identifier: item for item in load_manifest(engagement)}
    changed = [item for item in items
               if item.identifier not in stored
               or any(getattr(item, name) != getattr(stored[item.identifier], name)
                      for name in _PATH_FIELDS)
               or (item.asked and not stored[item.identifier].asked)]
    need = room_for(engagement, changed).need
    if need > MAX_PATH_LENGTH:
        raise ManifestError(PATH_TOO_LONG.format(folder=engagement, length=need,
                                                 limit=MAX_PATH_LENGTH))


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
    spec = _read_spec()
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


def _cmd_rename(argv: list[str]) -> dict:
    """Give a request another identifier and move its filed documents with
    it (decision 160).

    JSON spec on stdin: {"from": "A01", "to": "A1", "head": "..."} - the
    request as the list spells it, the new identifier, and the version of
    the list the editor was opened on (``state``'s ``list_head``). One act
    through ``filer.rename_request``: the list renamed and each row's
    intent in one write, then the moves, then the rows; refused - nothing
    written, nothing moved - on a stale list, a change of case alone, a
    name already on the list, or a copy that is not where the record put
    it. Then the re-scan, as ``unlearn`` does it, and the client README.

    The rename lands on its own, not as part of a save: the reply carries
    the list's new version beside the fresh state, so the editor it came
    from keeps the rows the person typed and not saved, and saves them
    against the version this rename left.
    """
    engagement = _engagement_dir(argv)
    spec = _read_spec()
    done = rename_request(engagement, str(spec.get("from") or ""), str(spec.get("to") or ""),
                          head=spec.get("head"))
    _refresh_readmes(engagement)
    return {
        "renamed": {"old": done.old, "new": done.new, "moved": done.moved, "rows": done.rows,
                    "left": list(done.left), "head": done.head, "scan_note": done.scan_note},
        "state": _state(engagement),
    }


def _cmd_unlock(argv: list[str]) -> dict:
    """Clear a stale engagement lock. A fresh one is refused with how long to wait."""
    engagement = _engagement_dir(argv)
    status = clear_stale_lock(engagement)
    return {"cleared": True, "age_minutes": int(status.age_seconds // 60),
            "state": _state(engagement)}


def _cmd_list(argv: list[str]) -> dict:
    """Every household, return and left-alone folder under the root - the
    same discovery the scheduled run uses.

    The app's picker groups the returns by household and the misfit list
    is drawn from the same walk the pass makes, so what a person sees and
    what the job walks cannot disagree (decision 125). ``engagements``
    keeps its two old keys so the picker changes as little as it can.
    """
    # The app's first call: an app too deep for its reader says so at once,
    # in a banner that stays (SPEC-169 section 9).
    empty = {"engagements": [], "households": [], "misfits": [],
             "reader_warning": ocr.reader_path_warning(),
             # When the scheduled pass last ran and how it ended (decision
             # 159, E4): one line on the main screen, in the runner's words,
             # with or without a root - a missing root is one way it stops.
             "last_pass": last_pass_line()}
    # A saved root the rule refuses (decision 188, E-13) is never walked:
    # the app asks for the folder again and says why, and the rest of the
    # app - its vocabulary, its commands - still arrives with this reply.
    try:
        root = _saved_root()
    except door.DoorError as exc:
        return {**empty, "needs_root": True, "root": str(clients_root() or ""),
                "root_problem": str(exc), "vocab": _vocab()}
    if root is None or not root.is_dir():
        return {**empty, "needs_root": True, "root": str(root or ""), "vocab": _vocab()}
    try:
        registry = discover_engagements(root)
    except EmptyRoot:
        # An empty root is a practice nobody has set up yet, not a failure.
        return {**empty, "needs_root": False, "root": str(root), "vocab": _vocab()}
    except RegistryError as exc:
        # One that could not be walked is said, never answered as empty
        # (decision 193): the class to the log, the sentence to the page.
        log.warning("The clients root could not be walked (%s)", content_check.said_as_class(exc),
                    exc_info=True)
        _warn(PRACTICE_NOT_WALKED)
        return {**empty, "needs_root": False, "root": str(root),
                "root_problem": PRACTICE_NOT_WALKED, "vocab": _vocab()}
    return {**_list_payload(root, registry), "needs_root": False, "vocab": _vocab(),
            "reader_warning": empty["reader_warning"], "last_pass": empty["last_pass"]}


def _list_payload(root: Path, registry: Registry) -> dict:
    """The list half of the ``list`` reply - the households, the returns
    and the left-alone folders of one walk, and the root - without the
    vocabulary (decision 194). ``list`` adds the vocabulary; a write that
    changes the list carries this alone (:data:`LIST_CHANGING`)."""
    grouped = registry.by_household()
    households = []
    for household in registry.households:
        returns = grouped.get(household.path, [])
        households.append({
            "name": household.name,
            "path": str(household.path),
            "client_folder": str(client_household_dir(root, household.name)),
            "inbox": str(inbox_dir_for(root, household.name)),
            "members": list(household.info.members),
            "contact": household.info.contact,
            "link": household.info.link,
            "problem": household.problem,
            "open_years": open_years(returns),
            "returns": [
                {"label": one.label, "path": str(one.path),
                 "year": one.tax_year if one.tax_year is not None else year_of(one.path),
                 "return_name": one.info.return_name or one.path.name,
                 "active": one.active, "superseded_by": one.superseded_by}
                for one in returns
            ],
        })
    engagements = [
        {"name": one.label, "path": str(one.path),
         "household": str(one.household_path),
         "year": one.tax_year if one.tax_year is not None else year_of(one.path),
         "return_name": one.info.return_name or one.path.name}
        for one in registry.engagements
    ]
    return {
        "engagements": engagements,
        "households": households,
        # Where each misfit is below the root, worded by the layout (decision
        # 188): the page never works out whether one path lies under another.
        "misfits": [{"path": str(misfit.path), "sentence": misfit.sentence,
                     "where": str(Path(*below)) if (below := layout.parts_below(root, misfit.path))
                     else str(misfit.path)}
                    for misfit in registry.misfits],
        "root": str(root),
    }


#: The commands whose reply carries the list, because they change it
#: (decision 194). Showing a return reads the list no more: the app keeps
#: start-up's and takes the one these writes carry. Each is a whole walk
#: (:func:`_listing`), never one household's entry patched in (R5): two
#: folders claiming one household, and the walk's order, are practice-wide
#: facts a one-household read cannot give, and a spliced list could
#: disagree with the walk that is the only discovery (decision 125). They
#: are set-up acts, once per return per season, so the walk there costs no
#: daily click. ``edit`` carries it only when it changed ``active``, the
#: one field it saves that the list shows (R6); ``scan`` carries the list
#: of the walk it already makes, and adds none (R7). ``set-root`` is not
#: here: the app starts again after it, because the vocabulary depends on
#: the settings it writes (R8).
LIST_CHANGING = ("create", "rollover", "roll-household", "edit-household",
                 "accept-folder-name", "edit", "scan")


def _listing(registry: Registry | None = None) -> dict | None:
    """The list a :data:`LIST_CHANGING` write carries: :func:`_list_payload`
    of ``registry``, or of one walk of the saved root, without the
    vocabulary. ``None`` where the root cannot be walked - said once, as
    :data:`PRACTICE_NOT_WALKED` - and the app keeps the list it has; the
    write itself stands."""
    try:
        root = _saved_root()
        if root is None or not root.is_dir():
            return None
        try:
            walked = registry if registry is not None else discover_engagements(root)
        except EmptyRoot:
            return {"engagements": [], "households": [], "misfits": [], "root": str(root)}
        return _list_payload(root, walked)
    except (RegistryError, door.DoorError, SettingsError) as exc:   # the write stands (N4)
        log.warning("The clients root could not be walked (%s)", content_check.said_as_class(exc),
                    exc_info=True)
        _warn(PRACTICE_NOT_WALKED)
        return None


def _with_list(reply: dict, registry: Registry | None = None) -> dict:
    """``reply`` with the list added, when the root could be walked - and
    only for a command :data:`LIST_CHANGING` names, which is what decides
    it (decision 194's review, S3): a command outside it neither walks nor
    carries a list, whoever calls this."""
    if _RUNNING["command"] not in LIST_CHANGING:
        return reply
    listed = _listing(registry)
    if listed is not None:
        reply["list"] = listed
    return reply


#: What the wizard is told when a household name typed again is, by the
#: layout's key, a household already in the list (decision 188, R7; the
#: tie-breaker is Jason's ruling of 2026-09-26: a first name or a middle
#: initial, then the city - never an identifier).
DUPLICATE_HOUSEHOLD = ("A household with that name is already in the list, as '{existing}'. Pick it "
                       "there to add a return to it. If this is another household, add a first name "
                       "or a middle initial to tell the two apart, and if the names still match, add "
                       "the city. Nothing was changed.")
#: What it is told when the name is a client folder no household owns.
CLIENT_FOLDER_TAKEN = ("A folder with that name is already in the clients' tree and no household owns "
                       "it. It is listed under Folders the tracker leaves alone; give it back to its "
                       "household or move it aside first. Nothing was changed.")


def _folders_in(tree: Path) -> list[Path]:
    """The folders directly in one tree, by name, from one listing."""
    try:
        with os.scandir(tree) as entries:
            return sorted(Path(entry.path) for entry in entries if entry.is_dir(follow_symlinks=False))
    except OSError:
        return []


def _refuse_a_taken_household_name(root: Path, household: str) -> None:
    """Refuse a typed household name that is, by the layout's key, one
    already taken in either tree (decision 188, R7): a household folder or
    a household record's name (:data:`DUPLICATE_HOUSEHOLD` - pick it in the
    list), a folder the tracker did not make where a household would be
    (:data:`HOUSEHOLD_NOT_OURS`), or a client folder no household owns
    (:data:`CLIENT_FOLDER_TAKEN`). Names are unique across both trees."""
    key = layout.name_key(household)
    for folder in _folders_in(layout.private_tree_of(root)):
        recorded = ledger.path_for(folder).is_file()
        claim = ""
        if recorded:
            try:
                claim = load_household_info(folder).name
            except ManifestError:
                claim = ""
        if layout.name_key(folder.name) == key or (claim and layout.name_key(claim) == key):
            if recorded:
                raise ManifestError(DUPLICATE_HOUSEHOLD.format(existing=folder.name))
            raise ManifestError(HOUSEHOLD_NOT_OURS.format(name=folder.name))
    for folder in _folders_in(layout.clients_tree_of(root)):
        if layout.name_key(folder.name) == key:
            raise ManifestError(CLIENT_FOLDER_TAKEN)


def _cmd_create(argv: list[str]) -> dict:
    """Create a new return - and, where it is a new one, its household -
    from a JSON spec on stdin:

    {"household": "...", "household_path": "<an existing household folder, or absent>",
     "members": [..], "contact": "..", "link": "..",
     "form": "1040", "year": 2026, "return_name": "...", "client": "...",
     "due": <ISO_DATE_HINT>, "items": [{identifier, document, extensions, ...}, ...]}

    With ``household_path`` the household is that one and its own record
    stands: ``members``, ``contact`` and ``link`` are ignored, because a
    household's details are edited in ``edit-household`` and not written
    over by every return added to it. The same holds for a household named
    by ``household``, where the record already knows one of that name.
    Otherwise a new household is made first, and the return after it.

    The year defaults to the most recently ended year; catalog rows are
    shifted to it. The return's greeting and link default to the
    household's contact and inbox link, so the reminder is filled in from
    the one place a person typed them (decision 125).
    """
    spec = _read_spec()
    root = _root()
    form = str(spec.get("form", "")).strip()
    if form:
        require_form(form)
    client = str(spec.get("client", "") or "").strip()
    # The return's tax year: the calendar's default unless chosen.
    year = _tax_year(spec.get("year"), default_tax_year())

    given = str(spec.get("household_path", "") or "").strip()
    if given:
        household_dir = _household_dir(given)
        if not ledger.path_for(household_dir).is_file():
            raise ManifestError(f"No household record found in '{given}'")
        household = household_dir.name
        # A household paused or stopped takes no new return (decision 188,
        # R7): the new record would be written from one name and filed
        # under another, or into one of two folders that claim one family.
        if held := registry_held_back(household_dir):
            raise ManifestError(held)
    else:
        household = _folder_name(spec.get("household"), "household")
        _refuse_a_taken_household_name(root, household)
        household_dir = private_household_dir(root, household)
    # A household the record already knows is that household, whether the
    # wizard named it by its folder or a person typed its name again: its
    # own details stand, and ``edit-household`` is where they change.
    existing = ledger.path_for(household_dir).is_file()
    made_household: Path | None = None
    if existing:
        household_info = load_household_info(household_dir)
    elif household_dir.exists():
        # A folder of that name the tracker never made (decision 137): a
        # misfit, and the misfit rule is that it is left alone. Adopting it
        # would put a record into a person's folder, and a failure after
        # that would remove the folder whole.
        raise ManifestError(HOUSEHOLD_NOT_OURS.format(name=household))
    else:
        household_info = HouseholdInfo(
            name=household,
            members=tuple(" ".join(str(m).split()) for m in (spec.get("members") or [])
                          if str(m).strip()),
            contact=" ".join(str(spec.get("contact", "") or "").split()),
            link=" ".join(str(spec.get("link", "") or "").split()),
        )

    # Decision 142: the wizard sends every catalog row, each with its tick
    # as ``asked``, and the custom rows (always asked). A list nobody is
    # asked for is still refused - it would chase nothing.
    items = [item_from_spec(s) for s in spec.get("items", [])]
    _refuse_a_list_nobody_is_asked_for(items)
    # The wizard sends catalog rows as written (the base year); shift them
    # to the return's year so TY2025 does not get asked for in 2027.
    base = base_year(form) if form else None
    if base:
        items = [shift_item(item, year - base) for item in items]

    return_name = str(spec.get("return_name", "") or "").strip() or default_return_name(form, client)
    engagement = _new_return_dir(root, household, year, return_name, items)

    # The wizard's dates, or the form's own (decision 117) - a new return
    # is on the reminder's ladder from its first draft. Its greeting and
    # its link come from the household where the spec is silent.
    # A household link recorded before decision 137's rule that is not a web
    # address is left behind with the reason, as at rollover - never a
    # refusal of a link nobody typed here (the review's F2). A link the spec
    # itself sends is still refused by create_engagement.
    link, link_dropped = carried_link(household_info.link)
    base_info = EngagementInfo(client=household_info.contact, link=link)
    info = with_default_dates(_info_from_spec(spec, carry=base_info), form, year)
    if info.link:
        link_dropped = ""
    info = _placed(info, household, year, engagement.name)
    # A return with nobody on it can never file a named request (decision
    # 128), so it is refused at setup rather than left to park every W-2
    # that arrives and say why afterwards.
    if not info.people:
        raise ManifestError(NO_PEOPLE)
    #: Every folder this call's own mkdir made, outermost first: the whole
    #: of what a failure may remove (decision 137).
    made: list[Path] = []
    owned: set[Path] = {engagement}
    try:
        # The household first, so a return never exists under one the
        # record does not know; then the return.
        if not existing:
            try:
                made += make_new_folders(household_dir)
            except FileExistsError:
                # Made by someone else between the look above and now.
                raise ManifestError(HOUSEHOLD_NOT_OURS.format(name=household)) from None
            owned.add(household_dir)
            create_household(household_dir, household_info)
            made_household = household_dir
        made += make_new_folders(engagement)
        # The catalog the wizard chose is recorded in the details: a
        # return that cannot say which checklist it came from cannot be
        # checked against it later. The list is validated whole before a
        # line is written, so a bad row leaves nothing behind.
        create_engagement(engagement, items, info, form=form)
        scaffold_engagement(engagement)
    except Exception:
        # Never a half-built return, in the folder or in the store - and
        # never a folder this call did not make: the return, its year and
        # its household go only where this call's own mkdir made them.
        _undo_made(made, owned)
        raise
    _refresh_readmes(engagement)
    reply = {"created": Engagement(path=engagement, info=info,
                                   household_path=household_dir).label,
             "state": _state(engagement),
             "link_dropped": link_dropped}
    # A household's **first** return is the moment the two grants have to
    # be made, so the checklist comes back with it and the app shows it
    # once (decision 126). A second return added to a household already
    # set up gets none: its inbox was shared when the household was, and
    # nothing is ever re-shared.
    if made_household is not None:
        reply["checklist"] = _sharing_checklist(root, household)
    return _with_list(reply)   # a new return, perhaps a new household (decision 194)


def _undo_made(made: list[Path], owned: set[Path]) -> None:
    """Undo, innermost first, the folders one create or rollover made -
    :func:`tracker.fsio.make_new_folders`' list and nothing else.

    Only a folder this call **owns** - the return, or a household whose
    record it wrote - is removed whole (:func:`_undo_create`). A level
    above one, such as a year folder it had to make, is removed only when
    it is empty (the review's F4): a second create running at the same
    moment may have put its own return there, and that is not this call's
    to take."""
    for folder in reversed(made):
        if folder in owned:
            _undo_create(folder)
            continue
        try:
            folder.rmdir()
        except OSError:
            pass


#: Creation's refusal of a list that asks the client for nothing, and the
#: editor's (decision 142's review, R6): one refusal, one sentence.
NOTHING_ASKED = "Select at least one request item"


def _refuse_a_list_nobody_is_asked_for(items: list) -> None:
    """A return always asks for at least one thing: every catalog row is on
    it, but a list with no asked row would chase nothing and list nothing
    as needed. Refused at creation and at every editor save, in the same
    words, before anything is recorded."""
    if not any(item.asked for item in items):
        raise ManifestError(NOTHING_ASKED)


def _undo_create(engagement: Path) -> None:
    """What a failed create or rollover leaves behind: nothing.

    **Only ever called on a folder this call's own mkdir created**
    (decision 137; :func:`_undo_made` is how every caller reaches it). The
    ``rmtree`` is whole because everything under such a folder is this
    call's too; called on a folder that was already there it would remove
    a person's folder, or an old return, which is what it once did.

    The folder first, so the name is free again whatever happens next;
    then the store's row, in its own try, because a store that cannot be
    reached at this moment (locked, refused by version) must not replace
    the refusal sentence the person is owed with its own, nor leave the
    folder standing for :func:`_new_return_dir` to refuse by name. The
    row it could not drop is a ghost ``create_engagement`` forgets on the
    next attempt.
    """
    shutil.rmtree(engagement, ignore_errors=True)
    try:
        store.forget(store.connect(), engagement)
    except Exception:
        pass


def _feeds_from_spec(sent: object, household_dir: Path) -> tuple[Feed, ...]:
    """The feed list a person built in the editor, refused where it is not
    one (decision 129).

    A household cannot feed itself - its own returns are fed already - and
    a blank household or return line names nothing a pass could resolve.
    A line the list already holds is refused rather than folded away, so a
    person sees that the one they picked was already there instead of
    wondering which of two rows is the real one.
    """
    if not isinstance(sent, (list, tuple)):
        raise ManifestError(f"{FEEDS_LABEL} is a list of returns this drop folder feeds")
    wanted: list[Feed] = []
    for one in sent:
        raw = one if isinstance(one, dict) else {}
        household = layout.normalised_name(raw.get("household", "") or "")
        return_name = layout.normalised_name(raw.get("return_name", "") or "")
        refusal = FEED_REFUSED.format(household=household or "(blank)",
                                      return_name=return_name or "(blank)")
        if not household or not return_name:
            raise ManifestError(refusal)
        # A feed names two folders, so each half is held to the layout's
        # one name rule (decision 188), and says why as a typed name does;
        # identity is the layout's one key, never a spelling.
        _folder_name(household, "household")
        _folder_name(return_name, "return")
        if layout.name_key(household) == layout.name_key(household_dir.name):
            raise ManifestError(refusal)
        if any(layout.name_key(held.household) == layout.name_key(household)
               and layout.name_key(held.return_name) == layout.name_key(return_name)
               for held in wanted):
            raise ManifestError(refusal)
        wanted.append(Feed(household=household, return_name=return_name))
    return tuple(wanted)


def _cmd_edit_household(argv: list[str]) -> dict:
    """Save the household's own details from the app's small modal.

    ``--engagement`` names any return of the household; the household is
    the folder above its year. JSON on stdin: the fields a person may
    change, and a blank clears one. One ``household_changed`` event,
    carrying exactly what moved (decision 125).

    ``feeds`` is the list of return lines in other households this drop
    folder also feeds (decision 129), as ``[{"household", "return_name"}]``
    - a list a person built from what is already there, never inferred. A
    feed naming this household, a blank half, or one the list already
    holds is refused by name.
    """
    engagement = _engagement_dir(argv)
    household_dir = household_of(engagement)
    spec = _read_spec()
    unknown = set(spec) - set(HOUSEHOLD_EDITABLE)
    if unknown:
        raise ManifestError(f"Not a household field: {', '.join(sorted(unknown))}")
    held = load_household_info(household_dir)
    members = held.members
    if "members" in spec:
        typed = spec["members"]
        if isinstance(typed, str):
            typed = typed.splitlines()
        members = tuple(" ".join(str(one).split()) for one in (typed or []) if str(one).strip())
    info = replace(
        held,
        name=held.name or household_dir.name,
        members=members,
        contact=" ".join(str(spec.get("contact", held.contact) or "").split()),
        link=" ".join(str(spec.get("link", held.link) or "").split()),
        feeds=_feeds_from_spec(spec["feeds"], household_dir) if "feeds" in spec else held.feeds,
    )
    saved = save_household(household_dir, info)
    # The household's members, contact and link are in the list (decision 194).
    return _with_list({"saved": {"household": list(saved.fields)}, "state": _state(engagement)})


def _cmd_priors(argv: list[str]) -> dict:
    """Engagements already on disk that a new year could be rolled from.

    The same discovery the scheduled run uses, so what the wizard offers
    and what the job walks are one list; superseded_by comes from it too.
    """
    root = _saved_root()
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
        # The record's year where it carries one (decision 125), the rows'
        # periods where it does not: a prior recorded before the year was
        # a detail still knows which year it was for.
        year = engagement.tax_year if engagement.tax_year is not None else detect_year(items)
        priors.append({
            "name": engagement.path.name,
            "path": str(engagement.path),
            "label": engagement.label,
            "household": str(engagement.household_path),
            "household_name": engagement.info.household or engagement.household_path.name,
            "return_name": engagement.info.return_name or engagement.path.name,
            # The catalog the return was cut from, which the returning-client
            # page picks by default so the rows it never had arrive as not
            # asked without anybody choosing (decision 142's review, R2).
            "form": engagement.info.form,
            "client": engagement.client,
            # Who the return is for (decision 128): the returning-client
            # page lists them under each ticked return, because the roll
            # carries the list unchanged and it is worth one look.
            "people": [person_to_json(one) for one in engagement.info.people],
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
                         "form": "1040", "year": 2026}
    Prior-year data wins on every field it specifies; the form template only
    fills blanks. Rows the client has never had are added as not asked
    (decision 142).
    """
    spec = _read_spec()
    prior_raw = str(spec.get("prior", "")).strip()
    if not prior_raw:
        raise ManifestError("Pick the engagement to roll forward")
    prior = _return_dir(prior_raw)
    if not ledger.path_for(prior).is_file():
        raise ManifestError(f"No record found in '{prior_raw}'")
    # The prior year's rows are read out of the store, so the store has to
    # describe the prior year before roll_forward() asks what never got
    # filed.
    ensure(prior)
    # A household paused, stopped, or whose client folder is gone (decision
    # 188 and its review's M3, S4): refused before anything is written.
    if held := registry_held_back(household_of(prior)):
        raise ManifestError(held)

    form = str(spec.get("form", "")).strip()
    template = template_items(form) if form else []

    report = roll_forward(
        prior,
        target_year=_tax_year(spec.get("year")),
        template=template,
    )

    if report.target_year is None:
        raise ManifestError("The prior's tax year could not be read; give the year")
    # **The target is computed, never typed** (decision 125). A return
    # keeps its name every year under the same household, so the folder is
    # the layout's answer: the household's, the target year, the prior's
    # own return name unless a person gives another.
    prior_info = load_engagement_info(prior)
    # A return rolls forward where it sits (decision 177): the folder it is
    # in and its own folder name, never the names its record carries.
    household_dir = household_of(prior)
    household = household_dir.name
    return_name = str(spec.get("return_name", "") or "").strip() or prior.name
    engagement = _new_return_dir(_root(), household, report.target_year, return_name,
                                 report.items)

    # Last year's details, carried by the one rule (tracker.rollover); the
    # wizard's fields go over it. Rolled From is what retires the prior.
    carried = carry_engagement_info(prior_info, rolled_from=str(prior),
                                    tax_year=report.target_year)
    # The household's own contact and inbox link refill what the carry
    # cleared or the prior never had: the inbox is the household's and
    # does not change from one year to the next.
    try:
        household_info = load_household_info(household_dir)
    except ManifestError:
        household_info = HouseholdInfo()
    # A link that is not a web address is dropped with the reason, not a
    # refused roll (decision 137, L5); the reason rides back to the app.
    link, report.link_dropped = carried_link(carried.link or household_info.link)
    carried = replace(carried,
                      client=carried.client or household_info.contact,
                      link=link)
    # Last year's deadline did not carry, and this year's is the form's:
    # the rolled engagement starts on the ladder as a new one does.
    info = with_default_dates(_info_from_spec(spec, carry=carried),
                              carried.form or form, report.target_year)
    info = _placed(info, household, report.target_year, engagement.name)
    made: list[Path] = []
    try:
        # The return and, in a new year, the year folder: only what this
        # call's own mkdir made is undone (decision 137), and the year only
        # when it is empty.
        made += make_new_folders(engagement)
        create_engagement(engagement, report.items, info)
        scaffold_engagement(engagement)
    except Exception:
        _undo_made(made, {engagement})
        raise
    _refresh_readmes(engagement)

    return _with_list({   # next year's return is in the list now (decision 194)
        "created": Engagement(path=engagement, info=info,
                              household_path=household_dir).label,
        "rollover": {
            "prior": prior.name,
            "prior_year": report.prior_year,
            "target_year": report.target_year,
            **_carried_payload(report, prior),
        },
        "state": _state(engagement),
    })


def _carried_payload(report, prior: Path) -> dict:
    """One return's rollover as the app reads it: every rolled row with its
    origin, its note and whether it is asked, last year's unfiled files, and
    - since decision 177 - the prior's own warning, which decision 188
    leaves empty for a disagreement: a household whose folders and record
    disagree is paused and never rolls."""
    return {
        "warning": engagement_from(prior).warning,
        "carried": [
            {"identifier": r.item.identifier, "document": r.item.document,
             "origin": r.origin, "note": r.note, "asked": r.item.asked}
            for r in report.rolled
        ],
        "unfiled_last_year": report.unfiled_last_year,
        # Decision 137 (L5): the prior's link, when it was left behind.
        "link_dropped": report.link_dropped,
    }


def _cmd_roll_household(argv: list[str]) -> dict:
    """Roll a whole household's year forward, and retire what is left out.

    ``--engagement`` names **any** return of the household; the household
    is the folder above its year. JSON on stdin::

        {"year": 2027 | null,
         "returns": [{"prior": "<return folder>", "form": "1040",
                      "return_name": ""}, ...]}

    Every ticked return is rolled into the year by the same carry rule the
    per-return ``rollover`` uses - which stays the primitive this plans
    with. **Every open-year return the list leaves out is retired** with
    one details edit, so the household has exactly one open year again and
    its inbox goes on being sorted (decision 126). **Every ticked return or
    none** (decision 159): one return's refusal is the whole call's error,
    naming that return, and nothing is rolled; ``skipped`` stays in the
    reply's shape and is always empty. A retirement that fails after every
    return was rolled is not an error of the call - the new returns exist -
    so the reply says what was done: ``not_retired`` names the returns
    left open and ``warning`` is the rollover's own sentence
    (``RolledNotAllRetired``), which the app shows as its banner.

    The year defaults to the one after the household's open year. Nothing
    under the client tree is touched but the new year's folder, and no
    permission is changed: the inbox was shared once, and a new year is a
    new folder under the same grant.
    """
    engagement = _engagement_dir(argv)
    household_dir = household_of(engagement)
    spec = _read_spec()
    years, _ = open_year_returns(household_dir)
    target_year = _tax_year(spec.get("year"),
                            next_tax_year(years[0]) if years else None)
    if target_year is None:
        raise ManifestError("The household's open year could not be read; give the year")

    plans = []
    for one in spec.get("returns") or []:
        given = str((one or {}).get("prior", "") or "").strip()
        if not given:
            raise ManifestError("Pick the returns to roll forward")
        prior = _return_dir(given)
        named = str((one or {}).get("return_name", "") or "").strip()
        plans.append(ReturnPlan(
            prior=prior,
            form=str((one or {}).get("form", "") or "").strip(),
            # A name a person typed is one folder name, checked here as
            # every other typed name is; blank keeps the prior's own.
            return_name=_folder_name(named, "return") if named else "",
        ))

    warning = ""
    not_retired: list[Path] = []
    try:
        done = roll_household(household_dir, target_year=target_year, plans=plans)
    except RolledNotAllRetired as exc:
        done, not_retired, warning = exc.result, exc.not_retired, str(exc)
    rolled = [
        {"prior": was.name, "created": str(created),
         "label": Engagement(path=created, household_path=household_dir,
                             info=load_engagement_info(created)).label,
         **_carried_payload(one_report, was)}
        for was, created, one_report in done.rolled
    ]
    # The state the app lands on: the first return this call made, else
    # the one it was pointed at - a household rollover that rolled nothing
    # still has a household card to redraw.
    landed = done.rolled[0][1] if done.rolled else engagement
    # The year's returns, and the ones retired, are in the list now (decision 194).
    return _with_list({
        "rolled": rolled,
        "skipped": [{"prior": was.name, "reason": why} for was, why in done.skipped],
        "retired": [Engagement(path=one, household_path=household_dir,
                               info=load_engagement_info(one)).label
                    for one in done.retired],
        "not_retired": [Engagement(path=one, household_path=household_dir,
                                   info=load_engagement_info(one)).label
                        for one in not_retired],
        "warning": warning,
        "target_year": target_year,
        "state": _state(landed),
    })


def _cmd_mark_shared(argv: list[str]) -> dict:
    """Record that the firm has shared this household with its client.

    ``--engagement`` names any return of the household; no stdin. One
    ``sharing_confirmed`` event goes on the household's record, under its
    lock, carrying nothing but the day (decision 126).

    **The tracker cannot see Drive's sharing**, so this records a person's
    word and claims nothing more. The one part of the checklist it *can*
    see was done is the inbox's link, and a household with none is refused
    (:data:`SHARE_LINK_FIRST`): a household marked shared with no link
    would send a letter pointing at nothing. Nothing in the pass reads the
    day - filing never waits on a share the tracker cannot check.
    """
    engagement = _engagement_dir(argv)
    household_dir = household_of(engagement)
    info = load_household_info(household_dir)
    if not info.link.strip():
        raise ManifestError(SHARE_LINK_FIRST)
    with engagement_lock(household_dir):
        # The store is brought up to the household's journal before a line
        # is written, which is what load_household_info() has just done.
        store.record(store.connect(), household_dir, ledger.new(ledger.SHARING_CONFIRMED))
    marked = shared_on(household_dir)
    return {"shared_on": marked.isoformat() if marked else None, "state": _state(engagement)}


def _cmd_accept_folder_name(argv: list[str]) -> dict:
    """Accept a paused household's (or one return's) folder name as its
    name (decision 188, R6): ``--engagement`` names a return of the
    household; JSON on stdin ``{"seq": n, "scope": "household" | "return"}``.

    Under the household's lock and each return's, judged by the seq the
    page was drawn from, it appends one ``household_changed`` line naming
    the household's folder to the household record where its record
    claimed another name, and - for ``household`` - one ``rules_changed``
    line with the folder's name as ``info.household`` to each return whose
    claim disagrees, or - for ``return`` - one with ``info.household`` and
    ``info.return_name`` for that return - never the household's name.
    Every line carries
    ``accepted: folder_name``, the person's word, dated by its own stamp.
    **Nothing is moved or renamed.** Refused, with nothing written, when a
    year disagrees (:data:`YEAR_NOT_ACCEPTED`: a return's year is its
    record's) and, whatever the scope, when a recorded original of an
    accepted return rests under a client folder of another name
    (:data:`ORIGINALS_UNDER_OLD_NAME`: a household that has received a
    document is not renamed this season, and its originals are never
    orphaned).
    """
    engagement = _engagement_dir(argv)
    spec = _read_spec()
    seq = _seq_of(spec)
    scope = spec.get("scope")
    if scope not in ("household", "return"):
        raise ManifestError("Say what to accept: the household's name or this return's")
    household_dir = household_of(engagement)
    folder_name = household_dir.name
    accepted = {ledger.ACCEPTED_KEY: ledger.FOLDER_NAME_ACCEPTED}
    returns = household_returns(household_dir)
    written: list[str] = []
    with ExitStack() as locks:
        for folder in [household_dir, *sorted(returns, key=layout.lock_order_key)]:
            locks.enter_context(engagement_lock(folder))
        if seq != _household_seq(household_dir):
            raise _Stale(ACCEPT_STALE)
        info = load_household_info(household_dir)
        details = {one: load_engagement_info(one) for one in returns}
        if not pause_of(household_dir, info, list(details.items())):
            raise ManifestError(NOT_PAUSED)
        judged = returns if scope == "household" else [engagement]
        if any(return_disagrees(one, details[one]) == "year" for one in judged):
            raise ManifestError(YEAR_NOT_ACCEPTED)
        # Whatever the scope, before anything is written (the review's M2):
        # an accept whose returns hold originals under a client folder of
        # another name would orphan them.
        if _originals_under_another_name(household_dir, judged):
            raise ManifestError(ORIGINALS_UNDER_OLD_NAME)
        conn = store.connect()
        # Only an accept of the household renames it: a return's accept
        # writes that return's own line and never the household's name.
        if scope == "household" and claim_disagrees(info.name, folder_name):
            store.record(conn, household_dir, ledger.new(
                ledger.HOUSEHOLD_CHANGED, **{ledger.HOUSEHOLD_KEY: {"name": folder_name}}, **accepted))
            written.append(str(household_dir))
        for one in judged:
            if scope == "household":
                if not claim_disagrees(details[one].household, folder_name):
                    continue
                named = {"household": folder_name}
            else:
                named = {"household": folder_name, "return_name": one.name}
            store.record(conn, one, ledger.new(
                ledger.RULES_CHANGED, **{ledger.INFO_KEY: named}, **accepted))
            written.append(str(one))
    # An accepted name is the list's name now (decision 194).
    return _with_list({"accepted": written, "state": _state(engagement)})


def _originals_under_another_name(household_dir: Path, returns: list[Path]) -> bool:
    """Whether a recorded original of these returns rests under a client
    folder whose name is not this household folder's."""
    root = household_dir.parent.parent
    for one in returns:
        for entry in read_index(one):
            if not entry.pbc_location:
                continue
            place = layout.place_of(root, locate(one, entry.pbc_location))
            if place.kind in layout.CLIENT_KINDS and \
                    layout.name_key(place.household) != layout.name_key(household_dir.name):
                return True
    return False


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


def _fed_returns(engagement: Path, household: dict | None = None) -> dict[Path, str]:
    """Every return this return's drop folder feeds, by folder, with its
    label (decision 129).

    ``household`` is the payload :func:`_state` already built, so a state
    builds it once (decision 192); the two clicks that write through the
    list pass none and build it fresh.

    Its household's own open-year returns and the return lines a person
    extended it to. The one list that says what a hand-over may name, and
    the one the app's picker is drawn from, so a person can only send a
    document where the feed list already goes.
    """
    household_dir = household_of(engagement)
    payload = household or _household_payload(engagement)
    years = payload["open_years"]
    fed = {Path(one["path"]): one["label"] for one in payload["returns"]
           if one["active"] and one["year"] in years}
    fed.update({Path(one["path"]): one["label"] for one in payload["feeds"] if one["path"]})
    fed.pop(engagement, None)
    log.debug("%s feeds %d return(s)", household_dir.name, len(fed))
    return fed


def _hand_over(engagement: Path, original: str, target: Path, identifier: str, *,
               seq: int | None, keyword: str, spelling: Spelling | None,
               also: tuple[str, ...] = (), answers: str = "", waiting: bool = False) -> dict:
    """Hand one parked document to a return this drop folder feeds.

    The target is checked against the feed list before a byte is read:
    nothing routes outside it, and a person extends it in the household's
    editor rather than by naming a folder here. The re-scan afterwards is
    the **target's** - it is the return that gained a document - and this
    return's own row is released (decision 132): it held a parked
    document, which no request's status counted, so nothing about it
    changed that a scan would see.
    """
    fed = _fed_returns(engagement)
    label = fed.get(target)
    if label is None:
        raise ManifestError(NOT_FED.format(label=target.name))
    result = hand_over(engagement, original, target, identifier,
                       seq=seq, keyword=keyword, spelling=spelling,
                       also=also, answers=answers, waiting=waiting)
    scan_note = ""
    try:
        scan_engagement(target)
    except ScanLockedError as exc:
        scan_note = f"not re-scanned: {exc}"
    _refresh_readmes(engagement, target)
    return {
        "handed_over": {
            "original_name": result.entry.original_name,
            "identifier": result.target_entry.identifier,
            "filed_as": result.target_entry.filed_as,
            "prepared_location": result.target_entry.prepared_location,
            "target": str(result.target),
            "label": result.label,
            "moved_original": result.moved_original,
            "keyword": result.keyword,
            "keyword_note": result.keyword_note,
            "spelling": result.spelling,
            "spelling_note": result.spelling_note,
            "left_in_review": result.left_in_review,
            "scan_note": scan_note,
        },
        "state": _state(engagement),
    }


def _hand_over_waiting(engagement: Path, original: str, seq: int | None) -> dict:
    """The one click (decision 204): hand a parked row that names another
    household's person to the return its Waits For cell names, under the
    requests and with the Also Answers that cell recorded.

    The page sends the row and its version and nothing else - no target,
    no identifier - so it decides nothing. The claim is resolved here
    against the feed list, exactly as the card's offer was
    (:func:`_waiting_payload`), and :func:`tracker.filer.hand_over` reads
    the row again under both locks and refuses unless it is still that
    row, waiting for that return and those requests. Everything after is
    a hand-over: the taking return re-scanned, both READMEs rewritten.
    """
    entries = read_index(engagement)
    entry = entries[find_parked(entries, original)]
    claim = entry.waiting_for
    if claim is None:
        raise FilingError(NOT_WAITING.format(name=entry.original_name))
    offer, refused = _waiting_payload(engagement, entry, lambda: _fed_returns(engagement))
    if offer is None:
        raise ManifestError(refused)
    return _hand_over(engagement, original, Path(offer["target"]), claim.identifiers[0],
                      seq=seq, keyword="", spelling=None, also=claim.identifiers[1:],
                      answers=claim.answers, waiting=True)


def _cmd_assign(argv: list[str]) -> dict:
    """File one parked document under a request, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "identifier": "A01", "keyword": "optional",
                         "spelling": {"person": "...", "spelling": "..."},
                         "target": "<a return this drop folder feeds, or absent>",
                         "seq": <the row's record version, as shown>}
    or, for the one click (decision 204),
             {"original": "...", "seq": <as shown>, "waiting": true}
    with no identifier and no target: the row's own Waits For cell says
    both (:func:`_hand_over_waiting`).

    With ``target`` the document is **handed over** (decision 129): the
    identifier names a request of that return, the original moves where it
    must rest - under the household the return lives in - the working copy
    is made there, the parked copy here goes, and this return's row is
    released (decision 132): nothing about it stays here, and the journal
    says which return took it. The target must be a return this drop folder
    feeds, own or fed (:data:`NOT_FED`); nothing routes outside the feed
    list. Without it, everything below is as it has always been.

    The working copy is filed under the canonical name, the index row is
    rewritten as Filed (attributed to a person), the keyword - if given - is
    added to the request so the next such file routes itself, the spelling
    - if given - is added to that person on the return so the next document
    that prints it confirms itself (decision 128), and the engagement is
    re-scanned so the status reflects it straight away.

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
    spec = _read_spec()
    original = str(spec.get("original", "")).strip()
    identifier = str(spec.get("identifier", "")).strip()
    if original and spec.get("waiting") is True:
        return _hand_over_waiting(engagement, original, _seq_of(spec))
    if not original or not identifier:
        raise ManifestError("Pick the file and the request it belongs to")
    seq = _seq_of(spec)
    taught = spec.get("spelling") or {}
    spelling = Spelling(
        person=str(taught.get("person", "") or "").strip(),
        spelling=str(taught.get("spelling", "") or "").strip(),
    ) if taught else None
    target = str(spec.get("target", "") or "").strip()
    if target:
        return _hand_over(engagement, original, Path(target), identifier,
                          seq=seq, keyword=str(spec.get("keyword", "") or ""), spelling=spelling)
    result = assign_review_file(
        engagement, original, identifier, keyword=str(spec.get("keyword", "") or ""),
        spelling=spelling, seq=seq, shortlist=_shortlist_now(engagement, original),
    )
    # The re-scan puts the request's status right straight away. There is
    # one reason left for it not to (decision 103): another run holds the
    # engagement.
    scan_note = ""
    try:
        scan_engagement(engagement)
    except ScanLockedError as exc:
        scan_note = f"not re-scanned: {exc}"
    _refresh_readmes(engagement)
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
            "spelling": result.spelling,
            "spelling_note": result.spelling_note,
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
    spec = _read_spec()
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the file no request asks for")
    result = dismiss_review_file(engagement, original, str(spec.get("note", "") or ""),
                                 seq=_seq_of(spec))
    _refresh_readmes(engagement)
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
    spec = _read_spec()
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the document to send back for review")
    result = unfile_document(engagement, original, str(spec.get("note", "") or ""),
                             seq=_seq_of(spec))
    _refresh_readmes(engagement)
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


def _cmd_mark_missing(argv: list[str]) -> dict:
    """Mark one request missing again that a consolidated statement was
    answering without a copy (decision 146, the owner's answer to 146-Q).

    JSON spec on stdin: {"original": "<the statement's PBC location or name>",
                         "identifier": "A02",
                         "note": "optional",
                         "seq": <the row's record version, as shown>}
    The statement stays filed where it is; only that request comes off its
    Also Answers cell, on the record, and the re-scan puts the request back
    to what its own folder holds, so the next draft asks for it.

    Since decision 157 the same command takes a row's **own** request on a
    row whose working copy and original are both gone - the moved card's
    Mark missing: the row stops counting and the next draft asks the
    client for the document. On any other row its own request is refused.
    """
    engagement = _engagement_dir(argv)
    spec = _read_spec()
    original = str(spec.get("original", "")).strip()
    identifier = str(spec.get("identifier", "")).strip()
    if not original or not identifier:
        raise ManifestError("Pick the statement and the request to mark missing")
    result = mark_missing_again(engagement, original, identifier,
                                str(spec.get("note", "") or ""), seq=_seq_of(spec))
    _refresh_readmes(engagement)
    return {
        "marked_missing": {
            "original_name": result.entry.original_name,
            "identifier": result.identifier,
            "reason": result.entry.reason,
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
    says which of the four happened. Since decision 157 a Filed or parked
    row whose copy was simply deleted is accepted too, and the copy is made
    again from the original, as the pass would.

    ``seq`` is the row as the person saw it and is required (decision 112),
    as it is for the other three: a row the pass rewrote while the card was
    open is refused before a byte is read.
    """
    engagement = _engagement_dir(argv)
    spec = _read_spec()
    original = str(spec.get("original", "")).strip()
    if not original:
        raise ManifestError("Pick the working copy to put back")
    result = restore_working_copy(engagement, original, seq=_seq_of(spec))
    _refresh_readmes(engagement)
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


# --------------------------------------------------------------- the reminder ----
# Decision 118. The app shows the week's draft, regenerates it at any of
# the four stages without touching the file, puts the same words on the
# clipboard as a body Outlook keeps, and lets a person approve the text
# they are looking at. Nothing sends, and nothing here can: reading takes
# no lock and writing takes the engagement's, as every other write does.

#: What a panel that has gone stale is refused with: the draft on disk, or
#: the rows behind it, moved between the reading and the click.
DRAFT_MOVED = "the draft changed since it was shown; look again"


def _letter_payload(letter) -> dict:
    """The letter as data, so the app draws it with DOM nodes.

    The page is built from API data and never from an HTML string - its
    own first rule - so the preview cannot be the clipboard's markup. It
    is this shape instead, rendered by the renderer, and the HTML string
    goes to the clipboard alone. The deadline paragraph travels as its
    runs, each saying what it is, so the emphasis lands where the letter
    puts it and the page never searches a sentence for a date.
    """
    if letter is None:
        return {}
    marks = reminder.stage_emphasis(letter.stage)
    return {
        "greeting": letter.greeting,
        "progress": letter.progress,
        "intro": letter.intro,
        "sections": [{"heading": section.heading, "items": list(section.items)}
                     for section in letter.sections],
        "drop": list(letter.drop),
        "link": letter.link,
        "deadline": [_run_payload(run, marks) for run in letter.deadline],
        "close": letter.close,
        "signoff": list(letter.signoff),
        "stage": letter.stage,
    }


def _run_payload(run, marks) -> dict:
    """One run of the deadline paragraph, with what its stage does to it
    already decided: the page marks what it is told to mark."""
    coloured, bold = reminder.run_emphasis(run, marks)
    return {"text": run.text, "kind": run.kind, "colour": coloured, "bold": bold}


def _stage_asked(spec: dict) -> int | None:
    """The stage a click asked for, or None for the one the record gives."""
    asked = spec.get("stage")
    if asked in (None, ""):
        return None
    try:
        return int(asked)
    except (TypeError, ValueError):
        raise ManifestError(f"{asked!r} is not a stage number") from None


def _reminder_now(engagement: Path, requested: int | None, today: dt.date) -> dict:
    """The reminder as the record and the draft file now stand.

    What both commands work from, so the panel and the approval cannot
    disagree about what is on screen. Reads only - no lock, no write, no
    draft file touched (decision 12: the app does not decide the draft
    day; regenerating in memory is not drafting).

    A held reminder has no letter at all (decision 115's rule, carried to
    this surface): a held client's composed text would ask for the clean
    rows alone, which is the partial reminder the hold exists to prevent,
    and the card is something a person can copy from. So the subject, the
    text, the body and the letter are all empty while it is held, the
    toggle stands at the stage the day gives, and a stage asked for is
    ignored - there is nothing to re-stage. A reminder held only by files
    still waiting in the household's inbox (decision 133) is held the same
    way: ``held`` is the rows (none), ``unsorted`` is the count, and the
    card's hold line comes from ``vocab.reminder.inbox_held_line``.
    """
    try:
        info = load_engagement_info(engagement)
        draft = reminder.draft_reminder(engagement, today=today)
    except reminder.ReminderError as exc:
        raise ManifestError(str(exc)) from None

    day_stage = reminder.stage_for(info.due, today)
    last = reminder.last_draft_event(engagement, carrying=ledger.FILE_KEY)
    path = engagement / reminder.DRAFT_FILENAME
    exists = path.is_file()
    edited = exists and not reminder.is_unedited(path)
    approved = reminder.last_approved_event(engagement)
    in_force = reminder.is_approved_this_week(engagement, path,
                                              since=last_draft_day(today, DRAFT_WEEKDAY))
    # Said in the app, not only on the page (decision 193): a fresh draft
    # sitting beside an edited one, and a hold older than a week.
    if (engagement / reminder.NEW_DRAFT_FILENAME).is_file():
        _warn(reminder.DRAFT_WRITTEN_BESIDE)
    late = (reminder.held_too_long(engagement, today, created=created_on(engagement))
            if draft.is_held else "")
    _warn(late)

    if draft.is_held:
        stage = day_stage
    else:
        recorded = last.get(reminder.STAGE_KEY) if last else None
        stage = requested if requested is not None else (recorded or day_stage)
        if draft.has_outstanding and stage != draft.stage:
            try:
                draft = reminder.draft_reminder(engagement, today=today, stage=int(stage))
            except reminder.ReminderError as exc:
                raise ManifestError(str(exc)) from None

    if draft.is_held:
        subject, text, html, letter = "", "", "", None
    elif edited:
        # What a person edited is what they approve and what they copy:
        # the header above the rule is the machine's note to them and was
        # never part of the email, and the words below it are theirs, so
        # no stage's emphasis is put on them.
        body = reminder.pasted_text(path)
        subject, text = reminder.split_pasted(body)
        html, letter = reminder.render_text_html(text), None
    else:
        subject, text = draft.subject, draft.body
        html, letter = reminder.render_html(draft), draft.letter

    shown = f"{reminder.SUBJECT_PREFIX}{subject}\n\n{text}" if subject else text
    return {
        "draft": draft,
        "stage": stage,
        "held": _held_rows(draft.held),
        "unsorted": draft.unsorted,
        "refusal": reminder.held_refusal(draft) if draft.is_held else "",
        "held_too_long": late,
        "last": ({"date": ledger.day_of(str(last.get(ledger.AT_KEY, ""))).isoformat(),
                  "stage": last.get(reminder.STAGE_KEY) or 0,
                  "asked": list(last.get(ledger.ASKED_KEY) or []),
                  "file": last.get(ledger.FILE_KEY, "")} if last else None),
        "approved": ({"date": ledger.day_of(str(approved.get(ledger.AT_KEY, ""))).isoformat(),
                      "stage": approved.get(reminder.STAGE_KEY) or 0,
                      "file": approved.get(ledger.FILE_KEY, "")}
                     if approved and in_force else None),
        "file": {"name": path.name, "exists": exists, "edited": edited, "path": str(path)},
        "subject": subject,
        "text": text,
        "html": html,
        "letter": _letter_payload(letter),
        "fingerprint": reminder.draft_fingerprint(shown),
        "asked": draft.asked,
        "stages": _stages(),
        "editable": not draft.is_held and not edited and draft.has_outstanding,
        # Why the letter has no link, when the record's was not a web
        # address (decision 137, L5; the review's F3).
        "link_dropped": draft.link_dropped,
    }


def _reminder_card(state: dict) -> dict:
    """The reminder command's answer: everything above but the draft
    itself, which is a Python object and stays in this process."""
    return {key: value for key, value in state.items() if key not in ("draft", "refusal")}


def _cmd_reminder(argv: list[str]) -> dict:
    """The week's draft as the record and the file now stand, at a stage.

    JSON on stdin: ``{"stage": n | null}`` - the rung a person moved the
    toggle to, or null for the one the record gives (the stage the last
    draft was written at, else the one the Due Date gives today). Nothing
    is written: the text at another stage is regenerated in memory, the
    draft file is read and never touched, and the HTML body is rendered
    for the clipboard and never stored.

    ``today`` is the day itself. The command line's ``--today`` is for
    reading next week's letter this week; the app is used on the day.
    """
    engagement = _engagement_dir(argv)
    return _reminder_reply(engagement, _stage_asked(_read_spec()), dt.date.today())


def _reminder_reply(engagement: Path, requested: int | None, today: dt.date) -> dict:
    """What the ``reminder`` command answers, without the envelope - and
    what ``state`` carries as ``reminder_card`` (decision 194), so the card
    drawn from either is the same card."""
    # A return nobody has scanned yet has no reminder: a line on the card,
    # not an error (D7, decision 193). Anything else that fails is a failure
    # the app shows, and the card stays.
    items = load_manifest(engagement)
    if not any(item.status for item in items):
        return {"reminder": None, "not_yet": reminder.REMINDER_NOT_YET}
    return {"reminder": _reminder_card(_reminder_now(engagement, requested, today))}


def _reminder_said(engagement: Path) -> dict:
    """The Reminder card at the record's stage, for ``state`` (decision 194).

    **Said, never hidden** (193's D7, carried here): a letter that cannot
    be composed does not take the page with it. Its failure is said by the
    one rule (:func:`_failure_of`) - a worded refusal as itself, anything
    else by its class, with the traceback to the log only (security
    principle 7) - as ``unreadable`` on the card and in the reply's
    ``warnings``. Only the card is caught: the rest of ``state`` fails as
    it always did, because catching more would hide real failures.
    """
    try:
        return _reminder_reply(engagement, None, dt.date.today())
    except Exception as exc:
        failure = _failure_of(exc)
        if failure["kind"] == "failed":
            log.warning("The Reminder card could not be composed (%s)",
                        content_check.said_as_class(exc), exc_info=True)
        _warn(failure["sentence"])
        return {"reminder": None, "unreadable": failure["sentence"]}


def _cmd_approve(argv: list[str]) -> dict:
    """Make the text the panel showed this week's draft, and record it.

    JSON on stdin: ``{"stage": n, "fingerprint": "..."}`` - the rung the
    toggle stood on and the fingerprint of the text that was on screen. A
    panel that has gone stale is refused by that fingerprint before a file
    is touched, exactly as a review card is refused by its row's sequence
    number (decision 112): what is approved must be what was read.

    Under the engagement lock, because it writes: an unedited draft is
    written at the chosen stage, a file somebody edited is approved as it
    stands, any draft standing beside it is set aside by name and never
    deleted, and one ``draft_approved`` event goes on the record. For the
    rest of that draft week the pass treats the file as it treats an
    edited one. A held reminder is refused in the sentence the run and the
    command line give. Nothing is sent, and no socket is opened.
    """
    engagement = _engagement_dir(argv)
    spec = _read_spec()
    requested = _stage_asked(spec)
    shown = str(spec.get("fingerprint", "") or "")
    today = dt.date.today()
    with engagement_lock(engagement):
        state = _reminder_now(engagement, requested, today)
        if state["draft"].is_held:
            raise ManifestError(state["refusal"])
        if shown != state["fingerprint"]:
            raise _Stale(DRAFT_MOVED)
        draft = state["draft"]
        path = engagement / reminder.DRAFT_FILENAME
        written = path if state["file"]["edited"] else reminder.write_draft(
            draft, engagement_dir=engagement, preserve_edits=False)
        set_aside = reminder.set_aside_other_draft(engagement, today)
        store.record(store.connect(), engagement, reminder.approved_event(draft, written))
    return {"reminder": _reminder_card(_reminder_now(engagement, requested, today)),
            "set_aside": set_aside.name if set_aside else ""}


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
    spec = _read_spec()
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
            "engagements": _cmd_list([])["engagements"],
            "short_of_room": _short_of_room(root)}


def _short_of_room(root: Path) -> list[dict]:
    """Every return short of room under a clients root a person has just
    set, in label order (decision 131).

    The one moment every move the tracker survives passes through - a root
    that moved is a root the tracker cannot find until somebody sets it
    again - so it is the moment to say what the move costs. The root is
    recorded regardless: the firm's data is where it is. One walk, one read
    of each list; the one time this is done outside a pass, because it is
    the one moment a person is asking. A return whose list will not read
    is left to the pass and the picker, which already say why.
    """
    try:
        registry = discover_engagements(root)
    except RegistryError:
        return []
    short = []
    for engagement in registry.engagements:
        # The returns a pass would work: a prior rolled forward and a client
        # finished with are never written to, so their room is nobody's worry.
        if engagement.problem or engagement.superseded_by or not engagement.active:
            continue
        try:
            room = room_for(engagement.path, load_manifest(engagement.path))
        except Exception as exc:          # the pass and the picker say this return's problem
            log.warning("Could not measure %s (%s)", engagement.label, exc)
            continue
        if room.short or room.parks:
            short.append({"engagement": engagement.label, "short": room.short, "parks": room.parks,
                          "sentences": _room_sentences(room)})
    return sorted(short, key=lambda one: one["engagement"])


def _cmd_install_schedule(argv: list[str]) -> dict:
    """Generate the Task Scheduler job for this app's settings and register it.

    JSON on stdin (all optional): {"start": "HH:MM", "every": minutes},
    defaulting to tracker.scheduling's DEFAULT_START / DEFAULT_REPEAT_MINUTES.
    The job names this app's settings folder and the working folder it runs
    from, and reads the clients root from the settings file at every run
    (decision 131), so it walks exactly the folder the app shows - today
    and after the root is changed. A root must be set before a job is
    registered; the reply names it for the dialog's sentence. From a source checkout the job
    is the Python this API runs under; in the packaged app it is this same
    executable in runner mode (api_entry.py, RUNNER_MODE_FLAG), which needs
    none of the environment the shell gives the API.
    """
    spec = _read_spec()
    root = _root()
    # The job names this app's settings folder, never the root (decision
    # 131): it reads the root from the settings file at every run, so a
    # root changed in the app is the root the job walks next.
    folder = settings_dir()
    start = str(spec.get("start") or DEFAULT_START)
    every = int(spec["every"]) if spec.get("every") not in (None, "") else DEFAULT_REPEAT_MINUTES
    frozen = bool(getattr(sys, "frozen", False))
    working_dir = Path(sys.executable).resolve().parent if frozen else REPO_ROOT
    xml_path = settings_path().with_name(SCHEDULE_XML_FILENAME)
    write_text_atomically(
        xml_path,
        task_scheduler_xml(python=sys.executable, settings=folder, working_dir=working_dir,
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
        "settings": str(folder),
        "start": start,
        "every": every,
        "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
        "frozen": frozen,
    }


def _cmd_acknowledge_foreign(argv: list[str]) -> dict:
    """A person has looked at the lines another machine wrote in one
    return's record (decision 159, C-1 (a)): they stop being named on the
    practice page. Taken under the return's lock, like every write."""
    engagement = _engagement_dir(argv)
    with engagement_lock(engagement):
        acknowledged = store.acknowledge_foreign(engagement)
    return {"acknowledged": acknowledged, "state": _state(engagement)}


#: The commands that write a record, a file or the store. Each holds the
#: settings' root to this machine's record checkpoint first (decision 159,
#: E5): a checkpoint that belongs to another root is refused by name
#: before anything is written.
WRITING_COMMANDS = frozenset({
    "rollover", "roll-household", "mark-shared", "scan", "approve", "create", "assign",
    "dismiss", "unfile", "restore", "edit", "edit-household", "unlearn", "rename",
    "mark-missing", "acknowledge-foreign",
    # Decision 188's accept writes the household's and its returns' records
    # (the port review's M2): held to the checkpoint's root like every other.
    "accept-folder-name",
})


def _prove_the_root() -> None:
    """:func:`tracker.store.prove_the_root` for the root the settings name,
    said as the API says every refusal. The root is the door's first
    (decision 188, :func:`_saved_root`): a root its rule refuses is said in
    its sentence and never asked of the checkpoint."""
    root = _saved_root()
    if root is None:
        return
    try:
        store.prove_the_root(root)
    except (store.StoreError, checkpoint.CheckpointError) as exc:
        # Not this machine's root, or its checkpoint busy or unreadable -
        # each in its own sentence (the rebase review's SF1).
        raise ManifestError(str(exc)) from None


COMMANDS = {
    "state": _cmd_state,
    "priors": _cmd_priors,
    "rollover": _cmd_rollover,
    "roll-household": _cmd_roll_household,
    "mark-shared": _cmd_mark_shared,
    "accept-folder-name": _cmd_accept_folder_name,
    "scan": _cmd_scan,
    "reminder": _cmd_reminder,
    "approve": _cmd_approve,
    "templates": _cmd_templates,
    "list": _cmd_list,
    "create": _cmd_create,
    "assign": _cmd_assign,
    "dismiss": _cmd_dismiss,
    "unfile": _cmd_unfile,
    "restore": _cmd_restore,
    "edit": _cmd_edit,
    "edit-household": _cmd_edit_household,
    "propose-spellings": _cmd_propose_spellings,
    "unlearn": _cmd_unlearn,
    "rename": _cmd_rename,
    "mark-missing": _cmd_mark_missing,
    "unlock": _cmd_unlock,
    "watch": _cmd_watch,
    "cancel-pass": _cmd_cancel_pass,
    "settings": _cmd_settings,
    "set-root": _cmd_set_root,
    "install-schedule": _cmd_install_schedule,
    "acknowledge-foreign": _cmd_acknowledge_foreign,
}


def main(argv: list[str]) -> int:
    """Run one command and print its one reply (decision 193's envelope):
    ``warnings`` on every reply, ``failure`` beside ``error`` on every
    error, the traceback of an unexpected one in the error log only."""
    _WARNINGS.clear()
    _ASKED.clear()
    _RUNNING["command"] = argv[0] if argv else ""
    with error_log("tracker"):
        if not argv or argv[0] not in COMMANDS:
            return _reply_failure(ManifestError(USAGE.format(commands="|".join(COMMANDS))))
        try:
            if argv[0] in WRITING_COMMANDS:
                _prove_the_root()
            # One reading child for the command, started only if something is
            # read, and ended with it (decision 169, R-4).
            with ocr.reading_session(in_a_child=content_check.READ_IN_A_CHILD):
                payload = COMMANDS[argv[0]](argv[1:])
        except Exception as exc:  # said as JSON, never a traceback on screen
            if _failure_of(exc)["kind"] == "failed":
                log.error("%s failed", argv[0], exc_info=True)   # the whole text: the log only
            return _reply_failure(exc)
        finally:
            # The store is opened on first use by whatever command needed it;
            # closing it here checkpoints the write-ahead log and takes its two
            # side files with it, so the app's folder is left as it was found.
            store.close()
        payload["warnings"] = list(_WARNINGS)
        print(json.dumps(payload))
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
