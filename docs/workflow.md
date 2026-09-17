# Tax Information Request Workflow

How the tax engagement team works through this repository. The mechanics
are in [ROADMAP.md](ROADMAP.md) and the repository map; this page is the
people side.

## Roles

- **Engagement lead** — owns the engagement's request list: picks the return
  type or rolls last year's list forward, trims and extends it, and fills in
  the client, share link and due date in the wizard (they land on the
  manifest's Engagement sheet; nothing else needs registering).
- **Preparer / staff** — works the `Prepared/` tree, files anything in
  `00 - Needs Review` with the app's *File it* action, sets `Manual Override`
  when their judgment beats the rules, and sends the drafted reminders.
- **Client** — drops everything into one shared folder. Nothing else.

## Starting an engagement

The request list is built from one catalog, `tracker/templates.py`, and
the manifest an engagement is created with is the readable copy of it.

- **Returning client (the default):** roll last year's engagement forward.
  In the desktop app, *New Engagement* opens on the returning-client page;
  on the command line it is `python -m tracker.rollover <last year> <new
  folder> --form 1040`. Last year's rows win on every field; the form
  template only fills blanks and *offers* rows the client has never had.
- **New client:** pick the return type (`tracker.templates.FORM_TYPES`),
  tick what applies, add anything unusual. Every request needs a
  keyword the document itself contains; the wizard defaults it to the
  document name so a custom request can still auto-file.

Either way the result is `_manifest.xlsx` plus the scaffolded `Shared/` and
`Prepared/` trees, and a `_README.txt` for the client.

## Lifecycle of a request

The scanner owns the status column; people own the override column.

1. **Missing** — nothing usable has arrived. Asked for in the weekly draft.
2. **Pending Sync** — the file is there but the cloud has not finished
   copying it down. Nothing to ask the client for.
3. **Partial** — some of the expected files arrived. Asked for, unless what
   is missing is a file we have not read yet, which goes to a person here.
4. **Failed Validation** — something arrived that the rules could not use.
   Translated into a plain instruction for the client, never quoted.
5. **Received** — every check passed; the date is stamped once and kept
   through any later regression.
6. **Accepted / Waived** (Manual Override) — a person's decision. The
   scanner keeps refreshing the facts but never touches the status again,
   and the reminder never asks for the row.

## Rules

- **Never commit client material.** `runs.log` and the drafts are gitignored
  because they carry real names and share links.
  Client documents live in the synced engagement folders, never here.
- **Originals are never altered.** Work from the `Prepared/` copies; the
  `PBC/` originals are the record and `_index.xlsx` says where each one went.
- **Nothing is guessed.** If a file is in `00 - Needs Review`, a person
  decides — in the app, by picking the request and clicking *File it*. The
  filer does the move, the rename, the index row and the re-scan.
- **Nothing is ever sent by the system.** Open `reminder-draft.txt`, edit
  it, send it yourself. An edited draft is never overwritten.
- **Catalog changes affect every future engagement.** Edit
  `tracker/templates.py` and commit it; the test suite checks every row can
  recognise its own document.

## Two things a person still does in the app

- **Check Manifest** runs the same validation the scheduled job runs before
  it touches a file: a bad regex or a non-number typed in Excel is named
  with its row, and rows the rules cannot act on are listed as warnings.
  Allowed Extensions left blank means the manifest's default
  (`tracker.manifest.DEFAULT_EXTENSIONS`); `*` means any type. A Period
  that names a year is the year check; `*` in Date Pattern turns it off.
  Only the first `tracker.content_check.MAX_PAGES` pages of a PDF are read.
- **File it**, on anything in Needs Review: pick the request (the picker
  starts on the router's own guess), optionally give a keyword, and the
  filer moves the copy under the canonical name, rewrites the index row as
  assigned by a person, learns the keyword and re-scans. If a run has
  died, its lock is shown with its start time and can be cleared once it
  is older than `tracker.locking.STALE_LOCK_SECONDS`.

## Collaboration

- Small team: commit directly to the branch CI watches; pull before editing the catalog.
- Larger team: work on a branch and open a pull request. CI runs the suite
  and checks that the repository map is current.
