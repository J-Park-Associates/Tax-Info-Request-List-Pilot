# Season One Runbook

How the firm actually runs this thing, day to day, for one tax season.
Who does what, and the life of a request, is [workflow.md](workflow.md) —
this page does not repeat it. Why anything is the way it is, is
[ROADMAP.md](ROADMAP.md).

## 1. What runs where

| | |
|---|---|
| Designated machine | ______________________ (machine name) |
| Who sits at it | ______________________ |
| Clients root | the folder Google Drive for desktop syncs down to that machine |

Clients drop their own documents into a shared Google Drive folder. Google
Drive for desktop syncs that folder onto the designated machine, and the
synced engagement folder **is** the record: the manifest, the index, the
originals, the working copies and the drafts all live in it. There is no
database, no portal and no second copy anywhere.

The folder that holds every engagement is typed once, in the app, on first
launch. It is written to the settings file beside the app
(`tracker.settings.SETTINGS_FILENAME`), and the app, the schedule and every
command read that one value afterwards. From a terminal the same thing is
`python -m tracker.settings <folder>`.

**One machine per clients root.** The only thing that stops a scheduled
pass and a click in the app from moving the same client's files at once is
a lock file (`tracker.locking.LOCK_FILENAME`), and a file a cloud client
copies between two machines is not a lock — both machines can create their
own before either copy arrives. So the schedule runs, and **Sort & Scan**
is pressed, on the designated machine and nowhere else.

The schedule is one daily task that starts at
`tracker.scheduling.DEFAULT_START` and repeats every
`tracker.scheduling.DEFAULT_REPEAT_MINUTES` through the day. Each pass
files what arrived, scans it, and on the draft day writes the chase emails.
The app's **Install Schedule** button registers it for the folder the app
is showing.

**It only runs while someone is logged on.** The task is registered to run
as the logged-on person, not as a background service, so the designated
machine has to stay signed in. A Windows Update reboot in March that leaves
the machine at the sign-in screen stops every pass until someone logs in;
the task is set to start when it can, so the missed pass runs as soon as
they do. Whether that machine signs itself in again after a reboot is the
owner's call — nothing in the tool decides it. A draft day the machine
spent switched off is not lost either: drafting is weekly, not only on the
day, so the next pass drafts instead of skipping the week.

A pass still going at `tracker.locking.RUN_TIME_LIMIT_SECONDS` is stopped
by Task Scheduler — the task carries that as
`tracker.scheduling.EXECUTION_TIME_LIMIT` — and the next repeat carries on
from where it got to.

**Written exception, 2026-09-18.** The firm's Command Center rule is that
automations do not schedule themselves; the owner signed off an exception
for this tool alone, because it drafts and never sends, and because sorted
documents are no use arriving a day late.

## 2. Every morning

1. **Read what the last pass did.** The status page every pass writes into
   the clients root (`tracker.runner.STATUS_PAGE_FILENAME`) is the one-screen
   version — which engagements ran, which need a person, which failed, and
   every parked file across the practice, newest first; the app's
   **Open Status** button opens it. The run log
   (`tracker.runner.LOG_FILENAME`), in the clients root beside the
   engagement folders, has the same, pass by pass, including passes made from
   the app's button.
2. **Clear the review folder.** Anything the rules could not be sure of is
   parked in the review folder (`tracker.scaffold.REVIEW_DIR_NAME`) with a
   reason. In the app, pick the engagement, pick the request the document
   belongs to and press **File it**: the filer moves it, renames it, writes
   the index row, learns the keyword and re-scans. A document nobody ever
   asked for is closed with **Not requested** rather than filed under a
   request that does not want it; the draft stops warning about it, and
   **File it anyway** is the undo. A document filed in the wrong place is
   sent back to the review folder with **Unfile**, on the record, and filed
   again from there.
3. **A locked engagement.** The app shows a notice when a run holds one. If
   it says a run is still going, leave it — **Sort & Scan** waits for it.
   If it says a run left its lock behind, a **Clear lock** button appears;
   it only appears once the lock is older than
   `tracker.locking.STALE_LOCK_SECONDS`, which is past the point Task
   Scheduler must already have killed the run that made it, so clearing it
   then is safe. Never delete a lock file by hand.
4. **Google Drive placeholders.** A file Drive has listed but not yet
   copied down is not the document; the row sits at
   `tracker.manifest.Status.PENDING_SYNC` and the pass leaves it alone
   until Drive has it. Nothing to do, and nothing to ask the client — do
   not right-click it and force it offline. A `.gdoc` or `.gsheet` is a
   shortcut rather than a document: the note tells the client how to send
   an exported copy (`tracker.reasons.GOOGLE_EXPORT_HINT`), and that ask is
   already in the draft.

## 3. Every Saturday

The pass writes each engagement's chase email into its folder as
`tracker.reminder.DRAFT_FILENAME`. If you have already edited that file,
the run never writes over your edits — it leaves them and puts the newer
draft beside them under `tracker.reminder.NEW_DRAFT_FILENAME`, so an edited
draft and a fresh one are never the same file.

Open it, read it, edit it, paste it into Gmail and send it. Nothing in the
tool sends anything, ever.

One warning before you send: if the app or the command line says files the
client has already sent are still sitting in review, identify those first.
A reminder sent over the top of them asks the client for documents already
in hand.

## 4. What the index's Reason column means

Every original gets a row in the engagement's index: where it went, what it
became, and — when it was not filed — why not.

| The index says | In plain words | What you do |
|---|---|---|
| `filer.FILED` | Exactly one request accepted it. | Nothing. |
| `filer.DUPLICATE` | The same bytes were already filed. | Nothing. The original is kept. |
| `filer.NEEDS_REVIEW` | Parked for a person; the reason says which of the rows below. | Work it in the app. |
| `filer.ASSIGNED_BY_PERSON` | Someone filed it with **File it**, on the date shown, and what the rules had said is kept after it. | Nothing. This is the audit trail. |
| `router.UNMATCHED` | No request on this manifest accepted it. | File it to the right request, or add the request. |
| `router.AMBIGUOUS` | More than one request accepted it. | Pick the right one. |
| `router.CONTESTED_PREFIX` | It looks like a named request but failed one of that request's own rules — last year's W-2, say. | Read the named rule. Usually it is the wrong year or the wrong client. |
| `router.OCR_ONLY` | A scan with no text layer; OCR read it, but only loosely enough to guess. | Confirm what it is and file it. |
| `router.NO_REQUEST_ACCEPTS` | No request on this manifest takes that file type at all. | Usually a stray file. Otherwise widen the request's allowed types. |
| `router.PENDING` | A cloud placeholder, still copying down. | Nothing. The next pass picks it up. |

Two more appear as warnings on the run rather than as index rows:

| The run warns | In plain words | What you do |
|---|---|---|
| `filer.REPLACED_IN_PBC` | The client replaced an original we had already filed; the working copy was made from the earlier file. | Look at both, and re-file if the new one differs. |
| `filer.UNTIED_IN_PBC` | A row was recorded without its bytes and its working copy no longer matches the original. | Look at it. Nothing is adopted automatically, by design. |

## 5. What the manifest's Validation Notes mean

Some rows failed because of something the client did. Some failed because
of something on our side. `tracker/reasons.py` holds which is which, and
the drafted email uses it: a firm-side row is reported to us and never put
to the client, so nobody asks a client to resend a file we simply have not
read yet.

**Ours to deal with** (never in the client's email):
`reasons.PENDING_SYNC`, `reasons.VANISHED`, `reasons.NO_TEXT_LAYER`,
`reasons.NO_TEXT_AFTER_OCR`, `reasons.OCR_FAILED`,
`reasons.UNCHECKABLE_TYPE`, `reasons.NO_REQUEST_FOLDER`. These mean the
document may be perfectly fine and no person here has read it yet — or, for
the last one, that the request has no folder and the next pass makes it.

**The client's to fix** (translated into one plain sentence in the draft):
`reasons.PASSWORD_PROTECTED`, `reasons.GOOGLE_STUB`, `reasons.TOO_SMALL`,
`reasons.EXTENSION_NOT_ALLOWED`, `reasons.WRONG_DOCUMENT`,
`reasons.NO_EXPECTED_KEYWORD`, `reasons.WRONG_PERIOD`,
`reasons.NO_PAGES`, `reasons.UNREADABLE_PDF`,
`reasons.EXTRACTION_FAILED`.

The note itself is never pasted into an email. It names keywords, size
floors and our own folders, and a client should never see any of that.

## 6. If the designated machine dies, or you move to another one

About thirty minutes, and nothing is lost.

**Nothing to restore.** Every engagement's manifest, index, originals,
working copies and drafts are in the engagement folder, which syncs. Any
machine signed into the same Drive account has all of it already.

**What was only on that machine:** the settings file beside the app
(`tracker.settings.SETTINGS_FILENAME`), the scheduled task, the app folder
itself, and the Tesseract OCR engine if it was installed.

1. Install Google Drive for desktop on the new machine, sign in with the
   firm account, and wait for the clients folder to finish syncing. Do not
   start until it has.
2. Put the app on it: copy the packaged app folder from the backup, or
   rebuild it from this repository. Running from source needs Python and
   Node; the packaged build needs neither. Keep the folder's path short — a
   few levels deep at most, like the `C:\Tools\tax-tracker` the README's
   scheduling example uses: past the classic Windows path limit the packaged
   program silently loses its command line and answers every call with a
   usage error.
3. Start the app. It asks where the clients live on first launch — give it
   the same folder, the synced one.
4. Press **Install Schedule**.
5. If the firm's scans need OCR, install the Tesseract engine and the
   optional packages `requirements.txt` names. Without them a scan with no
   text layer is flagged for a person instead of being read; nothing
   breaks.
6. Run one pass — **Sort & Scan** on a single engagement — and read the run
   log before trusting the schedule.

**Two machines must never both run it.** Before the new machine's first
pass, turn the old machine's scheduled task off, or keep that machine off
the clients folder entirely. Two machines on one clients root can each take
their own lock and overwrite the other's index rows, and that is the one
way an original ends up filed with no record of how it got there.

## 7. What to expect in season one

Expect the review folder to be busy, particularly in the first weeks.

The routing rules have been read against the IRS forms themselves and
against reconstructions of what those forms print, so the rows that ask for
tax forms are well defended. The rows that ask for business documents —
bookkeeping exports, receipts, statements, agreements — have far less
behind them, because there is no public corpus of those. They will park
documents a person then files. That is the system working as designed: it
parks anything it cannot be sure of, because misfiling a tax document is
worse than not filing it, and every file a person files teaches the row a
keyword.

What turns that from an impression into a number is the backtest
(`tools/backtest.py`): the firm's own already-sorted documents routed
against the catalogs at the office, under neutral names, measuring where the
rules actually land; its agreement, once recorded, is the number no routing
change may lower. Until it has been run, read the review folder as the
measure.

The four standing rules the whole system rests on — no generative AI reads
a client document, originals are never altered, nothing is guessed, nothing
is ever sent — are worded once in the package, shown in the app and quoted
in [../README.md](../README.md) and [../CLAUDE.md](../CLAUDE.md). Read them
there rather than here.

## 8. Who to ask, and where the record is

- **Who does what**, and the life of a request: [workflow.md](workflow.md).
- **Why something odd is the way it is**: the decision log in
  [ROADMAP.md](ROADMAP.md). The odd choice is usually load-bearing.
- **What every pass did**, engagement by engagement, with the failures:
  `tracker.runner.LOG_FILENAME` in the clients root.
- **What happened to one document**: the engagement's index. Every move and
  every rename is in it.

Nothing here sends an email, moves money, or tells a client anything. Every
message a client gets was read and sent by a person at this firm.
