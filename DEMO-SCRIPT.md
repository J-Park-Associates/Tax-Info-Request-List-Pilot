# Tax Document Tracker — In-Person Demo Script

**Audience:** prospective tax clients / referral partners
**Length:** 10–12 minutes
**Requires:** this one Windows computer. Nothing else — no internet, no cloud
account, no second machine.

---

## Before the meeting (2 minutes)

1. Double-click **`Start Demo.bat`** in the project folder
   (first run installs Electron — allow a few minutes; every run after is instant)
2. When the app opens, click **Reset Demo** — every request shows *Missing*
3. Optional: pre-open File Explorer windows side-by-side so drag-and-drop is smooth:
   - **Open Client Folder** (the engagement's `Shared\` drop folder)
   - **Open Sample Documents** (the files you'll play "client" with)
4. Close Excel if it's open (you'll open the manifest live in step 7)
5. Optional but powerful: learn the prospect's family or company name — in
   step 2 you'll create their engagement live, named after them

The left panel of the app carries this same script in short form — you can
glance at it while presenting.

---

## The demo

### 1. Set the scene *(45 sec)*

> "Every tax season starts the same way: we send you a list of documents we
> need — W-2s, 1099s, mortgage interest — and then everyone spends February
> playing email ping-pong. 'Did you get it?' 'That was last year's W-2, can
> you resend?'
>
> We replaced that with a shared folder that **checks the documents itself**."

**Do:** point at the dashboard — five requests, all *Missing*.

### 2. Pick the return type *(1 min)*

> "First question every new engagement answers: what kind of return are we
> preparing? Because the documents we need depend entirely on that. An
> individual 1040 needs W-2s and mortgage interest; an S corporation needs
> the trial balance and shareholder basis schedules."

**Do:**
1. Click **New Engagement**
2. Show the six form-type cards — **1040, 1120, 1120-S, 1065, 1041, 990** —
   and read a couple aloud
3. Click **Form 1040** — the tailored individual checklist appears instantly

> "One click, and this is now a 1040 engagement with a 1040 document list.
> Pick 1120-S instead and you'd be looking at a completely different list."

### 3. Build the tailored list *(1.5 min)*

> "Setting up the client takes a minute, not a morning. We keep a standard
> checklist per form type from years of engagements — I tick what applies
> to your situation, add anything unusual, and everything behind the scenes
> builds itself."

**Do:**
1. Type the **prospect's own name** (e.g. "Smith Family 2025 Form 1040") —
   this lands every time
2. Untick one or two template items ("no marketplace insurance — gone")
3. Add a custom request: type "Rental Property Records", keyword "rental",
   click **Add**
4. Click **Create Engagement** — the banner confirms folders are scaffolded
5. Click **Open Client Folder** — their drop folder is ready, README included

> "That's the whole onboarding. The list you just watched me build is now a
> live, self-checking engagement."

*(The engagement you created works for the rest of the demo — the core 1040
items match the sample documents. Or switch back to the Smith Family
engagement with the dropdown; both work identically.)*

### 4. What the client sees *(1 min)*

> "Here's the part your clients will actually notice. They get **one folder**.
> Not a folder per document, not a portal with another password — one folder,
> and the instruction is: drop everything in here. They never sort anything,
> never rename anything, and never work out which file matches which line on
> our list. That's our job, and we've automated it."

**Do:** click **Open Client Folder**. Show how nearly empty it is — just
`_README.txt` and a `PBC` folder. Read a line or two of the README aloud.

### 5. Play the client — including the mistakes *(1.5 min)*

> "Let's be an honest client: helpful, busy, and occasionally wrong. I'll hand
> over both spouses' W-2s... but also **last year's W-2** by mistake, the same
> W-2 **twice**, a **Word doc** where we need the actual 1098 PDF, and — because
> it always happens — a **vacation photo**. All of it into the one folder,
> because that's all they were asked to do."

**Do:** click **Open Sample Documents**, select them **all**, and drag them into
the client folder in one go. Do not sort them. The pile is the point.

| Sample file | Why it's in the demo |
|---|---|
| `W-2 John Smith 2025.pdf` | files itself to A01 |
| `W-2 John Smith 2025 - Copy.pdf` | identical duplicate — kept, but filed once |
| `W-2 Jane Smith 2025.pdf` | completes the 2 W-2s A01 expects |
| `W-2 Jane Smith 2024 - old.pdf` | **wrong year** — looks like a W-2, so it is never filed as anything else |
| `1099-INT First National.pdf`, `1099-DIV Vanguard 2025.csv` | only 2 of the 3 A02 wants → Partial |
| `2024 Form 1040 Tax Return.pdf` | files itself to B01 |
| `Form 1098 Mortgage Interest.pdf` | files itself to C01 |
| `Mortgage Notes.docx` | wrong file type → review |
| `Donation Receipts 2025.xlsx` | files itself to D01 |
| `Donation Receipts 2025.gsheet` | Google Sheets *shortcut*, not the file → review, with export instructions |
| `W-2 Jane Smith 2025.pdf.tmp.driveupload` | Google Drive upload caught mid-sync — ignored entirely |
| `vacation photo.jpg` | nothing matches it → review, never guessed at |

*OneDrive prospect? Skip the two Google rows — everything else is identical.*

### 6. The moment — sort and scan *(2.5 min)*

> "In production this runs by itself every fifteen minutes. Watch it take that
> pile apart — without a person opening a single file."

**Do:** click **Sort & Scan**. Then re-open **Open Client Folder** — the drop
zone is empty, and every original is sitting in `PBC` under the client's own
file name. Now walk the results:

- **The client's folder is clean.** "Everything they sent is in PBC, byte for
  byte, under the name they gave it. We never rename or delete their originals —
  we move them there and work from copies."
- **A01 — Received, 2 of 2.** "Both 2025 W-2s, renamed to our convention. The
  duplicate was kept but not counted twice."
- **A02 — Partial, 2 of 3.** "It knows exactly what's still owed. The reminder
  email to the client writes itself."
- **Needs review — and this is the important slide.** "Four things it refused to
  guess about: last year's W-2 — and read that note, *'looks like A01 but the
  period is wrong'* — the Word file, the Google Sheets link, and the holiday
  photo. It would have been easy to shove last year's W-2 into the prior-year
  returns folder. It didn't, because a tax document in the wrong folder is worse
  than one waiting for thirty seconds of your attention."

### 7. The accountant's view *(1 min)*

> "And where does all this land? In the tool every accountant already lives
> in — Excel. Status, date received, file counts, and plain-English notes
> you can paste into an email to the client verbatim."

**Do:** click **Open Manifest in Excel**. Show the Status/Notes columns and the
**Unfiled** sheet tab. Then click **Open Index** — `_index.xlsx`, the map from
every file the client sent to where it ended up and what we renamed it to, with
a reason recorded for anything in review.

> "If a client ever asks 'what happened to the thing I sent you on the 3rd?',
> that question takes five seconds to answer, and the answer is written down."

Bonus: keep Excel open, run another scan — the app banner explains the update
was safely parked and merges next scan.

### 8. The trust close *(1 min)*

> "Three guarantees, because you're trusting us with tax documents:
>
> 1. **Every decision is a deterministic rule.** No AI ever reads your
>    tax documents. A keyword either matches or it doesn't.
> 2. **Your originals are never altered.** We move each file you send into
>    the PBC folder — same bytes, same file name you gave it — and we work
>    from copies. Nothing of yours is ever renamed, edited or deleted, and
>    every move is written into the index.
> 3. **Professional judgment wins.** One column in the spreadsheet lets the
>    accountant override any automated result — the software advises,
>    the CPA decides."

**Do:** point at the assurance bar across the bottom of the app.

---

## Q&A crib sheet

- **"What about my business return?"** Same system, different first click —
  show the 1120-S or 1065 card and its completely different checklist.
- **"What if I rename a folder?"** Still tracked — matching is by the ID
  prefix, tolerant of renames.
- **"What about scanned paper documents?"** Text PDFs are read directly; pure
  image scans are flagged for human review (OCR is an optional add-on).
- **"Where do files live?"** Any shared folder — in production, a OneDrive or
  Google Drive folder shared per engagement; only the request folders are shared, the
  tracking sheet stays private to the firm.
- **"What does a wrong upload do?"** Nothing destructive — it's flagged with
  a reason; the client just drops in a replacement.

## Reset between meetings

Click **Reset Demo** in the app. Ten seconds; everything regenerates.
