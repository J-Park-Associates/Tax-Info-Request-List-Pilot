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
in the folders (though, until a ledger can prove its own lines, it may hold
the only other copy of one, so it is copied aside before any rebuild, as the
store check below says), it is never synced and nobody opens it.

**The app's folder is private to the firm.** `tracker.db` holds every
client's index rows. (The reader writes nothing there or anywhere else
while it reads, since decision 169, so there is no longer a folder of
pages being read beside it.) The folder inherits its permissions from
wherever the app was unpacked: put the app in a folder only the firm's
accounts on that machine can read, not in a shared or public one. This is
a machine-setup step; the tracker does not change permissions.

**A return the store refuses as "changed behind the tracker's back".** The
store keeps a fingerprint of every line of a return's record it has read
(decision 137). If a sync client or a person rewrote or reordered the record
while keeping its length, the pass and the app refuse that return, apply
nothing and say so. Run the store check (`python -m tracker.store "<the app folder>" check "<clients root>"`)
to see it named. **A rebuild replays whatever the record now says.** So
before rebuilding a refused return, copy the database file
(`tracker.store.STORE_FILENAME`, beside the app) aside, into the same
folder as the store under a new name with today's date (never to the
desktop, a USB drive, an email or a chat), and keep any conflict copy of
the record — any other file beside the return's `_ledger.jsonl` whose name begins `_ledger`, which a sync client makes when
two copies disagree. They hold the only other copy of the lines the record
may have lost. If there is a conflict copy, stop and have the two compared
before anything is rebuilt. Then rebuild **that return only**, with
`python -m tracker.store "<the app folder>" rebuild "<clients root>" --engagement "<the return's folder>"`
- without `--engagement` it rebuilds every return, and the next pass
re-reads every document in the firm.

**Once, after installing the version that holds every record line to the
editor's bounds** (decision 187). Run the store check once
(`python -m tracker.store "<the app folder>" check "<clients root>"`). It
judges every line of every return's record by today's rule, so a line an
earlier version accepted that the rule now refuses - a Date Pattern that
could run away, a step outside its return's folders, a value of the wrong
kind - is named on the day of the upgrade. A return it names as
"malformed" is shown to Jason before that household is sorted, and
repaired the way any malformed line is repaired (section 9); until then
its household stops with the same sentence.

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
- **A folder the client drags into the inbox is flattened** (decision 147).
  Each file in it moves into the year's folder under its own name, and the
  emptied folders are removed. Its row's Reason ends with
  `filer.CAME_FROM_SUBFOLDER` — *came from the client's subfolder
  'Bank statements\2025'* — so you can still see how the client had sorted
  it. That sentence is ours, in the record; the client is never told it.
- **A file is renamed ` (2)` only when another file already has its name**
  in the year's folder — a file sitting there, one a row still names
  although it has since gone from there, or one an interrupted filing
  is still waiting to move there. The files at the top of the
  inbox are moved first and the folders after them in name order, so when
  `W2.pdf` and `Scans\W2.pdf` arrive together it is the one from `Scans`
  that becomes `W2 (2).pdf`. A byte-identical copy still gets its own
  numbered name and its row says Duplicate, as it always did. And when
  `W2.pdf` has gone from the year's folder — a client cannot delete it under
  the shares in *Sharing a household with a client*, so somebody at the firm
  or the sync client did — a corrected `W2.pdf` the client sends is filed as
  `W2 (2).pdf` with a row of its own, while the first
  row goes on saying its original is missing (`filer.MISSING_IN_PBC`) —
  the truthful state, until you look. Only the very same file sent back
  takes its old name again: it is that row's original coming home, and the
  pass moves it back to its old place with no new row (decision 157,
  *A working copy went missing* below).
- **One accepted limit:** the move out of the inbox is not written down
  before it happens (decision 119 left it that way on purpose). If the
  machine dies between the move and the row, the next pass finds the file
  in the year's folder and files or parks it correctly, but its row does
  not say which subfolder it came from.
- Inside a return, `Prepared` holds the firm's working copies **side by
  side**, each named by its request - `A01 - W-2 - TY2025.pdf`, then
  `A01 - W-2 - TY2025 (2).pdf` - and the review folder `00 - Needs Review`
  (decision 168). There is no folder per request: the name says which
  request a copy is for, and Explorer sorts a request's copies together. A
  folder anyone makes inside `Prepared` is theirs: the tracker files nothing
  into it, counts nothing in it and moves nothing out of it, and every pass
  names it once on the run - *"<folder> is a folder inside Prepared. The
  tracker files into Prepared itself and counts nothing in this folder."* A
  return made before decision 168 keeps its old request folders, and each is
  named that way. What sits in them is not counted, so such a return reads
  Missing for every document in its old folders, and its letter would ask
  the client for them: set it aside before its letter is drafted, and make
  it again. A file in
  `Prepared` whose name begins with no request's identifier is named on the
  run too, and not counted.
- The inbox holds one file of ours, `_README.txt`, which the tracker writes
  and nobody edits. Step 2 of it reads *"We will examine and place all
  documents into the current year's folder."*; step 3 reads *"Please keep
  sending the documents listed under REQUESTED, NOT YET RECEIVED."*; step 4 begins *"Original
  PDFs or Excel files are preferred. A clear photo from your phone is fine
  too, just get the whole page in the frame."* After **REQUESTED, NOT YET RECEIVED**
  (only the active requests the client is **asked** for that nothing has
  been received for yet - a row nobody asked for is never listed there,
  decision 142; a return
  with nothing left has no heading there, and an empty list reads
  *Nothing at the moment.*) comes **WHAT WE HAVE RECEIVED**,
  once something has arrived (decision 130): each document confirmed into
  a request, by that request's name, under its return, with the day it
  came in - a request nobody asked for included, which is the only place
  the client ever sees one; and under **Under Review**, how many documents a person is
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
else. The fourteen columns you edit there (`tracker.manifest.HEADERS`) are Identifier, Document, Period,
Expected Count, Allowed Extensions, Min Size KB, Required Keywords, Any
Keywords, Date Pattern, Manual Override, Override Reason, Named, Asked and Short name; **each request's status,
Received Date, File Count and Validation Notes are on the Status Report**,
not in the editor. The engagement's details — client, share link, due
date, sender, firm, reminders, active — and the **people** the return is
for are edited in the same place.
The editor keeps each value inside the bounds the tracker will read back
(decision 187): Expected Count is a whole number from 1 to 9,999, Min Size
KB from 0 to 1,048,576, a date is a real date between 1900 and 2100, and a
Date Pattern is at most 200 characters with at most eight variable parts
(`?`, `*`, `+`, `{m,n}`), of which at most three repeat more than once, one
at most is open-ended (`+`, `*`) and the rest at most `{…,20}`. No
repetition may sit inside another, no back-reference inside one, and a `|`
only inside a plain `?` (so `(?:Dec|12)?` is fine). And the tracker counts
every way the pattern could try one line and refuses one with more than
16,384: the slowest pattern that passes took about a quarter of a second
on a 500-character line, so a pattern cannot hold a pass on one page. The
count reads the pattern; it is not a clock. Descriptions (Document, Period, Override Reason,
the client and firm details) may run over several lines; identifiers, short
names and household and return names may not.

**Renaming a request** (decision 160). A request that already holds filed
documents keeps its identifier through a save: changing `A01` to `A1` in
the list, or deleting the row, and pressing **Save** is refused with a
sentence naming the request and how many documents it holds - saved, the
documents would be left under a name no request has, and the letter and
the client's README would ask for them again. To stop asking for such a
request, set it **Not Applicable** rather than deleting it. To change the identifier,
open **Rename a request** below the list, pick the request, type the new
identifier and press **Rename**: every working copy of the request's in
`Prepared` takes the new identifier at the front of its name, every row of
the index moves to the new identifier at once, and the request is
re-scanned. Nothing else you have typed in the editor is lost; save it
afterwards as usual. A change of **case** alone (`C01` to `c01`) is the
same request everywhere and is simply saved. A rename is refused while a
copy of the request's is not where the record put it - put it back or send
it to review first. A file named for the old identifier that no row names
is left where it is, and the editor names it. If a rename is interrupted
(a copy held open by another program), the next pass finishes it.

A request that a broker's consolidated statement answers (decision 146) -
the statement filed under the brokerage request, this request named in its
**Also Answers** with no copy of its own - is renamed the same way: the
rename carries it in the statement's Also Answers too, so it stays
Received under its new identifier. It also counts as holding that
statement, so deleting it in a save is refused with the same sentence
(one filed document: the statement). To delete such a request, first press
its **Mark ... missing** button (**Mark A04 missing**, say) on the statement
in the filed list, then delete the row and save.

**Save refused: "the list changed since you opened it".** The list was
saved after you opened the editor — by the review queue teaching a
spelling, for one. Nothing you saved was
recorded. Close the editor, open it again (it now shows the other save),
and make your change again. The app opens **one window**: a second
double-click brings the open window forward rather than opening another
editor beside it.

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
  the database again from the ledgers — it replays whatever they now say,
  so copy the database aside first, into the same folder as the store
  under a new name with today's date (never to the desktop, a USB drive,
  an email or a chat), and keep any conflict copy of a record,
  exactly as for a refused return at the top of §1. A `tracker.db` from
  before decision 107 is refused by name; move it aside (rename it; do not
  delete it) and run `rebuild` — the first pass after it reads every
  document once to fill the verdict cache the database also keeps.
- **Once, when decision 137 lands** (and again at decisions 142, 143, 144 and 146,
  `user_version` 13 to 16). Its database is a new version
  (`user_version` 12), so the `tracker.db` already on the machine is refused
  by name. Move it aside and run `rebuild` as above. The rebuild itself takes
  minutes; what takes longer is the **first pass after it**, which reads
  and OCRs every document again to refill the verdict cache - on a full
  season that can run past the scheduler's two-hour limit. A pass the
  scheduler stops keeps what it read for the returns it finished, and the
  next pass goes on from there. So
  do it outside office hours, and if one return matters first, rebuild it
  alone ahead of the rest with `--engagement "<the return's folder>"`. It
  happens once; later passes read only what is new.
- **Once, when decision 169 lands** (the new reader). The database's
  version does not change, so there is nothing to delete for it (set
  `tracker.db` aside only if another decision in the same install asks).
  But every verdict on a scan or a photo was reached by the old reader, so
  the **first pass after the install reads every scan and photo again** -
  slow once, as above. On the office machine, copy the graphics card pack
  beside the app once (§6, step 5). And delete the folder `ocr-scratch`
  beside the app if it is there: the old reader kept the page it was reading
  in it, the new one writes nothing, and nothing empties that folder any more.

There used to be a second one, a comparison flag on the ledger's own
statuses against the request list's. There is nothing left for it to
compare: the request list holds no status.

The folder that holds every engagement is typed once, in the app, on first
launch. It is written to the settings file beside the app
(`tracker.settings.SETTINGS_FILENAME`), and the app, the schedule and every
command read that one value afterwards. From a terminal the same thing is
`python -m tracker.settings <folder>`.

**One machine per clients root — today's rule.** The schedule,
**Sort & Scan**, filing, every save in the app and **Roll Forward** happen
on the designated machine (the table at the top of §1) and nowhere else. The only
thing that stops a scheduled pass and a click in the app from moving the
same client's files at once is a lock file
(`tracker.locking.LOCK_FILENAME`), and a file a cloud client copies between
two machines is not a lock — both machines can create their own before
either copy arrives. From another desk, one way to work at the designated
machine today is Remote Desktop into it. Any other machine may open a
return's Status Report and read it; it does not run the app against the
clients folder. This is the rule for now, while the owner decides how
several machines may write; this paragraph changes when that decision
does, and nothing else in these pages restates it.

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
from where it got to. **A killed pass loses at most the reading it was
in** (decision 189): every document's verdict is kept the moment the pass
moves on to the next file, so the next pass reads again only what it was
killed on. A file the killed pass had already moved into the client's
folder for the year shows up on the next pass as a file with no row, and
is filed again from its kept verdict — nothing to do.

**No client holds up the others** (decision 189). Each household gets
`tracker.runner.HOUSEHOLD_BUDGET_SECONDS` (fifteen minutes) of a pass,
counted only while the machine is awake and checked between files, so one
can run at most about 25 minutes. Only a file that still has to be read is
stopped: a file sent again, or a request whose files were read on an
earlier pass, is taken whatever the time. A household out of time stops taking
files, records what it did, drafts nothing this pass and says on every
return *this household's time for this pass ran out after N file(s); the
rest wait for the next pass* — nothing to do; the next pass carries on,
and drafts the week's letter if it is owed. **Run now** (Sort & Scan) has
the same fifteen minutes, so it finishes inside the app's thirty-minute
limit and says the same sentence rather than failing. Households are
taken **least recently completed first**, not in folder order, so the
one that ran out of time, or was stopped, does not go first and stop the
same clients every pass: a household the last pass was stopped in goes
last. The order is kept in `tracker.runner.PASS_ORDER_FILENAME`
(`pass-order.json`) beside the database; it is a hint and safe to delete
— the next pass goes in folder order and starts counting again. A
household skipped because another run held its lock is tried once more
at the end of the same pass.

**Task Scheduler's Last Run Result.** `0x0` is a pass that served every
household; `0x1` is a pass in which a return failed (the page's Problems
list says which). **`0x3`** (`tracker.runner.NOT_SERVED_TWICE_EXIT_CODE`)
means a household has not been served for two passes running or more —
it ran out of time, a lock was held, there was no room, or it failed. Open
the page: its Problems list names the household and why (*… has not been
served for N passes running (held lock)*), and that is the thing to fix.

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
deep in a return with a long household name and a long return name can
pass it. Since decision 144 a request's working copies are named by the
request's **short name**, twenty characters at most, where the full title
used to appear twice - so the firm's own root,
`G:\Shared drives\Income Tax Clients` (35 characters), refuses none of the
39 returns of the owner's intake test with the wizard's default rows asked
(9 were refused with the full titles) and none with every row asked (34
were); the deepest working copy there was 209 and 210 characters. Since
decision 168 there is no folder per request either: a copy sits in
`Prepared` itself as `A01 - W-2 - TY2025.pdf`, so every working path is
shorter again by the folder that held it: under the firm's own root the
deepest working copy of the intake test's 39 returns is 184 characters with
the default rows and 185 with every row (from 209 and 210), none of the 39
refused either way, and the whole 1040 core list under a 28-character root
went from 163 characters to 138. The client never sees a short name: the README,
the reminder letter and the received list keep the full title. So the reply to setting the root lists,
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
it), **a shorter Short name** in the editor for the request (every copy
filed from then on is shorter; the folder keeps its name - a folder made
under the full title before decision 144 keeps that name too, and takes
short copies), and **a shorter return name** at the next rollover. Nothing in the tracker ever renames a
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
must rest, the working copy is made in that return's `Prepared` folder, the copy
waiting here goes, and the row here is released: nothing about it stays in
this household; the journal says which return took it; if it went to the
wrong return, unfile it *there*.

If the machine dies in the middle of one of these, each household's next pass
finishes its own half; the queue of a return with a half-finished decision
refuses actions until that pass has run, as it does for any interrupted move.

### An email or a zip

A client who forwards an email (`.msg` from Outlook, `.eml` from most other
mail programs) or drops a zip with the documents attached does not have to
send them again (decision 143). The pass:

1. moves the container into the client's folder for the year, like any
   original - same name, same bytes - and records it **Opened**;
2. takes out each attachment, in memory, into a hidden folder in the
   **private** tree, `J Park & Associates/<household>/<year>/_Opened/<the
   container's name>/`, never into anything the client is shared;
3. sorts each attachment as a document of its own: filed where exactly one
   request accepts it, parked for you where several or none do. Its row's
   Came Inside column names the container, and the client's README lists
   each one that filed under its request.

Nothing inside is ever run. The message's own text, pictures shown inside
the message (a logo, a signature) and attachments that are only links are
left inside and named on the container's line in the record. An email held
inside a zip, or a zip inside an email, is opened through; one level deeper
is taken out whole and parks. The same email sent twice is recognised by
its bytes and not opened again, and an attachment the client also sent on
its own is a duplicate of it. An attachment's name loses any invisible
formatting character when it is saved, including the zero-width joiners
some Persian, Arabic and Indic names and emoji use; the record keeps the
name exactly as the email gave it (decision 176).

The opening runs where the pass can stop it (decision 154), in the
reading's own process (decision 150), under the stop
for a file - ten minutes. A container whose opening does not finish by
then parks with the stop's sentence (`reasons.READING_STOPPED`), and one
whose opening crashes parks with `reasons.READING_CRASHED`; either way
nothing is taken out, the pass goes on to the next file, and the
container is not opened again until it changes. If that process could not
start at all (`reasons.READER_UNAVAILABLE`), the container is left in the
year's folder with no row and opened on the next pass.

**When a container parks** (§4 has each sentence): a locked or damaged one
is the client's to fix - they send the documents on their own, and the
reminder asks for them; one with nothing attached, or past a limit, is
yours - ask the client what they meant to send, and if you must look
inside, do it as §4's *Before you open anything a pass parked* says, never
on the designated machine. A document you find goes in as *A document the
tracker did not file* below says. Close the container with
**Not requested** once you have. A
document from inside a container is never filed into another household's
return, by the pass or by **File under another return**: file it by hand
in the return it belongs to, from its own row.

The `_Opened` folder is synced with the rest of the private tree, on
purpose (the owner's decision of 2026-09-23, a named exception to decision
107's rule): a pass that recovers an interrupted filing, and a move to
another machine, both need what is in it. Do not tidy it by hand; a file
there that no row names is said on every pass until a person has looked.

### A document the tracker did not file

A file turns up that no row accounts for — in `Prepared` under a request's
name, in a hidden `_Opened` folder, or inside an email or a zip you have
looked into. **Confirm whose document it is first.** A file nobody can
account for is very often another client's, and a document put in a
client's folder is published to that household.

A document goes in through the app or a firm-side folder a person
controls, never the client-visible tree:

- **It is this return's.** Keep it in a folder of your own inside the
  return's `Prepared` — the tracker counts nothing there and names the
  folder on each run (*The layout*, above) — and in **Edit Request List**
  set the request's Manual Override to Accepted, with the Override Reason
  for a document received outside the system. The save is recorded, the
  request reads Received, and the letter stops asking.
- **It is another return's.** Do the same on that return.
- **You cannot tell whose it is.** Leave it where it is and ask whoever
  would know. Never put it in a client's folder to see where the pass
  sends it.
- **It is not a whole document** — a partial or broken copy: delete it by
  hand, and never ask the client for it.

### A working copy went missing

A working copy in `Prepared` is ours and can always be made again; the
client's original in their folder for the year is the record. So when a
copy disappears — a colleague tidies the Shared Drive in the browser and
trashes it, Drive's cache on the designated machine is cleared or the
account is disconnected before it uploaded, a person deletes it, or the
whole `Prepared` folder goes — **the next pass makes it again** from the
original, at the same place under the same name (decision 157). It checks
the original holds exactly the bytes the record filed before it copies, and
the copy is made whole or not at all. The row's Reason ends with
`filer.REMADE_SENTENCE`, the run says it once, the request's status does
not move, and **the client is never asked** for a document we hold. A
deleted `Prepared` comes back whole, the review folder included.

- **The original cannot be read right now** (Drive still bringing the
  year's folder down, or refusing it): it is not touched and nothing is
  made; the request's note says `reasons.COPY_MISSING` and the letter holds
  off. The pass after makes the copy once the original is readable.
- **The original is gone too**, or it holds a different file now: nothing
  can be made again and nothing is guessed. The row becomes File Moved
  with `filer.BOTH_GONE_SENTENCE`, said once; the request's note says
  `reasons.COPY_AND_ORIGINAL_GONE`, and the letter holds off until you
  look. Look in the Shared Drive's trash (kept 30 days) and, after a Drive
  error notice on the designated machine, in Drive for desktop's
  `lost_and_found` folder. If you find the original, put it back in the
  client's folder for the year under its own name: the next pass makes the
  copy. If it is really gone, press **Mark … missing** on that row in the
  app's moved list (the only answer it offers; **Put it back**,
  **Keep it here** and **Send to review** have nothing to work with and say
  so). The row stays on the record with your sentence, stops counting, and
  leaves the client's received list; the request reads Missing and the
  next letter asks the client for it. What they send is filed as a new
  arrival. Once a row is marked missing, an original you then find and put
  back at its old place in the client's folder is not filed again (the
  mark cannot be undone, and the row's place stays taken): move it from
  there into `Drop files here` instead, and the pass files it as a new
  arrival under a name of its own and the letter stops asking.
- **The original comes back into `Drop files here`** — Drive undoing a
  move it refused, or a colleague dragging the filed original back — under
  its own name or any other: when its bytes are those of exactly one row
  whose original is gone, the pass moves it back to that row's place under
  the recorded name. No new row is written; the row's Reason gains
  `filer.RETURNED_SENTENCE`, and anything the same pass had said about the
  original being missing is taken back. A copy whose original was gone too
  is made again in the same step. Where two rows could be its row, nothing
  is guessed: it is a duplicate with a name and a row of its own, and no
  row is ever replaced.
- **You can make it again yourself**: **Put it back** (the `restore`
  command) on a row whose copy was deleted makes it from the original
  exactly as the pass would, and says so in the same words.

A consolidated statement's answers (decision 146) go with its copy: while
the statement's own copy is missing, not the one filed, or gone with its
original, each request it answers says `reasons.ANSWER_NOT_COUNTED` instead
of Received, and the letter holds off; the pass that makes the copy again
puts them back.

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

**A return rolls forward where it sits.** When a household separates, the
way to move one return into a household of its own is still to drag its
folder there in Explorer — the app has no action for it. Its record goes on
naming the old household, and the app shows a warning beside it ("the
folder is named … but its record says …"). That warning is information:
Roll Forward puts next year's return in the household it now sits in, under
its own folder name, and next year's record names that household, so the
old household's client never sees its requests or its documents. The
warning is repeated in the rollover's reply, because the roll is the moment
someone acts on that return.

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
   the app's button. Each pass's first line ends with which device read its
   scans and photos: `reader=processor` or `reader=graphics card` (§6,
   step 5). For one client, **open the Status Report** in that
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

   **Every logged pass says it started** (decision 189): the run log has
   a `[time] pass started` line before each pass's summary. When the next
   pass finds a *started* line with no summary after it, it says *the
   pass that started at … did not finish (it was stopped or the machine
   went off); this pass picks up where it left off* in the log and on the
   page. Usually nothing to do: the pass kept every reading it finished.
   If it says so every morning, the machine is going to sleep or off
   during the schedule — look at its power settings.

   **The page is always this morning's** (decision 189). Whatever went
   wrong in the pass, the page and the run log are each still written, and
   the page's **Problems** list starts with what the pass itself could not
   do: *the pass stopped early (…)* names the kind of fault and means the
   households after it were not looked at this pass — the next pass looks
   at them; tell whoever looks after the machine if it repeats. *the run
   log could not be written (…)* means `runs.log` is held open or the
   disk is full — close whatever has it open. A return whose line reads
   *the record could not be read: the database could not be used
   (SQLITE_BUSY)* — or another `SQLITE_` code — met the app's database
   busy or unwell; the rest of the practice ran, and the next pass tries
   again. *the record could not be written (ENOSPC)* is a full disk; other
   codes are the disk refusing the write (`EACCES`: a sync client or
   antivirus holding the file). A line the page read rather than ran, and
   a household that stopped on something unexpected, name the same fault
   by its kind and code alone - *StoreUnavailable (SQLITE_BUSY)*,
   *RecordNotWritten (ENOSPC)*, *PermissionError (EACCES)* - never the
   system's own words, which can name a client's folder. *the practice
   page could not be written (…)* is said in `runs.log` instead, and the
   Last Run Result is `0x1`: the page you are looking at is an old one. The run log gives each return's warnings
   as a count, *(warnings: 3)*; the page and the app have the sentences.
   **Run now** says the same: under the return's own result it lists the
   household's other returns' problems and the pass's own (the reader,
   the log, the page).
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

   **Scans and photos are read by the reader that ships inside the app**
   (decision 169), so they are filed like any other document. One that the
   reader cannot read is in that queue: nothing is filed on a file name
   (owner, 2026-09-18) - a client called the file "W2 2025.pdf", the form
   did not, and a document nobody here can read is filed by nobody. What
   the name says is not thrown away — it is the bottom line of the
   shortlist, *the file name says W-2* — but it is a place to start
   reading, never the answer. **A page scanned sideways or upside down**
   keeps its words, but its title may not come first in what was read, so
   it can file less surely than an upright one or wait here for you; it is
   never read as empty (the rule that turns such a page arrives later).
3. **A working copy that has moved is yours, and it is the first card on
   the screen.** Every pass proves each working copy against the
   fingerprint its own index row carries (decision 109). A copy somebody
   dragged away from where the record put it, or renamed, makes that row
   `tracker.filer.FILE_MOVED`, and it is said on the run and on the
   practice page the same morning: the request reads Missing until it is
   back, and the client is never asked for it. The app lists every such
   copy above the review queue with its home, where its bytes are now, and
   three answers — **Put it back**, **Keep it here** (only when the copy
   sits in `Prepared` itself under a name that begins with a request's
   identifier: it is filed there, under that request, which you can
   change) and **Send to review** — because which one
   you meant is never guessed (decision 110). Answer them before Saturday:
   the draft holds nothing up for a mislaid copy, and a request that reads
   Missing all week is one nobody is chasing. Nothing you press there
   overwrites a file or deletes one — a different document already at home
   is left where it is and this one's copy goes to review instead, and a
   left-over copy is named every pass until you remove it yourself. §4 has
   the row and what each answer means. A copy that was simply deleted is
   not on this card: the pass makes it again from the original (decision
   157, §1 *A working copy went missing*). One whose original is gone too
   is, with one answer, **Mark … missing**, which puts the document back on
   the client's letter.
4. **A locked engagement.** The app shows a notice when a run holds one. If
   it says a run is still going, leave it — **Sort & Scan** waits for it.
   If it says a run left its lock behind, a **Clear lock** button appears;
   it only appears once the lock is older than
   `tracker.locking.STALE_LOCK_SECONDS`, which is past the point Task
   Scheduler must already have killed the run that made it, so clearing it
   then is safe. Never delete a lock file by hand. On the Google Drive
   drive, a run letting go at the same moment as another can have its
   lock file stay behind even though Windows said it was deleted (decision
   171). The run checks, and marks the file released when it stayed. The
   run that left it clears it the next time it takes that lock, and any
   later run clears it once the run that left it has ended, or at once if
   it was marked released; otherwise it is cleared when it goes stale, as
   above. A notice that says the lock "is changing hands" means two runs
   met at that instant; press the button again a moment later. A run that
   says it was refused permission to create the lock is not waiting for
   another run: the account running it cannot write to that return's
   folder, and that has to be fixed on the folder. **After a power cut
   or a restart** nothing waits (decision 189): a lock this machine wrote
   before it last started is cleared by the next run, whatever process
   number it names, and an empty lock file - the power went between the
   lock being made and its line being written, which the run now forces
   to disk at once - is cleared once it is a minute old. A lock written by
   another machine still waits for the age rule.
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

Open it, read it, edit it, paste it into Outlook and send it. Nothing in the
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

**Before you open anything a pass parked.** A file the tracker refused to
open — an email or a zip that is locked, damaged, empty or past a limit, or
a file too large, too slow or that crashed the reader — is opened, if at
all, on a machine with no Drive sign-in and no client folder, never the
designated machine. Until the tracker sets such files aside itself, a
parked file whose name ends in a program, script or shortcut extension
(.exe, .com, .scr, .msi, .bat, .cmd, .ps1, .vbs, .js, .jar, .hta, .lnk,
.url and the like) is not opened anywhere: ask the client what they meant
to send. A parked document is opened as its working copy in
`00 - Needs Review`, never the client's original, and in Protected View
(the read-only view Office and Acrobat give a file from outside).

| The index says | In plain words | What you do |
|---|---|---|
| `filer.FILED` | Exactly one request accepted it. | Nothing. |
| `filer.DUPLICATE` | The same bytes are already in the record, and the reason says what the row holding them is: `filer.DUPLICATE_OF_FILED` says "already filed as" of a filed document, `filer.DUPLICATE_OF_PARKED` says "parked as" of one still waiting for you, `filer.DUPLICATE_OF_MOVED` names the copy of a row whose file is not where the record put it, and `filer.DUPLICATE_OF_UNCOPIED` says plainly that the row holding those bytes never got a working copy. No second copy is made. | Nothing. The original is kept, and the row holding the bytes is where the work is. |
| `filer.RESENT_AFTER_SET_ASIDE` | The client sent again a document somebody had closed with **Not requested**. It was routed afresh: filed if exactly one request accepts it now, otherwise parked again with a copy of its own. The reason quotes the earlier decision whole — the date and the note whoever closed it typed. | Read what was decided last time, then decide again: file it, or close it again. The copy set aside earlier stays where it is. |
| `filer.NEEDS_REVIEW` | Parked for a person; the reason says which of the rows below. | Work it in the app. |
| `filer.ASSIGNED_BY_PERSON` | Someone filed it with **File it**, on the date shown, and what the rules had said is kept after it. | Nothing. This is the audit trail. |
| `filer.CAME_FROM_SUBFOLDER` | Said at the end of any row - filed, parked, a duplicate, the opened email or zip's own row, or a row saying it could not be filed - whose file the client dropped inside a folder of their own in `Drop files here` (§1, *The layout*). It names that folder, below the inbox. | Nothing. It is where the client had put it; use it when the row's name alone does not say enough. |
| `router.UNMATCHED` | No request on this manifest accepted it. | File it to the right request, or add the request. |
| `reasons.SHOWS_ITS_FORM_NUMBER` / `reasons.NAME_POINTS_AT` | No request accepted it, but the page shows the **form number** of the request(s) named — in its title, or as the form its first page is about, beside another of that request's own words — most often a scan whose reading lost one of the phrases the request asks for; or, where the page shows none, the file's **name** points at a request, and the sentence says "file name" instead. Those requests are the card's shortlist, never a filing, and the client's reminder is held for them rather than asking for what they sent (decision 140). | Open it: if it is that request's document, file it there; if not, file it where it belongs or set it aside, and the reminder is released. |
| `router.AMBIGUOUS` | More than one request accepted it. A broker's consolidated 1099 no longer parks here when exactly one request accepted it because of its 1099-B section (decision 146, below); two requests asking for a 1099-B, or none, and it still does. | Pick the right one. |
| `reasons.FILED_WHOLE` / `reasons.ALSO_ANSWERS` | A broker's consolidated 1099 (decision 146): several requests accepted it, and exactly one - E01 on a 1040, B01 on a 1041 - was accepted because of its 1099-B section, so it filed whole there, one copy in one folder. The Also Answers column names every other asked request one of its sections answers (a 1099-INT/DIV row, a 1099-MISC row) and the sections that did; each of those requests reads Received with `reasons.IN_CONSOLIDATED` in its notes, counting one document per section - so a 1099-INT/DIV row asking for three is Partial after one statement with interest and dividend sections - and the letter does not ask for them. A statement with only interest and dividend sections is not a brokerage statement and files under the 1099-INT/DIV row as before. | Nothing. If the statement does not in fact carry what one of those requests needs, press **Mark … missing** beside it in the app's filed list: the statement stays where it is, that request comes off, and the letter asks for it again. |
| `router.CONTESTED_PREFIX` | It looks like a named request but failed one of that request's own rules — last year's W-2, say. | Read the named rule. Usually it is the wrong year or the wrong client. |
| `router.OCR_ONLY` | A scan or a photo with no text layer; OCR read it, but only loosely enough to guess. | Confirm what it is and file it. |
| `reasons.NO_READABLE_TEXT` | Nothing in the file could be read at all — a scan or a photo the reader could not run on, an image-only PDF, an empty sheet. Nothing was matched against anything, so this is not "matched no request". | Open it and file it. If many files say it at once, the reader itself is damaged: re-install the app (§6, step 5). The shortlist shows what its **file name** suggests; the document decides. |
| `reasons.UNREADABLE_IMAGE` | A photo arrived that would not open — a half-finished upload, most often. | Ask the client for it again; the reminder does. |
| `reasons.HEIC_NOT_SUPPORTED` | An iPhone photo arrived and this machine's HEIC reader is missing. Ours, never the client's: they sent an ordinary photo. | Run `Setup.bat` again (it installs `pillow-heif` from the locks); for the packaged app, rebuild it. Until then, open the photo and file it by hand. |
| `reasons.ISSUER_NOT_NAMED` | The request list asks for this document one row per issuer (§8) and this one names none of them — a K-1 from a partnership nobody listed. | File it to the right row, or add a row for that issuer (§8) and it files itself next pass. |
| `reasons.NAME_NOT_ON_PAGE` | A request that asks for a **named** document accepted it, and the page names nobody on this return's people list (§10). | Open the page. If it does name them in a spelling the list has not got, file it and **teach the spelling** on the same card; if it is somebody else's, file it by hand on the return it belongs to. |
| `reasons.NAMES_ANOTHER_RETURN` | The page names somebody who is on another return of this household, and nobody on this one. The sentence says who, and which return. | Switch to that return and file it there. Nothing was moved. |
| `reasons.NO_PEOPLE_ON_FILE` | This return lists nobody yet, so nothing can confirm a named request. | Open **Edit Request List** and add the return's people (§10). Everything parked for this reason files itself on the next pass. |
| `reasons.SEVERAL_FORMS_UNSORTED` | One page prints two or more forms' own names (a stack scanned in one pass) and they will not sort one to a request: a form no row asks for, two rows wanting one form, or a row that accepted the page on a phrase rather than a form number. When they do sort, the page files a copy under each request and the row's Reason says so (`reasons.NAMES_SEVERAL_FORMS`). | Split the scan, or file the whole page to the one request that matters and note the rest. |
| `reasons.TOO_LARGE` | The file is larger than the tracker will read (`validators.MAX_READ_MB`) — a video, a disk image, a whole mailbox, or a genuinely enormous scan. It was not opened: no text, no OCR. It is still counted and kept like any other original. | Ask the client what it was meant to be. If you must look, do it as the paragraph above this table says, then file it. |
| `reasons.READING_STOPPED` | The reader gave up on this file at the safety stop — a minute a page, ten minutes a file (decision 137). Something in it made reading far slower than any real document, or the machine was very busy at the time (time the machine spent asleep does not count, decision 189). Since decision 189 the stop bounds the rules as well as the reading: the file is judged against its requests in the same process it is read in, so a typed Date Pattern on a request that is slow to match can cause this for every file judged against that request, until the pattern is changed - several files parked with this sentence against one request point at that request's Date Pattern. The verdict is kept, and not tried again until the file or its request's rules change. The stop covers the whole reading and the judgment - the text layer, each page's drawing, the OCR and the rules - because they run in the reading's own process, which the pass ends at the stop (decision 150). An email or a zip is opened in that process too, under the stop for a file, and one stopped there parks whole with nothing taken out of it (decision 154). That process never outlives the pass: if the schedule's own time limit stops the pass, the reading stops with it. | Open its working copy as the paragraph above this table says, and file it. |
| `reasons.READING_CRASHED` | The reader's own process ended on this file without an answer - the PDF or OCR library crashed, the email or zip opener crashed (decision 154), or the machine ran out of memory (decision 150). Only this file is affected: the pass went on to the next one, and this file will not be tried again until it changes. | Open its working copy as the paragraph above this table says — never on the designated machine — and file it. If many files say it at once, the machine itself needs a look. |
| `reasons.READER_UNAVAILABLE` | The reader could not start on this machine at all, so the file was never opened (decision 150). The machine's problem, never the file's: nothing is kept about the file and nothing is recorded - no index row, no Needs Review row. The file waits (in the inbox, or in the year's folder with no row) and is read again on the next pass. The pass's own summary and the run log say it once. | Look at the machine (memory, disk, antivirus, a damaged install). Once it is fixed, the next pass reads and files the waiting files; there is nothing to file by hand. |
| `reasons.UNNAMED_ACROSS_HOUSEHOLDS` | This household's drop folder feeds a return in another household, and that return would have taken this document on its keywords alone — but the page names nobody, so it was not moved into a folder other people can open. It waits here (decision 137). The Evidence names the return and the request that wanted it, as `<return> / <request>`. The same holds for a document sent again that the other household already has. | Open it. If it is that return's, file it there with **File it**; if it is this household's, file it here. |
| `router.NO_REQUEST_ACCEPTS` | No request on this manifest takes that file type at all. | Usually a stray file. Otherwise widen the request's allowed types. |
| `reasons.CONTAINER_LOCKED` | An email or a zip arrived and one of the files inside is locked with a password (or packed in a way this machine cannot unpack), so nothing in it was opened. The container is kept like any original, with a review copy. | Ask the client for the documents themselves; the reminder does. Do not unlock it on the designated machine, even with the password: open it, if at all, as the paragraph above this table says, and put any document in as §1, *A document the tracker did not file*, says. |
| `reasons.CONTAINER_DAMAGED` | An email or a zip arrived that does not read as one - a broken zip, an Outlook file whose structure is damaged, an email with no headers at all. Nothing in it was opened. | Ask the client to send the documents on their own; the reminder does. Do not try to open it on the designated machine. |
| `reasons.CONTAINER_EMPTY` | An email or a zip arrived with nothing attached - only the message's own text, or a picture shown inside it. Ours, never the client's. | Ask the client what they meant to send, or read the message as the paragraph above this table says — never on the designated machine. Close it with **Not requested** once you know. |
| `reasons.CONTAINER_LIMIT` | An email or a zip past one of the limits it is opened under, named in the sentence: nested more than two deep, more than 200 attachments, more than 250 MB once unpacked, a file inside that unpacks to more than 100 times its packed size (the shape of a "zip bomb"), or more than 200 parts that are not documents. Nothing was taken out. A container nested too deep inside another is taken out whole and parks with this reason on its own row, while the rest of what was attached files. | Ask the client to send the documents on their own. If you must look inside, do it as the paragraph above this table says, never on the designated machine, and put any document you find in as §1, *A document the tracker did not file*, says. |
| `reasons.OPENED_NOT_ACROSS` | A document that came inside an email or a zip, which a return in **another** household would have taken. A document from inside a container is the firm's copy of a part of the client's file, and it is never moved into another household's folder. The Evidence names the return and the request that wanted it. It is also what an attachment says when its bytes are already on record only in another household: nothing is written in that household's record, and the Evidence is empty. | File it by hand where it belongs (§1, *An email or a zip*). **File under another return** refuses it in the same words. |
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

These appear as warnings on the run rather than as index rows:

| The run warns | In plain words | What you do |
|---|---|---|
| `filer.REPLACED_IN_PBC` | An original we had already filed no longer holds the bytes we filed. A client cannot change one under the documented shares (§1, *Sharing a household with a client*), so somebody at the firm or the sync client did; the working copy was made from the earlier file. Said too for a file taken out of an email or a zip that was replaced under its own name in the hidden `_Opened` folder. | Look at both, re-file if the new one differs, and find out who at the firm changed it. |
| `filer.README_UNREAD` | The README in a household's inbox could not be opened just now - most often because someone has it open, or antivirus is holding it (decision 179). It is neither sorted nor written over; it waits where it is, as a file held open does. | Nothing, unless it is said pass after pass: then close whatever has it open. The next pass looks again. |
| `filer.UNTIED_IN_PBC` | A row was recorded without its bytes and its working copy no longer matches the original. | Look at it. Nothing is adopted automatically, by design. |
| `filer.UNRECORDED_OPENED` / `filer.OPENED_CONTAINER_GONE` | A file sits in a hidden `_Opened` folder that no row names, or a container's folder there whose email or zip has no row any more (decision 143). A pass killed half way that the next pass did not finish can leave one; so can a file somebody put there by hand. It is never sorted from there and never deleted. | Confirm whose it is first, opening it only as §4's *Before you open anything a pass parked* says: as a copy, never the client's original, in Protected View, never on the designated machine; a name ending in a program, script or shortcut extension is opened nowhere — ask the client. A document goes in as §1, *A document the tracker did not file*, says — never into a client's folder; then delete the stray by hand. If you cannot tell whose it is, leave it and ask. |
| `filer.REMAKE_FAILED` | A working copy that was gone could not be made again from the original this pass - a full disk, a path past the limit, or an original that changed while it was read (decision 157). Nothing half made is left, nothing is recorded, and the request is held for you (`reasons.COPY_MISSING`), never asked of the client. | Nothing, if the next pass makes it. If the line comes back every pass, look at what it names: free the disk, shorten the root, or look at the original. |
| `filer.UNRECORDED_COPY` | A file is sitting in `Prepared` under a name that begins with a request's identifier (or in the review folder) that nothing on the record put there and no row's bytes account for. It **is** counted for that request — what a request has is what `Prepared` holds under its name — but nobody can say where it came from. It is never a copy the tracker left half made: since decision 155 a copy that fails or is killed part-way (antivirus holding it, a full disk, the power going out) leaves only a temporary file, which nothing counts and the next pass removes. | Confirm whose it is first, opening it only as §4's *Before you open anything a pass parked* says: as a copy, never the client's original, in Protected View, never on the designated machine; a name ending in a program, script or shortcut extension is opened nowhere — ask the client. A document goes in through the app or a firm-side folder a person controls, never a client's folder: §1, *A document the tracker did not file*. If it is not a whole document — a partial or broken copy, say one an older version left — delete it by hand; never ask the client for it. Said every pass until you do. |

And since decision 143 the Decision column has a sixth value, for an email
or a zip the pass opened:

| The index says | In plain words | What you do |
|---|---|---|
| `filer.OPENED` | An email (`.msg`, `.eml`) or a zip the client dropped. It rests in their folder for the year, untouched; each attachment was taken out and has a row of its own, whose Came Inside column names this one. The Reason says how many documents came out (`filer.OPENED_SENTENCE`) and how many parts were left inside - the message's text, a picture shown in it, an attachment that was only a link. It belongs to no request. | Nothing. Work each attachment's own row. |
| `filer.DUPLICATE_OF_OPENED` | The same email or zip again, byte for byte. It was not opened a second time. | Nothing. |

And since decision 109 the Decision column has a fifth value, for a working
copy that is not where the record put it:

| The index says | In plain words | What you do |
|---|---|---|
| `filer.FILE_MOVED` | Every pass proves each working copy against the fingerprint its own row carries. This row's copy is not in the folder the record filed it into, and its bytes turned up somewhere else under `Prepared/` — somebody dragged it. The Reason names where it belongs and where it is now; the Prepared Location column still says where it *belongs*. Nothing was moved to find that out and nothing is moved because of it. | Open the app: put it back where it belongs, keep it where it is, or send it to review (decision 110's three buttons, coming). Until then, drag it back yourself and the next pass files it again. The request it left reads Missing meanwhile, and the client is never asked for it. |
| `filer.REMADE_SENTENCE` | Said at the end of a row whose working copy was gone - deleted, trashed, lost from Drive's cache - with its bytes nowhere else under `Prepared/`, and was made again from the client's original, proved against the row's fingerprint (decision 157). By the pass, or by you with **Put it back**. The request's status did not move. | Nothing. |
| `filer.BOTH_GONE_SENTENCE` | The row is File Moved: its working copy is gone and so is the client's original, or the original holds a different file now (decision 157). Nothing could be made again; the request is held for you and the client is not asked. Said once. | Look for the original (the Shared Drive's trash, Drive's `lost_and_found`). Put it back in the client's folder for the year and the next pass makes the copy; if it is really gone, press **Mark … missing** on the row in the app, and the letter asks the client. Once marked, the row names no working copy and ends with `filer.MARKED_MISSING`. |
| `filer.RETURNED_SENTENCE` | The row's own original came back into `Drop files here` - Drive undoing a move, or somebody dragging it back - and the pass moved it back to the place the row names, with no new row (decision 157). | Nothing. |

## 5. What the Validation Notes mean

**Where to read them:** on the engagement's **Status Report**, in the
Requests section, beside each row's status — and in the app. They used to
be a column of the request list; since September 2026 the list holds only
the fourteen columns you edit, and every note the machine writes is in the
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
`reasons.READING_CRASHED`, `reasons.READER_UNAVAILABLE`,
`reasons.UNNAMED_ACROSS_HOUSEHOLDS`,
`reasons.UNCHECKABLE_TYPE`,
`reasons.FILE_MOVED`, `reasons.COPY_CHANGED`,
`reasons.COPY_MISSING`, `reasons.COPY_AND_ORIGINAL_GONE`,
`reasons.ANSWER_NOT_COUNTED`,
`reasons.INTERRUPTED_MOVE`, `reasons.INTERRUPTED_MOVE_LOST`. These mean the
document may be perfectly fine and no person here has read it yet. (Until
decision 168 there was one more, "request folder not found": no request
has a folder any more, so a request with nothing in is simply Missing.)
`reasons.FILE_MOVED` and `reasons.COPY_CHANGED` are decision 109's, and they are ours by
definition: the client sent the document and somebody here moved the copy
or put another file in its place.

- `reasons.FILE_MOVED` — this request's working copy is not where the
  record put it any more and the record has found it elsewhere under `Prepared/`. The
  note names where it belongs and where it is; §4 is the row it comes
  from. The request reads Missing until the copy is back.
- `reasons.COPY_CHANGED` — the file at the request's copy's place is not the one
  the record filed there: its size or its bytes disagree with the
  client's original. It is **not counted** (decision 155) — a copy torn in
  half, or another file put in its place, is not the document, whatever
  rules it passes — so the request reads Missing, and because the note is
  ours the letter does not ask the client for it. Open it, because nothing
  on the record says what that file is: put the right copy back (the
  original is in the client's folder for the year), or file whatever it
  is properly. It is on the practice page too, so you see it across every
  engagement at once.
- `reasons.COPY_MISSING` — the request's working copy is gone and the pass
  could not make it again this time: the client's original could not be
  read (still syncing, or refused), or the copy could not be written
  (decision 157). Nothing is asked of the client — we hold the original —
  and the pass makes the copy as soon as it can. If it stays, look at the
  original in the client's folder for the year (§1, *A working copy went
  missing*).
- `reasons.COPY_AND_ORIGINAL_GONE` — the working copy is gone and so is the
  client's original (decision 157). The request reads Missing and the
  letter holds off until you look: find the original and put it back, or
  press **Mark … missing** on the row in the app, and the next letter asks
  the client for it.
- `reasons.ANSWER_NOT_COUNTED` — a consolidated statement answers this
  request (decision 146), and the statement's own working copy is not
  counted: it is missing, not the one filed, or gone with its original. The
  answer is not counted either, so the request reads Missing, and the
  letter holds off. It heals the moment the statement's copy is made again.
- `reasons.INTERRUPTED_MOVE` — a step that was putting a working copy of
  this request's in `Prepared` was interrupted (the machine went off, the power
  went out) and that place now holds a different file. Nothing there was
  touched, the document itself is parked for you in `00 - Needs Review`
  with a copy of its own, and the file that is sitting there is **not**
  counted, so the request reads Missing rather than Failed Validation for
  a document the client sent perfectly well. Open the app, file the parked
  copy, and take the leftover file out of `Prepared`; it is named every
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

Four reasons in that file are not validation notes at all:
`reasons.NO_READABLE_TEXT`, `reasons.ISSUER_NOT_NAMED`,
`reasons.SHOWS_ITS_FORM_NUMBER` and `reasons.NAME_POINTS_AT` are the
router's, and they appear in the index's Reason column (§4) rather than
against a request. All four are ours: the client may well have sent the
right document. The last two are the firm-side reasons that hold the
reminder (decision 140), and their held line says a person here is
confirming the file, never that the file was wrong; the reminder's refusal
says it is "held until a person confirms the parked file (open it in Needs
Review)".

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

About thirty minutes.

**Nothing to restore.** Every engagement's manifest, ledger, originals,
working copies and drafts are in the engagement folder, which syncs. Any
machine signed into the same Drive account has all of it already.

**What was only on that machine:** the settings file beside the app
(`tracker.settings.SETTINGS_FILENAME`), the database beside it
(`tracker.store.STORE_FILENAME`) and the pass-order hint beside it
(`tracker.runner.PASS_ORDER_FILENAME`), the scheduled task, the app folder
itself, and the graphics card pack if that machine had one (step 5). **The database
is not carried over** — the new machine builds its own from the ledgers in
the engagement folders on its first pass — **but if the old machine still
starts, copy its database aside and keep it** - into the same folder as
the store, under a new name with today's date, never to the desktop, a USB
drive, an email or a chat - until the new machine's first pass has run clean: until the record can prove its own lines, it is the
only other copy of them. The first
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

**And no file the tracker writes is ever half there** (decision 155). A
working copy, the weekly draft, the client's README, the Status Report
and the settings are each written to a temporary name beside the real one
(ending `.tmp`, with the program's process number and a random tag in it)
and renamed into place only once every byte is on the disk. So a power
cut, a restart, or antivirus grabbing a new file part-way leaves at worst
that temporary file and the real one as it was - never half a statement
under the proper name. The next pass on the household removes those
temporary files itself, and only its own: the exact shape, left by a
program that has since stopped, in the firm's folders or beside the
README, never in the client's folders for the year. You never delete
one by hand. A working copy of a read-only file the client sent (from a
CD, or taken out of a zip by Explorer) is made writable, so a person's
filing or hand-over can always move it; the client's original is left
exactly as it came.

1. Install Google Drive for desktop on the new machine, sign in with the
   firm account, and wait for the clients folder to finish syncing. Do not
   start until it has.
2. Put the app on it: rebuild it from this repository (`Build App.bat`),
   or download the package from the `build.yml` run a `v*` release tag
   started (decision 191: a package is built from a tag and from nothing
   else, and only an admin can make one, so it is the build of reviewed
   code). **Before putting it on the machine, check the package**, in
   this order:
   1. Download the run's artifact. GitHub always hands it over wrapped in
      a zip of its own, `portable-package.zip`.
   2. Unzip `portable-package.zip`. Inside are the package itself,
      `tax-document-tracker-<tag>.zip` (the tag, such as `v1.2.0`, in its
      name), and its `.sha256` file.
   3. In a Command Prompt in that folder, run
      `certutil -hashfile tax-document-tracker-<tag>.zip SHA256` - on the
      inner zip, never on `portable-package.zip`.
   4. Compare the answer with the line "SHA-256 of
      `tax-document-tracker-<tag>.zip`" on the run's own summary page on
      GitHub. Not only with the `.sha256` file beside the zip, which
      travelled with it; and not with the artifact's own digest GitHub
      shows on the run page, which is the outer zip's.
   5. Only when they match, unzip `tax-document-tracker-<tag>.zip` into
      the app's folder on the machine's own drive. When they differ, do not
      install it: download it again,
      and if they still differ, ask.

   There is no separate backup of the app, and none is needed.
   The client files are on the Shared Drive, `settings.json` holds only the
   clients folder, the firm's name and its telephone number, all three typed
   again at step 3, and `tracker.db` rebuilds itself from the journals. Running from source needs Python and
   Node, and **`Setup.bat` run once** with the internet on: it makes the
   app's own private Python (`.venv`) and installs into it exactly the
   locked packages, each checked against its SHA-256, and never touches
   the machine's own Python. After that `Start App.bat` starts offline and
   installs nothing; when the lock files change (an update pulled from
   the repository), it says "The package list changed since Setup ran on
   this computer" - run `Setup.bat` again. **After `Setup.bat`, press
   Install Schedule once** (step 4): the button registers the Python the
   app runs under, which from source is now `.venv`'s; a job registered
   before `Setup.bat` names the machine's own Python, which holds none of
   the locked packages, and would fail every run. The packaged build needs
   neither. Keep the folder's path short — a
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
5. **Reading needs nothing installed** (decision 169). The reader -
   RapidOCR and its three models - ships inside the app and reads scans and
   photos (a JPEG, a PNG, an iPhone's HEIC, a scanner's TIFF) on the
   processor on any machine. Nothing is downloaded while it reads, ever.
   **On a machine with an NVIDIA graphics card**, copy the **graphics card
   pack** once: the folder `gpu-runtime` (about 1.6 GB, made by
   `Build GPU Pack.bat`) goes beside `tracker-api.exe`, in the app's
   `resources\tracker-api\` folder. Reading is then about two and a half
   times faster; what it reads is the same. Nowhere else: a machine
   without the card reads on the processor and needs no pack.
   - **Which reader is in use:** the run log's first line for each pass
     ends `reader=graphics card` or `reader=processor`. With the pack there
     and the card unusable - a driver too old, a card it does not support
     - the pass reads on the processor and the log's next line says why
     ("the graphics card pack is here but could not be used: ..."). That
     is not a warning: look at the machine when convenient.
   - **If the card fails mid-pass**, the page is read again on the
     processor, the rest of that pass reads on the processor, and the pass
     warns once ("the graphics card failed while reading ..."). Nothing is
     lost and nothing fails; the next pass tries the card again. If it
     says so every pass, remove the pack and look at the machine. The same
     holds when the card's driver crashes the reading outright: that
     document is read again on the processor rather than parked.
   - **A crash is blamed on a document only once it is proved.** The pass
     reads its documents in one helper process. If that process ends
     unexpectedly after it has already read another document, the document
     is read once more in a fresh one, and only a second crash parks it
     for a person ("The reader could not read this file (it stopped
     unexpectedly)").
   - **Memory is capped:** the helper process may use at most 2 GB on the
     processor, 6 GB on the graphics card. A document that needs more is
     parked for a person like a crash, and the pass carries on with a
     fresh helper, rather than the machine running short of memory.
   - **The safety stop** (decision 137) is kept between pages: no page
     starts once the page before it has overrun its minute, and a page the
     reader never finishes is ended with its whole reading at the stop for
     a file (ten minutes; a photo's minute).
   - A scan the reader cannot read at all parks for a person like any
     unreadable document; neither is filed on what its file name says,
     because the client wrote that name and the form did not (owner,
     2026-09-18).
   - **Keep the app's folder at a short path** (under about 160
     characters, such as a folder directly under `C:\`). The reader's
     libraries sit up to about 110 characters deep inside the app, and
     Windows will not load one whose whole path passes 260: from a deeper
     folder the reader cannot run, and every scan and photo waits for a
     person with "the reader could not run on this machine". The app says
     so loudly: from a folder too deep (any of its libraries past 240
     characters, counted on the real folder, so a shortcut or junction does
     not help) it shows a red banner that stays, "Move the app to a shorter
     folder, for example C:\JPA Tracker; scans can't be read from here",
     and the scheduled pass puts the same sentence in its warnings once.
6. Run one pass — **Sort & Scan** on a single engagement — and read the run
   log before trusting the schedule.

**Before the new machine's first pass**, turn the old machine's scheduled
task off, or keep that machine off the clients folder entirely: from then
on the new machine is the designated one (§1, *One machine per clients
root*), and the table at the top of §1 is changed to name it.

### Package updates and the weekly audit

The packages the app is built from are locked by version and by hash
(decision 191); nobody installs anything else. Three things keep that
current, all on GitHub, none on the office machine:

- **One Dependabot pull request per ecosystem a week** (Python, the
  Electron shell, the workflows' actions). A Python one fails its checks
  until someone moves the same pin in the matching `.lock` file, runs
  `python tools/lockfiles.py hash` and the suite, and pushes: no hash
  enters the repository unless a person fetched it.
- **The weekly audit** (`audit.yml`, early each week) asks OSV about every
  locked package. A red run names each advisory, package and version: read
  it, bump the pin, rebuild.
- **The two native engines** - `pillow` (images) and `pypdfium2` (PDFs) -
  parse every client file in compiled code, so they have a stated cadence:
  bumped within 7 days of an advisory, and at least every 90 days when a
  newer release exists. The audit fails when the first release newer
  than the pin came out more than 90 days ago - however recent the newest
  one is. A red run for either is the cadence asking for the bump.

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

And the rows the owner added after the first run on the firm's own mail
(decision 141), every one of them unticked in the wizard. Since decision
142 every catalog row is on every return and the tick is **Ask the
client**: an unticked row is never listed as needed and never chased, but a
document that arrives for it files there instead of parking. So a 1040 now
accepts the Social Security or railroad benefit statement (SSA-1099 /
RRB-1099), the 1099-C, the W-2G, the 1098-E, the 1099-Q, the 1042-S and a
client's own Schedule C income and expense sheet. The 1120, 1120-S and
partnership checklists each ask for the K-1s the business itself received,
the 1099-K and 1099-NEC it received, and the 1042-S. The trust checklist
asks for its estimated tax vouchers (the 1041-ES; an individual's 1040-ES
voucher dropped there still parks). And every checklist ends with **Z01, IRS &
State Tax Notices and Letters**. Two things to know about that last one. It
is deliberately narrow: it recognises the IRS's current notice layout - the
CP number printed beside "Tax year" (or "Tax period") and "Notice date" -
so an older-style IRS letter or a state notice still parks for you to file
by hand. And a Social Security statement no longer reaches the 1099-R row:
the SSA prints a code with "1099-R" in it at the top of the page, and the
statement now has a row of its own that wins. A corrected or amended form
(a W-2c, a 1065-X) still parks, on purpose. So does this year's own return
when it arrives with papers stapled to it - a 1065 with its K-1s, a 1040
with a W-2G - rather than filing as the K-1s or the W-2G; you see it as
"looks like" the prior-year return row, with the period quoted. And a
business's 1099-K / 1099-NEC row takes only the recipient's copy (Copy B):
the copies a business keeps of 1099s it issued park.

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
| Document | `Schedule K-1 - ` and the entity, e.g. `Schedule K-1 - Ashford Holdings LP`. This is what the client reads in the README and the letter. |
| Short name | Leave it blank. A Document written `Schedule K-1 - ` and the entity gives the short name `K-1 ` and the entity, cut to 20 characters at a whole word - `K-1 Ashford Holdings` - which names the firm's folder and the filed copies (decision 144). Type one only to name the folder differently. |
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

- **A household the pass stopped with "names … for a step (…), which is
  outside the places a step of this return may touch"**
  (`tracker.filer.OP_OUTSIDE`, decision 180): the return's record holds a
  step the tracker did not write - a copy of the record restored over a
  newer one, a line another machine wrote, or a hand edit - pointing
  outside that return's own folders. The word in brackets says which way
  it is outside (decision 187): `absolute` (a drive, a share or a full
  path), `above-root`, `not-a-place` (inside the clients root but in none
  of this return's folders), `other-household` or `other-year` (a write
  into another household's client folder or another year's `_Opened`),
  `client-tree` (a removal naming a client's original or inbox - the
  tracker only ever removes its own copies), `blank`, or `not-a-return`.
  "… would be copied to … with no fingerprint to prove the copy against"
  (`tracker.filer.COPY_UNPROVED`) is the same kind of line: a copy whose
  source is not there to be fingerprinted. (An interrupted copy an earlier
  version left without a fingerprint is proved against the original and
  finished by the next pass; "… could not be read just now …, so no copy
  was made" is an original a sync client held: the original is kept in
  the year's folder and waits in Needs Review for a person to file, and
  nothing in the record needs checking.) The
  pass moved, copied and removed nothing for it, and every other household
  was sorted as usual. Do not edit the record by hand: say which return and
  which path, and have the record checked
  (`python -m tracker.store <store> check <clients root>`) before that
  household is sorted again.

- **A household the pass stopped with "line N of the record is malformed
  (…)"** (`tracker.store.MALFORMED_LINE`, shown as "the record could not be
  read"; decision 187): the record holds a line the tracker will not obey.
  The words in brackets say which field and which kind of problem, never
  the value: a value outside the editor's bounds ("must be a whole number
  from 1 to 9999", "must be a date written YYYY-MM-DD", "must be true or
  false", a Date Pattern that "repeats something that itself repeats",
  "could try too many ways to match one line" or "has more than 8 variable
  repetitions"); a line naming "an event this version does not know"; a
  step "outside this return's places"; a household or return label that
  "is not one folder name"; or a line stamped in a form the tracker never
  writes. Nothing was
  moved, copied or removed for that household, and every other household
  was sorted as usual. Do not edit the record by hand: say which return and
  which line, and the store check
  (`python -m tracker.store "<the app folder>" check "<clients root>"`)
  names every such line in every return.

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
not. Sixty-one of the hundred and seven shipped rows are named. For a named
request the name must confirm or the document parks; for an unnamed one a
missing name is nothing at all and the keywords file it as they always did. Either
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
