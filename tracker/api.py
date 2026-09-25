"""JSON bridge for the desktop app (Electron) — python -m tracker.api <command>.

Commands print a single JSON object to stdout and exit 0, or {"error": ...}
and exit 1. All real logic lives in the tracker package; this module only
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
  scan      one pass over this return's household, exactly as the scheduled
            run makes it (no draft)
  reminder  the week's draft as the record and the file now stand, at any
            of the four stages, with the body Outlook wants (never sends)
  approve   make the text the panel showed this week's draft, and record it
  assign    file one Needs Review document under a request (a person's call)
  dismiss   record that no request asks for one Needs Review document
  unfile    send one filed document back to Needs Review (a person's call)
  restore   put one moved working copy back where the record put it
  unlearn   take back a keyword a filing taught one request, and re-scan
  rename    give a request another identifier and move its filed documents
            with it, as one recorded act (JSON on stdin)
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

from tracker import STANDING_RULES, ledger, names, reminder, review, store
from tracker.filer import (
    DUPLICATE,
    FILE_MOVED,
    FILED,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    ROOM_PARKS,
    ROOM_SHORT,
    FilingError,
    Spelling,
    assign_review_file,
    dismiss_review_file,
    documents_by_request,
    ensure,
    find_parked,
    hand_over,
    moved_to,
    read_index,
    refresh_household_readme,
    refuse_a_path_past_the_limit,
    rename_request,
    restore_working_copy,
    room_for,
    unfile_document,
)
from tracker.fsio import make_new_folders, write_text_atomically
from tracker.households import (
    create_household,
    fed_by,
    household_returns,
    load_household_info,
    open_years,
    resolve_feeds,
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
    is_year_folder,
    originals_dir_for,
    private_household_dir,
    return_dir_for,
    year_of,
)
from tracker.locking import STALE_LOCK_SECONDS, clear_stale_lock, engagement_lock, lock_status
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
    Engagement,
    Registry,
    RegistryError,
    discover_engagements,
    engagement_from,
    mark_superseded,
)
from tracker.rollover import (
    ORIGIN_NEW,
    ORIGIN_NOT_APPLICABLE,
    ORIGIN_PRIOR,
    UNKNOWN_YEAR_LABEL,
    ReturnPlan,
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
    NOTHING_OUTSTANDING,
    REMINDERS_NEVER,
    STATUS_PAGE_FILENAME,
    WEEKDAY_NAMES,
    EngagementRun,
    RunReport,
    append_log,
    last_draft_day,
    last_drafted,
    reader_start_warning,
    run_household,
    status_report,
    write_status_page,
)
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
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
    NOT_ASKED_SECTION,
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


def _folder_name(value: str, what: str) -> str:
    """One folder name from what a person typed, or the refusal that says
    which box to fix.

    A household and a return are each **one** folder name: the layout puts
    them where they go (decision 125), so a name carrying a separator, or
    one that sanitising leaves empty, is a typo and not a path.
    """
    typed = str(value or "").strip()
    name = sanitize_component(typed)
    if not name or not any(ch.isalnum() for ch in name) or name != typed.strip():
        raise ManifestError(f"'{typed}' is not a folder name; {what}")
    return name


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
    household = _folder_name(household, "type the household's name on its own")
    return_name = _folder_name(return_name, "type the return's name on its own")
    year = check_tax_year(int(year))
    engagement = return_dir_for(root, household, year, return_name)
    if engagement.exists():
        raise ManifestError(
            f"A return named '{return_name}' already exists for {household} {year}")
    refuse_a_path_past_the_limit(engagement, items or [])
    return engagement


#: What creating a household says when a folder of that name is already
#: there and holds no record (decision 137, M1): the tracker did not make
#: it, so it is a misfit, and a misfit is left alone. Refused before
#: anything is written.
HOUSEHOLD_NOT_OURS = ("A folder named '{name}' is already there and the tracker did not make it. "
                      "Choose another name, or move that folder aside first. Nothing was changed.")
#: What a command naming a folder that is not a return is told (decision
#: 137, L1). A year folder or a household folder holds a journal too - the
#: household's own record - so a folder is a return by where it sits, as
#: discovery reads it, and not by whether some record is in it.
NOT_A_RETURN = ("{name} is not a return's folder (a return sits at <clients root>\\{tree}"
                "\\<household>\\<year>\\<return>); it is not an engagement")


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
    folder = _under_root(Path(given))
    parts = folder.resolve().relative_to(_root().resolve()).parts
    if (len(parts) != 4 or parts[0].casefold() != PRIVATE_TREE.casefold()
            or not is_year_folder(parts[2])):
        raise ManifestError(NOT_A_RETURN.format(name=folder.name or folder, tree=PRIVATE_TREE))
    return folder


def _under_root(folder: Path) -> Path:
    """``folder`` if it lies under the clients root, else a ManifestError.

    Checked whether or not the folder it names is reachable right now: an
    unplugged drive is not a licence to read from anywhere. Resolved on
    both sides, so ``..``, a junction out of the root and a case difference
    are all seen for what they are. **With no root set it refuses**
    (decision 137, L1): it used to pass any folder at all then, which made
    an unconfigured app a reader of anywhere.
    """
    root = _root()
    try:
        folder.resolve().relative_to(root.resolve())
    except ValueError:
        raise ManifestError(f"{folder} is not under the clients root {root}") from None
    return folder


def form_label(form: str) -> str:
    """``Form 1120-S`` for ``1120S``: the one id -> label map is FORM_TYPES."""
    for entry in FORM_TYPES:
        if entry["id"] == form:
            return entry["label"]
    return FORM_LABEL_PATTERN.format(form=form) if form else "Engagement"


def default_return_name(form: str, client: str) -> str:
    """How a return folder is named when nobody types a name: the form
    first, the client after (``layout.RETURN_NAME_PATTERN``).

    The catalog's own id, not its label - ``1040 - John & Maria Park``,
    which is the name the same return keeps every year (decision 125). The
    renderer fills the same pattern for its preview, so the box and the
    folder agree.
    """
    return sanitize_component(
        RETURN_NAME_PATTERN.format(form=form, client=client or "New client").strip()
    )


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
                          "handed_over": HANDED_OVER_LINE},
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
        },
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

    Each suggestion carries ``name`` - what the page said about whose
    document this is, as ``{"outcome", "spelling", "label"}`` or null
    (decision 128) - so the card can offer *Teach this spelling* where the
    page named nobody without deciding anything of its own.
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


def _return_reminder(path: Path, today: dt.date) -> dict:
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
    says nothing rather than breaking the card.
    """
    blank = {"last": None, "approved": None, "held": 0, "unsorted": 0}
    try:
        items = load_manifest(path)
        entries = read_index(path)
        _, _, _, held = reminder.triage(items, entries)
        last = reminder.last_draft_event(path, carrying=ledger.FILE_KEY)
        approved = reminder.last_approved_event(path)
        in_force = reminder.is_approved_this_week(
            path, path / reminder.DRAFT_FILENAME,
            since=last_draft_day(today, DRAFT_WEEKDAY))
        unsorted = reminder.unsorted_in_inbox(path)
    except Exception:                        # said elsewhere; the card still draws
        return blank
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

    The feed list is resolved against the practice: a feed names a return
    line in another household, and only a walk can say which return that
    is this year. Every caller here wants the same thing and the same
    forgiveness - a root that is unset, gone or unreadable answers with
    nothing rather than failing the card or the pass - so the walk is
    asked for in one place and both the card (:func:`_feed_payload`) and
    *Run now* (:func:`_cmd_scan`) ask it the same way.
    """
    root = clients_root()
    try:
        return discover_engagements(root) if root and root.is_dir() else None
    except RegistryError:
        return None


def _feed_payload(household_dir: Path, years: list[int]) -> tuple[list[dict], list[dict]]:
    """What this drop folder also feeds, and whose drop folders feed it
    (decision 129).

    Each feed is the household and the return line as a person recorded
    them - so the editor sends back exactly what it was shown - with the
    return it resolves to this year, or the sentence saying it resolves to
    nothing. ``fed_by`` is the other direction, for the destination's own
    card: who else may drop for a return that lives here.

    One walk of the practice, and only for a household that has a feed or
    might be fed - which is the question itself, so the walk is made
    whenever the root can be walked at all. A root that cannot be walked
    answers with nothing rather than failing the card.
    """
    try:
        info = load_household_info(household_dir)
    except ManifestError:
        info = HouseholdInfo()
    registry = _the_practice()
    if registry is None:
        return ([{"household": one.household, "return_name": one.return_name,
                  "label": "", "path": "", "warning": ""} for one in info.feeds], [])
    year = years[0] if len(years) == 1 else None
    found, said = ((resolve_feeds(household_dir, info.feeds, year, registry))
                   if year is not None else ([], []))
    by_line = {(one.info.household or one.household_path.name, one.info.return_name or one.path.name):
               one for one in found}
    unresolved = iter(said)
    feeds = []
    for one in info.feeds:
        match = next((found_one for key, found_one in by_line.items()
                      if key[0].casefold() == one.household.casefold()
                      and key[1].casefold() == one.return_name.casefold()), None)
        feeds.append({
            "household": one.household, "return_name": one.return_name,
            "label": match.label if match else "",
            "path": str(match.path) if match else "",
            "warning": "" if match else next(unresolved, ""),
        })
    fed = [{"name": one.name, "path": str(one.path), "members": list(one.info.members)}
           for one in fed_by(registry, household_dir)]
    return feeds, fed


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
    years = open_years(returns)
    queue = sum(
        sum(1 for entry in read_index(one.path) if entry.decision == NEEDS_REVIEW)
        for one in returns if one.active and one.tax_year in years
    )
    feeds, fed = _feed_payload(household_dir, years)
    return {
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
             "reminder": (_return_reminder(one.path, today)
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
    # The room this return has under the clients root (decision 131),
    # measured from the list already loaded - no second read - so a person
    # opening a return sees the number without waiting for a pass.
    room = room_for(engagement, items)
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
                         # The short name the row's folder and copies go by
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
        # The household this return belongs to (decision 125): its own
        # record, the years still open across it, its returns and the one
        # queue a person works. The card is drawn from this and types
        # nothing of its own.
        "household": _household_payload(engagement),
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
    _, _, _, held = reminder.triage(items, entries)
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
    names both. Never raises - :func:`filer.refresh_household_readme` is a
    log line on failure - and is reached only after the action succeeded,
    so a refused action refreshes nothing."""
    for household_dir in dict.fromkeys(household_of(Path(one)) for one in engagements):
        refresh_household_readme(household_dir)


def _cmd_state(argv: list[str]) -> dict:
    return _state(_engagement_dir(argv))


def _record_pass(runs: list[EngagementRun] | EngagementRun) -> None:
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
    every = [runs] if isinstance(runs, EngagementRun) else list(runs)
    root = clients_root()
    if root is None or not root.is_dir():
        return
    # Broadly, both of them: the pass has already moved the client's files
    # and recorded what it found, so nothing about recording it afterwards
    # may turn a finished pass into an error message in the app.
    try:
        append_log(root / LOG_FILENAME, RunReport(today=dt.date.today(),
                                                  reminders=REMINDERS_NEVER, runs=every))
    except Exception as exc:
        log.warning("Could not write %s (%s)", LOG_FILENAME, exc)
    try:
        write_status_page(root, status_report(discover_engagements(root), passed=every))
    except Exception as exc:
        log.warning("Could not write %s (%s)", STATUS_PAGE_FILENAME, exc)


def _cmd_scan(argv: list[str]) -> dict:
    """One pass over this return's **household** - the same pass the
    scheduled job makes.

    Scaffold, sort the household's one inbox, scan, in that order, with
    the same locks, the same error isolation and the same warnings; only
    the weekly draft is left to the scheduled run (or `python -m
    tracker.reminder`). There is one definition of a pass, in
    tracker.runner, and this is it - including the record it leaves behind
    (:func:`_record_pass`).

    **The whole inbox, always** (decision 125). One folder feeds every
    return of the household, so Run now on one return sorts all of it;
    sorting a share of a pile nobody sorted is not a thing the tracker can
    honestly do. The reply is about the return that was asked for.

    **And the whole feed list with it** (decision 129). The practice is
    walked and handed down, so the returns this drop folder feeds in other
    households are judged, locked and filed into here exactly as the
    scheduled pass does it: without the walk the same trial balance would
    file under the co-owned LLC on the schedule and park at home on Run
    now, which is two definitions of a pass and one of them wrong. Since
    decision 132 the pass cannot be called without the walk at all: a root
    that cannot be walked is refused by the runner in one sentence
    (``tracker.runner.NO_PRACTICE``), which is this reply's ``error``, and
    nothing is sorted.
    """
    engagement = _engagement_dir(argv)
    household_dir = household_of(engagement)
    returns = mark_superseded([engagement_from(folder)
                               for folder in household_returns(household_dir)]) \
        or [engagement_from(engagement)]
    runs = run_household(household_dir, returns, reminders=REMINDERS_NEVER,
                         registry=_the_practice())
    run = next((one for one in runs if one.engagement.path == engagement),
               EngagementRun(engagement=engagement_from(engagement)))
    # Said once, on the reply's own warnings (decision 150).
    if warning := reader_start_warning():
        run.warnings.append(warning)
    _record_pass(runs)
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
    spec = json.loads(sys.stdin.read() or "{}")
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
    spec = json.loads(sys.stdin.read() or "{}")
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
    return {
        "saved": {"changed": list(saved.changed), "removed": list(saved.removed),
                  "engagement": list(saved.info_fields), "recorded": saved.recorded},
        "warnings": state["warnings"],
        "state": state,
    }


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
    spec = json.loads(sys.stdin.read() or "{}")
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
    root = clients_root()
    empty = {"engagements": [], "households": [], "misfits": []}
    if root is None or not root.is_dir():
        return {**empty, "needs_root": True, "root": str(root or ""), "vocab": _vocab()}
    try:
        registry = discover_engagements(root)
    except RegistryError:
        # An empty root is a practice nobody has set up yet, not a failure.
        return {**empty, "needs_root": False, "root": str(root), "vocab": _vocab()}
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
        "misfits": [{"path": str(misfit.path), "sentence": misfit.sentence}
                    for misfit in registry.misfits],
        "needs_root": False, "root": str(root), "vocab": _vocab(),
    }


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
    spec = json.loads(sys.stdin.read() or "{}")
    root = _root()
    form = str(spec.get("form", "")).strip()
    if form:
        require_form(form)
    client = str(spec.get("client", "") or "").strip()
    # The return's tax year: the calendar's default unless chosen.
    year = _tax_year(spec.get("year"), default_tax_year())

    given = str(spec.get("household_path", "") or "").strip()
    if given:
        household_dir = _under_root(Path(given))
        if not ledger.path_for(household_dir).is_file():
            raise ManifestError(f"No household record found in '{given}'")
        household = household_dir.name
    else:
        household = _folder_name(spec.get("household"), "type the household's name on its own")
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
    return reply


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
        household = " ".join(str(raw.get("household", "") or "").split())
        return_name = " ".join(str(raw.get("return_name", "") or "").split())
        refusal = FEED_REFUSED.format(household=household or "(blank)",
                                      return_name=return_name or "(blank)")
        if not household or not return_name:
            raise ManifestError(refusal)
        # A feed names two folders, so each half must be a folder name the
        # sanitiser leaves as it is (decision 137, L6): a separator, a
        # device name or a trailing dot names no folder a pass could find.
        if sanitize_component(household) != household or sanitize_component(return_name) != return_name:
            raise ManifestError(refusal)
        if household.casefold() == household_dir.name.casefold():
            raise ManifestError(refusal)
        if any(held.household.casefold() == household.casefold()
               and held.return_name.casefold() == return_name.casefold() for held in wanted):
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
    spec = json.loads(sys.stdin.read() or "{}")
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
    return {"saved": {"household": list(saved.fields)}, "state": _state(engagement)}


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
    )

    if report.target_year is None:
        raise ManifestError("The prior's tax year could not be read; give the year")
    # **The target is computed, never typed** (decision 125). A return
    # keeps its name every year under the same household, so the folder is
    # the layout's answer: the household's, the target year, the prior's
    # own return name unless a person gives another.
    prior_info = load_engagement_info(prior)
    household_dir = household_of(prior)
    household = prior_info.household or household_dir.name
    return_name = (str(spec.get("return_name", "") or "").strip()
                   or prior_info.return_name or prior.name)
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

    return {
        "created": Engagement(path=engagement, info=info,
                              household_path=household_dir).label,
        "rollover": {
            "prior": prior.name,
            "prior_year": report.prior_year,
            "target_year": report.target_year,
            **_carried_payload(report),
        },
        "state": _state(engagement),
    }


def _carried_payload(report) -> dict:
    """One return's rollover as the app reads it: every rolled row with its
    origin, its note and whether it is asked, and last year's unfiled files."""
    return {
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

    Every ticked return is rolled into the year, one at a time, each under
    its own lock and by the same carry rule the per-return ``rollover``
    uses - which stays the primitive this calls. **Every open-year return
    the list leaves out is retired** with one details edit, so the
    household has exactly one open year again and its inbox goes on being
    sorted (decision 126). One return's refusal is reported in ``skipped``
    and undoes none of the others.

    The year defaults to the one after the household's open year. Nothing
    under the client tree is touched but the new year's folder, and no
    permission is changed: the inbox was shared once, and a new year is a
    new folder under the same grant.
    """
    engagement = _engagement_dir(argv)
    household_dir = household_of(engagement)
    spec = json.loads(sys.stdin.read() or "{}")
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
        prior = _under_root(Path(given) if Path(given).is_absolute() else _root() / given)
        named = str((one or {}).get("return_name", "") or "").strip()
        plans.append(ReturnPlan(
            prior=prior,
            form=str((one or {}).get("form", "") or "").strip(),
            # A name a person typed is one folder name, checked here as
            # every other typed name is; blank keeps the prior's own.
            return_name=_folder_name(named, "type the return's name on its own") if named else "",
        ))

    done = roll_household(household_dir, target_year=target_year, plans=plans)
    rolled = [
        {"prior": was.name, "created": str(created),
         "label": Engagement(path=created, household_path=household_dir,
                             info=load_engagement_info(created)).label,
         **_carried_payload(one_report)}
        for was, created, one_report in done.rolled
    ]
    # The state the app lands on: the first return this call made, else
    # the one it was pointed at - a household rollover that rolled nothing
    # still has a household card to redraw.
    landed = done.rolled[0][1] if done.rolled else engagement
    return {
        "rolled": rolled,
        "skipped": [{"prior": was.name, "reason": why} for was, why in done.skipped],
        "retired": [Engagement(path=one, household_path=household_dir,
                               info=load_engagement_info(one)).label
                    for one in done.retired],
        "target_year": target_year,
        "state": _state(landed),
    }


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


def _fed_returns(engagement: Path) -> dict[Path, str]:
    """Every return this return's drop folder feeds, by folder, with its
    label (decision 129).

    Its household's own open-year returns and the return lines a person
    extended it to. The one list that says what a hand-over may name, and
    the one the app's picker is drawn from, so a person can only send a
    document where the feed list already goes.
    """
    household_dir = household_of(engagement)
    payload = _household_payload(engagement)
    years = payload["open_years"]
    fed = {Path(one["path"]): one["label"] for one in payload["returns"]
           if one["active"] and one["year"] in years}
    fed.update({Path(one["path"]): one["label"] for one in payload["feeds"] if one["path"]})
    fed.pop(engagement, None)
    log.debug("%s feeds %d return(s)", household_dir.name, len(fed))
    return fed


def _hand_over(engagement: Path, original: str, target: Path, identifier: str, *,
               seq: int | None, keyword: str, spelling: Spelling | None) -> dict:
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
                       seq=seq, keyword=keyword, spelling=spelling)
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


def _cmd_assign(argv: list[str]) -> dict:
    """File one parked document under a request, by a person's decision.

    JSON spec on stdin: {"original": "<PBC location or original name>",
                         "identifier": "A01", "keyword": "optional",
                         "spelling": {"person": "...", "spelling": "..."},
                         "target": "<a return this drop folder feeds, or absent>",
                         "seq": <the row's record version, as shown>}

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
    spec = json.loads(sys.stdin.read() or "{}")
    original = str(spec.get("original", "")).strip()
    identifier = str(spec.get("identifier", "")).strip()
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
    spec = json.loads(sys.stdin.read() or "{}")
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
    spec = json.loads(sys.stdin.read() or "{}")
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
    spec = json.loads(sys.stdin.read() or "{}")
    return {"reminder": _reminder_card(
        _reminder_now(engagement, _stage_asked(spec), dt.date.today()))}


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
    spec = json.loads(sys.stdin.read() or "{}")
    requested = _stage_asked(spec)
    shown = str(spec.get("fingerprint", "") or "")
    today = dt.date.today()
    with engagement_lock(engagement):
        state = _reminder_now(engagement, requested, today)
        if state["draft"].is_held:
            raise ManifestError(state["refusal"])
        if shown != state["fingerprint"]:
            raise ManifestError(DRAFT_MOVED)
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
    spec = json.loads(sys.stdin.read() or "{}")
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


COMMANDS = {
    "state": _cmd_state,
    "priors": _cmd_priors,
    "rollover": _cmd_rollover,
    "roll-household": _cmd_roll_household,
    "mark-shared": _cmd_mark_shared,
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
