# Season One Runbook

How the firm actually runs this thing, day to day, for one tax season.
Who does what, and the life of a request, is [workflow.md](workflow.md) —
this page does not repeat it. Why anything is the way it is, is
[ROADMAP.md](ROADMAP.md).

## 1. What runs where

| | |
|---|---|
| Designated machine | JPPC (the office PC) |
| Who sits at it | Jason Park |
| Clients root | the folder Google Drive for desktop syncs down to that machine — a folder on the firm's **Shared Drive**, e.g. `"G:\Shared drives\JPA Clients"` |

Clients drop their own documents into a shared Google Drive folder. Google
Drive for desktop syncs that folder onto the designated machine, and the
synced return folder carries everything about that return: the
working copies, the drafts and the return's own ledger,
which holds the request list too; the originals sit in the client's own
folder for the year, one tree over. There is no portal and no second copy of any of
it. There *is* one database — `tracker.db`, beside the app on the
designated machine — but it is disposable: it is rebuilt from the ledgers
in the folders, it is never synced and nobody opens it.

**The app's folder is private to the firm.** `tracker.db` holds every
client's index rows, and the folder beside it where OCR puts a page it is
reading (emptied at the start of every pass) can hold a client's page. The
folder inherits its permissions from wherever the app was unpacked: put the
app in a folder only the firm's accounts on that machine can read, not in a
shared or public one. This is a machine-setup step; the tracker does not
change permissions.

**A return the store refuses as "changed behind the tracker's back".** The
store keeps a fingerprint of every line of a return's record it has read
(decision 137). If a sync client or a person rewrote or reordered the record
while keeping its length, the pass and the app refuse that return, apply
nothing and say so. Run the store check (`python -m tracker.store "<the app folder>" check "<clients root>"`)
to see it named, then rebuild **that return only**, with
`python -m tracker.store "<the app folder>" rebuild "<clients root>" --engagement "<the return's folder>"`
- without `--engagement` it rebuilds every return, and the next pass
re-reads every document in the firm. The record itself is the truth and
nothing is lost.

**The clients root is a folder of clients, and only that.** The app refuses
the system drive's root (`C:\`), the app's own folder, the folder holding its
settings and store, and any folder that holds one of them, and says which
(decision 137): a root like that would be walked every two hours and written
into. Another drive's root is fine — a drive letter mapped to the clients
share is a real root.

**The clients root must be on a Shared Drive, not in My Drive.** In My Drive
a client owns what they upload: they could delete a document the tracker has
already filed, and the rule that originals are never altered cannot hold on
a folder somebody outside the firm can empty. On a Shared Drive the firm owns
every file in it, whoever uploaded it.

### The layout: a household, a year, a return

A client folder is a **household** (decision 125). Inside it is one folder
per tax year, and inside that one folder per **return**. Two trees sit under
the clients root, and the difference between them is the whole point:

```
"G:\Shared drives\JPA Clients"
├── Clients\                      ← the only tree a client is ever shared
│   └── Park Family\
│       ├── Drop files here\      ← the household's one permanent inbox
│       ├── 2026\                 ← their originals for this year
│       └── 2025\
└── J Park & Associates\          ← never shared with anyone outside the firm
    └── Park Family\
        ├── _ledger.jsonl         ← the household's own record
        └── 2026\
            ├── 1040 - John & Maria Park\
            └── 1120S - Park Landscaping LLC\
```

- A return folder is named **form first** — `1040 - John & Maria Park` — and
  keeps that name every year. It is what the app and the rest of these pages
  call the **engagement**.
- A household has **one** inbox, `Drop files here`, for all of its returns and
  for every year. A pass runs a whole household at a time: it judges each
  dropped file against every return of the open year and files it where
  exactly one request accepts it.
- An original moves **once** — out of `Drop files here` into the year's folder
  the client can see — and never again.
- The inbox holds one file of ours, `_README.txt`, which the tracker writes
  and nobody edits. Step 2 of it reads *"We will examine and place all
  documents into the current year's folder."*; step 3 reads *"Please keep
  sending the documents listed under REQUESTED, NOT YET RECEIVED."*; step 4 begins *"Original
  PDFs or Excel files are preferred. A clear photo from your phone is fine
  too, just get the whole page in the frame."* After **REQUESTED, NOT YET RECEIVED**
  (only the active requests nothing has been received for yet; a return
  with nothing left has no heading there, and an empty list reads
  *Nothing at the moment.*) comes **WHAT WE HAVE RECEIVED**,
  once something has arrived (decision 130): each document confirmed into
  a request, by that request's name, under its return, with the day it
  came in; and under **Under Review**, how many documents a person is
  looking at, counted by the day they arrived and never named. It never
  says whether a request is complete or where anything was filed, and
  never shows the client's own file names. It is rewritten at the end of
  every pass and straight after each click in the app that files, unfiles,
  sets aside, hands over or puts back a document, or creates or edits a
  return - and only when its words changed.
- Type the root with the quotes: the firm's own name has an ampersand in it,
  and `G:\Shared drives\JPA Clients\J Park & Associates` without quotes is two
  commands to a Windows shell. `"G:\Shared drives\JPA Clients"` is safe.

**Folders the tracker leaves alone.** The tracker reads that layout and no
other. Anything else under the root — a stray folder beside the two trees, a
household with no record, a folder where a year should be that is not four
digits, a year folder with no return in it, a folder from before September
2026 holding a `_manifest.xlsx`, a folder Windows will not let it list — is
**listed with one sentence saying why, and left alone**. Nothing is renamed,
nothing is moved, nothing is deleted. The list is at the bottom of the status
page, in the app under the engagement picker, and at the end of every command
line pass, under **Folders the tracker leaves alone**. If a client's folder
appears there, that is the tracker telling you it is not set up — read the
sentence and set it up in the app.

The app will not adopt one either. Creating a household whose folder is
already there without a record is refused before anything is written, in
these words (decision 137): *"A folder named '<name>' is already there and
the tracker did not make it. Choose another name, or move that folder aside
first. Nothing was changed."* And a create that fails part way removes only
the folders it made itself — never one it found.

There is no migration and no importer: a folder from an older shape is set up
again in the app, and the old one is left where it is until somebody deletes
it by hand.

**Two files sit in an engagement folder, and only one of them is yours to
open:**

| File | What to do with it |
|---|---|
| **Status Report.html** | **Open this one.** Double-click it; it opens in the browser. Regenerated by every pass, so editing it is impossible — there is nothing in it to edit. |
| `_ledger.jsonl` | Never open it. It is the machine's own record of what it decided — the audit trail of every document, every status, and every edit you make to the request list. |

The request list is edited in the app — **Edit Request List** — and nowhere
else. The twelve columns you edit there are Identifier, Document, Period,
Expected Count, Allowed Extensions, Min Size KB, Required Keywords, Any
Keywords, Date Pattern, Manual Override, Override Reason and Named; **each request's status,
Received Date, File Count and Validation Notes are on the Status Report**,
not in the editor. The engagement's details — client, share link, due
date, sender, firm, reminders, active — and the **people** the return is
for are edited in the same place.

**A folder from before September 2026** may still hold a `_manifest.xlsx`.
The tracker no longer reads it: it is one of the folders left alone, listed
with its own sentence rather than treated as an engagement, and the return is
set up again in the app (New Engagement, then type or paste the rows). The
workbook may be deleted once that is done.

The status report is one web page with everything about that engagement on
it: a **Summary**, a **Requests** section (the list with each row's status
and any keyword somebody taught it), an **Index** section (every original
and where it went) and a **Needs Review** section (what is waiting for a
person, and under each file the shortlist of requests it might belong to —
the same suggestions the app shows). Click a column heading to sort by it.
**The Index section is where you look up what happened to a document** —
it is what the index workbook used to be for, and it is easier to read.
The page holds nothing of its own — every value on it is the ledger's — so
**anything anybody managed to change on it is gone at the next pass**, and
a copy somebody is reading is simply left alone until the next pass
replaces it. The Summary says which ledger it was drawn from, and the app
prints the answer beside the engagement's name: *current* (it still
describes this engagement), *behind* (somebody has edited the request list,
or the tool has decided something, since it was drawn) or *unknown* (there
is none yet, or it cannot be read). The app's **Open Status Report** button
opens it, and `python -m tracker.view "<engagement folder>"` redraws it and
prints the state. The request list is edited in the app, not on the page.

`_ledger.jsonl` is that ledger: a line the tool appends every time it
decides something about a document, records a status, or saves a change you
made to the request list, kept in the engagement's folder so what the
system did travels with the engagement. **Nobody edits it.**
Everything the app, the Status Report and the drafts say comes from it.
Leave it where it is; if you are ever asked what one engagement's history
looks like, `python -m tracker.ledger "<engagement folder>"` prints the
count and the dates without opening anything.

One check exists if you ever suspect things have parted company, and it
changes nothing:

- `python -m tracker.store "<the app folder>" check "<clients root>"` — the
  database against the ledgers, document by document, status by status and
  rule by rule. The first argument is the folder the app runs from, where
  the settings file and the database sit; the settings file's own path, or
  the database file's, is taken the same way. Anything else — a mistyped
  folder, a file that is neither — is refused, so a typo can never create
  an empty database somewhere and check it against the ledgers. If it ever disagrees, `rebuild` in place of `check` builds
  the database again from the ledgers; nothing is lost either way, because
  the ledgers are what it is made of. A `tracker.db` from before decision
  107 is refused by name; delete it and run `rebuild` — nothing is lost,
  the ledgers are what it is made of, and the first pass after it reads
  every document once to fill the verdict cache the database also keeps.
- **Once, when decision 137 lands.** Its database is a new version
  (`user_version` 12), so the `tracker.db` already on the machine is refused
  by name. Delete it and run `rebuild` as above. The rebuild itself takes
  minutes; what takes longer is the **first pass after it**, which reads
  and OCRs every document again to refill the verdict cache - on a full
  season that can run past the scheduler's two-hour limit. A pass the
  scheduler stops keeps what it read for the returns it finished, and the
  next pass goes on from there. So
  do it outside office hours, and if one return matters first, rebuild it
  alone ahead of the rest with `--engagement "<the return's folder>"`. It
  happens once; later passes read only what is new.

There used to be a second one, a comparison flag on the ledger's own
statuses against the request list's. There is nothing left for it to
compare: the request list holds no status.

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
The app's **Install Schedule** button registers it for this app's own
settings: the job names the settings folder, never the clients root, and
reads the root from `settings.json` there at every run (decision 131). So
changing the root in the app is all it takes for the schedule to follow.
A job installed by a version before decision 131 carries the root it was
installed with: **press Install Schedule once after upgrading**, and never
again for a move.

**It only runs while someone is logged on.** The task is registered to run
as the logged-on person, not as a background service, so the designated
machine has to stay signed in. A Windows Update reboot in March that leaves
the machine at the sign-in screen stops every pass until someone logs in;
the task is set to start when it can, so the missed pass runs as soon as
they do. The owner's call (2026-09-23, decision 139): the machine does not
sign itself in. Nobody at the keyboard should find a machine already signed
in to every client's files, so whoever arrives signs in. Windows Update's
active hours are set to cover office hours so an update does not restart
it mid-day. Both are set on the machine; nothing in the tool decides them.
A draft day the machine spent switched off is not lost either: drafting is
weekly, not only on the day, so the next pass drafts instead of skipping
the week.

A pass still going at `tracker.locking.RUN_TIME_LIMIT_SECONDS` is stopped
by Task Scheduler — the task carries that as
`tracker.scheduling.EXECUTION_TIME_LIMIT` — and the next repeat carries on
from where it got to.

**Written exception, 2026-09-18.** The firm's Command Center rule is that
automations do not schedule themselves; the owner signed off an exception
for this tool alone, because it drafts and never sends, and because sorted
documents are no use arriving a day late. The exception is declared rather
than hidden: `automation.manifest.json` carries it in the dated
`safety.scheduled_exception` field the Command Center's contract gained the
same day, and the tool's card there prints that sentence.

### If the clients root moves

A Shared Drive remounted at another letter, a parent folder renamed, the
tree copied under an archive folder: every one of these leaves the old
path naming nothing, so the app asks where the clients live and the next
scheduled pass stops with *Clients folder problem*. Nothing is lost - the
record keys every return by its path below the root - and the whole
answer is to **set the root again in the app** (or
`python -m tracker.settings <folder>`). The schedule follows by itself;
it reads the root from the settings file at every run.

A longer root leaves every return less room: Windows opens a path of
`tracker.layout.MAX_PATH_LENGTH` characters at most, and a working copy
deep in a return with a long household name, a long return name and a
long document label can pass it. So the reply to setting the root lists,
under *Returns short of room under this root*, every return the new root
leaves short, with the number. Nothing is refused - the firm's data is
where it is - and the pass copes: it cuts the document part of a working
copy's name to fit, keeping the request's identifier, the period, the
`(2)` of a series and the extension, and records the name it wrote. A
reader's limit counts too: Excel opens a workbook from a path of at most
218 characters (Microsoft's own figure), so spreadsheet copies - `.xlsx`,
`.xlsm`, `.xls`, `.csv` - are cut to fit 218 (`tracker.layout.OPEN_LIMITS`,
the owner's ruling of 2026-09-23); creation still refuses only past
Windows's own limit.

A person has exactly three levers, and every sentence the tracker says
about room names one of them: **a shorter clients root** (a drive letter
over a profile path, the Shared Drive's own folder over one deep inside
it), **a shorter label** in the editor for the request (every copy filed
from then on is shorter; the folder keeps its name), and **a shorter
return name** at the next rollover. Nothing in the tracker ever renames a
folder or a filed copy to make room.

### Sharing a household with a client

The tracker never makes, checks or changes a share. Two grants, made once by
a person in Google Drive, on the firm's Shared Drive:

1. Share the household folder under `Clients` (for example `Clients\Park
   Family`) with the client as **Viewer**. Every year folder under it is then
   view-only for the client through the parent — they can read what they sent
   and nothing can be deleted or changed from their side.
2. Share `Drop files here` inside it with the client as **Contributor**. They
   can add files there and cannot move, delete or share them. On a Shared
   Drive the firm owns a file the moment it lands, which is why rule 2 holds:
   the pass moves each original out of the inbox into the year's folder, and
   only the firm can move it again.
3. Paste the inbox's link into the household's *Inbox link* in the app and
   press **Mark as shared**. The date is recorded as the firm's word; the
   letters carry the link.

The app asks for all three in those words — once, when a household's first
return is made, and on the household's card until the third step is done. It
records only that a person said so: Drive for desktop exposes no permission
to a program, so the tracker cannot see a share and does not pretend to.
Nothing about filing, scanning or drafting waits on it.

Nothing is ever re-shared. A new year is a new folder under the same
household, view-only through the same grant; Roll Forward changes no
permission. A household's members list in the app is what the firm typed, not
what Drive says: keep the two the same by hand.

**Before the first real client (once, by an admin):** confirm in the Shared
Drive's settings that a folder inside it can be shared with someone outside
the firm as **Viewer**, and that a folder inside it can be shared with
someone outside the firm as **Contributor**. If either is off, the client
cannot be given the inbox and nothing else in this section works. Then check
with a test account outside the firm: upload from outside, try to delete from
outside (it must be refused), and let a pass move the file.

### Households that feed each other

A household's drop folder feeds that household's own returns. Sometimes it
has to feed one somewhere else, and a person extends it, by name, in the
household's editor — *Also feeds*. Two shapes come up every season:

- **A co-owned business.** The father's household holds his 1040. The LLC
  he owns with his partner is a household of its own, shared to both
  co-owners, with its own inbox and its own returns. Each owner's drop
  folder feeds the LLC's return line, so either of them can drop the trial
  balance into the folder they already use.
- **An adult daughter's return the father relays.** Her return lives in her
  own household, shared to her and to nobody else. The father's drop folder
  feeds it, so a W-2 he sends on her behalf files to her return — and the
  document then rests under *her* folder, which he cannot see.

The sub-rule, in the owner's words: **a drop folder may feed a return whose
folder the dropper cannot see. Dropping does not require seeing.** That is
the point of the arrangement, and it is also why a document handed to a fed
return **moves** into that household's year folder: the dropper stops seeing
it unless they are shared there too.

What the tracker does and does not do:

- The document is judged against every return the drop folder feeds, its own
  and the fed ones together: the request lists accept, the name on the page
  confirms or vetoes, and exactly one return is left or the document waits
  for a person **in the household it was dropped in**. Where a document
  has come before, the records are asked for its bytes with the household's
  own returns first and the fed ones after: the record closest to the drop
  decides.
- A feed is a **return line**, not a return: the household and the return's
  name, the name it keeps every year. Roll Forward carries nothing about
  feeds, and a line the other household has retired is said on the card
  rather than quietly feeding nothing.
- Nothing is ever inferred. The tracker never looks at two households and
  suggests that one feeds the other, any more than it decides who belongs
  in a household. Both are a person's assembly.
- **Ownership changes are a person's too.** When somebody buys in or sells
  out, a person changes the Drive grant, changes the members in the app and
  extends or trims the feed. The tracker records the change and does nothing
  else about it — it cannot see a share and does not pretend to.

Every feed a person adds is warned about, every time: anyone with access to
that drop folder may drop for that return, and its documents will rest under
the folder it lives in, shared with whoever that household's card says.
Adding a return to a household is warned about too: everyone with access to
the folder will see that return's documents.

A parked document can be filed under a request of any return the drop folder
feeds — *File under another return*, in the queue. The original moves where it
must rest, the working copy is made in that return's request folder, the copy
waiting here goes, and the row here is released: nothing about it stays in
this household; the journal says which return took it; if it went to the
wrong return, unfile it *there*.

If the machine dies in the middle of one of these, each household's next pass
finishes its own half; the queue of a return with a half-finished decision
refuses actions until that pass has run, as it does for any interrupted move.

### Rolling a household into the next year

Roll Forward in the app takes the **household**, not one return: it shows the
open year's returns with every one ticked, and rolls each ticked return into
the next year — its list carried from last year, its greeting and its inbox
link refilled from the household, its own folder made under the new year.

A return left unticked is **retired for that year**: set inactive, and no
longer chased. That is deliberate — it is how the household ends up with
exactly one open year again, which is what lets the pass go on sorting one
inbox. Tick it later and roll it on its own if that changes.

One return's refusal (a folder of that name already there, a path too long)
is printed and undoes none of the others; nothing under `Clients\` changes
but the new year's folder.

On the command line the same two forms live in one command, told apart by
what you point it at:

```
python -m tracker.rollover "<clients root>\J Park & Associates\Park Family" --year 2027 --all
python -m tracker.rollover "<clients root>\J Park & Associates\Park Family" --year 2027 --only "1040 - John Park"
python -m tracker.rollover "<a return folder>" --year 2027 --form 1040
```

## 2. Every morning

1. **Read what the last pass did.** The status page every pass writes into
   the clients root (`tracker.runner.STATUS_PAGE_FILENAME`) is the one-screen
   version — which engagements ran, which need a person, which failed, and
   every parked file across the practice, newest first; the app's
   **Open Status** button opens it. The run log
   (`tracker.runner.LOG_FILENAME`), in the clients root beside the
   engagement folders, has the same, pass by pass, including passes made from
   the app's button. For one client, **open the Status Report** in that
   engagement's folder — the pass you just read about regenerated it, so it
   is that engagement's list, index and review queue as of this morning, and
   the app says beside the engagement's name whether it is still current.

   What the page says about room (decision 131, and *If the clients root
   moves* in §1). A return merely **short of room** is not warned at all:
   it is sorted as usual and its copies' names are cut to fit, and the
   figure - *N characters short of the room its working copies need* - is
   shown as information on the return's page in the app and in the reply
   to setting the root, never in the Warnings column (a warning on every
   pass would be a warning nobody reads). A **Warnings** line *N
   request(s) have no room for a working copy* does need a person: a
   document for those requests parks in the review folder with the reason
   *the working copy's path would be N characters at its shortest, past
   the N characters a .pdf copy may have* (the sentence names the other
   return when the request is in a return this drop folder feeds):
   shorten the root or that request's label, then file it. A review
   copy's row that ends *longer than a spreadsheet program may open* is
   there and whole; open it from a shorter folder. A household **skipped**
   with *no room under ... for even a review copy* was not touched at all
   - nothing read, nothing moved, nothing scanned - and will not be until
   the clients root is shorter; move the root and set it again in the app.
   A scheduled run that ends red with *the scheduled job still names an
   old clients root* is the job installed before this version: open the
   app and press *Install Schedule* once.
2. **Clear the review folder.** Anything the rules could not be sure of is
   parked in the review folder (`tracker.scaffold.REVIEW_DIR_NAME`) with a
   reason. In the app, pick the engagement, pick the request the document
   belongs to and press **File it**: the filer moves it, renames it, writes
   the index row, learns the keyword and re-scans. A document nobody ever
   asked for is closed with **Not requested** rather than filed under a
   request that does not want it; the draft stops warning about it, and
   **File it anyway** is the undo. A document filed in the wrong place is
   sent back to the review folder with **Unfile**, on the record, and filed
   again from there. The keyword you typed when you filed stays with the
   request — unfiling never takes one back — so if a word turns out to be
   on documents that request does not want, open **Edit Request List** and
   press the button beside that word: it is taken back for this engagement
   on the record, and the request is re-scanned there and then, which may
   put a copy that passed only on that word back into Failed Validation.

   The card does not leave you to find the request yourself. Each parked
   file carries a shortlist: up to three requests, best first, at the head
   of its picker under *Suggested*, with every other request below them
   under *Other requests*, and under the row the one line that says why each
   is on the list — which of that request's keywords the document said,
   where it said it, and the rule that refused it. It is a shortlist and
   never a filing: nothing is moved, no status changes and no lock is taken
   until you press **File it**, the picker is still the whole list so you
   may file to anything on it, and a request the firm set aside as Not
   Applicable is never offered — it is named in one line under the
   shortlist ("C01 is Not Applicable in TY2025 - clear it in the editor to
   file here"), so you decide whether this document changes that call. A file whose evidence says nothing gets no suggestion at all
   rather than a guess — where the card says so, read the document. The
   same answer is on the command line, without the app:
   `python -m tracker.review` against the engagement folder prints it.

   **Until OCR is installed on this machine, every scanned PDF and every
   photo is in that queue.** Nothing is filed on a file name (owner,
   2026-09-18): a client called the file "W2 2025.pdf", the form did not,
   and a document nobody here can read is filed by nobody. What the name
   says is not thrown away — it is the bottom line of the shortlist, *the
   file name says W-2* — but it is a place to start reading, never the
   answer. Install Tesseract (§6, step 5) and those scans and photos are
   read and filed like any other document.
3. **A working copy that has moved is yours, and it is the first card on
   the screen.** Every pass proves each working copy against the
   fingerprint its own index row carries (decision 109). A copy somebody
   dragged out of its request folder makes that row
   `tracker.filer.FILE_MOVED`, and it is said on the run and on the
   practice page the same morning: the request reads Missing until it is
   back, and the client is never asked for it. The app lists every such
   copy above the review queue with its home, where its bytes are now, and
   three answers — **Put it back**, **Keep it here** (only when the copy
   sits in a request's folder) and **Send to review** — because which one
   you meant is never guessed (decision 110). Answer them before Saturday:
   the draft holds nothing up for a mislaid copy, and a request that reads
   Missing all week is one nobody is chasing. Nothing you press there
   overwrites a file or deletes one — a different document already at home
   is left where it is and this one's copy goes to review instead, and a
   left-over copy is named every pass until you remove it yourself. §4 has
   the row and what each answer means.
4. **A locked engagement.** The app shows a notice when a run holds one. If
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
5. **A file still waiting in a drop folder.** A file the sort could not take
   — it failed, it is still arriving, its name cannot be handled, or the
   household has two open years — is named on the run every pass, and from
   decision 133 it also holds the household's reminders (§3, *the reminder
   waits for the sort*). Deal with it before Saturday and nothing waits.

## 3. Every Saturday

The pass writes each engagement's chase email into its folder as
`tracker.reminder.DRAFT_FILENAME`. If you have already edited that file,
the run never writes over your edits — it leaves them and puts the newer
draft beside them under `tracker.reminder.NEW_DRAFT_FILENAME`, so an edited
draft and a fresh one are never the same file. A regenerated draft opens
with what changed since the last one — which requests are now asked for
that were not, and which no longer are — above the line you paste from, so
you reconcile in seconds rather than comparing two emails by eye.

**Read it in the app.** The engagement's **Reminder** card shows the same
draft: what the record says about it (the day and the stage of the last one,
or that it has not been drafted yet), the subject line, and the letter as
the client will read it. **Copy for Outlook** puts that letter on the
clipboard twice over — once as a formatted body Outlook keeps, once as plain
text — so you paste it straight into the message and type the subject from
the line above it. **Approve** makes the text on screen this week's draft:
it is written into the file, the approval goes on the record, any other
draft sitting beside it is renamed out of the way (never deleted), and
nothing writes over it afterwards — not the scheduled pass, and not
`python -m tracker.reminder <engagement_dir> --write`; each of them lands
its fresh draft beside it exactly as it does beside one you edited by
hand. Next week's pass writes next week's draft as before. **Open the
draft file** is still there for anyone who would rather work in Notepad,
and an edited file is shown as it stands with a note saying so — the card
shows the letter alone, so the staff-side lines under the dashed rule at
the foot of the file are never on the clipboard.

Open it, read it, edit it, paste it into Gmail and send it. Nothing in the
tool sends anything, ever — the card has no send button, and there is no
mail or network code anywhere in the reminder path.

**The letter gets firmer as the date gets closer.** There are four stages,
and which one you get is decided by how far the draft day is from the
engagement's **Due Date** — the date you are asking the client to send
things by, which is one of the engagement's details and yours to change.
The draft's header says which stage it is on, above the fingerprint line,
so you can see it without reading the letter; the practice page's Drafted
column says it too, and the app's Reminder card shows all four as a toggle
with the one in force pressed. **Moving that toggle changes the words and
nothing else** — the same requests are asked for at every stage, the letter
is regenerated on screen, and the file on disk is not touched until you
approve. The colour climbs with the rung: nothing at stage 1, the target
date at stage 2, the whole deadline paragraph at stage 3, and at stage 4
the subject, the list and the deadline paragraph with the consequences
sentence in bold.

| Stage | When | What the letter does |
|---|---|---|
| 1 | more than three weeks before the Due Date | a heads-up, with no deadline sentence at all |
| 2 | three weeks to ten days before | a check-in that names the Due Date as the firm's target |
| 3 | the last ten days | a firm request, naming the Due Date and the **Filing Deadline** beside it, with its own subject line |
| 4 | the Due Date and after it | a final notice: the consequences sentence, the firm's phone number, and its own subject line |

Two details drive it, and both are edited in the app. The **Due Date** is
the firm's ask-by target. The **Filing Deadline** is the statutory date the
return has to be filed by: a new engagement gets it from its form (weekends
shifted forward the way the IRS shifts them) and the Due Date five days
before that, and a holiday is yours to correct. A year rolled forward gets
both the same way, whether it was rolled with **Roll Forward** in the app
or with `python -m tracker.rollover` on the command line: the new year's
Due Date and Filing Deadline come from the form's table, and you clear or
change them in the editor like any other detail. Leave the Filing Deadline
blank and the letter never mentions it. Leave the Due Date blank and every
letter is stage 1, because there is no date to measure from and nothing to
tell the client. The firm's phone number lives in the app's settings beside
the firm's name, and stage 4 leaves the sentence out when it is blank.

To see what a client will get next week, ask for it today:
`python -m tracker.reminder <engagement_dir> --stage 3` writes the same
requests at that stage, and `--today 2026-03-01` writes the letter that day
would have produced. Neither changes who is asked: the stage changes the
words, and the rows are whatever the last scan found.

**A reminder can be held.** A request whose file arrived and failed
validation with no firm-side reason is nobody's yet: a copy the tool filed
cannot fail its own rules, so this is a rule edited after filing, a copy
dragged into the folder by hand, or a copy replaced — and whether the client
resends or we fix it here is your call, not the tool's. One such request
holds that client's whole reminder: no draft is written, the run's own
unedited draft from an earlier week is removed (one you edited is left
exactly as it is), and the hold is said in `runs.log`, in the Drafted column
of the practice page and in the app, with the requests named. Clear the
question — unfile the copy, fix the rule, or set the row's override — and
the next pass writes the whole reminder, correct, once. The manual draft
(`python -m tracker.reminder <engagement_dir> --write`) and `--reminders
always` are held by the same question; nothing clears it but you. So is the
app's Reminder card: while a reminder is held it shows the hold, the
requests holding it and the stage the day would write at, and nothing that
reads like something to send — no letter, no clipboard, no approval.

**And so does a file the client sent that we could not use at all.** A
locked PDF, an empty upload, a file type nothing accepts: that drop never
reaches a request — it parks in `00 - Needs Review` and the request stays
**Missing** — so the reminder would ask the client for a document they
know they sent. When the parked file looks like a request that is still
outstanding, that request holds the reminder the same way, with the parked
file's own problem named. Work it in the app: file it, mark it not
requested, or ask the client for a copy we can open. A parked file that
looks like nothing holds nothing, and one nobody here could read is ours to
fix, not the client's to resend.

**And the reminder waits for the sort** (decision 133). The pass drafts after
it sorts the household's `Drop files here`, but the sort does not always take
everything: a household with two open years does not read its inbox at all,
a file can fail to sort, a transfer can still be arriving, a name can be one
the machine cannot handle, and a file can land after the sort. While the
household's own inbox holds any such file, every return of that household is
held the same whole way, because the letter cannot know which request the
file answers. The practice page's Drafted column says `held (N)`, `runs.log`
says *"held - N file(s) the client sent are still waiting in Drop files here
and have not been sorted yet"*, and the app's card says **"Reminder held: N
file(s) still waiting to be sorted"**. On a Saturday that means: press **Sort &
Scan** — Run now — (or wait for the next pass — the schedule runs every two hours, and the
pass that sorts the inbox drafts the reminder that same day), or deal with the
file the run log names — retire a year in the editor, rename a name the
machine cannot handle, or remove a transfer that never finished. A file that
can never be sorted keeps the letter held, and says so every pass, until you
deal with it: that is on purpose, because the alternative is a letter asking
the client for what they sent. The README the firm writes into the inbox and
sync junk never hold anything. Only the household's own inbox counts: a drop
folder in another household that also feeds a return (§1, *Households that
feed each other*) does not hold that return's letter.

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
| `filer.DUPLICATE` | The same bytes are already in the record, and the reason says what the row holding them is: `filer.DUPLICATE_OF_FILED` says "already filed as" of a filed document, `filer.DUPLICATE_OF_PARKED` says "parked as" of one still waiting for you, `filer.DUPLICATE_OF_MOVED` names the copy of a row whose file is not where the record put it, and `filer.DUPLICATE_OF_UNCOPIED` says plainly that the row holding those bytes never got a working copy. No second copy is made. | Nothing. The original is kept, and the row holding the bytes is where the work is. |
| `filer.RESENT_AFTER_SET_ASIDE` | The client sent again a document somebody had closed with **Not requested**. It was routed afresh: filed if exactly one request accepts it now, otherwise parked again with a copy of its own. The reason quotes the earlier decision whole — the date and the note whoever closed it typed. | Read what was decided last time, then decide again: file it, or close it again. The copy set aside earlier stays where it is. |
| `filer.NEEDS_REVIEW` | Parked for a person; the reason says which of the rows below. | Work it in the app. |
| `filer.ASSIGNED_BY_PERSON` | Someone filed it with **File it**, on the date shown, and what the rules had said is kept after it. | Nothing. This is the audit trail. |
| `router.UNMATCHED` | No request on this manifest accepted it. | File it to the right request, or add the request. |
| `router.AMBIGUOUS` | More than one request accepted it. | Pick the right one. |
| `router.CONTESTED_PREFIX` | It looks like a named request but failed one of that request's own rules — last year's W-2, say. | Read the named rule. Usually it is the wrong year or the wrong client. |
| `router.OCR_ONLY` | A scan or a photo with no text layer; OCR read it, but only loosely enough to guess. | Confirm what it is and file it. |
| `reasons.NO_READABLE_TEXT` | Nothing in the file could be read at all — a scan or a photo with no OCR on this machine, an image-only PDF, an empty sheet. Nothing was matched against anything, so this is not "matched no request". | Open it and file it, or install OCR (§6, step 5). The shortlist shows what its **file name** suggests; the document decides. |
| `reasons.UNREADABLE_IMAGE` | A photo arrived that would not open — a half-finished upload, most often. | Ask the client for it again; the reminder does. |
| `reasons.HEIC_NOT_SUPPORTED` | An iPhone photo arrived and this machine's HEIC reader is missing. Ours, never the client's: they sent an ordinary photo. | Re-install from `requirements.txt` (`pillow-heif`). Until then, open the photo and file it by hand. |
| `reasons.ISSUER_NOT_NAMED` | The request list asks for this document one row per issuer (§8) and this one names none of them — a K-1 from a partnership nobody listed. | File it to the right row, or add a row for that issuer (§8) and it files itself next pass. |
| `reasons.NAME_NOT_ON_PAGE` | A request that asks for a **named** document accepted it, and the page names nobody on this return's people list (§10). | Open the page. If it does name them in a spelling the list has not got, file it and **teach the spelling** on the same card; if it is somebody else's, file it by hand on the return it belongs to. |
| `reasons.NAMES_ANOTHER_RETURN` | The page names somebody who is on another return of this household, and nobody on this one. The sentence says who, and which return. | Switch to that return and file it there. Nothing was moved. |
| `reasons.NO_PEOPLE_ON_FILE` | This return lists nobody yet, so nothing can confirm a named request. | Open **Edit Request List** and add the return's people (§10). Everything parked for this reason files itself on the next pass. |
| `reasons.SEVERAL_FORMS_UNSORTED` | One page prints two or more forms' own names (a stack scanned in one pass) and they will not sort one to a request: a form no row asks for, two rows wanting one form, or a row that accepted the page on a phrase rather than a form number. When they do sort, the page files a copy under each request and the row's Reason says so (`reasons.NAMES_SEVERAL_FORMS`). | Split the scan, or file the whole page to the one request that matters and note the rest. |
| `reasons.TOO_LARGE` | The file is larger than the tracker will read (`validators.MAX_READ_MB`) — a video, a disk image, a whole mailbox, or a genuinely enormous scan. It was not opened: no text, no OCR. It is still counted and kept like any other original. | Open it yourself and file it, or ask the client what it was meant to be. |
| `reasons.READING_STOPPED` | The reader gave up on this file at the safety stop — a minute a page, ten minutes a file (decision 137). Something in it made reading far slower than any real document, or the machine was very busy at the time; it will not be tried again until the file changes. The stop covers the OCR reading; a file whose text layer or single page takes longer still is not stopped by it (decision 150 will). | Open it and file it yourself. |
| `reasons.UNNAMED_ACROSS_HOUSEHOLDS` | This household's drop folder feeds a return in another household, and that return would have taken this document on its keywords alone — but the page names nobody, so it was not moved into a folder other people can open. It waits here (decision 137). The Evidence names the return and the request that wanted it, as `<return> / <request>`. The same holds for a document sent again that the other household already has. | Open it. If it is that return's, file it there with **File it**; if it is this household's, file it here. |
| `router.NO_REQUEST_ACCEPTS` | No request on this manifest takes that file type at all. | Usually a stray file. Otherwise widen the request's allowed types. |
| `router.PENDING` | A cloud placeholder, still copying down. | Nothing. The next pass picks it up. |

Beside the Reason sits the Evidence column, which says what the decision
was actually made on, per candidate request: which of that request's own
keywords the document said, and where it said them — in the title, in a
page footer, on the first page, or deep inside. A cell reading
`A01: W-2@title:1 required` says "the keyword W-2, in the title, on page 1,
off A01's required list"; the number after the place is the page, and a
keyword found in the file's *name* has no page. A row parked for you
carries it as much as a filed one, and it is usually the fastest way to see
why the rules did or did not reach the answer you would have. The words in
it are ours — the keywords on the request list, the period asked for, the
file's own name — never a word out of the client's document.

Three more appear as warnings on the run rather than as index rows:

| The run warns | In plain words | What you do |
|---|---|---|
| `filer.REPLACED_IN_PBC` | The client replaced an original we had already filed; the working copy was made from the earlier file. | Look at both, and re-file if the new one differs. |
| `filer.UNTIED_IN_PBC` | A row was recorded without its bytes and its working copy no longer matches the original. | Look at it. Nothing is adopted automatically, by design. |
| `filer.UNRECORDED_COPY` | A file is sitting in a request folder (or in the review folder) that nothing on the record put there and no row's bytes account for. It **is** counted for that request — what a request has is what its folder holds — but nobody can say where it came from. | Open the app and file it, or take it out and drop it in the client's folder so the next pass sorts and records it. Said every pass until you do. |

And since decision 109 the Decision column has a fifth value, for a working
copy that is not where the record put it:

| The index says | In plain words | What you do |
|---|---|---|
| `filer.FILE_MOVED` | Every pass proves each working copy against the fingerprint its own row carries. This row's copy is not in the folder the record filed it into, and its bytes turned up somewhere else under `Prepared/` — somebody dragged it. The Reason names where it belongs and where it is now; the Prepared Location column still says where it *belongs*. Nothing was moved to find that out and nothing is moved because of it. | Open the app: put it back where it belongs, keep it where it is, or send it to review (decision 110's three buttons, coming). Until then, drag it back yourself and the next pass files it again. The request it left reads Missing meanwhile, and the client is never asked for it. |

## 5. What the Validation Notes mean

**Where to read them:** on the engagement's **Status Report**, in the
Requests section, beside each row's status — and in the app. They used to
be a column of the request list; since September 2026 the list holds only
the twelve columns you edit, and every note the machine writes is in the
record and on the page.

Some rows failed because of something the client did. Some failed because
of something on our side. `tracker/reasons.py` holds which is which, and
the drafted email uses it: a firm-side row is reported to us and never put
to the client, so nobody asks a client to resend a file we simply have not
read yet.

**Ours to deal with** (never in the client's email):
`reasons.PENDING_SYNC`, `reasons.VANISHED`, `reasons.NO_TEXT_LAYER`,
`reasons.NO_TEXT_AFTER_OCR`, `reasons.OCR_FAILED`,
`reasons.HEIC_NOT_SUPPORTED`, `reasons.TOO_LARGE`, `reasons.READING_STOPPED`,
`reasons.UNNAMED_ACROSS_HOUSEHOLDS`,
`reasons.UNCHECKABLE_TYPE`, `reasons.NO_REQUEST_FOLDER`,
`reasons.FILE_MOVED`, `reasons.COPY_CHANGED`,
`reasons.INTERRUPTED_MOVE`, `reasons.INTERRUPTED_MOVE_LOST`. These mean the
document may be perfectly fine and no person here has read it yet — or, for
`reasons.NO_REQUEST_FOLDER`, that the request has no folder and the next
pass makes it. The last two are decision 109's, and they are ours by
definition: the client sent the document and somebody here moved the copy
or put another file in its place.

- `reasons.FILE_MOVED` — this request's working copy is not in its folder
  any more and the record has found it elsewhere under `Prepared/`. The
  note names where it belongs and where it is; §4 is the row it comes
  from. The request reads Missing until the copy is back.
- `reasons.COPY_CHANGED` — the file in the request's folder is not the one
  the record filed there. The status is still whatever the files earn, so a
  replacement that passes the rules leaves the row Received and one that
  does not is an ordinary regression; either way open it, because nothing
  on the record says what that file is. It is on the practice page too, so
  you see it across every engagement at once.
- `reasons.INTERRUPTED_MOVE` — a step that was putting a working copy in
  this request's folder was interrupted (the machine went off, the power
  went out) and that place now holds a different file. Nothing there was
  touched, the document itself is parked for you in `00 - Needs Review`
  with a copy of its own, and the file that is sitting there is **not**
  counted, so the request reads Missing rather than Failed Validation for
  a document the client sent perfectly well. Open the app, file the parked
  copy, and take the leftover file out of the folder; it is named every
  pass until you do (decision 119).
- `reasons.INTERRUPTED_MOVE_LOST` — the same interrupted step, where
  neither the place it was taking the file from nor the place it was
  taking it to holds those bytes now. Nothing is guessed: the row is
  parked and the note says whether the client's own original is still in
  the client's folder for the year, which it nearly always is.

**The client's to fix** (translated into one plain sentence in the draft):
`reasons.PASSWORD_PROTECTED`, `reasons.GOOGLE_STUB`, `reasons.TOO_SMALL`,
`reasons.EXTENSION_NOT_ALLOWED`, `reasons.WRONG_DOCUMENT`,
`reasons.NO_EXPECTED_KEYWORD`, `reasons.WRONG_PERIOD`,
`reasons.NO_PAGES`, `reasons.UNREADABLE_PDF`,
`reasons.EXTRACTION_FAILED`.

A note on a `.csv`, `.tsv` or `.txt` may end with `reasons.TEXT_CUT`: only
the first part of a very long text file was read
(`validators.TEXT_READ_CAP_MB`), so "not found" means not found in that
part. Open the file before believing it.

Two reasons in that file are not validation notes at all:
`reasons.NO_READABLE_TEXT` and `reasons.ISSUER_NOT_NAMED` are the router's,
and they appear in the index's Reason column (§4) rather than against a
request. Both are ours: the client sent the right document either way.

**A row that was Received and is not any more** keeps its Received Date
and its note begins *was Received <date>;* followed by why it left: *files
changed* (a file went missing or changed under its name), or that the
Expected Count is now a number the files no longer reach (somebody asked
for more). The reason is the one from the pass the row left Received, and
stays: a later pass carries it rather than deciding again, so a row that
lost a file never reads as if somebody had raised its count. How far the
row has got now is said separately, as *1 of 3 expected files*.

The note itself is never pasted into an email. It names keywords, size
floors and our own folders, and a client should never see any of that.

## 6. If the designated machine dies, or you move to another one

About thirty minutes, and nothing is lost.

**Nothing to restore.** Every engagement's manifest, ledger, originals,
working copies and drafts are in the engagement folder, which syncs. Any
machine signed into the same Drive account has all of it already.

**What was only on that machine:** the settings file beside the app
(`tracker.settings.SETTINGS_FILENAME`), the database beside it
(`tracker.store.STORE_FILENAME`), the scheduled task, the app folder
itself, and the Tesseract OCR engine if it was installed. **The database
is not worth carrying over.** It is built from the ledgers in the
engagement folders, and the new machine builds its own on the first pass;
copying the old one would only be copying something it can make. The first
pass there reads every document once - the verdicts the old machine had
cached were in its database, not in the folders - and is slower for it,
never wrong. The same is true of the first pass after this version, on
whichever machine: it reads every working copy once to prove it against
the record (decision 109), and every pass after that reads none of them.

**If the machine died in the middle of a pass, nothing is half done for
long** (decision 119). Before any of it moves a file, a pass or a person's
click writes down what it is about to do - which file goes where, and the
fingerprint each end should have - so the next pass on that engagement
finishes it from the record rather than leaving it for somebody to notice:
a copy that was not made is made, a copy already in place is recorded, a
filing somebody pressed just before the lights went out is recorded as
theirs and dated the day they pressed it. Where the place a file was going
holds something else now, nothing there is touched: the document parks in
`00 - Needs Review` with a copy of its own and the note in §5 says so.
Until that pass has run, the app refuses the buttons on that engagement
with *a run was interrupted here; the next pass finishes it first* - press
**Run now** on it and they come back.

1. Install Google Drive for desktop on the new machine, sign in with the
   firm account, and wait for the clients folder to finish syncing. Do not
   start until it has.
2. Put the app on it: rebuild it from this repository (`Build App.bat`),
   or download the package from a `build.yml` run (the Actions tab, *Run
   workflow*). There is no separate backup of the app, and none is needed.
   The client files are on the Shared Drive, `settings.json` holds only the
   clients folder, the firm's name and its telephone number, all three typed
   again at step 3, and `tracker.db` rebuilds itself from the journals. Running from source needs Python and
   Node; the packaged build needs neither. Keep the folder's path short — a
   few levels deep at most, like the `C:\Tools\tax-tracker` the README's
   scheduling example uses: past the classic Windows path limit the packaged
   program silently loses its command line and answers every call with a
   usage error.
3. Start the app. It asks where the clients live on first launch — give it
   the same folder, the synced one — with the firm's name and telephone
   number beside it. This is the one place the root is set;
   if the new machine mounts it at a longer path, the reply lists every
   return that leaves short of room (§1, *If the clients root moves*).
4. Press **Install Schedule** - once. Since decision 131 the job names the
   app's settings folder and reads the clients root from it at every run,
   so a later change of root is made in the app alone.
5. Install the **Tesseract engine** (the UB Mannheim Windows installer),
   with the `eng` and `osd` language data — `osd` is ticked by default and
   is what turns a page the right way up before it is read. The reader
   packages themselves ship with the app; the engine is the one thing to
   install by hand. **Without it every scan with no text layer and every
   photo parks for a person** — neither is filed on what its file name
   says, because the client wrote that name and the form did not (owner,
   2026-09-18). Nothing breaks and nothing is lost: the originals are
   moved into the client's folder for the year as always, the shortlist on
   each parked file says which request its name points at, and installing
   Tesseract later means the next pass reads those scans and photos itself.
   Photos need nothing beyond this — a JPEG, a PNG, an iPhone's HEIC and a
   scanner's TIFF are all read by the same install.
6. Run one pass — **Sort & Scan** on a single engagement — and read the run
   log before trusting the schedule.

**Two machines must never both run it.** Before the new machine's first
pass, turn the old machine's scheduled task off, or keep that machine off
the clients folder entirely. Two machines on one clients root can each take
their own lock and each append to the same ledger at the same moment, and
that is the one way an original ends up filed with no record of how it got
there.

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

Two things a person will notice changed this season. A W-2 printed one copy
to the page — which is how the 2024 and 2025 revisions print, and how a
client's own copy usually arrives — is recognised now; it used to park with
"matched no request" because its only mention of its own number is the line
at the foot of the form. And the brokerage row (1040 E01) takes a workbook
as well as a PDF or a CSV, because a broker's realized gain/loss export is
sent as an `.xlsx` at least as often; a file that used to come back
"extension .xlsx not allowed" now files. The trust's 1099 row (1041 B01)
reads that export as the 1099-B it stands in for.

Three more the owner decided after the second corpus review. A state
return that arrives on its own — a California 540 or 100S or 568, a New
York IT-201 or IT-204 — files into the prior-year return row that has
always said "Federal **& State**", instead of parking as it used to. A
1040 engagement now has a row of its own for the 1099-NEC, the 1099-MISC,
the 1099-K and the 1099-G, so those stop landing in review. And the
depreciation schedule row the 1120 always had is in the 1120-S and the
partnership checklists too; a register of what was bought and sold, which
never says depreciation, still belongs to the fixed-asset row beside it.

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

## 8. K-1s by issuer

A client can be a partner in three partnerships and a shareholder in two
S corporations, and all five Schedule K-1s answer the one row `F01 -
Schedule K-1s Received`. One folder with five K-1s in it is a folder
nobody can work from, so the rule (the owner's, 2026-09-18) is **one row
per issuing entity**. The catalog cannot do this for you: which entities a
client is in is a fact about that client.

**Adding one.** In the app, **Edit Request List**, then **Add a request**,
and fill the same five cells as `F01` with these differences; then
**Save**.

| Column | What to put |
|---|---|
| Identifier | The next free one in F's block — `F02`, then `F03`. Leave `F01` where it is. |
| Document | `Schedule K-1 - ` and the entity, e.g. `Schedule K-1 - Ashford Holdings LP`. This becomes the folder and the filed name. |
| Any Keywords | Exactly what `F01` has. Copy the cell. |
| **Required Keywords** | **The entity's name**, and nothing else. |
| Period, Allowed Extensions, Min Size KB | Copy `F01`'s. |

There is nothing else on the row to fill in: the status and the notes are
not in the editor. The next scheduled pass reads your new row, makes its
folder and starts looking for the document; nothing else has to be done by
hand.

**How to write the name.** No commas — the keyword cells are
comma-separated, so `Ashford Holdings, L.P.` is read as two separate
requirements and the row stops matching. Type the distinctive words and
leave the legal suffix off: `Ashford Holdings`, not `Ashford Holdings,
L.P.`. The suffix is the part whose punctuation differs between your
typing and the form's printing, and the match is on whole words. Two
issuer rows must not have one name inside the other — `Ashford` and
`Ashford Holdings` would both claim the same K-1 — and the save is
refused, by name, if they do.

**What then happens.**

- A K-1 that prints one issuer row's name files on that row. It beats
  `F01` outright: naming the entity is the stronger evidence, and `F01`
  asks for no name at all.
- The **federal and the California K-1 from the same entity land in the
  same row** — California's Schedule K-1 (568) heads itself "Member's
  Share of Income" and `F01` asks for that too.
- A K-1 from an entity **no row names** parks in `00 - Needs Review`,
  and the reason names the issuer rows you do have. File it in the app,
  or add the row for that issuer and the next pass files it. It is not
  put on `F01`, and it is not guessed onto whichever issuer row has not
  had a K-1 yet.
- `F01` stays. A client with one K-1 and no issuer rows files on it as
  before.

**Next year.** The rollover carries the issuer rows like any other row,
with their names, statuses cleared. A partnership the client left is a row
you delete or set aside as Not Applicable; a new one is a new row, added
the same way.

## 9. Who to ask, and where the record is

- **Who does what**, and the life of a request: [workflow.md](workflow.md).
- **Why something odd is the way it is**: the decision log in
  [ROADMAP.md](ROADMAP.md). The odd choice is usually load-bearing.
- **What every pass did**, engagement by engagement, with the failures:
  `tracker.runner.LOG_FILENAME` in the clients root.
- **What happened to one document**: the Index section of that
  engagement's **Status Report.html**. Every move and every rename is in
  it, and it is drawn from the ledger, which is the record itself.

Nothing here sends an email, moves money, or tells a client anything. Every
message a client gets was read and sent by a person at this firm.

## 10. Names

**Why there is a name check at all.** Two 1040s in one household share
every row of their request lists. Once that household's inbox held two
people's papers, the keywords could not say whose W-2 this was — and the
mistake they allowed was the worst kind: filed quietly on the wrong
return, where nobody would look for it. So every return carries the names
its documents will show, and a document is filed only where the name on it
confirms.

**What the people list is.** Each return has one, edited in the app —
**Edit Request List**, the People block — and nowhere else. A person on it
is three things: *who they are* (taxpayer, spouse, dependent, entity, DBA,
owner, decedent, trust or estate, fiduciary), *their name* as you would
write it, and *the spellings a document might print it in*. The app
proposes the obvious spellings — `John A. Park`, `John Park`, `Park, John
A.`, `Park, John` — and **you tick the ones you want**; you can add any the
app did not think of, one per line. The wizard asks for the first person
when the return is made, and a return with nobody on it is refused. There
is nothing to tick for a person who writes the family name first: because
punctuation is ignored, `Park, John A.` already matches a page that prints
`PARK JOHN A`.

**Two words, always.** A spelling has to be at least two words. A family
name on its own would match inside a company's name — `Park` is inside
`Park Landscaping LLC` — so the app refuses a one-word spelling wherever
one is typed. An entity's spellings are its name with and without its
suffix (`Park Landscaping LLC`, `Park Landscaping`), and both are two
words.

**How a page is matched.** Case and punctuation are ignored, so `O'Brien`,
`PARK JOHN A` and `Park, John A.` all read alike. A spelling matches only
as a *whole phrase*, never inside a longer word. Nothing is guessed: the
page either prints one of your spellings or it does not.

**Named and unnamed requests.** Each row of the request list says whether
the document it asks for carries a name — the **Named** column. A W-2, a
1099, a K-1, a mortgage statement, a bank statement, a return: named. A
receipt, a mileage log, a trial balance, a schedule, a spreadsheet export:
not. Forty of the eighty-four shipped rows are named. For a named request
the name must confirm or the document parks; for an unnamed one a missing
name is nothing at all and the keywords file it as they always did. Either
way, a page naming somebody on *another* return of the household parks
rather than files.

**A name is never a keyword, and a keyword is never a name.** The K-1
issuer rows (§8) carry an entity's name in Required Keywords: that says
*which* K-1 this is. The people list says *whose* it is. They are two
questions and two columns, and neither stands in for the other.

**What the record keeps.** The firm's own spelling that matched, and the
outcome — nothing else. Not a word of the client's document, and no part
of anybody's tax identification number, ever, anywhere.

**When one parks.** The card says which of the three it was, and the three
rows in §4 say what to do. The usual one is a spelling the list has not
got: file the document and type the spelling the page prints into the box
beside **Teach this spelling**, and the next one like it files itself.

**Next year.** The rollover carries the people unchanged and asks you to
look at the list once — a child who now files their own return, a spouse's
new name. Nothing waits on that look; the check simply parks what it
cannot confirm until you give it.
