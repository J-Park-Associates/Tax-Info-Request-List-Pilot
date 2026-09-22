# Tax Information Request Workflow

How the tax engagement team works through this repository. The mechanics
are in [ROADMAP.md](ROADMAP.md) and the repository map; this page is the
people side.

## Roles

- **Engagement lead** — owns the engagement's request list: picks the return
  type or rolls last year's list forward, trims and extends it, and fills in
  the client, share link and due date in the wizard (they land in the
  record as the engagement's details; nothing else needs registering). Starts the
  morning on `tracker.runner.STATUS_PAGE_FILENAME` — the whole practice on one
  page, written into the clients folder by every pass and opened by the app's
  **Open Status** button: what each engagement still owes, what is waiting for
  a person across all of them, and what failed overnight.
- **Preparer / staff** — works the `Prepared/` tree, files anything in
  `00 - Needs Review` with the app's *File it* action, sets `Manual Override`
  when their judgment beats the rules, and sends the drafted reminders.
- **Client** — drops everything into one shared folder. Nothing else.

## Starting an engagement

The request list is built from one catalog, `tracker/templates.py`, and
an engagement's list is cut from it into the record, where the app's
editor shows it.

- **Returning client (the default):** roll last year's engagement forward.
  In the desktop app, *New Engagement* opens on the returning-client page;
  on the command line it is `python -m tracker.rollover <last year> <new
  folder> --form 1040`. Last year's rows win on every field; the form
  template only fills blanks and *offers* rows the client has never had.
- **New client:** pick the return type (`tracker.templates.FORM_TYPES`),
  tick what applies, add anything unusual. Every request needs a
  keyword the document itself contains; the wizard defaults it to the
  document name so a custom request can still auto-file.

Either way the result is the request list in the record plus the
scaffolded `Shared/` and `Prepared/` trees, and a `_README.txt` for the
client.

## Lifecycle of a request

The scanner owns the status and records it; people own the request list and
the Manual Override column. The two do not share a file: the status is read
on the Status Report and in the app, and the request list holds only what a
person types.

1. **Missing** — nothing usable has arrived. Asked for in the weekly draft.
2. **Pending Sync** — the file is there but the cloud has not finished
   copying it down. Nothing to ask the client for.
3. **Partial** — some of the expected files arrived. Asked for, unless what
   is missing is a file we have not read yet, which goes to a person here.
4. **Failed Validation** — something arrived that the rules could not use.
   With a firm-side reason (a scan nobody has read) it is ours; with none it
   is ambiguous and **holds the reminder for a person** (decision 115) —
   never quoted to the client, never guessed at.
5. **Received** — every check passed; the date is stamped once and kept
   through any later regression.
6. **Accepted / Not Applicable** (Manual Override) — a person's decision. The
   scanner keeps refreshing the facts but never touches the status again,
   and the reminder never asks for the row. Accepted carries the reason the
   person gave; Not Applicable is shown with the row's year and folded away
   on the Status Report and in the editor.

## Rules

- **Never commit client material.** `runs.log` and the drafts are gitignored
  because they carry real names and share links.
  Client documents live in the synced engagement folders, never here.
- **Originals are never altered.** Work from the `Prepared/` copies; the
  `PBC/` originals are the record and the Status Report says where each one went.
- **Nothing is guessed.** If a file is in `00 - Needs Review`, a person
  decides — in the app, by picking the request and clicking *File it*. The
  filer does the move, the rename, the index row and the re-scan.
- **Nothing is ever sent by the system.** Read the draft in the app's
  Reminder card or open `reminder-draft.txt`, edit it, send it yourself.
  There is no send button anywhere, and an edited draft is never overwritten.
- **Catalog changes affect every future engagement.** Edit
  `tracker/templates.py` and commit it; the test suite checks every row can
  recognise its own document. The keywords staff have taught one engagement
  at a time are listed together by `python tools/learned_keywords.py`, once a
  season — that list is what the next catalog commit is made of.

## Six things a person still does in the app

- **Edit Request List** opens the list in the app: add, change, remove or
  paste rows and the engagement's details; a bad value is refused when you
  save, with its row and column named, and rows the rules cannot act on
  are listed as warnings. Allowed Extensions left blank means the default
  (`tracker.manifest.DEFAULT_EXTENSIONS`); `*` means any type. A Period
  that names a year is the year check; `*` in Date Pattern turns it off.
  Only the first `tracker.content_check.MAX_PAGES` pages of a PDF are read.
- **File it**, on anything in Needs Review: pick the request (the picker
  starts on the router's own guess), optionally give a keyword, and the
  filer moves the copy under the canonical name, rewrites the index row as
  assigned by a person, learns the keyword and re-scans. Picking a request
  the suggestions did not point at is recorded on the row as your override,
  with the shortlist it overruled — you may still file to any request, and
  the record says when you filed against the evidence. If the row changed
  after the card was drawn — somebody else filed it, set it aside or sent
  it back — the app refuses, says what the record now holds and shows you
  the row as it now is; nothing is moved and you look again. If a run has
  died, its lock is shown with its start time and can be cleared once it
  is older than `tracker.locking.STALE_LOCK_SECONDS`.

  The queue can be read two ways, and the toggle in the card's head picks
  one: **All at once** is the list above, every row with its whole picker;
  **One at a time** shows one card, in the same order, with the document,
  why it parked and the top suggestion with the sentence behind it.
  **Accept the suggestion** files it to that suggestion — the same filing
  **File it** makes, so the two cannot differ — **Pick another request**
  opens that row in the list, where every request is offered, and
  **Skip for now** sends the card to the back of the deck without sending
  anything anywhere: the count does not change and nothing is remembered
  about it. The deck is redrawn from the record after every action, so a
  row filed or set aside elsewhere simply leaves it. Which rendering you
  are on is remembered on this machine and nowhere else; setting a
  document aside is the list's, because it deserves the note box.
- **Not requested**, on anything in Needs Review no row asks for: an agency
  notice, an extra statement. The index row is rewritten
  `tracker.filer.NOT_REQUESTED`, with an optional note saying why and what
  the row said before kept after it. Nothing moves — the copy stays parked
  and the client's original is untouched — so the file is out of the way,
  not gone: the weekly draft stops warning about it, and a person who was
  wrong files it from the folded-away list, which is the only undo there
  is. It says nobody asked for this document *that day*, so if the client
  sends it again it is looked at afresh — filed if the list now asks for
  it, otherwise parked again with a copy of its own and a row that quotes
  this decision back, date and note and all. As with **File it**, a row
  that changed after the card was drawn is refused rather than overwritten,
  and the card is redrawn from the record.
- **Unfile**, on anything in the folded-away *Filed documents* list: the
  working copy goes back to `00 - Needs Review` under the client's own name,
  the index row is rewritten `tracker.filer.NEEDS_REVIEW` as unfiled by a
  person with what it said before, and the engagement is re-scanned, so the
  request the document was answering goes back to what it is without it,
  with the regression note that pass would have written. Do this rather than
  dragging the file in Explorer — and since decision 109 that has teeth: a
  drag is **said**, not learned. Every pass proves each working copy against
  the fingerprint its own index row carries, so a copy that is not where the
  record put it, and whose bytes turn up somewhere else under `Prepared/`,
  makes its row `tracker.filer.FILE_MOVED`: the request it left reads
  Missing, truthfully, with a firm-side note so the client is never asked for
  it, the copy is not counted under whatever request it now sits in, and
  nothing is moved — a person decides. Drag it back and the next pass files
  it again. Refiling is unfiling and then
  **File it**; a working copy somebody annotated is left where it is and
  said so, because the notes are work and which file the firm wants is not
  the tracker's to decide. The keyword the request learned when it was filed
  is not unlearned — it is a rule about documents, and the request still
  wants it. A document somebody re-filed since the list was drawn is a newer
  filing, and unfiling it is refused with what the record now says rather
  than undoing a decision you never saw.
  A word that turned out not to be distinctive is taken back on
  purpose instead, in **Edit Request List**, where every keyword a filing
  taught has its own button beside the row: one click records it, the
  request is re-scanned at once, and nothing you have typed into the rows
  and not saved is touched. It is that engagement's list only — the firm's
  own vocabulary is `tracker/templates.py` and still changes by a commit.
- **Moved by hand**, the card above the review queue: every working copy
  the last pass found somewhere other than where the record put it, with
  its home, where its bytes are now, and three answers — the system never
  guesses which one you meant (decision 110). **Put it back** returns the
  bytes to where the record put them: the copy itself is moved home when it
  still holds them, and a fresh one is made from the client's original when
  nothing under `Prepared/` does. **Keep it here** files the copy where it
  now sits — offered only when it sits in a request's folder, and starting
  on that request, so keeping the file and correcting the request is one
  click. **Send to review** sends it back to `00 - Needs Review` under the
  client's own name. Two things no answer will do: a file already at home
  that is *not* this document is never overwritten — it stays, this
  document's copy goes to review instead, and the row parks naming both —
  and nothing is ever deleted, so a copy left over after the bytes were
  already home is named every pass until you remove it yourself. A page
  filed under several requests is put back and never kept or sent from
  here, because which copy you meant is not the tracker's to guess.
- **The Reminder card**, under the request table: the week's draft, and the
  only place in the app a client letter is read (decision 118). It says what
  the record says — the day and stage of the last draft, or that one was
  approved, or that there has been none — and shows the subject line and the
  letter as the client will read it. The four stages are a toggle with the
  one the Due Date gives pressed; moving it rewrites the letter on screen at
  that rung and touches no file, and who is asked never changes with it.
  **Copy for Outlook** puts the body on the clipboard twice, as formatted
  HTML and as plain text with the same words, so it pastes into Outlook with
  the ladder's colour intact; the subject is not on the clipboard, because
  it goes in Outlook's own box. **Approve** makes the text on screen this
  week's draft: it is written to `reminder-draft.txt`, one
  `tracker.ledger.DRAFT_APPROVED` event records the stage and the
  fingerprint, any draft standing beside it is renamed
  `reminder-draft.set-aside-<date>.txt` and never deleted, and no writer
  overwrites it afterwards — the pass and the command line's own `--write`
  both land beside it, as they do beside one you edited, and the pass
  spends the approval on the next draft day. **Open the draft file** opens
  the file itself. A draft you have edited by hand is shown as it stands
  with the toggle dead — approve it as it is, or delete it to get a
  regenerated one. What the card shows and copies is the letter alone: the
  staff-side lines the file ends with, under their own dashed rule, are the
  machine's note to you and never reach the clipboard. A held reminder
  shows the hold and the requests holding it and nothing that reads like
  something to send.

## Collaboration

- Small team: commit directly to the branch CI watches; pull before editing the catalog.
- Larger team: work on a branch and open a pull request. CI runs the suite
  and checks that the repository map is current.
