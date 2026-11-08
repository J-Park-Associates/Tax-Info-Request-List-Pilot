"""The words the API sends the screen, in one home.

Every word a person reads in the app that Python owns and the API says:
the envelope's and the shell's sentences, the household's card, the review
card, the dialogs, the request-list editor's labels and help, the menu bar
(``MENU``), the screen's own words (``SCREEN``), the words a Mac is shown in
place of a Windows one (``MAC_MENU``, ``MAC_SCREEN``, ``MAC_SCAN_REASONS``),
the refusals the commands say and the schedule's dialog - and the fixed
values the vocabulary carries beside them (``LOCK_WATCH_SECONDS``,
``PATH_KINDS``, the editor's two column lists and the ``assert`` that holds
them to the request list's columns). The renderer types none of them:
:func:`tracker.api.vocab` hands them over (decision 42), and a command's
reply or refusal says them by these names. A wording change is an edit here
and nowhere else (P66: wording only, no behaviour).

**Where it came from** (SPEC-architecture-p5 P5.3, P340; the architecture
audit's C-1 item 1 and C-6). The words sat among the API's handlers, in
twelve runs from ``USAGE`` to ``AFTER_INSTALL_HEADING``. They moved here
byte for byte with their comments, in the order they stood - not in the
order the vocabulary sends them, because file order keeps the move a move
and a word beside its old neighbours and its own ``#:`` comment. The
section headers are this module's. The API imports back by name every word
its own code reads, so :func:`tracker.api.vocab` and every handler read the
same objects under the same names, and no reply changed.

**What stayed in the API**, and why: a key, a flag or a command table is
not a word. ``ENGAGEMENT_FLAG`` is the door's command-line flag; the review
buckets' keys (with ``BUCKET_HEADINGS``, which is keyed by them), the group
keys and ``GROUPS``, the link keys and ``_CONTAINER_CODES`` are codes a
reply carries, and they went with the rules that decide them - to
:mod:`tracker.firm_view` (P344), all but ``BUCKET_HEADINGS``, which the
API's vocabulary sends; ``COMMANDS``, the command sets and
``PASS_COMMAND`` are the door itself; the pilot record's block and the firm
page refusal's are each a word read beside the file name, the bound or the
envelope key it is said with. And ``FIRM_UNREADABLE`` went with the
practice's rows to ``firm_view`` (SPEC-architecture-p5 P5.7, P344), which
the pass could load to fill the firm cache in its own process (Q-C), so
that word must not live here (below).

**Why layer 1.** It reads two labels of the request list (``COLUMNS``,
``COL_ISSUER``) from ``manifest`` and the record's ``NO`` from ``records``,
both layer 1, and the error log's file name (``errlog``) and the product's
name (``settings``) at layer 0. It defines no function and no class, does
not log, and imports nothing else of the package;
``tests/test_screen_words.py`` holds it to words and fixed values.

**Nothing the scheduled pass loads may import it.** ``SCREEN`` reads the
product's name at import (``"product": product_name()``, the side panel's
brand band; P220 counts it among the names fixed at import). The scheduled
task starts the runner with no product name in its environment
(``api_entry.py``'s docstring), and there ``settings.product_name()``
raises - so a module the pass loaded that imported this one would stop the
scheduled pass before it started. Only the API, the editor's save rules
(:mod:`tracker.request_edit`, P341), a household's edits
(:mod:`tracker.household_edit`, P342) and the create transaction
(:mod:`tracker.creation`, P343) import it, and the runner imports none of
them (P313). A guard in ``tests/test_layers.py``,
``test_nothing_the_scheduled_pass_loads_reads_the_products_name_at_import``,
holds every module the runner loads, and every module the firm view
loads, to that.
"""

from __future__ import annotations

from tracker.errlog import ERROR_LOG_FILENAME
from tracker.manifest import COL_ISSUER, COLUMNS
from tracker.records import NO
from tracker.settings import product_name

# ---------------------------------------------- the envelope and the shell ----

#: The usage line, a refusal like any other (its text is unchanged).
USAGE = "usage: tracker.api {commands}"
#: What an error the tracker did not expect is said as: its class and code,
#: never its message, and where its detail went.
FAILED = ("The app hit an error it did not expect ({kind}). What it finished is on the record; "
          "the details are in {log} beside the app's database.")
#: A database the engine refused and a record the disk refused (decision 189's
#: two expected classes, P298): said as themselves with their code, never as
#: "an error it did not expect". The kind stays ``failed``, so the window
#: keeps Retry.
STORE_UNAVAILABLE = ("The app's database could not be used just now ({code}). What it finished is on the record; "
                     "try again in a moment, and if it keeps happening the details are in {log}")
RECORD_NOT_WRITTEN = ("The record could not be written ({code}). What it finished is on the record; "
                      "free the disk or close whatever holds the record open, then try again - "
                      "the details are in {log}")
#: The notices' three buttons (decision 193, ruling 12). Static in
#: ``index.html``'s template, pinned to these word for word, because a
#: notice must work when the very first ``list`` fails, before any
#: vocabulary exists.
NOTICE_LABELS = {"retry": "Retry", "look": "Look Again", "dismiss": "Dismiss"}


#: A clients root that could not be walked (decision 193): said, never an
#: empty answer that reads as a practice with nothing in it.
PRACTICE_NOT_WALKED = ("The clients folder could not be walked just now, so what needs the whole "
                       f"practice is not shown; the details are in {ERROR_LOG_FILENAME}.")
#: The Reminder card kept on screen when its reminder cannot be read (D7).
REMINDER_UNREADABLE = "Reminder Could Not Be Read"
#: One return's reminder line on the household card that could not be read.
REMINDER_LINE_UNREADABLE = "Reminder Could Not Be Read"
#: The same, said as a warning, which names the return by its label. The
#: bare constant above is what the app is sent (``vocab.reminder``).
REMINDER_LINE_UNREADABLE_WARNING = REMINDER_LINE_UNREADABLE + ": {label}"
#: Stop asked of a pass this app is not running (ruling 7 and the lane's).
NOTHING_TO_STOP = "There is no pass this app started running to stop; nothing was changed."
#: How often the app asks whether a lock it shows has gone (ruling 10).
LOCK_WATCH_SECONDS = 5
#: The lock notice's words (D4): nothing waits, and nothing needs clearing.
LOCK_RUNNING = "In Use on {host}"
#: The same, about a lock that is not the shown return's - a sibling, a fed
#: return or the household (the review's S1): named by its own label.
LOCK_RUNNING_OTHER = "{label} in Use on {host}"
LOCK_ON = "It Is on {household}: {name}."
LOCK_GREYED = ("This return's buttons are greyed while it runs and come back by themselves the "
               "moment it lets go.")
LOCK_LEFT_BEHIND = "Stuck Lock From {host}"
LOCK_CLEARED = "The lock left behind was cleared ({minutes} min old)."
LOCK_BUTTONS_BACK = "The pass let go of this return; its buttons are back."
#: Sort & Scan, watched (decision 193).
PROGRESS_HOUSEHOLD = "{household} ({n} of {of})"
PROGRESS_SORT = "Sorting {name}"
PROGRESS_SCAN = "Checking {name}"
PROGRESS_STOP = "Stop"
PROGRESS_STOPPING = "Stopping After This File\u2026"
#: What the shell says when a child is killed, ends with no reply, or
#: cannot start - learned from here, with pinned defaults for a first
#: start (``app/main.js``).
SHELL_KILLED = "Sort Stopped: Ran Too Long."
#: A command killed at the same cap that is not a sort (final review A,
#: finding 5): a write says part of it may have happened, a read only that it
#: stopped. ``main.js`` tells them apart by :data:`tracker.api.WRITING_COMMANDS`.
SHELL_KILLED_WRITE = "Change Stopped: Ran Too Long."
SHELL_KILLED_WRITE_NOTE = "It May Be Partly Done."
SHELL_KILLED_READ = "Stopped: Ran Too Long."
SHELL_KILLED_AT = "It Was on {household}: {name}."
SHELL_NO_REPLY = "No Reply From the App"
SHELL_COULD_NOT_START = "The App Could Not Start"
SHELL_COULD_NOT_SEND = "Could Not Send; Nothing Changed"
#: With no error log named (no data folder yet) the reply says just this, two
#: words, and the details are saved only in the shell's fallback log in
#: Electron's per-user app folder, never shown: the shell never writes a log
#: beside the program (decision 186's rebase review, MF2; Jason, 2026-09-29;
#: SPEC-shell 11.2).
SHELL_NO_LOG = "App Failed"
#: An error of the page's own, said by its class; its message goes to the
#: error log through the shell (the review's S5).
PAGE_ERROR = "The App Hit an Error"
#: What a Sort & Scan reply is said as (the review's S4, decision 42).
SCAN_SCANNING = "Scanning\u2026"
SCAN_NOTHING_DONE = "Nothing Done: {why}."
SCAN_PROBLEM = "Sort Failed"
#: A skipped return whose kind has no approved word is said as just this, never
#: with the engine's sentence (it carries folder paths; final re-review NEW 1).
SCAN_NOTHING_DONE_BARE = "Nothing Done"
#: A failed sort with its short reason after it (Jason, rulings 25 and 29):
#: five words at most in all, no path; the long detail stays in the error log.
SCAN_PROBLEM_REASON = "Sort Failed: {reason}"
#: The short reason by the runner's own ``code`` for the failure (the final
#: line's ``code``); any code not listed here is ``other``. Approved by
#: Jason, ruling 29. Not mapped, because the engine does not tell them apart
#: at this point: Drive not signed in (a notice of its own) and the 30-minute
#: cap (the shell's own sentence, ``SHELL_KILLED``).
SCAN_REASONS = {
    "lock-held": "Another PC Sorting",
    "household-paused": "Two Years Open",
    "client-folder-missing": "Folder Not Found",
    "folder-missing": "Folder Not Found",
    "other": "Unexpected Error",
}
#: Why a return skipped for want of room did nothing: "Nothing Done: Names
#: Too Long." (P134; Jason chose it, 2026-09-30, SPEC-wincheck-fixes Q1).
#: The other skip words, Inactive and Rolled Forward, are the screen's own
#: (``SCREEN``), referenced in :func:`tracker.api.vocab`'s ``scan.skipped``, never
#: restated. A lock held elsewhere says :data:`SCAN_REASONS`'s word; a kind
#: listed nowhere is :data:`SCAN_NOTHING_DONE_BARE` (P117).
SCAN_NO_ROOM = "Names Too Long"
SCAN_COMPLETE = "Pass complete \u2014 {did}.   {summary}"
SCAN_FILED = "Filed {n}"
SCAN_REVIEW = "{n} to Review"
SCAN_SYNCING = "{n} Still Syncing"
SCAN_NOT_SORTED = "{n} Files Not Sorted"
#: A Sort that ran and found nothing to do - nothing filed, nothing to review,
#: nothing syncing, no file it could not sort, no warning - says so in its
#: own short words (P199, owner question Q1, built as recommended), as a
#: skipped return says "Nothing Done" (P134): before, it said nothing at all.
#: When a file is still arriving in the inbox, nothing was sorted though
#: something waits: that is "Nothing Done: 1 Still Syncing." in the words
#: already approved (:data:`SCAN_NOTHING_DONE` with :data:`SCAN_SYNCING`).
SCAN_NOTHING_TO_SORT = "Nothing to Sort"
SCAN_BUT = "But {problems}."
#: A pass whose final line does not name the return it was asked for
#: (decision 203's review, S2): its counts are not guessed from another's.
SCAN_NOT_IN_PASS = ("The pass ended, but its final line does not name this return, so its counts "
                    "are not shown; the page is drawn from the record.")
#: A notice said more than once is one notice with a count.
NOTICE_REPEATED = "({n} Times)"
#: A warning a reply brought about a return other than the one shown - the
#: hand-over picker's read of its target (decision 194's review, S1): said
#: with that return's label, so no notice reads as about the return shown.
NOTICE_ABOUT = "{label}: {sentence}"


# --------------------------- the household, the review card and the editor ----

#: Every word the household's card, the New household step and the
#: misfit list show (decision 125). The renderer types none of it: it
#: reads these from the vocabulary, as it reads every other word Python
#: owns.
HOUSEHOLD_HEADING = "Household"
HOUSEHOLD_NAME_LABEL = "Household"
MEMBERS_LABEL = "Shared With"
MEMBERS_HELP = ("who this household's folder is meant to be shared with - the app cannot "
                "read Drive's sharing, so this is the firm's own note")
CONTACT_LABEL = "Contact"
CONTACT_HELP = "the greeting name in every return's letter, filled into each return when it is made"
INBOX_LINK_LABEL = "Inbox Link"
INBOX_LINK_HELP = "pasted into every return's letter; paste it once the inbox is shared"
OPEN_CLIENT_FOLDER_LABEL = "Open Client Folder"
OPEN_INBOX_LABEL = "Open Inbox"
EDIT_HOUSEHOLD_LABEL = "Edit Household"
NEW_HOUSEHOLD_LABEL = "New Household"
#: Decision 196: the household's card carries the two ways a return is made
#: for a household the tracker knows - Roll forward to the next year, and Add
#: a return - and the toolbar's New household makes one it does not. There is
#: no wizard and no household picked on one page for another to act on; every
#: word of the three is here, and the page types none of them.
ROLL_FORWARD_TO = "Roll Forward to {year}"
ROLL_TICKED_LABEL = "Roll Forward"
ROLL_INTRO = ("Last year's list is the starting point. Everything the client actually sent, set "
              "aside or under-delivered carries forward - what was set aside as not applicable "
              "under its own heading, for a fresh decision; the form template only fills blanks.")
ROLL_NO_TEMPLATE = "Keep Last Year's List"
ROLL_DONE_LINE = "{rolled} return(s) rolled into {year}; {retired} retired"
ROLL_CARRIED = "{n} Request(s) Carried"
ROLL_UNFILED = "{n} Last-Year Files Never Filed"
ROLL_RETIRED_LINE = "{label}: Retired."
ROLL_FORMS_UNLOADED = "Return Types Did Not Load"
ADD_RETURN_LABEL = "Add a Return"
ADD_RETURN_TITLE = "Add a Return to {household}"
NEW_HOUSEHOLD_INTRO = ("A client folder is a household: one folder per tax year inside it, one "
                       "folder per return inside that, and one inbox the client drops everything "
                       "into.")
FORM_STEP_TITLE = "What Type of Return?"
FORM_STEP_NOTE = "The request list is tailored to the form you pick."
CHANGE_FORM_LABEL = "Change Form Type"
CHANGE_HOUSEHOLD_LABEL = "Change Household Details"
EMPTY_ROOT_LINE = "No Households Yet"
ITEMS_TITLE = "New {form} Return"
CREATE_RETURN_LABEL = "Create Return"
RETURN_CREATED_LINE = ('Return "{label}" created with {n} request(s) asked for, client README '
                       "generated. Open the Client Folder to show it.")
HOUSEHOLD_RETURNS_HEADING = "Returns This Year"
HOUSEHOLD_QUEUE_LINE = "{n} document(s) waiting for a person across this household"
#: The feed list (decision 129): what a drop folder feeds beyond its own
#: household's returns, what a household is fed by, and the two warnings a
#: person reads before they extend either. Every one of them is the API's
#: word and the page types none of them.
FEEDS_LABEL = "Also Feeds"
FEEDS_HELP = ("returns in other households this drop folder feeds, by return line; most "
              "households feed only their own")
FEEDS_LINE = "Also Feeds"
FED_BY_LINE = "Also Fed by: {listed}"
ADD_FEED_LABEL = "Feed Another Return"
FEED_WARNING = "Its Members Can Drop Here"
RETURN_WARNING = "Shared Members See Documents"
HAND_OVER_LABEL = "File Under Another Return"
#: The two boxes that answer come with their own words rather than borrowing
#: the household heading and the editor's title, which happened to read
#: nearly right and would have drifted the moment either was reworded. What
#: is being picked is a return and then one of that return's requests.
HAND_OVER_RETURN_LABEL = "The Return That Takes It"
HAND_OVER_REQUEST_LABEL = "Under Which Request"
#: What the app says once a document has been filed under another return
#: (decision 132): where it went, and that the row here is gone - released,
#: nothing about it kept in this return. Filled by the page with the
#: label and the request the reply carries.
HANDED_OVER_LINE = "Filed Under {label}"
#: The one click (decision 204): a document that names the person of a
#: return in another household waits here, and this is the button that
#: hands it over to that return - the requests its list accepted, shown
#: under it, and nothing picked on the page. Filled with the return's label.
FILE_WHERE_IT_WAITS_LABEL = "File It Under {label}"
#: What stands in for the members of a household nobody has typed any for.
#: The warning must still say who will see the documents, and "nobody typed
#: yet" is the honest answer - the tracker cannot see Drive's sharing.
NOBODY_TYPED = "Nobody Typed Yet"
#: What a hand-over to a return this drop folder does not feed is refused
#: with. Nothing routes outside the feed list, and a person extends it
#: deliberately or not at all.
NOT_FED = "{label} is not a return this drop folder feeds; add it to the household's feeds first"
#: The related households (pilot P141, P170): a person's note that two
#: households belong together, kept on both records and never a route.
#: The editor's label and button, and what a name that is not one is
#: refused with.
RELATED_LABEL = "Related Households"
ADD_RELATED_LABEL = "Add Related Household"
RELATED_REFUSED = "{household} is not a household this one can be related to"
RELATED_UNKNOWN = "{household} is not a household under the clients folder"
RELATED_NOT_A_LIST = "Related Households is not a list of household names"
#: The catalog ids each side-panel Client Type stands for (pilot P153).
CLIENT_TYPE_FORMS = {
    "individuals": ["1040"],
    "businesses": ["1120", "1120S", "1065"],
    "trusts": ["1041"],
    "nonprofits": ["990"],
}

MISFITS_HEADING = "Folders the App Leaves Alone"
MISFITS_NOTE = ("Each is listed with the one reason it does not fit the layout; nothing in it "
                "is ever read, moved or renamed.")
TWO_OPEN_YEARS_NOTE = "Two Years Open; Sorting Paused"
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
    "Paste the inbox's link into the household's Inbox link, then press Mark as Shared.",
)
SHARING_HEADING = "Before the client can drop anything"
MARK_SHARED_LABEL = "Mark as Shared"
SHARED_ON_LINE = "Shared {day}"
NOT_YET_SHARED_LINE = "Not Yet Marked as Shared"
SHARING_NOTE = ("The app cannot see Drive's sharing. The two grants are the firm's to make, once; "
                "the year folders are view-only through the household folder, and nothing is ever re-shared.")
#: Why *Mark as shared* refuses: the inbox's link is the one part of the
#: three the tracker can see was done, so it is the one part it insists on.
SHARE_LINK_FIRST = "paste the inbox's link into the household first"
#: What the roll fold on the household's card says beside its ticks, so
#: nobody unticks a return expecting it to sit still (decision 126).
ROLLOVER_UNTICKED_NOTE = "Unticked Returns Go Inactive"
#: What the Needs Review card calls the decisions a person makes there and
#: on what is already filed, and what it asks them for. The renderer shows
#: these; it types none of them.
DISMISS_LABEL = "Not Requested"
#: What the card says of a row whose file the client dropped inside a
#: folder of their own in the inbox (decision 147), filled from the row's
#: own Client's Subfolder column. The sentence every such row's Reason used
#: to end with, moved here unchanged when the subfolder became a column
#: (decision 190): a folder the client called "not allowed" was read as
#: the file type being refused.
CAME_FROM_SUBFOLDER = "came from the client's subfolder '{folder}'"
DISMISS_NOTE_HINT = "Reason (Optional)"
DISMISSED_HEADING = "Not Requested ({n})"
FILE_LABEL = "File It"
FILE_ANYWAY_LABEL = "File It Anyway"
UNFILE_LABEL = "Unfile"
UNFILE_NOTE_HINT = "Reason (Optional)"
#: Decision 146: the button beside each request a filed consolidated
#: statement answers without a copy, and the words that introduce them.
MARK_MISSING_LABEL = "Mark {identifier} Missing"
ALSO_ANSWERS_LABEL = "Also Answers"
FILED_HEADING = "Filed Documents ({n})"
#: How the picker divides itself: the triaged shortlist first, under the
#: first heading, then every other request under the second. The two are
#: headings, not decisions - a person may still pick anything on the list.
SUGGESTED_HEADING = "Suggested"
OTHER_REQUESTS_HEADING = "Other Requests"
#: The three answers to a working copy that is not where the record put it
#: (decision 110), the card they sit on, and the word for a row whose bytes
#: are nowhere under the firm's folder. Nothing is guessed and nothing is
#: preferred: three buttons, one of which is offered only when the copy sits
#: in the firm's folder under a name that belongs to a request (decision
#: 168), because "keep it where it is" means nothing anywhere else. The renderer shows these and types none of them.
RESTORE_LABEL = "Put It Back"
KEEP_LABEL = "Keep It Here"
SEND_TO_REVIEW_LABEL = "Send to Review"
MOVED_HEADING = "Moved by Hand ({n})"
MOVED_SUMMARY = ("these working copies are not where the record put them; "
                 "choose for each - nothing is guessed")
MOVED_NOWHERE = "Nowhere Under the Firm's Folder"
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
ACCEPT_LABEL = "Accept the Suggestion"
SKIP_LABEL = "Skip for Now"
OPEN_IN_LIST_LABEL = "Pick Another Request"
CARD_MODE_LABEL = "One at a Time"
LIST_MODE_LABEL = "All at Once"
CARD_POSITION = "{n} of {total}"

#: The action that opens a parked row's review copy - the firm's copy in
#: the private tree, marked for Protected View when it can carry macros -
#: and what the card says beside a not-a-document row's true type.
OPEN_COPY_LABEL = "Open"
TRUE_TYPE = "A .{extension} File"
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
EDITOR_TITLE = "Request List"
EDITOR_ENGAGEMENT_TITLE = "Engagement Details"
EDITOR_SAVE_LABEL = "Save"
EDITOR_CANCEL_LABEL = "Cancel"
EDITOR_ADD_LABEL = "Add a Request"
EDITOR_REMOVE_LABEL = "Remove"
EDITOR_PASTE_LABEL = "Paste Rows"
EDITOR_PASTE_HINT = (
    "Paste rows copied from a spreadsheet: one request per line, cells separated by tabs or "
    "as CSV, in the column order above; a first line that repeats the headings is skipped. "
    "Nothing is recorded until you save."
)
EDITOR_WARNINGS_HEADING = "Worth a Look"
RULES_SAVED = "Saved"
NOTHING_CHANGED = "Nothing Changed; Nothing Was Recorded."
LEARNED_NOTE = "Taught by a Filing: {keywords}"
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
RENAME_TITLE = "Rename a Request"
RENAME_HINT = ("Gives a request another identifier and moves its filed documents with it, at once. "
               "Changing an identifier in the list and saving is refused while the request holds "
               "documents; a change of case alone is saved in the list.")
RENAME_FROM_LABEL = "Request"
RENAME_TO_LABEL = "New Identifier"
RENAME_LABEL = "Rename"
RENAMED_NOTE = "Renamed"
RENAME_LEFT_NOTE = "Some Copies Stayed Behind"
#: What the roll's banner says of last year's set-aside rows, in
#: one line beside the carried counts.
NOT_APPLICABLE_CARRIED = "Review {n} Set-Aside Requests"
#: And of the catalog rows the client never had, added as not asked
#: (decision 142, rewording decision 9: they used to be offered, not added).
NEW_NOT_ASKED_CARRIED = "{n} Requests Added, Not Asked"
#: The request list's heading over the catalog's checkboxes, and the sentence
#: under it (decision 142): a tick is a request the client is asked for
#: and reminded of; every row is on the return either way. The screen says
#: "Taxpayer" where it means the person (P196); the name keeps its code name.
ASK_THE_CLIENT = "Ask the Taxpayer"
#: The words the new-return dialog's heading names the list by, between the
#: form's label and :data:`ASK_THE_CLIENT` ("1040 request list - Ask the
#: Taxpayer"): sent so the page types none of them (D-9, SPEC-architecture
#: R5.5). A fragment of the heading, so in lower case as it has always read.
REQUEST_LIST_WORDS = "request list"
#: The name the app's folded table of not-asked rows is read out by, and
#: the roll fold's label over the template pick (decision 142).
NOT_ASKED_TABLE_LABEL = "Requests Not Asked For"
ROLL_TEMPLATE_LABEL = "Form Template"
#: The dialog's help sentence under the catalog's ticks, cut from the screen
#: (the audit's E84-E91) and no longer sent in the vocabulary (P300): kept
#: as the sentence ``tests/test_single_source`` and ``test_api`` guard the
#: renderer against typing again.
ASK_THE_CLIENT_NOTE = ("Every row is on the return. A ticked row is asked for and reminded; "
                       "an unticked one is never asked for, but a document that arrives for "
                       "it is filed there.")
#: The settings page's box for the firm's telephone number (decision 117).
#: It sits beside the firm's name because it is the firm's, not one
#: engagement's, and only the final-notice reminder ever says it.
FIRM_PHONE_LABEL = "Firm Phone"
FIRM_PHONE_HELP = "named in the final-notice reminder; blank drops that sentence"
#: And the setup card's other two boxes, each named by a label that stays
#: while a person types (decision 201, D11): a placeholder is gone the
#: moment somebody types, so no box is named by one alone.
FIRM_NAME_LABEL = "Firm Name"
FIRM_NAME_HELP = "as it should sign the reminders"
CLIENTS_FOLDER_LABEL = "Clients Folder"

# ---- the dialogs and the editor's plain view (decision 201) -----------------
#: What every dialog says when it is asked to close with changes not saved,
#: and its two answers: Keep editing, focused, and the only way out.
UNSAVED_CHANGES = "Unsaved Changes"
KEEP_EDITING = "Keep Editing"
DISCARD_CHANGES = "Discard My Changes"
#: The editor's plain view (M13): the boxes a preparer changes, shown on
#: every row, and the routing columns folded per row - a custom row's
#: Document is drawn with the plain boxes, because nothing else names it.
#: Together they are exactly the request list's columns, asserted below.
PLAIN_COLUMNS = ("expected_count", "asked", "manual_override", "override_reason", "short_title")
ROUTING_COLUMNS = ("identifier", "document", "period", "allowed_extensions", "min_size_kb",
                   "required_keywords", "any_keywords", "date_pattern", "named")
assert (sorted((*PLAIN_COLUMNS, *ROUTING_COLUMNS)) == sorted(field for _, field in COLUMNS)
        and not set(PLAIN_COLUMNS) & set(ROUTING_COLUMNS)), \
    "the plain view and the routing fold must share the request list's columns between them"
#: The one switch that shows a row's routing columns (S5).
EDITOR_ADVANCED_LABEL = "Advanced"
ROUTING_HELP = ("How the app recognises this document when it arrives. A save checks these "
                "the same way whether the fold is open or not.")
#: Edit Request List pressed while the state on screen is still another
#: return's, after reading it again (decision 201, the review's S4): said
#: in the banner rather than a button that does nothing.
EDITOR_NOT_THIS_RETURN = "Request List Did Not Open"
#: What ``assign`` says it did, as ``said`` (D-9, SPEC-architecture R5.5):
#: the document filed; the keyword it taught the request, when one was
#: added; and the spelling it taught one of the return's people (decision
#: 128), when one was. The page shows these as sent and types none of them.
ASSIGNED_FILED = "{name} filed as {filed_as}"
ASSIGNED_KEYWORD_ADDED = '"{keyword}" added to {identifier} so the next one files itself'
ASSIGNED_SPELLING_ADDED = '"{spelling}" added so the next page that prints it confirms itself'
#: The keyword box on a parked or moved document's card (decision 201,
#: D11): its label, and what the word does, as its title.
KEYWORD_LABEL = "Keyword to Learn (Optional)"
KEYWORD_HELP = ("A word this document contains that others like it will too. Taught to the "
                "request so the next one files itself; the editor shows it beside the row.")
#: The card of a K-1 parked for an unnamed issuer (decision 201): its one
#: box, what it will add - the next free row, named before anything is
#: pressed - and its one button; and what the banner says once it is done.
ISSUER_LABEL = COL_ISSUER
ISSUER_HELP = ("Adds {identifier}, a K-1 row for this issuer, to the request list and files this "
               "document under it. Type the distinctive words and leave off the suffix (L.P., LLC).")
ISSUER_ADD_LABEL = "Add Issuer"
ISSUER_ADDED_AND_FILED = "{identifier} - {document} added to the request list, and {name} filed under it."
#: The issuer added and filed, but the re-scan after it met the engagement
#: lock: said by the error's class, never its text (principle 7; the
#: restack review's N2). The next pass puts the row's status right.
ISSUER_NOT_RESCANNED = "Next Sort Rechecks It"
#: A card's issuer that is not a piece of text - only a hand-written
#: stdin can send one - refused rather than turned into a name (the
#: review's N4, as ``tracker.api._seq_of`` refuses a missing version).
ISSUER_NOT_TEXT = "the issuer's name must be typed as text, as the K-1 prints it"

# ---- the people block (decision 128) ----------------------------------------
#: Every word the new-return dialog's and the editor's People block shows. The record
#: owns the heading and what the list is for (``records.PEOPLE_LABEL`` and
#: ``PEOPLE_HELP``) and :mod:`tracker.names` owns the two refusals; these
#: are the block's own controls, and the page types none of them.
PERSON_KIND_LABEL = "Who"
PERSON_NAME_LABEL = "Name"
SPELLINGS_LABEL = "Spellings Documents Use"
SPELLINGS_HELP = ("ticked spellings are what a page is matched against; untick one a document "
                  "never prints, and add any the app did not propose")
ADD_PERSON_LABEL = "Add a Person"
REMOVE_PERSON_LABEL = "Remove"
#: The box for a spelling the app did not propose takes one per line: a
#: comma is part of the very form a document prints (``Park, John``), so
#: splitting on one would turn the form a person typed into two one-word
#: spellings and then refuse both.
OWN_SPELLING_HINT = "Another Spelling, One Per Line"
REVIEW_PEOPLE_LABEL = "Review People"
#: Said once after a household rolls forward: the people carried unchanged
#: and are worth one look (decision 128). Nothing blocks on it - strict
#: parking is the safety net.
PEOPLE_ROLLED_NOTE = "Check Each Return's People"
#: The card's offer beside a page that named nobody, and what the box asks
#: for. Pre-filled with nothing: the person types what the page shows.
TEACH_SPELLING_LABEL = "Teach This Spelling"
TEACH_SPELLING_HINT = "Spelling"


# ------------------------------------------------ two refusals at the door ----

#: What creating a household says when a folder of that name is already
#: there and holds no record (decision 137, M1): the tracker did not make
#: it, so it is a misfit, and a misfit is left alone. Refused before
#: anything is written.
HOUSEHOLD_NOT_OURS = ("A folder named '{name}' is already there and the app did not make it. "
                      "Choose another name, or move that folder aside first. Nothing was changed.")

#: What a command is told when the app's JSON is not one object.
NOT_A_SPEC = "The app sent something that is not a JSON object; nothing was changed"


# -------------------- the root dialog, the paths, the menus and the screen ----

#: The heading the root dialog lists the returns short of room under, after
#: a person sets the clients root (decision 131).
ROOM_HEADING = "Names Shortened to Fit"


#: What each key of a return's ``paths`` names: a folder or a file
#: (decision 188, E-14). The shell ``lstat``s a path before it opens it and
#: refuses a link, or a path that is no longer the kind reported.
PATH_KINDS: dict[str, str] = {
    "engagement": "folder", "inbox": "folder", "originals": "folder", "client_folder": "folder",
    "household": "folder", "prepared": "folder", "view": "file", "draft": "file", "status": "file",
    "clients_root": "folder",
    # A row's key is a word, a space and the row (``review_copy <row>``);
    # the shell reads the word, so a file name on the page opens as a file.
    # ``review_copy`` opens (decision 190: only a marked review copy opens in
    # the default program). The rest are REVEAL-ONLY (``"reveal"``): a filed
    # or moved-by-hand working copy, or a set-aside or parked one, is shown
    # in File Explorer and never opened, because none of them carries the
    # Protected View mark (review 1, F1/F2). The shell refuses a plain open.
    "review_copy": "file", "filed_copy": "reveal", "moved_copy": "reveal", "shown_copy": "reveal",
}
#: The request-list editor's label for a return's detail where the screen's
#: word differs from the record's (P196): the record and the files it writes
#: keep "Client" for the greeting name (``records.ENGAGEMENT_LABELS``); the
#: editor says "Taxpayer", the person the letter greets.
EDITOR_LABELS: dict[str, str] = {"client": "Taxpayer"}
#: The editor's help line where the screen's word differs from the record's
#: (P196, combined review M1): ``records.ENGAGEMENT_NOTES`` keeps "this client"
#: for the README it writes (R7, R9); the editor, which draws the help beside
#: every yes/no box, says the Taxpayer.
EDITOR_HELP: dict[str, str] = {"reminders": f"{NO} = this taxpayer is not chased by email"}

#: The menu bar's words, keyed by item (SPEC-shell 11.3, P84). ``vocab.menu``
#: carries this, and ``main.js`` holds the same words as its defaults so the
#: menu is there from the first frame; a test keeps the two equal. ``&``
#: marks an access key and is not counted in the five words.
MENU: dict[str, str] = {
    "file": "&File",
    "new_household": "New Household…",
    "change_root": "Change Clients Folder…",
    "open_root": "Open Clients Folder",
    "exit": "Exit",
    "edit": "&Edit",
    "client": "H&ousehold",
    "edit_household": "Edit Household…",
    "add_return": "Add a Return…",
    "roll_forward": "Roll Forward…",
    "mark_shared": "Mark as Shared",
    "edit_list": "Edit Request List…",
    "draft_reminder": "Draft Reminder…",
    "open_client_folder": "Open Client Folder",
    "open_inbox": "Open Inbox",
    "open_working": "Open Working Folder",
    "view": "&View",
    "overview": "Overview",
    "needs_review": "Needs Review",
    "reminders": "Reminders",
    "clients": "Households",
    "find": "Find",
    "refresh": "Refresh",
    # Forgets the list column widths this PC keeps (pilot SPEC-lists 4, P139).
    "reset_columns": "Reset Column Widths",
    # A checked item: every list's rows 32px instead of 40px, kept on this PC
    # (pilot SPEC-ui-menu-layout, P271).
    "compact_rows": "&Compact Rows",
    # A checked item: shows or hides the side panel's Under Construction
    # items, kept on this PC (pilot SPEC-hide-under-construction, P197).
    "show_under_construction": "Show &Under Construction",
    "tools": "&Tools",
    "sort_now": "Sort Now",
    "stop_sorting": "Stop Sorting",
    "schedule": "Schedule…",
    "repair_schedule": "Repair Schedule",
    # A Mac's only (the shell leaves it out elsewhere): the schedule is a
    # launchd agent that dragging the app to the Bin leaves behind (SPEC-mac R29).
    "remove_schedule_here": "Remove the Schedule From This Mac…",
    "firm_report": "Firm Report",
    "clear_lock": "Clear Stuck Lock",
    "help": "&Help",
    "tour": "Take the Tour",
    "safeguards": "Safeguards",
    "terms": "Terms",
    "error_log": "Open Error Log",
    "about": "About",
    "check": "Check…",
    "not_requested": "Not Requested",
    "another_return": "Another Return…",
    "put_back": "Put Back",
    "keep_here": "Keep Here",
    "edit_request": "Edit Request…",
    "unfile": "Unfile",
    "mark_missing": "Mark Missing",
    # A file row's right-click item that shows its copy in File Explorer
    # (ruling 12; the same words as ``screen.show_in_explorer``, the tooltip).
    "show_in_explorer": "Show in File Explorer",
}

#: What a Mac says where the words above name a Windows program or place
#: (SPEC-mac R11): File Explorer is Finder, and another computer sorting is
#: another Mac, because the Mac is the one machine (P238). One small table per
#: place the words are kept, laid over the Windows words by :func:`tracker.api.vocab` on a
#: Mac and nowhere else, so a Windows or Linux reply is unchanged and no Mac
#: is ever shown a Windows word (``test_a_mac_is_never_shown_a_windows_word``).
MAC_MENU = {"show_in_explorer": "Show in Finder"}
MAC_SCREEN = {"show_in_explorer": "Show in Finder"}
MAC_SCAN_REASONS = {"lock-held": "Another Mac Sorting"}

#: The words of the new screen that no existing key already says (SPEC-shell
#: 11.4, P84), nested by where each is shown. ``vocab.screen`` carries it.
SCREEN: dict = {
    "sections": {
        "overview": "Overview",
        "needs_review": "Needs Review",
        "reminders": "Reminders",
        "clients": "Households",
    },
    "side_label": "Sections",
    "path_label": "Path",
    # The tooltip of a file name, the only live link that opens File Explorer
    # (ruling 12), and the word of a right-click item that does the same.
    "show_in_explorer": "Show in File Explorer",
    # The tooltip of a household name, which navigates to the household's page
    # in the app (no path, no engine call).
    "navigate_client": "Navigate to Household",
    # The tooltip of a return name, which navigates to the return's page.
    "navigate_return": "Navigate to Return",
    "find": "Find a Household",
    "find_none": "No Match",
    # The search box's placeholder (pilot SPEC-lists 13, P173): every page,
    # and Needs Review, where the box also finds the waiting files.
    "find_placeholder": "Households and Returns",
    "find_placeholder_files": "Files, Households and Returns",
    "sort": {
        "now": "Sort Now",
        "stop": "Stop Sorting",
        "locked": "In Use Elsewhere",
        "stopping": "Stopping",
        # The Sort Now button's tooltip (P274): what it sorts.
        "tip": "Sort This Household's Inbox",
    },
    "last_sort": {
        "today": "Sorted {time}",
        "other_day": "Sorted {date}",
        "failed": "Sort Failed",
        "never": "Not Sorted Yet",
        "running": "Sorting {n} of {total}",
        "done": "Sorted",
        # A pass the schedule is running (pilot P256): not a failure, and
        # the page has no count of it to show, so one word and the bar.
        "scheduled": "Sorting",
    },
    "figures": {
        "need": "Need a Person",
        "waiting": "Waiting on Taxpayers",
        "complete": "Complete",
    },
    "work": "Work Waiting",
    # The linked households (pilot SPEC-lists 10, P141, P171): the icon's
    # tooltip and the panel's name, and each link's kind (owner question
    # Q10, recommendation A).
    "linked": {
        "tip": "Linked Households",
        "feeds": "Also Feeds",
        "fed_by": "Fed By",
        "related": "Related",
    },
    # Overview's filter tabs (pilot SPEC-lists 11, P145); "All" is
    # ``filters.all``.
    "tabs": {
        "need": "Need You ({n})",
        "waiting": "Waiting ({n})",
    },
    # A Needs Review group's count (pilot SPEC-lists 12, P149).
    "documents": {
        "one": "1 Document",
        "many": "{n} Documents",
    },
    # The page buttons of the four firm lists (pilot SPEC-lists 14, P152,
    # P174): the footer, its two buttons and each list's noun.
    "paging": {
        "showing": "Showing {from}-{to} of {total} {noun}",
        "previous": "Previous",
        "next": "Next",
        "nouns": {
            "overview": "Returns",
            "needs_review": "Files",
            "reminders": "Drafts",
            "clients": "Households",
        },
    },
    # The side panel (pilot SPEC-lists 15, P153, P154): the brand band's
    # product name (the firm's name is the window's title, P266), the section
    # headings, Settings, and the pages that are not built yet, each a short
    # name with a "Soon" tag, doing nothing but say so (P265). The product is
    # named from its one home, app/package.json's productName (P155,
    # SPEC-rename R1).
    "side": {
        "product": product_name(),
        "types": "Taxpayer Types",
        "workspace": "Workspace",
        "settings": "Settings",
        "under_construction": "Under Construction",
        "soon": {
            "ready_to_sign": "Ready to Sign",
            "family_entities": "Family Entities",
            "personal_trusts": "Personal Trusts",
            "corporate_entities": "Corporate Entities",
            "portal_settings": "Portal Settings",
        },
        "soon_tag": "Soon",
    },
    # The Taxpayer Types of the side panel (pilot SPEC-lists 15.3; the
    # heading's word is P196's): each opens Households filtered to the
    # households with a return of one of its forms (CLIENT_TYPE_FORMS,
    # ``vocab.client_type_forms``; the keys keep their code names).
    "client_types": {
        "individuals": "Individuals",
        "businesses": "Businesses",
        "trusts": "Trusts & Estates",
        "nonprofits": "Nonprofits",
    },
    # The column headers of the four firm lists (pilot SPEC-lists 2, P138):
    # a header's word, its tooltip - "Sort by {Column}", Jason's choice
    # (P180), whose "by {Column}" keeps it apart from the filing pass's
    # Sort Now - and what a screen reader hears after a keyboard resize.
    "columns": {
        # Overview's and Reminders' return columns, one field each, in
        # Jason's order (pilot P194, P195; "Taxpayer" is his word): the
        # household has no column, and is named in the Taxpayer link's tooltip.
        "tax_year": "Tax Year",
        "taxpayer": "Taxpayer",
        "form_type": "Form Type",
        "taxpayer_tip": "{action} ({household})",
        "status": "Status",
        "date": "Date",
        "file": "File",
        "suggestion": "Suggestion",
        "reason": "Reason",
        "received": "Received",
        "stage": "Stage",
        "drafted": "Drafted",
        "returns": "Returns",
        # Households' own word for its name column (pilot SPEC-lists 15.2;
        # a row there is a household, so "Household Name", P196 R2).
        "client_name": "Household Name",
        "sort_by": "Sort by {column}",
        "width": "{column} Width {n}",
    },
    "empty": {
        "overview": "Nothing Is Waiting",
        "next_sort": "Next Sort {time}",
        "needs_review": "Nothing Needs Review",
        "reminders": "No Drafts Ready",
        "clients": "No Households Yet",
        "work": "No Work Waiting",
        "returns": "No Returns Yet",
        "received": "Nothing Received Yet",
    },
    "filters": {
        "work": "Work Waiting",
        "all": "All",
    },
    "counts": {
        "need": "{n} Need You",
        "waiting": "{n} Waiting",
        "complete": "Complete",
        "returns": "{n} Returns",
        "one_return": "1 Return",
        "files": "{n} Files",
        "one_file": "1 File",
    },
    "due": "Due {date}",
    # A return that needs a person says since when (P269, option c): the day
    # its oldest waiting file arrived. The header stays "Date".
    "since": "Since {date}",
    "partly": "{n} of {total}",
    "groups": {
        "needs_you": "Needs You",
        "waiting": "Waiting on Taxpayer",
        "received": "Received",
        "set_aside": "Set Aside",
    },
    "steps": {
        "check": "Check",
        "open": "Open",
        "draft": "Draft Reminder",
        "edit": "Edit",
    },
    "moved": "Moved by Hand",
    "held": "Held",
    "inactive": "Inactive",
    "rolled": "Rolled Forward",
    "shared": "Shared",
    "not_shared": "Not Shared",
    # The household page's card (pilot SPEC-ui-menu-layout, P275): the
    # household's contact, who it is shared with and whether its inbox link
    # is saved. The link itself is never drawn.
    "household_card": {
        "contact": "Contact",
        "shared_with": "Shared With",
        "inbox_link": "Inbox Link",
        "link_saved": "Saved",
        "no_link": "Not Saved",
    },
    "icons": {
        "dismiss": "Dismiss",
        "open": "Open",
        "next": "Next",
        "more": "More",
        # A Needs Review group's button that opens its right-click menu, and
        # the Client Type chip's dismiss (pilot SPEC-lists 12, 15.3).
        "more_actions": "More Actions",
        "remove_filter": "Remove Filter",
    },
    "sheet": {
        "reminder": "Reminder",
        "drafted": "Drafted {date}, Stage {n}",
    },
    "loading": "Loading",
    # A firm page drawn from counts already held while they are asked
    # again, and how far a long firm wait has read (pilot P222; both
    # approved by Jason 2026-10-08). ``reading_households`` is filled with
    # a count line's ``done`` and ``total``.
    "updating": "Updating",
    "reading_households": "Reading {n} of {total} Households",
    # The Overview's last counts at launch, drawn under the Updating mark
    # until the fresh ones land (pilot P229; approved by Jason 2026-10-08).
    # ``time`` is ``firm-last``'s ``as_of``, said as the app says a time.
    "updating_as_of": "Updating, as of {time}",
    # The one word for closing a sheet or a dialog (S5 review F9); the
    # ``icons.dismiss`` word above stays for the notice's own icon.
    "close": "Close",
    "setup": {
        "title": "Choose Your Clients Folder",
        "choose": "Choose Folder…",
        "start": "Start",
        "missing": "Folder Not Found",
    },
    "notices": {
        "firm_failed": "Counts Not Available",
        "skipped": "{n} Folders Skipped",
        "show": "Show",
        "no_log": "No Error Log Yet",
        "drive": "Drive Not Signed In",
        # The short words of the other notices (S4's missing keys). The long
        # sentences stay in the API for the error log only; a notice shows
        # these. ``machine`` is the one line for a machine warning with no
        # word of its own; ``machine``, ``paused`` and ``feed`` are approved
        # by Jason, ruling 14 (the SPEC names no words for them).
        "reader": "Install Folder Name Too Long",
        "machine": "Machine Needs Attention",
        "renamed": "Folder Renamed",
        "paused": "Two Years Open; Sorting Paused",
        "feed": "Prior Year Data Not Found",
        # The word on the closed disclosure under a notice's one line, which
        # holds the engine's sentence for it (pilot P257).
        "details": "Details",
        # The two short warnings beside a disabled Save in the request-list
        # editor (S5 rebuild 1). Approved by Jason, ruling 23.
        "pick_request": "Pick a Request First",
        "name_requests": "Name Each Custom Request",
        # What choosing a side-panel page that is not built yet says, and
        # all it does (pilot P154).
        "under_construction": "Under Construction",
        # A related link saved on the household edited, not yet on the
        # other, whose lock another pass holds; saving again completes it
        # (P170, the re-check's MUST-R1; Jason's words, P183).
        "related_pending": "Link Pending: {household} Is Busy",
    },
    "misfits": {
        "title": "Folders Skipped",
        # A two-word reason beside each skipped folder's name, by the misfit's
        # `code` (Jason, ruling 18). The app draws reasons[misfit.code].
        "reasons": {
            "not_a_tree": "Unknown Folder",
            "record_misplaced": "Old Layout",
            "no_household_record": "No Household",
            "client_no_record": "Unowned Folder",
            "bad_name": "Name Refused",
            "no_return": "No Return",
            "unlisted": "Cannot List",
            "client_look_alike": "Look-Alike Folder",
            "legacy_folder": "Old Workbook",
            # Ruling 18a: the two-word replacement for "Not A Year".
            "not_a_year": "Bad Year",
        },
    },
    "safeguards": {
        "title": "Safeguards",
    },
    "about": {
        "edition": "Pilot {version}",
    },
    "retry": "Retry",
    "copied": "Copied",
    "saved": "Saved",
}

#: Said before the schedule is moved to this computer, beside the question
#: (SPEC-shell 11.2): a risky act keeps its warning (P77).
SCHEDULE_MOVE_WARNING = "Only If {host} Is Retired"

#: The short line the Setup notice says; the long one stays in
#: :data:`tracker.after_install.FINDINGS_WAIT` for the error log and the
#: after-install reply (SPEC-shell 11.2).
AFTER_INSTALL_WAIT = "Setup Needs Attention"

#: The triage's and the room's words as the app says them (SPEC-shell 11.2,
#: P84). The status report and the console keep the full sentences in
#: :mod:`tracker.review` and :mod:`tracker.filer`, which they still read; the
#: app's card, its ``warnings`` and its ``room_note`` say these.
NOTHING_SUGGESTED_WORDS = "No Suggestion"
SET_ASIDE_NOTE_WORDS = "Set Aside in Request List"
FOOTER_PLACE_WORDS = "in the page {page} footer"
ROOM_SHORT_WORDS = "Names Shortened to Fit"
ROOM_PARKS_WORDS = "{count} Requests Can't Be Filed"

#: What the app's request-list editor says under Active (P77): a warning
#: before a risky act, short. The record's own sentence
#: (:data:`tracker.records.ENGAGEMENT_NOTES`) stays in the README.
ACTIVE_HELP = "No: Sorting Skips This Return"

#: What the shell says when a reported path is no longer what it was.
SHELL_NOT_OPENED = "Not Opened; It Has Changed"
#: What the shell says on a Mac each time it opens a review copy that can
#: carry code (P240, R8). Windows marks such a copy as from the internet so
#: Office opens it in Protected View; a Mac has no mark that does that, so the
#: copy opens normally, which is true to say, and the setting that stands in
#: for the mark is Office's. Not a confirmation and not a refusal: the file has
#: opened, and the sentence is for the next one.
PROTECTED_VIEW_MAC = ("Protected View does not exist on a Mac, so this file opened normally. Keep "
                      "macros off in Excel, Word and PowerPoint: Settings > Security > Macro "
                      "Security > Disable all macros without notification.")


# ---------------------- the feeds, the accept, the create and the reminder ----

#: What *Fed by* says in place of a household whose stored record this
#: computer could not read (decision 192): a name in the line's own list,
#: so the card says it without a word of its own, and the class alone -
#: an exception's text can name a client's folder (security principle 7).
FED_BY_UNREADABLE = "a household whose record this computer could not read ({kind})"

#: The app's action on a paused household (decision 188, R6) and its help.
ACCEPT_FOLDER_NAME_LABEL = "Accept the Folder's Name"
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

#: What New household is told when a household name typed again is, by the
#: layout's key, a household already in the list (decision 188, R7; the
#: tie-breaker is Jason's ruling of 2026-09-26: a first name or a middle
#: initial, then the city - never an identifier).
DUPLICATE_HOUSEHOLD = ("A household with that name is already in the list, as '{existing}'. Pick it "
                       "there to add a return to it. If this is another household, add a first name "
                       "or a middle initial to tell the two apart, and if the names still match, add "
                       "the city. Nothing was changed.")
#: What it is told when the name is a client folder no household owns.
CLIENT_FOLDER_TAKEN = ("A folder with that name is already in the clients' tree and no household owns "
                       "it. It is listed under Folders the App Leaves Alone; give it back to its "
                       "household or move it aside first. Nothing was changed.")

#: Creation's refusal of a list that asks the client for nothing, and the
#: editor's (decision 142's review, R6): one refusal, one sentence.
NOTHING_ASKED = "Tick at Least One Request"

#: What a panel that has gone stale is refused with: the draft on disk, or
#: the rows behind it, moved between the reading and the click.
DRAFT_MOVED = "the draft changed since it was shown; look again"


# ------------------------------------------------------------ the schedule ----

#: The repair path's button, its tooltip and its confirm dialog (decision
#: 209): the schedule registers itself at Setup, at the first launch after an
#: upgrade and when the clients root is saved; this is the deliberate re-run.
SCHEDULE_REPAIR_LABEL = "Repair the Schedule"
SCHEDULE_REPAIR_HELP = ("Register the daily job again on this computer - only needed if the schedule "
                        "was deleted or broken")
SCHEDULE_REPAIR_CONFIRM = "Repair the Schedule Here?"
#: The question before a Mac's schedule is removed (SPEC-mac R29); the answer
#: is ``after_install.SCHEDULE_REMOVED_FROM_MAC``, the step's own sentence.
SCHEDULE_REMOVE_CONFIRM = "Remove the Schedule From This Mac?"
#: Asked when **Repair the Schedule** finds that another computer runs it
#: (decision 209, the review's S5): the packaged app's way to move the
#: schedule, as ``--move-schedule-here`` is from source. ``{host}`` is the
#: computer the designation names; the page fills it in and types nothing
#: else.
SCHEDULE_MOVE_CONFIRM = "Move Schedule Here From {host}?"
#: The Schedule button and its dialog (pilot P21): the page types none of
#: these words.
SCHEDULE_BUTTON = "Schedule"
SCHEDULE_TITLE = "Schedule on This Computer"
SCHEDULE_ENABLED_LABEL = "Run the Schedule"
SCHEDULE_ON = "On"
SCHEDULE_OFF_LABEL = "Off"
SCHEDULE_START_LABEL = "First Run At"
SCHEDULE_EVERY_LABEL = "How Often"
SCHEDULE_EVERY_LABELS = {0: "Once a Day", 30: "Every 30 Minutes", 60: "Every Hour",
                         120: "Every 2 Hours", 240: "Every 4 Hours", 480: "Every 8 Hours"}
SCHEDULE_NOTE = "Scan works either way. Nothing is ever sent."
SCHEDULE_LOADING = "Reading the Schedule Setting..."
SCHEDULE_SAVE = "Save"
SCHEDULE_CANCEL = "Cancel"
#: The heading of the first screen's notice while the last after-install
#: run left findings or failures.
AFTER_INSTALL_HEADING = "Setup Needs Attention"
