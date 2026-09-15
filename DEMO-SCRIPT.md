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
   - **Open Client Folder** (the engagement's `Shared\` tree)
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
> to your situation, add anything unusual, and your entire folder structure
> builds itself."

**Do:**
1. Type the **prospect's own name** (e.g. "Smith Family 2025 Form 1040") —
   this lands every time
2. Untick one or two template items ("no marketplace insurance — gone")
3. Add a custom request: type "Rental Property Records", keyword "rental",
   click **Add**
4. Click **Create Engagement** — the banner confirms folders are scaffolded
5. Click **Open Client Folder** — the folders *already exist*, README included

> "That's the whole onboarding. The list you just watched me build is now a
> live, self-checking engagement."

*(The engagement you created works for the rest of the demo — the core 1040
items match the sample documents. Or switch back to the Smith Family
engagement with the dropdown; both work identically.)*

### 4. What the client sees *(1 min)*

> "Here is your entire experience as the client. One shared folder. One
> subfolder per document. Plain-English instructions. No portal, no password,
> no software to learn. If you can drag a file, you're done."

**Do:** click **Open Client Folder**. Open `_README.txt` briefly.

### 5. Play the client — including the mistakes *(2 min)*

> "Let's be an honest client: helpful, busy, and occasionally wrong. I'll
> hand over both spouses' W-2s... but also **last year's W-2** by mistake,
> the same W-2 uploaded **twice**, a **Word doc** where we need the actual
> 1098 PDF, and — because it always happens — a vacation photo dropped in
> the wrong place."

**Do:** click **Open Sample Documents**, drag into the client folder:

| Sample file | Drop into | Why it's in the demo |
|---|---|---|
| `W-2 John Smith 2025.pdf` | A01 | valid |
| `W-2 John Smith 2025 - Copy.pdf` | A01 | duplicate — ignored, not double-counted |
| `W-2 Jane Smith 2025.pdf` | A01 | valid — completes the 2 expected |
| `W-2 Jane Smith 2024 - old.pdf` | A01 | wrong tax year — content check will catch it |
| `1099-INT First National.pdf`, `1099-DIV Vanguard 2025.csv` | A02 | only 2 of the 3 requested → Partial |
| `2024 Form 1040 Tax Return.pdf` | B01 | valid |
| `Form 1098 Mortgage Interest.pdf` | C01 | valid |
| `Mortgage Notes.docx` | C01 | wrong file type |
| `Donation Receipts 2025.xlsx` | D01 | valid |
| `vacation photo.jpg` | **loose in the top folder** | goes to "Unfiled" |

### 6. The moment — run the scan *(2 min)*

> "In production this runs by itself every 15 minutes. Watch what it works out
> — without a person opening a single file."

**Do:** click **Run Scan**. Then walk the results top to bottom:

- **A01 — Received, 2 of 2.** "It found both 2025 W-2s, ignored the duplicate
  copy, and — read the note — it flagged the 2024 W-2 as the wrong year.
  It caught that by reading the document's own text."
- **A02 — Partial, 2 of 3.** "It knows exactly what's still owed. The reminder
  email to the client writes itself."
- **B01 — Received.** "Prior-year return, verified by content."
- **C01 — Received**, with a note rejecting the Word file. "Right document
  accepted, wrong format called out."
- **D01 — Received.**
- **Unfiled: vacation photo.jpg.** "Nothing is ever silently lost or deleted —
  anything unexpected is surfaced for a human to look at."

### 7. The accountant's view *(1 min)*

> "And where does all this land? In the tool every accountant already lives
> in — Excel. Status, date received, file counts, and plain-English notes
> you can paste into an email to the client verbatim."

**Do:** click **Open Manifest in Excel**. Show the Status/Notes columns and
the **Unfiled** sheet tab. Bonus: keep Excel open, run another scan — the app
banner explains the update was safely parked and merges next scan.

### 8. The trust close *(1 min)*

> "Three guarantees, because you're trusting us with tax documents:
>
> 1. **Every decision is a deterministic rule.** No AI ever reads your
>    tax documents. A keyword either matches or it doesn't.
> 2. **The scanner is read-only.** It never moves, renames, or deletes a
>    file. Ever. Your folder is your folder.
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
