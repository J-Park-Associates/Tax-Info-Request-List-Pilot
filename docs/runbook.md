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
it. There *is* one database — `tracker.db`, in the app's data folder on
the designated machine (`%LOCALAPPDATA%\tax-document-tracker`, decision 186) —
built from the ledgers in the folders, never synced
and never opened by a person. Beside it sits a second, small file,
`record-heads.db` (decision 159): this machine's note of how far every
return's record went when it last wrote or read it. It is what lets the
app notice a record that came back shorter, reordered or rewritten -
a sync client restoring an older copy, a careless hand edit - instead of
quietly rebuilding from it. It is never synced either, and it survives
deleting `tracker.db`. A third, `firm-view.json` (pilot P120), keeps the
Overview's last answer for each household, so the firm pages open in about
two seconds instead of reading every return again: like `tracker.db` it
holds household names, return folders and the names of files waiting for a
person, and it is never synced. A household whose folders changed since is
read again - "changed" meaning a file added, removed, or saved at a new size
or time; a record put back with its old size and time (a backup restore that
keeps times) shows on the next day's first Overview, which reads every
household again anyway (pilot P212); deleting the file is always safe (the next Overview reads every
household once, a few seconds longer). Every scheduled pass over the saved
clients folder ends by asking the Overview once itself, after its run log
line and its page are written, so this file is ready before anyone opens the
app: the first Overview of the day, after the morning's scheduled pass, opens
in about two seconds (pilot P201). A Sort leaves it to the app, which asks
the Overview the moment the Sort ends (pilot P218). Setup asks it once at
its end too, so the first Overview after an install or an upgrade opens at
once. The first Overview reads every household, with its count on screen,
only when that step could not make the Overview ready, or after an update
from source. A pass someone stopped asks nothing: Stop means stop.
When the app opens, the Overview first shows the counts this file last
held today, greyed and marked "Updating, as of" the time it was last
written, and swaps in the fresh counts the moment they arrive (pilot
P229): never yesterday's, never after a program update, never for another
clients folder, and never while any household is missing from the file -
then it simply waits, as before. Every button reads the return afresh, so
nothing is ever done on a marked count; if the fresh check fails, the
marked counts are taken down and the failure is shown with Retry.

A fourth, `page-rows.json` (pilot P227), keeps what the practice page
(`status.html`) last read from each return - its counts and the files
waiting for a person - so a Sort & Scan, which still draws the whole page
before it answers, reads again only the records that moved since: each
kept line is used only while that return's record is provably unchanged
(the record's own fingerprint of its history), and every line is read
again on the day's first page and after every program update. It holds
client file names, so like the others it is never synced; deleting it is
always safe (the next page reads every return once).

**The app's data folder is private to one Windows account.** `tracker.db`
holds every client's index rows, and it lives in
`%LOCALAPPDATA%\tax-document-tracker` (decision 186): the account's own local
application-data folder, which Windows lets only that account, the machine's
administrators and the system read, and which is never synced and never
roams. The scheduled task's file (`tax-tracker.xml`) sits there too. The
app's own folder holds the program and `settings.json` — the clients folder,
the firm's name and its telephone number, nothing about a client. Run the
app and the schedule as the same Windows account: another account on the
same machine keeps a database of its own, built from the ledgers on its
first pass (slow once, never wrong). Start the app from the
Start menu or its shortcut. A program started from inside another program's
window - some AI assistants among them - can be given a private copy of this
folder by Windows; the app refuses to run that way and says so on its first
screen. If Windows will not let the app list the folder where it keeps those
copies (`%LOCALAPPDATA%\Packages`), the app cannot tell, so it refuses too and
its first screen names that folder; let the account read it. Nobody opens, copies or backs up the
data folder; the ledgers are the backup. A reading's temporary files, if a library ever
writes one, go to a folder of that reading's own in the data folder
(`scratch`), removed when the reading ends — never the machine's temp folder.

**What the data folder does not cover** (decision 186, SPEC-186 §10). It
moves client data off the program's folder, the checkout, removable media
and the temp folder; it is not a lock. It is not encrypted, and anything
running as the schedule's Windows account can read it — which is why the AI
tooling runs under another account. Registering the schedule refuses a program on
what Windows *reports* as removable, network or unknown: an external hard disk,
a `subst` letter and a mounted VHD all report a fixed disk and pass, and a
job installed from a stick before 186 keeps running from it until the
schedule is registered again from the copy on the disk - `Setup.bat` there,
or **Repair the Schedule** in that copy's app (decision 209) - and the app's
first screen says so every time it opens from the stick. A data folder set with
`TRACKER_DATA_HOME` is trusted to be where it says, within the two checks,
and one junctioned elsewhere is judged by the drive its own spelling names.
A reading's `scratch` folder catches what a library writes *through the
temp folder*; a library that writes to a path of its own choosing is not
caught. A killed reading's folder lives until the next reading starts, and
one whose process number Windows reused lives until that process ends.
`TRACKER_STORE`, which points the app at another database, is held to
the same checks — a whole path, not inside the program, on a fixed disk —
and the store check refuses a copy inside the app's own folder. A `--log`
file and the scheduler's `--out` file are a person's explicit choice and go
where they are named: name a place in the data folder.

**If the data folder cannot be had** (`LOCALAPPDATA` unset or not a folder,
a bad `TRACKER_DATA_HOME`, a data folder not on a fixed disk), a pass files
nothing — the database and the run log both live there. It is not silent:
it writes the status page in the clients root, if the root can take one,
with the one problem "Data folder problem: …", and ends with a non-zero
Last Run Result; the app's first screen says why in its red banner. The page lists no return that morning, because each return's line
is read from the database. The residual risk: a clients root the pass
cannot reach at the same time leaves only Task Scheduler's Last Run Result.

**A return the store refuses as "changed behind the app's back".** The
store keeps a fingerprint of every line of a return's record it has read
(decision 137). If a sync client or a person rewrote or reordered the record
while keeping its length, the pass and the app refuse that return, apply
nothing and say so. Run the store check (`python -m tracker.store "<the app folder>" check "<clients root>"`)
to see it named, then follow **§6, *When a record needs recovering***:
`recover` for that return first, which saves both copies and shows the
lines that differ, and only then, if a person agrees, the rebuild. A plain
`rebuild` now refuses a return whose record does not match what this
machine last saw, because rebuilding from it would silently lose the lines
that went missing.

**The record check after every install and upgrade runs itself** (decisions
187 and 209). `Setup.bat` runs the after-install step as its last step, and
the app runs the same step at its first start after the program changed
(the packaged app included, which has no Setup). In the app it runs in the
background: the first screen appears at once, and the notice below appears
when the check finishes - on a streamed Drive folder the first start after
an upgrade can take a minute or two to check every record. It judges every line of
every return's record by today's rule, so a line an earlier version
accepted that the rule now refuses - a Date Pattern that could run away, a
step outside its return's folders, a value of the wrong kind - is named on
the day of the upgrade: at the end of Setup, and in a notice at the top of
the app's first screen headed *Setup Needs Attention*. The
notice stays until a later run finds nothing; it cannot be dismissed,
because the finding is true until the record is repaired. A return it
names as "malformed", or as "changed behind the app's back", is shown
to Jason before that household is sorted, and repaired the way any such
line is repaired (section 9); until then its household stops with the same
sentence and the rest of the practice runs as normal - the pass judges
every line an earlier version applied again under today's rule, once per
return, so an old line stops its household exactly as a new one would
(decision 209, R3b). Any other line the check names (a record that is gone,
a store that disagrees with its record) is for a person to look at and
does not stop anything by itself. The notice counts the records it
judged; a store that holds none yet says so rather than "nothing to
repair". A finding is not a failure: Setup still
finishes. If the step itself could not run - the store would not open, the
settings could not be read - Setup says so in one sentence and the app
tries again at its next start. On the computer that runs the schedule,
every start also asks Windows whether the scheduled task is still there:
one that an uninstall (or a person, in Task Scheduler) deleted is
registered again at that start, with no Repair (P198). The store check
below is the same check, for a deliberate look.

**The pilot's installer runs the same step** (pilot P218). Before it offers
to launch the app, the pilot's installer runs the after-install step while
its window is still on screen ("Preparing Overview..."), and the step's
last job makes the Overview ready, so the first Overview after an install
or an upgrade opens at once instead of reading every household. It never
fails the install, but it says so in a small window when something went
wrong:

- *"...the Overview could not be prepared..."* - the program is installed
  and set up; only the Overview's saved copy could not be made. The first
  Overview reads every household and says how many it has read. Nothing
  else needs doing.
- *"...its setup step could not finish..."* - the app runs the step again
  at its first start. If its notice then names a problem, it is one of the
  ones this section describes.

A silent install shows neither window.

**One waiting helper in Task Manager is normal** (pilot P220). While the
app is running it keeps one process of its own started and waiting for the
next click - `tracker-api.exe` in the installed app, a `python` process
when it runs from source - so a click does not wait for a program to
start. It uses no processor while it waits, holds no client file open,
and still does one thing and ends: each click is handed to the waiting
one, and another is started to wait in its place. A Sort always starts a
process of its own. When the app quits, the waiting one is ended with it;
one still there after the app has closed (other than a scheduled pass
that is running) is worth a look.

**The clients root is a folder of clients, and only that.** The app refuses
the system drive's root (`C:\`), the app's own folder, the folder holding its
settings and store, and any folder that holds one of them, and says which
(decision 137): a root like that would be walked on every scheduled pass and written
into. Another drive's root is fine — a drive letter mapped to the clients
share is a real root.

**The clients root must be on a Shared Drive, not in My Drive.** In My Drive
a client owns what they upload: they could delete a document the app has
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
  emptied folders are removed. Its row keeps the folder in a column of its
  own, **Client's Subfolder** — `Bank statements\2025` — which the Status
  Report shows and the review row says as `api.CAME_FROM_SUBFOLDER`
  (*came from the client's subfolder 'Bank statements\2025'*), so you can
  still see how the client had sorted it. It is ours, in the record; the
  client is never told it. Since decision 190 it is never part of the
  Reason: a folder the client called "not allowed" once read as the file
  type being refused.
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
  folder anyone makes inside `Prepared` is theirs: the app files nothing
  into it, counts nothing in it and moves nothing out of it, and every pass
  names it once on the run - *"<folder> is a folder inside Prepared. The
  app files into Prepared itself and counts nothing in this folder."* A
  return made before decision 168 keeps its old request folders, and each is
  named that way. What sits in them is not counted, so such a return reads
  Missing for every document in its old folders, and its letter would ask
  the client for them: set it aside before its letter is drafted, and make
  it again. A file in
  `Prepared` whose name begins with no request's identifier is named on the
  run too, and not counted.
- The inbox holds one file of ours, `_README.txt`, which the app writes
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

**Folders the app leaves alone.** The app reads that layout and no
other. Anything else under the root — a stray folder beside the two trees, a
household with no record, a folder where a year should be that is not four
digits, a year folder with no return in it, a folder from before September
2026 holding a `_manifest.xlsx`, a folder Windows will not let it list, a
client folder no household owns, a folder named in a way the app does
not accept for a household or a return — is
**listed with one sentence saying why, and left alone**. Nothing is renamed,
nothing is moved, nothing is deleted. The list is at the bottom of the status
page, in the app as the **Folders Skipped** notice (a count, with **Show**,
which opens the list of folders with a two-word reason beside each name:
Unknown Folder, Old Layout, No Household, Unowned Folder, Name Refused, No
Return, Cannot List, Look-Alike Folder, Old Workbook or Bad Year; the long
sentence goes to the error log), and at the end of every command line pass,
under **Folders the app leaves alone**. The app's list is as the app
last walked the root: when it started, at its last sort (the **Sort** icon
next to the search box, or Tools, Sort Now), or when it last created,
rolled forward or retired a return, accepted a folder's name, changed a
household, or had its clients folder set. So a folder made by hand shows
there after the next sort, or after **View, Refresh** (F5), or when the app
is started again. Of the client tree
only the first level is looked at, by name: nothing inside a client folder
no household owns is read. A household's client folder is the one named
exactly as the household, case aside; a folder that only *looks* like it -
a letter from another alphabet, a second space - is listed as *a look-alike
of the client folder of the household …* and nothing in it is read, so a
client who uploaded into it is found from that list, never silently. A folder where a household would be with no
household record is left alone and the app will not set a household up over
it (*"sits where a household would but holds no household record; left
alone - the app will not set a household up over it, so move it aside
first"*): move it aside, then set the household up in the app.

The app will not adopt one either. Creating a household whose folder is
already there without a record is refused before anything is written, in
these words (decision 137): *"A folder named '<name>' is already there and
the app did not make it. Choose another name, or move that folder aside
first. Nothing was changed."* And a create that fails part way removes only
the folders it made itself — never one it found.

There is no migration and no importer: a folder from an older shape is set up
again in the app, and the old one is left where it is until somebody deletes
it by hand.

**The folder is the name** (decision 188). A household is its folder's
name, and a return is its folder's name under its year folder; what the
record says about them is a claim the app checks. Rename a household or
return folder in Explorer, or drag a return into another household, and the
household is **paused**: the pass sorts, lays out and drafts nothing for it,
and every one of its returns shows red on every pass with this sentence
until somebody acts - *"Paused: this folder's name and its record's name
disagree. Nothing is sorted, laid out or drafted for the household until a
person opens it in the app and accepts the folder's name, or gives the
folder back the name its record holds."* **Roll Forward…** and **Add a
Return…** (the Household menu) are greyed for it, and the app and the command
line refuse both with the same sentence. The household is marked on Households
and on Overview with *Two Years Open; Sorting Paused* when the cause is two
open years.

- **When the move was meant** - a return dragged into a household of its
  own when a family separates - open the household in the app and press
  **Accept the folder's name**. It writes one dated line saying so on each
  record that claimed the old name; nothing is moved or renamed.
- **A return moved under another year** is never accepted, and the household's page
  shows no button for it: its year is its record's. Move the folder back
  under the year its record says; a return in the wrong year is retired and
  made again.
- **A household that has received a document is not renamed this season.**
  Its originals rest under its client folder of the old name, so the app
  refuses to accept a new name for it - for the household or for any one of
  its returns; give the folder back its name. The
  same for its client folder: if `Clients\<name>` of a household that was
  shared, or that holds originals, disappears, every run of the household
  fails with *"`Clients\<name>` is missing. Was the household renamed or
  moved? Give its client folder back the name `<name>`."* and nothing is
  made again under the old name - not by the pass, not by a new return
  into the household, and not by **Roll Forward…**, which all refuse with that
  sentence.
- **Never copy a household folder.** Two folders that claim one household -
  a copy, or two names that read as one - stop both: *"Two folders claim
  the household `<name>`: `<a>` and `<b>`. Keep one; a copy of a household
  folder is never a second household."*
- **A household whose `_ledger.jsonl` is gone** while its returns still hold
  theirs fails the pass: *"The household record `_ledger.jsonl` of
  `<folder>` is missing. Restore it from Drive's trash or version history;
  do not create the household again."*

**Two files sit in an engagement folder, and only one of them is yours to
open:**

| File | What to do with it |
|---|---|
| **Status Report.html** | **Open this one.** Double-click it; it opens in the browser. Redrawn by a pass whenever anything on it changes (its Generated time is when it last changed), so editing it is impossible — there is nothing in it to edit. |
| `_ledger.jsonl` | Never open it. It is the machine's own record of what it decided — the audit trail of every document, every status, and every edit you make to the request list. |

The request list is edited in the app — **Edit Request List** — and nowhere
else. The fourteen columns you edit there (`tracker.manifest.HEADERS`) are Identifier, Document, Period,
Expected Count, Allowed Extensions, Min Size KB, Required Keywords, Any
Keywords, Date Pattern, Manual Override, Override Reason, Named, Asked and Short name. Each row shows the
columns a preparer changes, and the routing columns (Identifier, Period, Allowed Extensions, Min
Size KB, Required Keywords, Any Keywords, Date Pattern, Named, and a catalog row's Document) sit in
the editor's one **Advanced** switch — hidden until switched on, never
dropped: a save carries every column. Closing the
editor with changes not saved asks first. **Each request's status,
Received Date, File Count and Validation Notes are on the Status Report**,
not in the editor. The engagement's details — client, share link, due
date, sender, firm, reminders, active — and the **people** the return is
for are edited in the same place.
The editor keeps each value inside the bounds the app will read back
(decision 187): Expected Count is a whole number from 1 to 9,999, Min Size
KB from 0 to 1,048,576, a date is a real date between 1900 and 2100, and a
Date Pattern is at most 200 characters with at most eight variable parts
(`?`, `*`, `+`, `{m,n}`), of which at most three repeat more than once, one
at most is open-ended (`+`, `*`) and the rest at most `{…,20}`. No
repetition may sit inside another, no back-reference inside one, and a `|`
not inside anything that repeats more than once (so `(?:Dec|12)?` is fine).
The app counts every way the pattern could try one line, and refuses
one with more than 16,384, or whose ways times the longest stretch of
matching each can do come to more than 200,000 (an assertion such as
`\b` counts toward that stretch). The slowest pattern found by the
reviews' attacks - `(?:1|11)?` seven times, then `(?:\d(?=\d)){35}` and
`(?:x|y)` - takes about 1.3 s on a 500-character line; the rule reads the
pattern and is not a clock; the time bound that does not
depend on analysis comes with Solution 4. Descriptions (Document, Period, Override Reason,
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
The app no longer reads it: it is one of the folders left alone, listed
with its own sentence rather than treated as an engagement, and the return is
set up again in the app (Household, **Add a Return…** with the household open,
or File, **New Household…** for a household the app has no record of;
then type or paste the rows). The workbook may be deleted once that is done.

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

### What the record says, and what the app shows

The record, the run log and `python -m tracker.scanner` keep the scanner's
own words for a request; this runbook uses them too. The app, the Status
Report and the staff lines under a draft show a preparer's word for each,
from one table in the app (`tracker.manifest.STATUS_LABELS`).

| The record says | The app shows |
|---|---|
| **Missing** | Outstanding - Asked for; nothing usable has arrived yet. |
| **Partial** | Partly In - Some of the expected files are in; the rest are still to come. |
| **Failed Validation** | Could Not Use - Something arrived that the rules could not use. |
| **Pending Sync** | Syncing - It is in; the cloud is still copying it down. |
| **Received** | Received - In, and every check passed or a person accepted it. |
| **Requested** | Not Yet Checked - Asked for; no pass has looked at it yet. |
| **Not asked** | Not Asked - On the list, not requested; filed if it arrives. |
| **Accepted** | Accepted - A person accepted it with a reason; the rules stop here. |
| **Not Applicable** | Not Applicable in TY<year> - Does not apply this year; not counted, not chased. |

Beside every request that is still outstanding the app says whose move it
is, with the one sentence behind it, from one table in the app
(`tracker.reminder.SIDES`):

| Whose move | The sentence beside it |
|---|---|
| **Client** | The letter asks the client for it. |
| **Us** | Waiting on us, not the client; the letter does not ask for it. |
| **Decide** | A person decides whether the client resends it or we fix it here; the letter is held until then. |

Requests nobody is waiting on - not asked, or not
applicable this year - are folded under **Set aside** below the table, each
under its own sub-heading.

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
  rule by rule. The first argument is the folder the app runs from, or its
  settings file: either means this Windows account's database, in the
  app's data folder (decision 186). A path to a `tracker.db` is taken as
  that file — a copy you want to ask about — except the old one beside the
  app, which is refused. Anything else — a mistyped
  folder, a file that is neither — is refused, so a typo can never create
  an empty database somewhere and check it against the ledgers. If it ever disagrees, do not
  reach for `rebuild`: run `recover` for the return it names (§6, *When a
  record needs recovering*), which saves both copies and shows the
  difference first. `rebuild` refuses a return whose record is shorter or
  rewritten since this machine last saw it; for a shorter one it lists the
  lines only the database holds (decision 188). A loss is accepted only
  for one return, by its folder's name typed exactly - `recover ...
  --accept-loss "<name>"`, or the same as `rebuild --engagement "<the
  return's folder>" --discard --accept-loss "<name>"` - after the export
  and the difference; `--discard` alone, or for the whole root, is
  refused. **An older database is set
  aside by itself** since decision 159: the app renames it
  `tracker.db.v<N>.old` and builds a new one from the ledgers (keep the old
  file until the first pass has finished), and a database from a *newer*
  version is refused with "install that version again". Either way the
  first pass after it reads every document once to fill the verdict cache
  the database also keeps.
- **Once, when decision 137 lands** (and again at decisions 142, 143, 144 and 146,
  `user_version` 13 to 16). Its database is a new version
  (`user_version` 12). Since decision 159 the old one is set aside and
  rebuilt by itself (above); before it, it was deleted by hand. The rebuild itself takes
  minutes; what takes longer is the **first pass after it**, which reads
  and OCRs every document again to refill the verdict cache - on a full
  season that can run past the scheduler's two-hour limit. A pass the
  scheduler stops keeps what it read for the returns it finished, and the
  next pass goes on from there. So
  do it outside office hours, and if one return matters first, rebuild it
  alone ahead of the rest with `--engagement "<the return's folder>"`. It
  happens once; later passes read only what is new.
- **Decision 204** (`user_version` 17) needs nothing: a version-16
  `tracker.db` is upgraded where it stands the first time it is opened -
  one new column, nothing deleted, the verdict cache kept - so the pass
  after it reads nothing again. Only an older one is set aside and
  rebuilt by itself, as above (one policy for both decisions).
- **Decision 209** (`user_version` 19) needs nothing either: a version-18
  `tracker.db` gains one column where it stands (a version-17 or version-16
  one takes decision 190's and 204's in-place steps first, the same way), and the first time each
  return's record is read after it - by the scheduled pass, or by the app
  when it first lists the clients folder - every line the record already
  holds is judged by today's rule, once per return. Measured on returns of
  two hundred lines: about three seconds for a hundred returns when one
  line in ten is a request-list edit (each carries the whole list), and
  about twelve when every line is one; it is processor time, not reading
  from Drive. So the first screen after this upgrade can take a few
  seconds to list the clients, once. A return whose old line the rule
  refuses stops, as above, and is judged again at every pass until it is
  repaired.
- **Once, when decision 169 lands** (the new reader). The database's
  version does not change, so there is nothing to delete for it (set
  `tracker.db` aside only if another decision in the same install asks).
  But every verdict on a scan or a photo was reached by the old reader, so
  the **first pass after the install reads every scan and photo again** -
  slow once, as above. On the office machine, copy the graphics card pack
  beside the app once (§6, step 5). And delete the folder `ocr-scratch`
  beside the app if it is there: the old reader kept the page it was reading
  in it, the new one writes nothing, and nothing empties that folder any more.
- **Once, when decision 186 lands** (the data folder). The database moves to
  `%LOCALAPPDATA%\tax-document-tracker` and nothing is carried over: the
  first pass builds it again from the ledgers and reads every document once
  to refill the verdict cache — slow once, as above, so let it run outside
  office hours. Its version does not change. Until you delete them, the
  app's first screen names what the old version left beside the app, in
  two sentences. **To move, never to delete:** the record checkpoint
  `record-heads.db` with its `record-heads.db-journal`, `record-heads.db-wal`
  and `record-heads.db-shm` if there are any, a
  copy of it renamed `record-heads.db.damaged` or set aside as
  `record-heads.db.v1.old`, and a `recovered` folder (decision 159) - the
  checkpoint cannot be made again, a journal can hold its last write, and
  the old copies and the records in `recovered` are evidence. **Setup moves
  them** (decision 209): its after-install step, whose first job this is,
  moves `record-heads.db` and its journal and write-ahead log together, the other copies and
  `recovered` from beside the app into `%LOCALAPPDATA%\tax-document-tracker`
  under their own names, before it registers the schedule; the packaged
  app does the same at its first start after the upgrade. The checkpoint,
  its journal, its write-ahead log and shared memory, and a `.damaged` copy
  move as one: a journal or write-ahead log found without its checkpoint
  beside it, or a data folder that already holds any of them, moves nothing - a journal beside a checkpoint that is not its own
  would be replayed into it. It never overwrites: if the data folder
  already holds one of those names, nothing moves, and the step says so in
  one sentence - then, and only then, a person acts, as below. It moves nothing on the delete list. Until
  `record-heads.db` is moved the app makes no new checkpoint - one
  would trust every record as it is that day (*the moment of trust*, §6) -
  so nothing is written: the pass serves no household, writes its page
  and its log and says *No record checkpoint was made* (reason
  `checkpoint-left-behind` in the last-pass line), and the app refuses to
  open a return or run a button that writes, saying what to move and
  where. The move ends that. If the data folder already holds a
  new checkpoint anyway (made before this refusal existed, by the first
  pass or by the app opening any return), do not copy the old file over
  the new one: move the old one
  into the data folder under a new name with today's date, keep it, and
  treat that day as the moment of trust (§6). **To delete:** `tracker.db`,
  `tracker.db-wal`, `tracker.db-shm`, a `tracker.db.v<N>.old` (and its
  `-wal`, `-shm` and `.1` copies) a version change set aside, `pass-order.json`, `last-pass.json`,
  `after-install.json` (decision 209),
  the error log `tracker-errors.log` and its copies `tracker-errors.log.1`
  to `.3`, a `passes` folder (decision 193), an `ocr-scratch` folder, and
  the old `runs.log` in the clients folder, which names clients. Nothing
  deletes them for you: delete them. The app never writes an error log
  beside itself: with no data folder, a failed command's message says just
  "App Failed", and its details are saved only in a small error.log
  file in the app's own local folder, `%LOCALAPPDATA%\Tax Document
  Console` (it does not roam with a profile, and it is not the data folder),
  never shown. Help, Open Error Log opens it.
  **The fallback error log's place (ruling 22):**
  `%LOCALAPPDATA%\Tax Document Console\error.log`, normally
  `C:\Users\<user>\AppData\Local\Tax Document Console\`, with one
  older copy `error.log.1`. (The app's normal error log is the
  `tracker-errors.log` in the data folder, above.) Uninstalling the app leaves that folder behind.
  The log can contain client names, so when the program is removed for good
  (or the PC is retired) delete the folder by hand. A PC upgraded from the
  earlier name may still hold an earlier log in
  `%LOCALAPPDATA%\Tax Document Tracker Pilot\`, which a person may delete
  the same way.

There used to be a second one, a comparison flag on the ledger's own
statuses against the request list's. There is nothing left for it to
compare: the request list holds no status.

The folder that holds every engagement is typed once, in the app, on first
launch. It is written to the settings file beside the app
(`tracker.settings.SETTINGS_FILENAME`), and the app, the schedule and every
command read that one value afterwards. From a terminal the same thing is
`python -m tracker.settings <folder>`.

**One machine per clients root — today's rule.** The schedule,
the app's **Sort**, filing, every save in the app and **Roll Forward…** happen
on the designated machine (the table at the top of §1) and nowhere else. The only
thing that stops a scheduled pass and a click in the app from moving the
same client's files at once is a lock file
(`tracker.locking.LOCK_FILENAME`), and a file a cloud client copies between
two machines is not a lock — both machines can create their own before
either copy arrives. From another desk, one way to work at the designated
machine today is Remote Desktop into it. Which computer runs the schedule
is written in one file in the firm's tree,
`J Park & Associates\_Scheduling computer.txt` under the clients root
(decision 209): the first Windows computer to set the root claims it, and
the app registers the schedule on that computer only. **When upgrading to
the version that holds decision 209, upgrade the office computer first and
start its app once before any other desk's**: every desk that once pressed
Install Schedule has a root set, and whichever starts the new version first
claims the schedule - if that is not the office computer, the office
computer then removes its own task. If another desk claimed first, press
**Repair the Schedule** on the office computer and answer yes when it
offers to move the schedule there (§6). Any other machine may open a
return's Status Report and read it; it does not run the app against the
clients folder. This is the rule for now, while the owner decides how
several machines may write; this paragraph changes when that decision
does, and nothing else in these pages restates it.

The schedule is one daily task. **Its time and how often it repeats are a
setting on each computer** (pilot P21): the **Schedule** button in the app
(after **Edit Request List**) turns it On or Off, sets the time of the
first run, and picks how often it repeats - once a day, or every 30
minutes, every hour, every 2, 4 or 8 hours. Until someone saves the
setting it is on, from `tracker.scheduling.DEFAULT_START`, repeating every
`tracker.scheduling.DEFAULT_REPEAT_MINUTES`. The choice is kept in
`settings.json` beside the app, per computer, and **every** way the task
is registered - `Setup.bat`, the app's first start after an upgrade,
saving the clients root, **Repair the Schedule**, the move to another computer (§6) -
registers the saved choice, never the defaults. **Off** removes this
computer's own task and leaves the designation file alone: turn it off on
the designated computer and no computer runs the schedule, which the app
says in one sentence; Sort still works by hand. A hand-edited value in
`settings.json` that the setting does not allow is refused in a sentence
naming the file and the key, at the first screen's notice, and no task is
registered until the choice is saved again with the button. Each pass
files what arrived, scans it, and on the draft day writes the chase emails.
Nobody registers it by hand (decision 209). `Setup.bat` runs the
after-install step last, the app runs it at its first start after an
upgrade, and saving the clients root in the app runs it - and it registers
the task only on the computer the designation file names (above). The
first Windows computer to run it with a root set writes its own name into
that file; any other computer registers none, and removes a task of its
own if it had one. The job names the app's settings folder, never the
clients root, and reads the root from `settings.json` there at every run
(decision 131), so changing the root in the app is all it takes for the
schedule to follow. **Repair the Schedule** in the app runs the step again
on purpose, for a task that was deleted or broken, registering the saved
choice; its banner says what it did in one sentence. The file is detection, not a lock: two desks that
set the root before the sync client carries the first claim can both
claim, and Drive then keeps one file and renames the other, which nothing
reads. The one-machine rule above still holds. A computer whose own
name cannot be written in the file (a name with a space or an accent) is
told so in one sentence and registers nothing.
Registering refuses, with a sentence saying why, when the app is on a
removable drive, a network drive or one Windows cannot name (decision 186):
the schedule runs whatever program sits there on every pass, so it must be
on this computer's own disk. The app's first screen says the same for as
long as it runs from such a drive.

**After the rename (P155).** Before Pilot 0.3 the app was called Tax
Document Tracker Pilot, the earlier name; it is now Tax Document Console.
Installing 0.3 over the earlier name upgrades it in place, in its own
folder `%LOCALAPPDATA%\Programs\Tax Document Tracker Pilot` (a new install
goes to `%LOCALAPPDATA%\Programs\Tax Document Console`), replaces the
earlier Start menu entry and desktop icon, and keeps `settings.json`
beside the program. The data folder keeps its name,
`%LOCALAPPDATA%\tax-document-tracker-pilot`, and nothing in it moves; the
column widths (and, since P199, the order each list was left in) stay
where they were, in `%APPDATA%\Tax Document Tracker
Pilot` (the earlier name, kept on purpose). The first start after the
upgrade, or `Setup.bat`, runs two carry-over jobs in the after-install
step, and each says one sentence every time, first among the step's lines:

- **The settings file,** copied from the earlier program folder only when
  this program has none (the earlier name uninstalled, then 0.3 installed
  fresh): "Run from source: the settings file is the checkout's own, so
  nothing is carried over from the earlier name." / "The program was
  upgraded in its own folder, so its settings file stayed where it was." /
  "This program already has its settings file (<file>), so the one left by
  the earlier name (<earlier file>) was not used; it was left where it
  was." / "There was no settings file from the earlier name to carry
  over." / "Copied the settings file left by the earlier name (<earlier
  file>) to <file>, so the clients folder and the schedule choice carry
  over; the earlier file was left where it was." If the copy fails: "The
  settings file left by the earlier name (<earlier file>) could not be
  copied to <file> (<problem>); nothing was changed. Start the app: it
  tries again at launch."
- **The scheduled task** under the earlier name, removed once the new
  task, Tax Document Console, is registered: "Removed the scheduled task
  under the earlier name, Tax Document Tracker Pilot; the schedule now runs
  as Tax Document Console where it is on." / "There was no scheduled task
  under the earlier name, Tax Document Tracker Pilot, on this computer."
  Only the installed program removes it; the app run from source says "Run
  from source: the scheduled task under the earlier name, Tax Document
  Tracker Pilot, belongs to an installed copy, so it was left alone." If
  the new task could not be registered the earlier one is kept, so the pass
  still runs: "The scheduled task under the earlier name, Tax Document
  Tracker Pilot, was kept because the new one could not be registered
  (above); the app tries again at its next start." If it cannot be
  removed: "The scheduled task under the earlier name, Tax Document Tracker
  Pilot, could not be removed (<problem>); until it is, both tasks start
  the pass, and the second finds the first's lock and moves nothing. Start
  the app: it tries again at launch, and Repair the Schedule tries at
  once."

A failed carry-over is a failure like any other: the first screen's notice
says it and the next start tries again. The firm's production product,
Tax Document Tracker, its task and its folders are never touched. An
earlier fallback error log may remain in `%LOCALAPPDATA%\Tax Document
Tracker Pilot\` (above).

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
and drafts the week's letter if it is owed. The app's **Sort** icon (Run now) is
the scheduled pass, started by the app for one household (decision 203):
the same runner, the same fifteen minutes and the same sentence when they
run out, and it leaves the same line in the run log and redraws the same
page. The app does not wait for it. The button becomes **Stop**, the
household and the file it is on show beneath it, every other return keeps
working, and the return redraws when the pass ends. Nothing cuts it off
before the run limit (`tracker.locking.RUN_TIME_LIMIT_SECONDS`, two hours).
**Stop** ends it at the next file — what it did is recorded and the rest
waits for the next pass — and closing the app does the same: its lock is
let go, and the next pass carries on. If a pass already holds the
household, the app says so and starts nothing. Households are
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
scheduled pass stops with *Clients folder problem*. The records are
untouched - every return is keyed by its path below the root - and the
answer is two steps, on the designated machine:

1. **Set the root again in the app** (or
   `python -m tracker.settings <folder>`). The schedule follows by itself;
   it reads the root from the settings file at every run.
2. **Tell the record checkpoint** (decision 159). This machine's
   `record-heads.db` belongs to the root the settings named on its first
   real pass (a folder typed by hand never claims it), and until it
   is told, the pass - whether the schedule runs it or a person types a
   folder by hand - and every button that writes refuse with *this
   machine's record checkpoint belongs to <old folder>; this would work in
   <new folder>*. (One client's folder inside the root is not refused.) Once you are sure the root really moved (and this is not
   a second copy of the tree), run, with the app's data folder (where
   `record-heads.db` sits since decision 186) and the new root:

   ```
   python -m tracker.checkpoint "%LOCALAPPDATA%\tax-document-tracker" move-root "<the new clients root>"
   ```

   Nothing else changes: the checkpoint, like the record, names every
   return by its path below the root. A *copy* of the tree put where the
   old root was is not a move; its records are behind the checkpoint and
   the practice page says so return by return.

**The root is the folder that holds both trees**, `Clients` and
`J Park & Associates`, side by side. Choosing one of the trees itself, or a
household inside one, is one level too deep and is refused with the root
to choose instead: *`<folder>` is inside the `Clients` folder of the
clients root `<root>`; choose `<root>`* (decision 188). The root is checked
again every time it is read - by every command in the app, by the pass, and
by every command line - so a root that became one level too deep after it
was saved (the trees moved around it) is refused with *Clients folder
problem*, and the app asks for the folder again.

A longer root leaves every return less room: Windows opens a path of
`tracker.layout.MAX_PATH_LENGTH` characters at most, and a working copy
deep in a return with a long household name and a long return name can
pass it. Since decision 144 a request's working copies are named by the
request's **short name**, twenty characters at most, where the full title
used to appear twice - so the firm's own root,
`G:\Shared drives\Income Tax Clients` (35 characters), refuses none of the
39 returns of the owner's intake test with the request list's default rows asked
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
under *Names shortened to fit*, every return the new root
leaves short, with the number. Nothing is refused - the firm's data is
where it is - and the pass copes: it cuts the document part of a working
copy's name to fit, keeping the request's identifier, the period, the
`(2)` of a series and the extension, and records the name it wrote. A
reader's limit counts too: Excel opens a workbook from a path of at most
218 characters (Microsoft's own figure), so spreadsheet copies - `.xlsx`,
`.xlsm`, `.xls`, `.csv` - are cut to fit 218 (`tracker.layout.OPEN_LIMITS`,
the owner's ruling of 2026-09-23); creation still refuses only past
Windows's own limit.

On a Windows PC with long paths off - the Windows default
(`LongPathsEnabled` = 0) - that limit is one character shorter, 259,
because Windows counts the character that ends a path, and a folder costs
more than its own length: Windows will not make a folder of 248
characters or more, and every file the app writes passes through a
temporary name up to twenty-six characters long beside it. So there each
return's room is measured with its review folder counted that way, and a
return that does not fit says so in the room's own sentences - never as
"could not be filed (FileNotFoundError)" (pilot decision P29). The
app asks Windows which applies when it starts; nothing needs setting.

A person has exactly three levers, and every sentence the app says
about room names one of them: **a shorter clients root** (a drive letter
over a profile path, the Shared Drive's own folder over one deep inside
it), **a shorter Short name** in the editor for the request (every copy
filed from then on is shorter; the folder keeps its name - a folder made
under the full title before decision 144 keeps that name too, and takes
short copies), and **a shorter return name** at the next rollover. Nothing in the app ever renames a
folder or a filed copy to make room.

### Sharing a household with a client

The app never makes, checks or changes a share. Two grants, made once by
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
   press **Mark as Shared**. The date is recorded as the firm's word; the
   letters carry the link.

The app asks for all three in those words — once, when a household's first
return is made, and on the household's page until the third step is done. It
records only that a person said so: Drive for desktop exposes no permission
to a program, so the app cannot see a share and does not pretend to.
Nothing about filing, scanning or drafting waits on it.

Nothing is ever re-shared. A new year is a new folder under the same
household, view-only through the same grant; **Roll Forward…** changes no
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
  feeds it, so a W-2 he sends on her behalf can be filed to her return — and
  the document then rests under *her* folder, which he cannot see.

The sub-rule, in the owner's words: **a drop folder may feed a return whose
folder the dropper cannot see. Dropping does not require seeing.** That is
the point of the arrangement, and it is also why a document handed to a fed
return **moves** into that household's year folder: the dropper stops seeing
it unless they are shared there too.

What the app does and does not do:

- The document is judged against every return the drop folder feeds, its own
  and the fed ones together: the request lists accept, the name on the page
  confirms or vetoes, and exactly one return is left or the document waits
  for a person **in the household it was dropped in**. Where a document
  has come before, the records are asked for its bytes with the household's
  own returns first and the fed ones after: the record closest to the drop
  decides.
- **The pass never files into another household** (decision 204). A
  document only a fed return is left with parks here, in the household it
  was dropped in, and its original stays in this household's year folder.
  If the page names that return's person, it waits for **one click** —
  *File it under <the return>* on its row, which shows the
  requests it will be filed under. If it names nobody, it waits for the
  picker (*File under another return*). The same holds for a document sent
  again. The cost: a co-owner's document reaches the other household when
  somebody here clicks, not on the next pass — until then that household's
  status does not count it and its drafted letter may still ask for it.
- A feed is a **return line**, not a return: the household and the return's
  name, the name it keeps every year. **Roll Forward…** carries nothing about
  feeds, and a line the other household has retired is said on the return's page
  rather than quietly feeding nothing.
- The page's *Also fed by* line is drawn from what this computer last
  read of every household: when the app last listed the clients, or
  a sort or a pass ran here. A feed a person added on another
  computer is named here after the next of those. The feeds a page
  lists as its own, and every click that files through a feed, read
  the other household's record at that moment.
- Nothing is ever inferred. The app never looks at two households and
  suggests that one feeds the other, any more than it decides who belongs
  in a household. Both are a person's assembly.
- **Ownership changes are a person's too.** When somebody buys in or sells
  out, a person changes the Drive grant, changes the members in the app and
  extends or trims the feed. The app records the change and does nothing
  else about it — it cannot see a share and does not pretend to.

Every feed a person adds is warned about, every time: anyone with access to
that drop folder may drop for that return, and its documents will rest under
the folder it lives in, shared with whoever that household's page says.
Adding a return to a household is warned about too: everyone with access to
the folder will see that return's documents.

A parked document can be filed under a request of any return the drop folder
feeds — *File under another return*, in the queue. A document that names a
fed return's person has a shorter way: **File it under <the return>**, one
click, which files it under the requests that return's list accepted (a
consolidated statement with its Also Answers) and picks nothing on the page.
If the feed was trimmed or a request removed since, the button is not
offered and the row says why; use the picker, or file it here. The original moves where it
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
some Persian, Arabic and Indic names and emoji use (decision 176), and so
does every name the record keeps (decision 190): a file's, the subfolder
it came from and its review copy's are recorded without invisible or
control characters, so a direction override cannot make a program read as
a PDF. A character Windows keeps out of a folder name, which a client on a
Mac can still type, is recorded in the subfolder as `_`: a folder called
`Q1: bank` shows as `Q1_ bank`. The original in the client's folder keeps
its own name, byte for byte. A program inside an email or a zip is never taken out of it: its row
parks as `reasons.NOT_A_DOCUMENT`, with no copy.

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
yours. Its row has no **Open**: an email or a zip is opened, if at all,
on a machine with no Drive sign-in and no client folder, never this one (decision 184). Read it there, and bring any document you find back
into **this household's `Drop files here`**:
it came in this household's own email or zip, so nothing is published
anywhere new, and the next pass sorts it like any other. Never into the
client's folder for the year. Close the container with **Not requested** once you have. A
document from inside a container is never filed into another household's
return, by the pass or by **File under another return**: file it by hand
in the return it belongs to, from its own row.

The `_Opened` folder is synced with the rest of the private tree, on
purpose (the owner's decision of 2026-09-23, a named exception to decision
107's rule): a pass that recovers an interrupted filing, and a move to
another machine, both need what is in it. Do not tidy it by hand; a file
there that no row names is said on every pass until a person has looked.

### A document the app did not file

A file turns up that no row accounts for — in `Prepared` under a request's
name, in a hidden `_Opened` folder, or inside an email or a zip you have
looked into. **Confirm whose document it is first.** A file nobody can
account for is very often another client's, and a document put in a
client's folder is published to that household.

Never open it where it sits (decision 190): where it sits, its name and
the run's line say whose it is. Then:

- **It is this household's** - it came out of this household's own email
  or zip, or it is a stray in this household's `Prepared` or `_Opened` you
  know to be theirs. Drop a copy into
  **this household's `Drop files here`**, never the client's folder for
  the year: it is already this household's, so nothing is published
  anywhere new. The next pass sorts it, and if it parks it gets a row,
  with **Open** when the app read it (decision 190). Then delete the stray by hand.
- **It is another return's, or another household's.** Do the same
  there: that household's `Drop files here`, and nowhere else.
- **You cannot tell whose it is.** Leave it where it is and ask whoever
  would know. Never put it in a client's folder to see where the pass
  sends it.
- **It is not a whole document** — a partial or broken copy: delete it by
  hand, and never ask the client for it.

To read such a file, let the pass give it a row and use **Open** on its
row: the firm's review copy, marked for Protected View, offered on a row
the app read and parked for a filing reason (decision 190's
allow-list). That replaces decision 184's reading of a copy set aside by
hand (Jason's answer of 2026-09-26). A row with no **Open** - an email
or a zip, a reading the app refused, a file that is not a document -
is read on a machine with no Drive sign-in and no client folder (decision
184), or you ask the client what they meant to send.

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
  app's moved list (the only answer it offers; **Put It Back**,
  **Keep It Here** and **Send to Review** have nothing to work with and say
  so). The row stays on the record with your sentence, stops counting, and
  leaves the client's received list; the request reads Missing and the
  next letter asks the client for it. What they send is filed as a new
  arrival. Once a row is marked missing, an original you then find and put
  back at its old place in the client's folder for the year is not filed again (the
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
- **You can make it again yourself**: **Put It Back** (the `restore`
  command) on a row whose copy was deleted makes it from the original
  exactly as the pass would, and says so in the same words.

A consolidated statement's answers (decision 146) go with its copy: while
the statement's own copy is missing, not the one filed, or gone with its
original, each request it answers says `reasons.ANSWER_NOT_COUNTED` instead
of Received, and the letter holds off; the pass that makes the copy again
puts them back.

### Rolling a household into the next year

Rolling forward is done from the **household** (Household, **Roll Forward…**
with the household open), not from one return, and only once the year it
rolls to has ended: from January 2028, say, it offers **Roll forward to
2027**. It opens a dialog that shows the open year's returns,
every one ticked, each with the people it carries and the form template it
will be filled from, and the sentence saying what unticking does. The button
names the year. It rolls each ticked return into that year - its list
carried from last year, its greeting and its inbox link refilled from the
household, its own folder made under the new year - and it can only roll the
household you have open. A household that is paused, or has
two open years, has **Roll Forward…** greyed until that is dealt with.

A return left unticked is **retired for that year**: set inactive, and no
longer chased. That is deliberate — it is how the household ends up with
exactly one open year again, which is what lets the pass go on sorting one
inbox. Tick it later and roll it on its own if that changes.

**It is all or nothing** (decision 159). Every ticked return is checked
and locked before anything is written; if one of them refuses (a folder of
that name already there, a path too long, the return busy with a pass),
**nothing is rolled**, and the reply names that return and why, ending
*Nothing was rolled.* Fix that one thing - or untick that return - and
press Roll Forward again. If something fails part-way through, the returns
already rolled are undone, so the household is never left half in one
year and half in the next. Nothing under `Clients\` changes but the new
year's folder.

**One exception, said in amber.** Retiring the unticked returns comes
last, after every ticked return has rolled. A retirement is a line in that
return's record and is never undone, so if one fails the returns stay
rolled and the app shows a warning (the command line heads it *ROLLED, NOT
ALL RETIRED*): *Rolled into <year>: ... Retired: ... Not retired: ...
retire those in the editor (Active: no) so the household has one open
year*. Do exactly that: open each return it names, set **Active** to *no*
and save. Until you do, the household has two open years and the next
Roll Forward refuses.

**A return rolls forward where it sits - once its move is accepted.** When a
household separates, the way to move one return into a household of its own
is still to drag its folder there in Explorer. Its record goes on naming the
old household, so the household it now sits in is **paused** (decision 188):
Roll Forward refuses it, with the pause sentence, before anything is
written. Open it in the app and press **Accept the folder's name**; then Roll
forward puts next year's return in the household it now sits in, under its
own folder name, and next year's record names that household, so the old
household's client never sees its requests or its documents.

Roll Forward also refuses, before anything is written and with the pass's
own sentence, a household that is **stopped** - its `_ledger.jsonl` gone, or
two folders claiming it - and one whose client folder is gone when it had
one (decision 188).

On the command line the same two forms live in one command, told apart by
what you point it at:

```
python -m tracker.rollover "<clients root>\J Park & Associates\Park Family" --year 2027 --all
python -m tracker.rollover "<clients root>\J Park & Associates\Park Family" --year 2027 --only "1040 - John Park"
python -m tracker.rollover "<a return folder>" --year 2027 --form 1040
```

## 2. Every morning

**The app's window, in one paragraph.** A side panel on the left lists the
four pages - **Overview**, **Needs Review**, **Reminders**, **Households**
(Ctrl+1 to Ctrl+4) - each with a count, and the last sort's time (or *Sort
Failed*) at its foot. The path row above the page names where you are; a
household or return name in it takes you there. A return or household name
anywhere is a link that opens its page; a file name is a link that shows that
working copy in File Explorer (an email or a zip is plain text, never
opened). Right-click a row for its menu (Check…, Not Requested, Show in File
Explorer, Unfile, Mark Missing, Edit Request…); the menu bar (File, Edit,
Household, View, Tools, Help) appears when you press Alt. **Check…** and
**Draft Reminder…** open a side sheet; where older text here says
"card", read the file's row on Needs Review or a side sheet. The one **Sort** icon beside the search
box sorts the open return's household (grey on the four pages: open a household
first); the overnight sort is the schedule. A *Sort Failed* notice with no
button shows on every page while the last **scheduled** sort failed, and
clears when the next scheduled sort succeeds - the app's own Sort names one
household and cannot clear it. **Unfile** asks for an optional reason first.

1. **Read what the last pass did.** The status page every pass writes into
   the clients root (`tracker.runner.STATUS_PAGE_FILENAME`) is the one-screen
   version — which engagements ran, which need a person, which failed, and
   every parked file across the practice, newest first. A return the pass
   did not run is shown as its record stood when the pass began. The app's
   **Open Status** button opens it. The run log
   (`tracker.runner.LOG_FILENAME`), in the app's data folder on the
   machine that runs the schedule (`%LOCALAPPDATA%\tax-document-tracker\logs`,
   decision 186), says of every pass — the app's button's included — when it
   ran and how many returns it filed, parked, failed, skipped or held, with a
   short code for each kind of trouble. It names no client and no file, and
   carries no text taken from a client's document: for which client, read
   the status page. The one exception is the reader's note, when the graphics
   card pack could not be used: it is the machine's own error, word for
   word, and may name a folder on this machine. It keeps about a megabyte, in four
   files. Each pass's first line ends with which device read its
   scans and photos: `reader=processor` or `reader=graphics card` (§6,
   step 5). For one client, **open the Status Report** in that
   engagement's folder — the pass you just read about redrew it if anything
   on it changed, so it is that engagement's list, index and review queue as
   of this morning (its Generated time is when it last changed, which may be
   earlier), and the app says beside the engagement's name whether it is
   still current.

   The files a household's inbox holds that the sort leaves alone by their
   name - desktop.ini, Thumbs.db, .DS_Store, an Office lock file
   (`~$...`), anything in a sync client's `.tmp.drive...` folder - are
   counted once a pass: *N system or temporary files in the inbox were left
   alone*, on the return's line in the run log and under **Left alone in
   the inboxes** on the practice page (decision 190). It is a count, never
   the names, and nothing needs doing - unless a file you expected to be
   sorted has a name like those (a client's own `~$W2.pdf` is left alone
   as a lock file is): rename it in the inbox and the next pass sorts it.

   What the page says about room (decision 131, and *If the clients root
   moves* in §1). A return merely **short of room** is not warned at all:
   it is sorted as usual and its copies' names are cut to fit, and the
   figure - *N characters short of the room its working copies need* - is
   shown as information on the return's page in the app (there it says only
   *Names shortened to fit*) and in the reply to setting the root, never in
   the Warnings column (a warning on every pass would be a warning nobody
   reads). A **Warnings** line *N request(s) have no room for a working
   copy* (in the app, *N requests can't be filed*) does need a person: a
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
   old clients root* is a job installed before decision 131: the app
   registers it again at its next start on the designated machine, and
   **Repair the Schedule** does it at once.

   **Every logged pass says it started** (decision 189): the run log has
   a `[time] pass started` line before each pass's summary. When the next
   pass finds a *started* line with no summary after it, it says *the
   pass that started at … did not finish (it was stopped or the machine
   went off); this pass picks up where it left off* on the page, and the
   log counts it (`pass-did-not-finish`). Usually nothing to do: the pass kept every reading it finished.
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
   page could not be written (…)* is said in `runs.log` instead (as the code
   `page-not-written`), and the
   Last Run Result is `0x1`: the page you are looking at is an old one. The run log gives the pass's warnings
   as a count, `warnings=3`, and each failure, skip and pass warning as a
   code; the page and the app have the sentences. A pass the app started
   that stopped because the app closed says so as a pass warning: the code
   `pass-app-closed` in the run log, and on the page *stopped when the app
   that started it closed, after N file(s)* (decision 203).
   *the Overview could not be made ready after the pass (…)* (the code
   `cache-not-filled`, pilot P201) means the pass's last step - asking the
   Overview once so `firm-view.json` is ready - did not finish; the pass
   itself is fine and its result is not changed, only the next Overview is
   slower. It is asked after the pass's own run log line and page are
   written, so the code arrives as a line of its own just below the pass's
   in `runs.log`. Nothing to do once; if it repeats, the error log beside
   `tracker.db` says why. Right after an upgrade it can say so until the app
   has been started once, which registers the schedule again with what the
   step needs.
   **Run now** says the same: under the return's own result it lists the
   household's other returns' problems and the pass's own (the reader,
   the log, the page).

   **The last-pass line.** The app's main screen shows one line about the
   schedule (decision 159): *Last scheduled pass: <date and time>,
   succeeded.* It comes from `last-pass.json`, which the scheduled job
   writes beside `tracker.db` when it starts and when it ends; a pass given
   a folder by hand, or a preview, does not touch it (a run naming only the
   app's settings folder is the scheduled job's shape, and does).
   - **Plain:** the schedule is running. Nothing to do.
   - **Amber**, *Nothing newer for over N hours*: no scheduled pass has
     started for two missed runs of the saved interval - four hours at the
     default every-two-hours, never fewer than four, 48 hours for a
     schedule set to once a day (pilot P21); the sentence states the N it
     used. With the schedule switched off the line says so and stays
     plain: no pass is due. On the designated machine, open Task Scheduler and
     check the task is there and enabled, or press **Repair the Schedule** in
     the app. Amber also shows before the first scheduled pass on a new
     machine (*No scheduled pass has run on this machine yet*). *Started <time>, not finished*
     that turns amber means a pass was stopped part-way (the machine
     restarted, or the scheduler's time limit): the next pass finishes what
     it left.
   - **Red**, *failed (<reason>)*: the last pass stopped. The reason says
     which of the few ways it stops: the settings file could not be read,
     no clients folder is set, the clients folder was refused, it is not
     the one this machine's record checkpoint belongs to (see *If the
     clients root moves*), this machine's record checkpoint was busy
     (another run was using it: nothing to do, the next pass tries again)
     or could not be read (follow §6, *A checkpoint that will not open*),
     the folder could not be walked, the pass ended
     with a problem - a return that failed, or a run log or page it could
     not write (the practice page and the run log name it) - or a
     household has not been served two passes running (the page names it
     and why). When the pass reached the clients folder, the run log has
     the same line, with the kind of fault and never its words. The line
     stands beside the page and the run log, which are written every pass
     (decision 189): it is the one of the three the app shows, and the
     only one that can speak when the pass stopped before it found the
     clients folder.

   **Records that need a person.** When there is something in it, the
   practice page has a section of this name (decision 159), and the run log
   a line *records that need a person: N copy(ies) beside a record, N
   line(s) from another machine, N record(s) refused*. On a good day it is
   not there at all. Each sentence means:
   - ***No household was served this pass: …***, first in the section: the
     pass could not ask this machine's record checkpoint whether the
     clients folder is its own, so it filed, scanned and drafted nothing.
     The words after it say which of two things it was. *…is busy -
     another run is using it*: something else (the app, `verify`, an
     `acknowledge`) held the file at that moment; nothing is wrong, do not
     set the file aside, and the next pass tries again - if it says so
     twice running, tell Jason. *…cannot read this machine's record
     checkpoint*: the file is damaged; follow §6, *A checkpoint that will
     not open*, today.
   - ***Lines from other machines could not be listed this pass: …***:
     the same checkpoint could not be read for the list below; the lines
     are not gone, and the next pass that can read it names them again.
     The words after it say busy or damaged, as above.
   - ***a copy beside a record or its lock, left by a sync client or a
     second machine***: Google Drive or a second computer saved a second
     copy of a return's record, or of its lock file, next to the real one
     (a name like `_ledger (1).jsonl` or `_ledger_conflict-*.jsonl`). **Never delete
     one**, now or later. Tell Jason; a person compares the copy with the
     record and decides which is right, and the copy is kept even then.
   - ***line N was written on <computer> (<time>)***: a line in this
     return's record was saved by another computer, not this one. Jason
     decided on 2026-09-26 that such a line is named here every pass, and
     filing goes on, until a person has looked. Check with whoever uses
     that computer that the change was theirs, then run the command the
     page prints, `python -m tracker.checkpoint "<the app's data folder>"
     acknowledge "<the return>"`, and it stops being named.
   - **a refused record**, a sentence ending *Run recover (runbook §6).*:
     the pass left that return alone because its record came back
     shorter, reordered or rewritten since this machine last saw it, or
     carries a line that claims to be from this machine and is not, or
     (in a record written before this version) a line with no writer, or
     a line from a newer version. Nothing was
     applied. Follow §6, *When a record needs
     recovering*, for that return, today.

   **When the app says something went wrong.** A notice stays until it is
   dismissed. *Look again* means the record changed under you: the row is
   outlined, and looking again shows what it holds now. *Retry* re-runs
   the same step. A greyed return is a pass in progress. Every unexpected
   error's detail is in the error log (`tracker.settings.ERROR_LOG_FILENAME`)
   beside the app's database, rotated at 1 MB, three kept. It can hold
   client names: it stays on this machine, and a developer reads it at
   this machine.
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
   A co-owner's document that names a person on a return in another
   household waits here too (decision 204): open it with **Open** on its
   row and press **File it under <the return>**.

   The row does not leave you to find the request yourself. Each parked
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
   rather than a guess — where the row says so, read the document. The
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
3. **A working copy that has moved is yours, and it is the first row on
   the screen.** Every pass proves each working copy against the
   fingerprint its own index row carries (decision 109). A copy somebody
   dragged away from where the record put it, or renamed, makes that row
   `tracker.filer.FILE_MOVED`, and it is said on the run and on the
   practice page the same morning: the request reads Missing until it is
   back, and the client is never asked for it. The app lists every such
   copy above the review queue with its home, where its bytes are now, and
   three answers — **Put It Back**, **Keep It Here** (only when the copy
   sits in `Prepared` itself under a name that begins with a request's
   identifier: it is filed there, under that request, which you can
   change) and **Send to Review** — because which one
   you meant is never guessed (decision 110). Answer them before Saturday:
   the draft holds nothing up for a mislaid copy, and a request that reads
   Missing all week is one nobody is chasing. Nothing you press there
   overwrites a file or deletes one — a different document already at home
   is left where it is and this one's copy goes to review instead, and a
   left-over copy is named every pass until you remove it yourself. §4 has
   the row and what each answer means. A copy that was simply deleted is
   not on this row: the pass makes it again from the original (decision
   157, §1 *A working copy went missing*). One whose original is gone too
   is, with one answer, **Mark … missing**, which puts the document back on
   the client's letter.
4. **A locked engagement.** The app shows a notice when a pass holds one:
   when it started, on which machine and — when it runs on this machine —
   the household and the file it is on. This return's buttons are greyed
   while it runs and come back by themselves the moment the pass lets go;
   nothing waits, and nothing needs clearing. If it says a run left its lock behind, a **Clear lock** button appears;
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

**Read it in the app.** The engagement's **Reminder** side sheet shows the same
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
hand. Next week's pass writes next week's draft as before. An approval
covers the text you approved and nothing after it (decision 190): edit
the file afterwards and the side sheet, the practice page's Drafted column and
the run log say *approved, then edited* instead of *approved*. The file is
still left alone, because you edited it; approve it again once it reads as
you want it. An approval given before this change reached the machine
recorded no text, so it reads *approved, then edited* the same way: the
file is still left alone, and you approve it again. **Open the
draft file** is still there for anyone who would rather work in Notepad,
and an edited file is shown as it stands with a note saying so — the side sheet
shows the letter alone, so the staff-side lines under the dashed rule at
the foot of the file are never on the clipboard. Those lines are headed **US** - the
requests waiting on us, not the client - each with the word the app shows
for its status.

Open the draft, read it, edit it, paste it into Outlook and send it. Nothing in the
tool sends anything, ever — the side sheet has no send button, and there is no
mail or network code anywhere in the reminder path.

**The letter gets firmer as the date gets closer.** There are four stages,
and which one you get is decided by how far the draft day is from the
engagement's **Due Date** — the date you are asking the client to send
things by, which is one of the engagement's details and yours to change.
The draft's header says which stage it is on, above the fingerprint line,
so you can see it without reading the letter; the practice page's Drafted
column says it too, and the app's Reminder side sheet shows all four as a toggle
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
both the same way, whether it was rolled with **Roll Forward…** in the app
or with `python -m tracker.rollover` on the command line: the new year's
Due Date and Filing Deadline come from the form's table, and you clear or
change them in the editor like any other detail. Leave the Filing Deadline
blank and the letter never mentions it. Leave the Due Date blank and every
letter is stage 1, because there is no date to measure from and nothing to
tell the client. The firm's phone number lives in the app's settings beside
the firm's name, and stage 4 leaves the sentence out when it is blank.
The draft's header names the number, above the rule, so a number changed
in the settings is seen before the letter goes (decision 190): *Firm phone
in this letter: ...*, or *Firm phone on file: ...; this letter gives none.*
at a stage that offers no call, or *No firm phone is set; this letter gives
none.*

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
exactly as it is), and the hold is said in the Drafted column of the
practice page and in the app, with the requests named, and counted in
`runs.log`. Clear the
question — unfile the copy, fix the rule, or set the row's override — and
the next pass writes the whole reminder, correct, once. The manual draft
(`python -m tracker.reminder <engagement_dir> --write`) and `--reminders
always` are held by the same question; nothing clears it but you. So is the
app's Reminder side sheet: while a reminder is held it shows the hold, the
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
counts it (`held=`), and the app's side sheet says **"Held: N files not
sorted"**. On a Saturday that means: press **Sort &
Scan** — Run now — (or wait for the next pass — the schedule runs on its saved interval, every two hours by default, and the
pass that sorts the inbox drafts the reminder that same day), or deal with the
file still waiting in the household's `Drop files here` — retire a year in the editor, rename a name the
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

**Before you open anything a pass parked.** A parked document is opened
with **Open** on its row, and only there, which opens the firm's working
copy in `00 - Needs Review` - never the client's original - marked as from
the internet so that Office and Acrobat show it in Protected View, the
read-only view they give a file from outside (decision 190). **Open** is
an allow-list, `api.READ_AND_PARKED_CODES`: it is offered only for a
document the app read and parked for a filing reason - it matched no
request or more than one, a request contested it, the name is not on the
page or names another return, or it names another household's person
and waits for one click (decision 204), its forms would not sort, its
issuer is not named, it shows its form number. Every other row has no **Open**: an
email or a zip; a file whose reading was refused (unreadable, extraction
or OCR failed, the reader crashed, stopped or could not start, too large,
locked, no pages, no readable text); a file the app never read (an
iPhone photo with no HEIC reader, no reader on this machine, a type no
request takes, a Google Docs shortcut, a file too small); and any cause
added since that nobody has placed in the list. For those, ask the client
to send it again, or open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184). A copy that
cannot be marked is never made (`filer.MARK_REFUSED`, below). Read it
there, and do not enable editing, content or macros. A program, script or
shortcut is not a document: since decision 190 the app sets it aside
itself (`reasons.NOT_A_DOCUMENT`; the one list is
`validators.PROGRAM_EXTENSIONS`), makes it no copy and offers no **Open**,
and it is opened nowhere - ask the client what they meant to send. A file
with no row - a stray in `Prepared` or `_Opened`, an original in the
client's folder for the year - is never opened where it sits; the rows
below, and §1's *A document the app did not file*, say where it goes.

**The Code column is what the machine reads** (decision 190). The Reason is
the sentence for you, and it may quote what the client chose — the file's
name, a page's spelling — so nothing the app decides reads it: the
letter, its holds and the review row read the row's **Code**, the cause's
one name in `tracker/reasons.py`. A row written before decision 190 has an
empty Code: its cause was not recorded, and the app does not guess it
from the words. Such a parked row holds the letter for the request its
row suggests, asked in the generic sentence, until you decide it.

| The index says | In plain words | What you do |
|---|---|---|
| `filer.FILED` | Exactly one request accepted it. | Nothing. |
| `filer.DUPLICATE` | The same bytes are already in the record, and the reason says what the row holding them is: `filer.DUPLICATE_OF_FILED` says "already filed as" of a filed document, `filer.DUPLICATE_OF_PARKED` says "parked as" of one still waiting for you, `filer.DUPLICATE_OF_MOVED` names the copy of a row whose file is not where the record put it, and `filer.DUPLICATE_OF_UNCOPIED` says plainly that the row holding those bytes never got a working copy. No second copy is made. | Nothing. The original is kept, and the row holding the bytes is where the work is. |
| `filer.RESENT_AFTER_SET_ASIDE` | The client sent again a document somebody had closed with **Not requested**. It was routed afresh: filed if exactly one request accepts it now, otherwise parked again with a copy of its own. The reason quotes the earlier decision whole — the date and the note whoever closed it typed. | Read what was decided last time, then decide again: file it, or close it again. The copy set aside earlier stays where it is. |
| `filer.NEEDS_REVIEW` | Parked for a person; the reason says which of the rows below. | Work it in the app. |
| `filer.ASSIGNED_BY_PERSON` | Someone filed it with **File it**, on the date shown, and what the rules had said is kept after it. | Nothing. This is the audit trail. |
| `api.CAME_FROM_SUBFOLDER` | Not in the Reason: the **Client's Subfolder** column, and the row's line under the reason, on any row - filed, parked, a duplicate, the opened email or zip's own row, or a row saying it could not be filed - whose file the client dropped inside a folder of their own in `Drop files here` (§1, *The layout*). It names that folder, below the inbox. A row written before decision 190 still ends its Reason with this sentence, and has an empty column. | Nothing. It is where the client had put it; use it when the row's name alone does not say enough. |
| `router.UNMATCHED` | No request on this manifest accepted it. | File it to the right request, or add the request. |
| `reasons.SHOWS_ITS_FORM_NUMBER` / `reasons.NAME_POINTS_AT` | No request accepted it, but the page shows the **form number** of the request(s) named — in its title, or as the form its first page is about, beside another of that request's own words — most often a scan whose reading lost one of the phrases the request asks for; or, where the page shows none, the file's **name** points at a request, and the sentence says "file name" instead. Those requests are the row's shortlist, never a filing, and the client's reminder is held for them rather than asking for what they sent (decision 140). | Open it with **Open** on its row: if it is that request's document, file it there; if not, file it where it belongs or set it aside, and the reminder is released. |
| `router.AMBIGUOUS` | More than one request accepted it. A broker's consolidated 1099 no longer parks here when exactly one request accepted it because of its 1099-B section (decision 146, below); two requests asking for a 1099-B, or none, and it still does. | Pick the right one. |
| `reasons.FILED_WHOLE` / `reasons.ALSO_ANSWERS` | A broker's consolidated 1099 (decision 146): several requests accepted it, and exactly one - E01 on a 1040, B01 on a 1041 - was accepted because of its 1099-B section, so it filed whole there, one copy in one folder. The Also Answers column names every other asked request one of its sections answers (a 1099-INT/DIV row, a 1099-MISC row) and the sections that did; each of those requests reads Received with `reasons.IN_CONSOLIDATED` in its notes, counting one document per section - so a 1099-INT/DIV row asking for three is Partial after one statement with interest and dividend sections - and the letter does not ask for them. A statement with only interest and dividend sections is not a brokerage statement and files under the 1099-INT/DIV row as before. | Nothing. If the statement does not in fact carry what one of those requests needs, press **Mark … missing** beside it in the app's filed list: the statement stays where it is, that request comes off, and the letter asks for it again. |
| `router.CONTESTED_PREFIX` | It looks like a named request but failed one of that request's own rules — last year's W-2, say. | Read the named rule. Usually it is the wrong year or the wrong client. |
| `router.OCR_ONLY` | A scan or a photo with no text layer; OCR read it, but only loosely enough to guess. | Confirm what it is and file it. |
| `reasons.NO_READABLE_TEXT` | Nothing in the file could be read at all — a scan or a photo the reader could not run on, an image-only PDF, an empty sheet. Nothing was matched against anything, so this is not "matched no request". | It has no **Open** (the app read nothing in it). Ask the client to send it again, or open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and file it by hand. If many files say it at once, the reader itself is damaged: re-install the app (§6, step 5). The shortlist shows what its **file name** suggests; the document decides. |
| `reasons.UNREADABLE_IMAGE` | A photo arrived that would not open — a half-finished upload, most often. | Ask the client for it again; the reminder does. |
| `reasons.HEIC_NOT_SUPPORTED` | An iPhone photo arrived and this machine's HEIC reader is missing. Ours, never the client's: they sent an ordinary photo. | Run `Setup.bat` again (it installs `pillow-heif` from the locks); for the packaged app, rebuild it. Until then it has no **Open**, because the app never read it: open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and file it by hand. |
| `reasons.ISSUER_NOT_NAMED` | The request list asks for this document one row per issuer (§8) and this one names none of them — a K-1 from a partnership nobody listed. | Type the issuer's name on the row and press **Add issuer** (§8), or file it to the right row. |
| `reasons.NAME_NOT_ON_PAGE` | A request that asks for a **named** document accepted it, and the page names nobody on this return's people list (§10). | Open the page with **Open** on its row. If it does name them in a spelling the list has not got, file it and **teach the spelling** on the same row; if it is somebody else's, file it by hand on the return it belongs to. |
| `reasons.NAMES_ANOTHER_RETURN` | The page names somebody who is on another return of this household, and nobody on this one. The sentence says who, and which return. | Switch to that return and file it there. Nothing was moved. |
| `reasons.NO_PEOPLE_ON_FILE` | This return lists nobody yet, so nothing can confirm a named request. | Open **Edit Request List** and add the return's people (§10). Everything parked for this reason files itself on the next pass. |
| `reasons.SEVERAL_FORMS_UNSORTED` | One page prints two or more forms' own names (a stack scanned in one pass) and they will not sort one to a request: a form no row asks for, two rows wanting one form, or a row that accepted the page on a phrase rather than a form number. When they do sort, the page files a copy under each request and the row's Reason says so (`reasons.NAMES_SEVERAL_FORMS`). | Split the scan, or file the whole page to the one request that matters and note the rest. |
| `reasons.NOT_A_DOCUMENT` | A program, or a file Windows runs as one - `.exe`, a shortcut, a script, a disk image; the one list is `validators.PROGRAM_EXTENSIONS`, read from the file's real last extension (decision 190). It was decided before anything read it, so nothing its name says reached a request, and it has **no review copy**: the Needs Review page lists it under its own heading with its true type, and offers no **Open** and no **File it**. It holds nothing, because it names no request, and the letter asks the client about it by the name they gave it, under *RECEIVED, BUT WE COULD NOT USE IT*, in the words any unusable file gets. A program sent again after it was set aside parks the same way, unread and with no copy. | Never open it, here or anywhere. Close it with **Not requested** once the client has said what they meant to send; the letter then stops asking. A program's review copy made before decision 190 may still sit in `00 - Needs Review`: nothing offers it, and you may delete it from there by hand. |
| `reasons.TOO_LARGE` | The file is larger than the app will read (`validators.MAX_READ_MB`) — a video, a disk image, a whole mailbox, or a genuinely enormous scan. It was not opened: no text, no OCR. It is still counted and kept like any other original. | It has no **Open**. Ask the client what it was meant to be, or open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and file it by hand. |
| `reasons.READING_STOPPED` | The reader gave up on this file at the safety stop — a minute a page, ten minutes a file (decision 137). Something in it made reading far slower than any real document, or the machine was very busy at the time; it will not be tried again until the file changes. The stop covers the whole reading - the text layer, each page's drawing and the OCR - because each document is opened and read in a process of its own that the pass ends at the stop (decision 150). An email or a zip is opened in that process too, under the stop for a file, and one stopped there parks whole with nothing taken out of it (decision 154). That process never outlives the pass: if the schedule's own time limit stops the pass, the reading stops with it. | It has no **Open**. Ask the client to send it again, or open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and file it by hand. |
| `reasons.READING_CRASHED` | The reader's own process ended on this file without an answer - the PDF or OCR library crashed, the email or zip opener crashed (decision 154), or the machine ran out of memory (decision 150). Only this file is affected: the pass went on to the next one, and this file will not be tried again until it changes. | It has no **Open**. Ask the client to send it again, or open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and file it by hand. If many files say it at once, the machine itself needs a look. |
| `reasons.READER_UNAVAILABLE` | The reader could not start on this machine at all, so the file was never opened (decision 150). The machine's problem, never the file's: nothing is kept about the file and nothing is recorded - no index row, no Needs Review row. The file waits (in the inbox, or in the year's folder with no row) and is read again on the next pass. The pass's own summary says it once, and the run log counts it (`reader-could-not-start`). | Look at the machine (memory, disk, antivirus, a damaged install). Once it is fixed, the next pass reads and files the waiting files; there is nothing to file by hand. |
| `reasons.UNNAMED_ACROSS_HOUSEHOLDS` | This household's drop folder feeds a return in another household, and that return would have taken this document on its keywords alone — but the page names nobody, so it was not moved into a folder other people can open. It waits here (decision 137). The Evidence names the return and the request that wanted it, as `<return> / <request>`. The same holds for a document sent again that the other household already has. | Open it with **Open** on its row. If it is that return's, file it there with **File under another return**; if it is this household's, file it here. |
| `reasons.NAMED_ACROSS_HOUSEHOLDS` | This household's drop folder feeds a return in another household, that return's list accepted this document, and the page names that return's person. The pass never files into another household (decision 204), so it waits here, its original in this household's year folder, and the row keeps what that return's list accepted. The same holds for a document sent again. Until somebody clicks, the other household's status does not count it. | Open it with **Open** on its row. If it is that return's, press **File it under <the return>** once — it files under the requests shown and nothing else. If the button is not offered (the row says the return is no longer fed, or a request is gone or N/A), use **File under another return**. If it is this household's, file it here. |
| `router.NO_REQUEST_ACCEPTS` | No request on this manifest takes that file type at all. | Usually a stray file. Otherwise widen the request's allowed types. It has no **Open**: the app never read the file (decision 190). |
| `reasons.CONTAINER_LOCKED` | An email or a zip arrived and one of the files inside is locked with a password (or packed in a way this machine cannot unpack), so nothing in it was opened. The container is kept like any original, with a review copy. | Ask the client for the documents themselves; the reminder does. It has no **Open**. If you have the password, open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and bring the documents back into this household's `Drop files here`, never the client's folder for the year; the next pass sorts them. |
| `reasons.CONTAINER_DAMAGED` | An email or a zip arrived that does not read as one - a broken zip, an Outlook file whose structure is damaged, an email with no headers at all. Nothing in it was opened. | It has no **Open**. Ask the client to send the documents on their own; the reminder does. It is opened, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184). |
| `reasons.CONTAINER_EMPTY` | An email or a zip arrived with nothing attached - only the message's own text, or a picture shown inside it. Ours, never the client's. | It has no **Open**. Open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and read it: the message may say what they meant to send. Close it with **Not requested** once read. |
| `reasons.CONTAINER_LIMIT` | An email or a zip past one of the limits it is opened under, named in the sentence: nested more than two deep, more than 200 attachments, more than 250 MB once unpacked, a file inside that unpacks to more than 100 times its packed size (the shape of a "zip bomb"), or more than 200 parts that are not documents. Nothing was taken out. A container nested too deep inside another is taken out whole and parks with this reason on its own row, while the rest of what was attached files. | It has no **Open**. Open it, if at all, on a machine with no Drive sign-in and no client folder, never this one (decision 184), and bring the documents you find back into this household's `Drop files here`, never the client's folder for the year; the next pass sorts them. |
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
| `filer.REPLACED_IN_PBC` | An original we had already filed no longer holds the bytes we filed. A client cannot change one under the documented shares (§1, *Sharing a household with a client*), so somebody at the firm or the sync client did; the working copy was made from the earlier file. Said too for a file taken out of an email or a zip that was replaced under its own name in the hidden `_Opened` folder. | Do not open either where it sits. Copy the new file from the year's folder into this household's `Drop files here`: it is already this household's, so nothing is published anywhere new. The next pass sorts it as a new arrival (an identical one is a Duplicate), and if it parks it gets a row, with **Open** when the app read it. If it is the better document, file it and **Unfile** or set aside the old row. Then find out who at the firm changed it. |
| `filer.README_UNREAD` | The README in a household's inbox could not be opened just now - most often because someone has it open, or antivirus is holding it (decision 179). It is neither sorted nor written over; it waits where it is, as a file held open does. | Nothing, unless it is said pass after pass: then close whatever has it open. The next pass looks again. |
| `filer.UNTIED_IN_PBC` | A row was recorded without its bytes and its working copy no longer matches the original. | Do not open either file where it sits, and do not **Unfile** the row: with no recorded bytes it cannot prove which copy is its own, so Unfile would put a copy of the client's new file on a row and leave the old copy in `Prepared`, still counted for the request - and filing it again counts two. In the app, leave the row as it is. Nothing is adopted automatically, by design. |
| `filer.UNRECORDED_OPENED` / `filer.OPENED_CONTAINER_GONE` | A file sits in a hidden `_Opened` folder that no row names, or a container's folder there whose email or zip has no row any more (decision 143). A pass killed half way that the next pass did not finish can leave one; so can a file somebody put there by hand. It is never sorted from there and never deleted. | Do not open it where it sits. Confirm whose it is first (§1, *A document the app did not file*): if it is this household's, drop a copy into this household's `Drop files here`; the next pass sorts it, and if it is a document it gets a row, with **Open** when the app read it. Then delete the stray by hand. If you cannot tell whose it is, leave it and ask. |
| `filer.REMAKE_FAILED` | A working copy that was gone could not be made again from the original this pass - a full disk, a path past the limit, or an original that changed while it was read (decision 157). Nothing half made is left, nothing is recorded, and the request is held for you (`reasons.COPY_MISSING`), never asked of the client. | Nothing, if the next pass makes it. If the line comes back every pass, look at what it names: free the disk or shorten the root; an original it names is never opened where it sits (§1, *A working copy went missing*). |
| `filer.UNRECORDED_COPY` | A file is sitting in `Prepared` under a name that begins with a request's identifier (or in the review folder) that nothing on the record put there and no row's bytes account for. It **is** counted for that request — what a request has is what `Prepared` holds under its name — but nobody can say where it came from. It is never a copy the app left half made: since decision 155 a copy that fails or is killed part-way (antivirus holding it, a full disk, the power going out) leaves only a temporary file, which nothing counts and the next pass removes. | Do not open it where it sits. Confirm whose it is first (§1, *A document the app did not file*): if it is this household's, drop a copy into this household's `Drop files here`; the next pass sorts it and it gets a row, with **Open** when the app read it. Then delete the stray by hand. If you cannot tell whose it is, leave it and ask. If it is not a whole document — a partial or broken copy, say one an older version left — delete it by hand; never ask the client for it. Said every pass until you do. |
| `filer.MARK_REFUSED` | A file that can carry macros (a macro workbook, an old `.doc` or `.xls`, an email or a zip) was not given a review copy, because the copy could not be marked as from the internet - the mark Office reads to open a file in Protected View (decision 190). The firm's folders sit on a volume that holds no such mark: FAT, or a network share that drops it. Fail closed: the row says it could not be filed, and its original rests safe in the client's folder for the year. An **Unfile** or a put-back that would move such a file into review is refused the same way and records nothing; one a pass was finishing from before is abandoned instead, said once (`filer.INTERRUPTED_MARK_REFUSED`), and the row stands as it was. | Never open the original. Ask the client to send the document as a PDF, and set this row aside with **Not requested** in the app; no later pass makes its copy. Move the firm's folders to an NTFS volume, so the next such file gets its marked copy. |

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
| `filer.REMADE_SENTENCE` | Said at the end of a row whose working copy was gone - deleted, trashed, lost from Drive's cache - with its bytes nowhere else under `Prepared/`, and was made again from the client's original, proved against the row's fingerprint (decision 157). By the pass, or by you with **Put It Back**. The request's status did not move. | Nothing. |
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
read yet. The email reads the code each note was written with, never the
note's words, which name the client's files (decision 190); a note written
before that has no codes, and its request is asked in the generic sentence
until the next scan writes it again.

**A note that says a file would not open ends with the error's class, in
brackets, and nothing more** — `not a readable PDF (PdfReadError)`,
`could not read it (FileNotFoundError (ENOENT))` (decision 190). The one
exception is a workbook packed a way only a person's zip program opens: its
note says so in the firm's own sentence. The class says what kind of
failure it was; the reader's own message is never shown, because it can
quote the document itself - a number, a name. The full message and its
trace go only to the debug log, `tracker-errors.log` in the data folder
beside the app's database (decisions 186 and 193): a person mending the
app reads it there, and it can name a client, so it is deleted with the
rest of that folder's client data. The same holds for a row the
filer could not file, for the run log's line and for the app: an error the
app did not foresee is shown by its class alone. So too for the
warnings a pass prints in the scheduled job's console window (a README or
a page that could not be refreshed, a record that could not be read): they
name the class and the firm's own file or return, never the error's words,
which can carry the path of a client's file.

**Ours to deal with** (never in the client's email):
`reasons.PENDING_SYNC`, `reasons.VANISHED`, `reasons.NO_TEXT_LAYER`,
`reasons.NO_TEXT_AFTER_OCR`, `reasons.OCR_FAILED`,
`reasons.HEIC_NOT_SUPPORTED`, `reasons.TOO_LARGE`, `reasons.READING_STOPPED`,
`reasons.READING_CRASHED`, `reasons.READER_UNAVAILABLE`,
`reasons.UNNAMED_ACROSS_HOUSEHOLDS`, `reasons.NAMED_ACROSS_HOUSEHOLDS`,
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
  ours the letter does not ask the client for it. Look at it with **Open**
  on its row, because nothing on the record says what that file is: put the right copy back (the
  original is in the client's folder for the year), or file whatever it
  is properly. It is on the practice page too, so you see it across every
  engagement at once.
- `reasons.COPY_MISSING` — the request's working copy is gone and the pass
  could not make it again this time: the client's original could not be
  read (still syncing, or refused), or the copy could not be written
  (decision 157). Nothing is asked of the client — we hold the original —
  and the pass makes the copy as soon as it can. If it stays, see §1, *A
  working copy went missing*; the original in the client's folder for the
  year is never opened where it sits.
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
part. The part that was read is bounded (decision 178), so the row keeps
**Open** where the row was parked for a filing reason; but the note speaks
only for that part - ask the client for it in smaller parts before
believing it.

Four reasons in that file are not validation notes at all:
`reasons.NO_READABLE_TEXT`, `reasons.ISSUER_NOT_NAMED`,
`reasons.SHOWS_ITS_FORM_NUMBER` and `reasons.NAME_POINTS_AT` are the
router's, and they appear in the index's Reason column (§4) rather than
against a request. All four are ours: the client may well have sent the
right document. The last two are the firm-side reasons that hold the
reminder (decision 140), and their held line says a person here is
confirming the file, never that the file was wrong; the reminder's refusal
says it is "held until a person confirms the parked file (open it from its
card)".

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

About thirty minutes when the old machine still starts; longer when it
does not, and then what the new machine can prove starts from the records
as they are that day (*The moment of trust*, below).

**The client files need no restoring.** Every engagement's manifest,
ledger, originals, working copies and drafts are in the engagement folder,
which syncs. Any machine signed into the same Drive account has all of it
already.

**What was only on that machine:** the settings file beside the app
(`tracker.settings.SETTINGS_FILENAME`), the app's data folder
(`%LOCALAPPDATA%\tax-document-tracker`, decision 186: the database
`tracker.store.STORE_FILENAME`, the record checkpoint beside it
(`record-heads.db`, `tracker.checkpoint.CHECKPOINT_FILENAME`, and, while a
command runs, its `-wal` and `-shm` beside it), the folder
`recovered` beside them if a recovery was ever run, the last-pass file
(`last-pass.json`), the pass-order hint (`tracker.runner.PASS_ORDER_FILENAME`),
the error log (`tracker.settings.ERROR_LOG_FILENAME`) and the `passes`
folder (`tracker.progress.PASSES_DIRNAME`) beside it, and the task's file),
the scheduled task, the app folder itself, and the graphics card pack if
that machine had one (step 5). The last-pass file, the pass-order hint, the
error log and the `passes` folder are not carried over: the new machine
starts them afresh.

**Carry `tracker.db` and `record-heads.db` over** (decision 159). The
database can be built again from the ledgers, but the checkpoint cannot:
it is this machine's own note of how far every record went, and it is the
only thing that can tell a record that a sync client quietly put back to
an older copy from one that is simply as it was. **Both files are client
data.** Copy them **over the office network**, straight from the old
machine's data folder into the new machine's data folder (the same
`%LOCALAPPDATA%\tax-document-tracker`, under the Windows account that runs
the app and the schedule there), with the app
closed and the old machine's schedule off. With the app closed and the
schedule off the checkpoint is one file; if a `record-heads.db-wal` is
beside it (the machine stopped mid-write), copy it with it - it holds
writes the file does not yet. **Never** by any other road:
not the desktop, a USB drive, an email or a chat, the program's own folder
in the repository or the Shared Drive. Then delete any copy left anywhere
else. Copy `recovered` the same way if
it is there. Leave the rest of the old data folder, and delete it when the
old machine is retired. The first pass on the new machine still reads every
document once - the verdicts the old machine had cached are rebuilt, not
trusted across machines - and is slower for it, never wrong.

**The moment of trust.** If the old machine cannot give up its
`record-heads.db` (it died, the disk is gone), the new machine starts its
checkpoint from the records **as they are on its first pass**. From then
on it will notice any record that goes shorter or is rewritten, but it
cannot tell whether one had already been put back to an older copy
before that first pass. What stands behind that moment is the firm's own
off-drive copy of the clients folder and any export in `recovered`: if a
return looks wrong on the new machine, compare its record with those
before trusting it. The same moment comes after an accepted recovery
(below) for that one return.

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

**And no file the app writes is ever half there** (decision 155). A
working copy, the weekly draft, the client's README, the Status Report
and the settings are each written to a temporary name beside the real one
(ending `.tmp`, with the program's process number and a random tag in it)
and renamed into place only once every byte is on the disk. So a power
cut, a restart, or antivirus grabbing a new file part-way leaves at worst
that temporary file and the real one as it was - never half a statement
under the proper name. The next pass on the household removes those
temporary files itself, and only its own: the exact shape, left by a
program that has since stopped, in the firm's folders or beside the
README, never in the client's folders for the year. Beside the README it
also has to hold nothing but the README's own text (decision 190): the
README's start, or nothing at all when the power went before the first
line was written. The inbox is the client's, and a client's file that
happens to carry that shape and holds anything else is left where it is.
It is not syncing, but the pass cannot tell it from a file still arriving,
so it is counted with them (*syncing N* on the run's line), pass after
pass, until you move it out of the inbox, unopened. You never delete
one of the app's own temporary files by hand. A working copy of a read-only file the client sent (from a
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
   again at step 3, and `tracker.db` and `record-heads.db` come across
   the office network as above (without them the database is rebuilt
   from the journals and the checkpoint starts at the moment of trust). Running from source needs Python and
   Node, and **`Setup.bat` run once** with the internet on: it makes the
   app's own private Python (`.venv`) and installs into it exactly the
   locked packages, each checked against its SHA-256, and never touches
   the machine's own Python. After that `Start App.bat` starts offline and
   installs nothing; when the lock files change (an update pulled from
   the repository), it says "The package list changed since Setup ran on
   this computer" - run `Setup.bat` again. `Setup.bat`'s last step
   registers the schedule with the Python the app runs under, which from
   source is `.venv`'s, on the computer that runs the schedule (step 4);
   a job registered before `Setup.bat` names the machine's own Python,
   which holds none of the locked packages, and would fail every run. The
   packaged build needs neither: the app runs the same step at its first
   start. Keep the folder's path short — a
   few levels deep at most, like the `C:\Tools\tax-tracker` the README's
   scheduling example uses: past the classic Windows path limit the packaged
   program silently loses its command line and answers every call with a
   usage error.
3. Start the app. It asks where the clients live on first launch — give it
   the same folder, the synced one — with the firm's name and telephone
   number beside it. This is the one place the root is set;
   if the new machine mounts it at a longer path, the reply lists every
   return that leaves short of room (§1, *If the clients root moves*).
4. **Move the schedule to this machine** (decision 209). The designation
   file still names the old machine, so this one registers nothing until
   it is told to. In the app press **Repair the Schedule**: it says which
   machine runs the schedule and offers to move it here; answer yes (the
   packaged app's way, and the same move as
   `python -m tracker.after_install --move-schedule-here` run in the app's
   folder from source, with `.venv\Scripts\python.exe`). It says which
   machine it replaces, names this one in the file and registers the task
   here, with this computer's saved time and interval (the Schedule button;
   a move never resets them to the defaults). The old machine removes its own task the next time its app
   starts, if it still does - the file no longer names what that machine
   last saw. Since decision 131 the job names the app's settings folder and
   reads the clients root from it at every run, so a later change of root
   is made in the app alone. Run it from the app's copy on this computer's
   own disk: it refuses from a stick or a network drive (decision 186).
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
     folder, for example C:\JPA App; scans can't be read from here",
     and the scheduled pass puts the same sentence in its warnings once.
6. Run one pass — the **Sort** icon on a single return — and read the run
   log before trusting the schedule.

**Before the new machine's first pass**, turn the old machine's scheduled
task off, or keep that machine off the clients folder entirely: from then
on the new machine is the designated one (§1, *One machine per clients
root*), and the table at the top of §1 is changed to name it. Two machines
on one clients root can each take their own lock and each append to the
same ledger at the same moment, and that is the one way an original ends
up filed with no record of how it got there. If it happens anyway, the new
machine's practice page names every line the other one wrote (*Records
that need a person*, §2).

### When a record needs recovering

Something - a sync client restoring an older copy, a person editing the
file by hand, a second machine - changed a return's record in a way this
machine did not. The practice page or the app says so for that return in
one sentence ending *Run recover (runbook §6).* The pass leaves that
return alone until a person has dealt with it; every other return goes on.

**Recover before you rebuild, always.** `rebuild` refuses such a return,
because rebuilding from the record as it is now would silently throw away
the lines this machine had and the record no longer has. It refuses too
whenever the database holds a line the record lacks or holds differently -
even when the checkpoint has never seen the return (the first pass after
installing, a new machine, a damaged checkpoint set aside): `rebuild` never
drops a line nobody has exported. Instead, on the
designated machine:

1. **Look first.** Run, with the app's folder, the clients root and the
   return's folder:

   ```
   python -m tracker.store "<the app folder>" recover "<clients root>" --engagement "<the return's folder>"
   ```

   This changes nothing in the return. It saves two files into
   `recovered` beside `tracker.db` - the database's copy of the record,
   and the record's current copy (its name ending `*.record-now.jsonl`) - and lists
   every line on which they disagree: which side has it, what kind of
   event, when, and which computer wrote it. Keep both files; never
   delete them.
2. **Understand which lines would go.** A line only *the database* has
   is a step the record no longer holds (a filing, an edit to the list):
   accepting the loss drops it from the app's view. Look at the
   return's folder and the Status Report to see whether that step still
   matters. If it does, stop and ask Jason. If a conflict copy sits beside
   the record (any other file whose name begins `_ledger`), stop too: have
   it compared with both saved files before anything is accepted - it may
   hold the only other copy of the lines the record lost (decision 184).
3. **Accept the loss only by typing the return's name.** When you and
   Jason agree the record as it is now is the one to keep, run the same
   command again with the return's own folder name, typed exactly:

   ```
   python -m tracker.store "<the app folder>" recover "<clients root>" --engagement "<the return's folder>" --accept-loss "<the return's folder name>"
   ```

   Any other spelling is refused and changes nothing. Accepted, the
   return's rows are rebuilt from the record and this machine's checkpoint
   for that return starts again from it (the moment of trust, for that
   return).

**A record that does not read** (recover's first look says *the record
itself does not read*, and offers no `--accept-loss`): the app never
rewrites a record, so this one is a person's job. A second person looks at
the difference first. Then do exactly what the sentence says:

- if it names the database's export as a copy that may be copied over the
  record (it does only when that export holds every line the record still
  reads), compare the export with the `*.record-now.jsonl` copy first, then
  copy the export over the return's record (`_ledger.jsonl` in the return's
  own folder, the app closed and the schedule off);
- if it says *this machine's store holds no copy of this return*, no file
  the app wrote is one to restore from - it wrote no export at all when
  the database held nothing: restore from a conflict copy or the firm's
  off-drive copy, and ask Jason. Never copy a file shorter than the
  record's readable part over it.

Then run `recover` again to check the record now reads.

**A checkpoint that will not open.** Three sentences name
`record-heads.db`, and each has its own step:
- *…is busy - another run is using it*: another run held the file for a
  moment. **Do not set it aside** - it is healthy, and setting it aside
  would make the next pass a moment of trust. The next pass tries again.
- *the clients folder is not the one this machine's record checkpoint
  belongs to*: see *If the clients root moves*.
- *the app cannot read this machine's record checkpoint* (the pass
  says *No household was served this pass*, or a return says it): the
  file is damaged, and the steps below are for this one only.

If the pass or a return says *the app cannot read this machine's
record checkpoint*, the file is damaged; the app never moves it by
itself, because a damaged checkpoint is exactly what a person must see.
Close the app, turn the schedule off, and rename the file - and a
`record-heads.db-wal` and `-shm` beside it, the same way - (for example to
`record-heads.db.damaged`) - keep it, never delete it - then run one pass:
the checkpoint starts again from every record as it then is. That pass is
the moment of trust, so run `verify` first and tell Jason.

**Keep every conflict copy and every lock sibling.** A `_ledger (1).jsonl`,
a `_ledger_conflict-*.jsonl`, a `_scan.lock` copy: never delete one, even
after the recovery. It is the evidence of what happened, and the practice
page goes on naming it so nobody forgets it is there.

**A read-only look over the whole firm.** To check every return at once
without changing anything - on a quiet day, or before trusting a new
machine - run:

```
python -m tracker.store "<the app folder>" verify "<clients root>"
```

It prints each problem it finds (a record that does not read, one shorter
or rewritten since this machine saw it, a line claiming this machine that
it did not write, a line past what this machine saw that names no writer -
the same judgment the pass makes - a line outside the record's rule, said
as the pass says a malformed line (below, section 9: a writer that is not
a machine's name among them), the database holding lines the record
does not, a recorded file missing or holding other bytes) and exits non-zero if there
is any. It writes nothing anywhere. `python -m tracker.checkpoint "<the app's
data folder>" state` shows the root the checkpoint belongs to and what it
vouches for.

**What this protects, said plainly.** The link in every line detects
accidents anywhere: a sync client restoring an older copy, a reorder, a
lost tail, a careless hand edit. The checkpoint on the machine that writes
detects a rewrite and an append that machine did not make. It does not
protect against a writer who controls that machine itself: malware or a
person at its keyboard can write the record and the checkpoint together;
that is contained by decision 180, which limits what a forged line can do.
It is not proof to a third party of who wrote a line: the host is written
by the program and could be typed by anyone. A secret key was rejected: it
would live on the machine it protects, and a lost key would make the
firm's own record unwritable.

**Jason's two live checks** (they need the office machine's synced drive
and cannot be proved in the cloud; Jason makes them a first time on the
version that holds decision 159, and again after moving machines):

- **L1, one holder.** Pick a return folder on `G:` that nobody is working
  on and run:

  ```
  python -m tracker.locking race "G:\Shared drives\<clients folder>\J Park & Associates\<household>\<year>\<return>" --processes 8 --rounds 20
  ```

  It races eight processes for a test lock (`_race.lock`, never the
  return's own `_scan.lock`) twenty times. It must print *one holder in
  every round*; anything else prints the round that failed - send that to
  Jason.
- **L2, a line from another machine is named.** On a second computer
  signed into the same Drive, make one small change to a test return
  through the app there (for example, edit its list and save). Let Drive
  sync, then run one pass on the office machine (the **Sort** icon). The
  practice page's *Records that need a person* must name that return's
  line as *written on <the second computer>*. Acknowledge it with the
  command the page prints, and check the next pass no longer names it.

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
(decision 141), every one of them unticked in the request list of **Add a
return**. Since decision
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

**Adding one.** When a K-1 arrives from an entity no row names, it parks in `00 - Needs Review`
and its row carries one box: type the issuer's name as the K-1 prints it and press **Add the
issuer and file it**. The app adds the next free row in F's block - `Schedule K-1 - ` and the
name, the entity in Required Keywords, everything else copied from `F01`, for this return's
year - and files the document under it, in one step; the banner names both. It is refused,
with nothing added and nothing filed, if the page is out of date, if the list changed since
the page was drawn, or if the name is inside - or the same as - another issuer row's name.

To add a row **before** a K-1 arrives, or on a return whose K-1 row is not the catalog's
`F01`, use **Edit Request List**, **Add a Request**, and fill the cells below; then **Save**.
The routing cells show when the editor's **Advanced** switch is on.

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
issuer rows must not have one name inside the other, or the same name
twice — `Ashford` and `Ashford Holdings`, or two rows both `Ashford
Holdings`, would all claim the same K-1 — and the save or the row is
refused, by name, if they do.

A list that **already** holds two rows of one name — written before
this check, or rolled forward from such a year — is not locked: a save
of anything else goes through, the roll forward carries the pair as it
was, and the banner warns *"Rows F02 and F03 both narrow F01 with the
same name, …: every document naming it would park."* It means every K-1
from that issuer will sit in Needs Review until one of the two rows is
gone. Remove one of them, or give it the other entity's name if it was
really a different issuer, and save; the warning stops.

**What then happens.**

- A K-1 that prints one issuer row's name files on that row. It beats
  `F01` outright: naming the entity is the stronger evidence, and `F01`
  asks for no name at all.
- The **federal and the California K-1 from the same entity land in the
  same row** — California's Schedule K-1 (568) heads itself "Member's
  Share of Income" and `F01` asks for that too.
- A K-1 from an entity **no row names** parks in `00 - Needs Review`,
  and the reason names the issuer rows you do have. File it in the app,
  or type the issuer's name on its row and add the row and file it in
  one step. It is not
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
  the practice page (`tracker.runner.STATUS_PAGE_FILENAME`) in the clients
  root; the run log (`tracker.runner.LOG_FILENAME`), in the app's data
  folder on the machine that runs the schedule, counts them by code.
- **What happened to one document**: the Index section of that
  engagement's **Status Report.html**. Every move and every rename is in
  it, and it is drawn from the ledger, which is the record itself.

- **A household the pass stopped with "names … for a step (…), which is
  outside the places a step of this return may touch"**
  (`tracker.filer.OP_OUTSIDE`, decision 180): the return's record holds a
  step the app did not write - a copy of the record restored over a
  newer one, a line another machine wrote, or a hand edit - pointing
  outside that return's own folders. The word in brackets says which way
  it is outside (decision 187): `absolute` (a drive, a share or a full
  path), `above-root`, `not-a-place` (inside the clients root but in none
  of this return's folders), `other-household` or `other-year` (a write
  into another household's client folder or another year's `_Opened`),
  `client-tree` (a removal naming a client's original or inbox - the
  app only ever removes its own copies), `blank`, or `not-a-return`.
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
  read"; decision 187): the record holds a line the app will not obey.
  The words in brackets say which field and which kind of problem, never
  the value: a value outside the editor's bounds ("must be a whole number
  from 1 to 9999", "must be a date written YYYY-MM-DD", "must be true or
  false", a Date Pattern that "repeats something that itself repeats",
  "could try too many ways to match one line", "could do too much matching
  on one line" or "has more than 8 variable repetitions"); a line naming "an event this version does not know"; a
  step "outside this return's places"; a household or return label that
  "is not one folder name"; a line stamped in a form the app never
  writes; or one of the three things every line since decision 159
  carries about itself, in a shape the app never writes - a writer
  ('host') that "must be a machine's name" (blank, spaced, too long, or
  holding a slash), a link ('prev') that "must be blank or 64 lowercase
  hexadecimal characters", or a format ('fmt') that "must be a whole
  number" this version writes. A line like that in a return's record was
  written by hand or by something other than the app. Nothing was
  moved, copied or removed for that household, and every other household
  was sorted as usual. Do not edit the record by hand: say which return and
  which line, and the store check
  (`python -m tracker.store "<the app folder>" check "<clients root>"`)
  names every such line in every return.

**If a `_ledger.jsonl` is lost.** The record of a return or a household is
its `_ledger.jsonl`, and a lost one comes back from **Drive's trash or
version history** - never by creating the return or the household again,
and never by a rebuild (decision 188, keeping SPEC-162's rulings). The
store check names a journal that is gone: *"The store holds <n> line(s) for
`<engagement>` and its record is not there. Restore `_ledger.jsonl` from
Drive's trash or version history."* A journal restored from an older
version holds fewer lines than the store applied, and the pass says so
before it touches the return: *"The journal of `<engagement>` holds fewer
lines than the store has applied (the journal <n>, the store <m>). First
restore the journal from Drive's trash or version history. `rebuild` would
discard the <k> line(s) only the store still holds. Run recover (runbook
§6)."* A rebuild never
discards those lines silently: `python -m tracker.store "<the app folder>"
rebuild "<clients root>"` lists each one (its kind, its document, its date),
says *"the store holds <k> line(s) the journal does not; rebuild would
discard them (listed above). Nothing was changed. Run recover (runbook
§6)."* and exits 1. Only once the list has been read and the journal
cannot be restored is the loss accepted - for that one return, by its
folder's name typed exactly, as §6's recover does it: `python -m
tracker.store "<the app folder>" rebuild "<clients root>" --engagement
"<the return's folder>" --discard --accept-loss "<its folder name>"`
(decision 159 narrowing 188's `--discard`, which alone is refused). The
export and the difference come first, always; if the export cannot be
written, nothing is discarded.

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
app did not think of, one per line. **Add a Return…** and **New Household…**
ask for the first person when the return is made, and a return with nobody on it is refused. There
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

**When one parks.** The row says which of the three it was, and the three
rows in §4 say what to do. The usual one is a spelling the list has not
got: file the document and type the spelling the page prints into the box
beside **Teach this spelling**, and the next one like it files itself.

**Next year.** The rollover carries the people unchanged and asks you to
look at the list once — a child who now files their own return, a spouse's
new name. Nothing waits on that look; the check simply parks what it
cannot confirm until you give it.

### Household and return names

A household's name and a return's name are folder names: every path under
them carries them, in both trees, on every machine the Shared Drive syncs
to. So one rule says what a name may be, and **New Household…**, **Add a
return**, a
rolled return's new name and a feed all hold you to it with the same
sentence — `'<what you typed>' is not a household name: <why>` (decision 188).
A name is refused when it:

1. is empty, or longer than 80 characters;
2. does not begin with a letter or a digit — the app passes over every
   folder that begins with `.`, `_` or `~$`, so a household named so would
   never be sorted or chased;
3. ends with a dot or a space (Windows drops them), or contains any of
   `< > : " / \ | ? *` or a control character;
4. is a name Windows keeps for a device (`CON`, `NUL`, `COM1` and the rest);
5. contains an invisible character — a zero-width space, a soft hyphen, a
   direction mark, a no-break space. It is refused, never quietly removed,
   and the sentence names it by its code (`U+200B ZERO WIDTH SPACE`). A
   name that uses a zero-width non-joiner is typed without it;
6. contains a full-width or compatibility character (`Ｐａｒｋ`, the `ﬁ`
   ligature, a superscript) — type it plainly;
7. mixes letters of two alphabets, such as a Cyrillic `а` inside a Latin
   name (Chinese, Japanese and Korean count as one);
8. is a word of the layout itself (`Clients`, `J Park & Associates`,
   `Drop files here`, `Prepared`, `00 - Needs Review`, `_Opened`), or four
   digits.

**Look-alikes are one name.** Two names are compared as the app reads
them, not as they are spelled: case, spacing, invisible characters, the
Cyrillic and Greek letters that look like Latin ones, the dashes and the
apostrophes all fold away, and so do `1`, `i` and `|` against `l`, `0`
against `o`, and `rn` against `m`. So `Kim` and `Klm` are one name. That
errs on the side of asking: a second household whose name reads as the
first is refused, and you add a first name or a middle initial — and then,
if the two names still match, the city — to tell them apart. The refusal
is shown on the request list and stays there with everything you typed;
**Change household details** on that list takes you back to the name, and
**Continue** brings you back to the list as you left it. Never add a tax
identification number or any part of one to a name.

A folder already on disk whose name breaks the rule is listed under
*Folders the app leaves alone* with the reason, and nothing in it is
read.
