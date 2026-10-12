# Reader bench - prompt for Claude Code on the office PC

This is the measurement of P283 (`pilot/SPEC-ocr-scans.md` section 2): which
reading settings help on the firm's own scans and photos, and what Needs
Review looks like before and after P282. It runs on the **office PC only**
(JPPC, the designated machine), never on a Mac or any other viewer, in a
Claude Code session opened in the office checkout. Part C (P284) ships the
settings the numbers favour; it waits for what this brings back.

## For Jason, before the session starts

1. The office checkout is on `claude/ocr-scans` at Part B's head, and a
   second checkout of `main` sits beside it (step 1 makes it).
2. Have two folders ready and tell the session where they are: the firm's
   sorted documents (the folder `backtest.py` runs on) and the photo corpus
   (the folder `TRACKER_REAL_CORPUS` names, if its expectations file is
   filled in). The session never opens, lists or reads either one.
3. The medium models are downloaded by one command in step 3. The session
   will ask you in the chat before it runs it: say yes or no there.
4. A full run can take a night. Step 4 gives the arithmetic and the cheaper
   order.

## The prompt

```
You are running the reader bench for Tax Document Console on this computer, for Jason Park (a CPA, not a
programmer - report in plain English). Follow these rules the whole time:

SAFETY - never break these:
- Generative AI never reads a client financial document. You do not open, list, read, name or quote
  any document, file name or folder name inside the firm's corpus folders, the photo corpus or the
  clients root. The tools below open the documents; you only run the commands and paste the counts
  and seconds they write. If a command prints anything else - a name, a path below a corpus folder, a
  word of a document - do not repeat it; tell Jason what kind of thing it was and stop.
- Nothing is sent: no email, no upload. The only file you ever commit is docs/backtest-baseline.json
  in step 2, on its own branch, as a DRAFT pull request. Do not push anything else, do not mark a pull
  request ready, do not run CI, and never trigger @claude in GitHub.
- Do not change the program's code. This is a measurement, not a fix. If something fails, record it.
- <outside> below is a folder outside both the repository and the clients root (for example
  %USERPROFILE%\ReaderBench). Every report goes there. The bench's and the backtest's --out refuse a
  path inside the repository themselves; do not work around that.
- Stop and ask Jason if: a step would touch a folder outside <outside>, the two checkouts and the
  two corpus folders, a download asks for anything but the two medium models, or a command wants
  administrator rights.

1. REFUSE IF THIS IS NOT THE OFFICE PC.
   Run, in the claude/ocr-scans checkout:
     .venv\Scripts\python -c "from tracker import scheduling, settings; print(bool(settings.clients_root()), scheduling.task_exists())"
   Both must print True: the clients root is set and the schedule is registered on this computer.
   Anything else, stop and tell Jason this is not the office PC. Do not print the clients root.
   Then: git status must be clean on claude/ocr-scans, and `git log -1 --format=%h` is Part B's head
   (Jason gives you the hash). Install from the locks the way Setup.bat does, hash-checked:
     .venv\Scripts\python -m pip install --require-hashes -r requirements.lock
     .venv\Scripts\python -m pip install --require-hashes --no-deps -r requirements-nodeps.lock
   Make the second checkout, for the numbers before P282 and for the baseline:
     git worktree add ..\bench-main main
     (in ..\bench-main) python -m venv .venv, then the same two pip installs there.
   Why: P282's rule lives in the claude/ocr-scans checkout, so "before" has to run on main's code.

2. TODAY'S NUMBERS, BEFORE PART A IS INSTALLED (the installed app is still main's build).
   a. Needs Review by code, today - why: it is the count Part A is meant to lower, and it needs the
      firm's recorded rows, which Part A's code does not change:
        .venv\Scripts\python -m tracker.api firm | .venv\Scripts\python tools\reader_bench.py review-codes --out <outside>\review-before.json
   b. The backtest baseline, with the reader on, on main's code (in ..\bench-main) - why: decision 92
      parks every scan without the reader, so a baseline without --ocr says nothing about Part A, and
      every later routing change is held to this number:
        .venv\Scripts\python tools\backtest.py run "<firm corpus>" --ocr --out <outside>\backtest-before.json
        .venv\Scripts\python tools\backtest.py record --report <outside>\backtest-before.json
      `record` rewrites docs\backtest-baseline.json. Commit that one file on a new branch cut from
      main (git switch -c baseline-before-p282), push the branch and open a DRAFT pull request. That is
      the only commit and the only pull request of this session.
   c. The photo corpus: if it has no filled-in expectations file, write the skeleton and STOP:
        .venv\Scripts\python tools\backtest.py collect "<photo corpus>" --catalog 1040 --year 2025 --out <outside>\photo-expectations.csv
      Tell Jason the skeleton is ready for a person to fill in; you do not fill it in. Carry on with
      the firm corpus alone until it is.

3. THE MEDIUM MODELS - a person approves the download.
   They are not shipped and the bench never fetches them. Ask Jason in the chat first, saying: the
   command below runs rapidocr's own downloader, fetching PP-OCRv6_det_medium.onnx and
   PP-OCRv6_rec_medium.onnx from www.modelscope.cn (the addresses in rapidocr's default_models.yaml),
   and rapidocr checks each file's SHA-256 against its own list. On a yes only:
     .venv\Scripts\rapidocr config --save_cfg_file <outside>\medium.yaml
   Edit <outside>\medium.yaml: set Global.model_root_dir to <outside>\medium-models, Global.use_cls to
   false, and Det.model_type and Rec.model_type to "medium". Then:
     .venv\Scripts\rapidocr download_models --config <outside>\medium.yaml
   <outside>\medium-models must now hold PP-OCRv6_det_medium.onnx and PP-OCRv6_rec_medium.onnx. If it
   does not, record that and run the bench without --models: every medium variant is then reported as
   not measured, which is a fine answer.

4. THE BENCH, in the claude/ocr-scans checkout, on each corpus that has an expectations file:
     .venv\Scripts\python tools\reader_bench.py variants          (the 36 names; check the first is dpi144-floor0.50-off-small)
     .venv\Scripts\python tools\reader_bench.py run "<corpus>" --out <outside>\bench-<corpus>.json --models <outside>\medium-models
   The full grid: 36 variants, each reading every scan and photo of the corpus once. Why each corpus on
   its own: the firm's sorted documents are mostly scans, the photo corpus is the phone photos, and the
   ceiling (6 seconds a page) is judged on both.
   Time, worked out before starting: read the shipped variant's per-page median from the first line of
   the table the run prints (it is printed as each variant finishes). Seconds for the grid are about
   pages x that median x 65 (18 small variants, plus 18 medium variants at about 2.6 times small),
   and the 300 dpi variants cost more than that: allow up to twice as much. `corpus.pages` in the
   report is the page count; the run prints nothing else about the corpus. If the estimate passes one
   night (ten hours), run the small tier first:
     ... run "<corpus>" --out <outside>\bench-<corpus>-small.json --tier small
   read the table, pick the dpi, floor and de-lining with the most `right` and the fewest `wrong`
   within the ceiling, and run the medium tier second at those alone:
     ... run "<corpus>" --out <outside>\bench-<corpus>-medium.json --models <outside>\medium-models --tier medium --dpi <d> --floor <f> --delining <off|on>
   (the shipped variant is always measured too, so the two reports share a baseline row). A variant
   that says "not measured" is a result, not a failure. The run reads on the processor, in this
   process, with no safety stop: if it seems stuck, wait; a page takes seconds, not minutes.

5. PART A INSTALLED, then the same numbers after it.
   Jason (or the usual route) installs the Part A build on this PC; wait until he says it is in, and
   until the first scheduled pass after it has run. Then:
     .venv\Scripts\python -m tracker.api firm | .venv\Scripts\python tools\reader_bench.py review-codes --out <outside>\review-after.json
   and, in the claude/ocr-scans checkout:
     .venv\Scripts\python tools\backtest.py run "<firm corpus>" --ocr --out <outside>\backtest-after.json
   and, in ..\bench-main (the checkout that holds the recorded baseline):
     .venv\Scripts\python tools\backtest.py check --report <outside>\backtest-after.json
   Exit 1 is a finding to report, not to fix: say the two agreements it printed and stop there.

6. WHAT COMES BACK.
   Paste into your reply for Jason's CODE UPDATE, and nothing else: the contents of review-before.json,
   backtest-before.json, review-after.json, backtest-after.json and every bench-*.json - they hold
   counts and seconds only - plus the exit code of `check`, the shipped variant's seconds per page
   from each bench report, which variants said "not measured", and the hours each run took. No
   document name, folder name, path below a corpus folder or word of a document, ever. The reports
   stay on this computer, in <outside>.
```

## Why the prompt reads as it does

- **Refuse off the office PC** - the schedule runs on one computer only (the
  runbook's "which machine runs the schedule"), and the corpus is only
  reachable from it.
- **Main's code for "before"** - `backtest.py` and `check` read the checkout
  they run in; P282's rule is in `claude/ocr-scans`. A baseline measured on
  that branch would already hold Part A's change and could not show it.
- **Nothing downloaded by the bench** - `ocr._refuse_downloads` stands under
  it; the medium models come from a person's approved command.
- **Counts and seconds only** - the standing rule that client data never
  enters a repository, a transcript or a Drive thread; the bench, the
  backtest and `review-codes` are built so their outputs hold none.
