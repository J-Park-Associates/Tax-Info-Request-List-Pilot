# Reader bench - prompt for Claude Code on the office PC

This is the measurement of P282 and P285 (P283's tool, P285's grid:
`pilot/SPEC-ocr-scans.md` section 2 and `pilot/SPEC-ocr-prepare.md`): which
reading settings help on the firm's own scans and photos - the page drawn at
300 or 144 dots per inch, prepared or raw, and each step of the preparation
turned off one at a time - and what Needs Review looks like before and after
P282 and P285. It runs on the **office PC only** (JPPC, the designated
machine), never on a Mac or any other viewer, in a Claude Code session opened
in the office checkout. P284 ships the settings the numbers favour, choosing
among prepared settings; it waits for what this brings back.

## For Jason, before the session starts

1. The office checkout is on **the branch and head you name**: P285's head
   on `claude/ocr-prepare`, or `main` once it has landed - never
   `claude/ocr-scans`, which is gone (it landed as pull request #45). A
   second checkout of the commit P282 stacks on sits beside it (step 1 makes
   it). Give the session two hashes: the head, and that "before" commit
   (today's value is `dcb02c3`, which holds neither P282 nor P285). `main`
   holds P282 already and may hold P285, so it is not the "before".
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
   Run, in the office checkout (the head Jason names):
     .venv\Scripts\python -c "from tracker import scheduling, settings; print(bool(settings.clients_root()), scheduling.task_exists())"
   Both must print True: the clients root is set and the schedule is registered on this computer.
   Anything else, stop and tell Jason this is not the office PC. Do not print the clients root.
   Then: git status must be clean, and `git log -1 --format=%h` is the head Jason gives
   (he gives you the hash and the branch, and a second hash beside it: the commit P282 stacks on,
   today's value `dcb02c3`; call it <before>). Install from the locks the way Setup.bat does, hash-checked:
     .venv\Scripts\python -m pip install --require-hashes -r requirements.lock
     .venv\Scripts\python -m pip install --require-hashes --no-deps -r requirements-nodeps.lock
   Make the second checkout, for the numbers before P282 and P285 and for the baseline:
     git fetch
     git worktree add --detach ..\bench-before <before>
     (in ..\bench-before) python -m venv .venv, then the same two pip installs there.
   Why: P282's rule and P285's preparation live in the head's checkout, and `main` may already hold
   both, so "before" has to run on the exact commit P282 stacks on, not on main.

2. TODAY'S NUMBERS, BEFORE P282 AND P285 ARE INSTALLED (the installed app is still the build from before them).
   a. Needs Review by code, today - why: it is the count P282 is meant to lower, and it needs the
      firm's recorded rows, which neither decision's code changes:
        .venv\Scripts\python -m tracker.api firm | .venv\Scripts\python tools\reader_bench.py review-codes --out <outside>\review-before.json
   b. The backtest baseline, with the reader on, on the before commit's code (in ..\bench-before) - why: decision 92
      parks every scan without the reader, so a baseline without --ocr says nothing about P282 or P285, and
      every later routing change is held to this number:
        .venv\Scripts\python tools\backtest.py run "<firm corpus>" --ocr --out <outside>\backtest-before.json
        .venv\Scripts\python tools\backtest.py record --report <outside>\backtest-before.json
      `record` rewrites docs\backtest-baseline.json. Commit that one file on a new branch cut from
      main (git switch -c baseline-before-p282 origin/main - the recorded file carries over), push the
      branch and open a DRAFT pull request. That is
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

4. THE BENCH, in the office checkout (the head Jason names), on each corpus that has an expectations file:
     .venv\Scripts\python tools\reader_bench.py variants          (the 21 names; check the first is dpi300-floor0.50-prep-small)
     .venv\Scripts\python tools\reader_bench.py run "<corpus>" --out <outside>\bench-<firm|photos>.json --models <outside>\medium-models
   The report names are fixed labels (bench-firm*.json, bench-photos*.json, with -small or -medium
   added below), never the corpus folder's name or path, which would be repeated in the transcript.
   The full grid: 21 variants, each reading every scan and photo of the corpus once - the 16 of the
   main grid (300 and 144 dpi, floor 0.5 and 0.7, prepared and raw, small and medium models) and
   the 5 ablation rows (the shipped settings with one step off, or Otsu's threshold in place of
   Sauvola's). The raw rows are the reading before P285 (the 144 dpi one exactly), so P285 needs no
   second checkout: its "before" is on the same code. Why each corpus on its own: the firm's sorted
   documents are mostly scans, the photo corpus is the phone photos, and the ceiling (6 seconds a
   page) is judged on both.
   Time, worked out before starting: read the shipped variant's per-page median from the first row
   under the table's header (call it m), which the run prints as each variant finishes. A 300 dpi
   small variant costs about m a page, a 144 dpi one about half, a medium one about 2.6 times its
   small one. So the 13 small variants (8 of the main grid, 5 ablation rows) cost about 11 m a page,
   the 8 medium ones about 16 m, and all 21 about 27 m a page: seconds for the grid are about
   pages x m x 27 (500 pages at m = 2 seconds is 7.5 hours). `corpus.pages` in the report is the
   page count; the run prints nothing else about the corpus. If pages x m x 27 passes one night
   (ten hours), run the small tier first (13 variants):
     ... run "<corpus>" --out <outside>\bench-<firm|photos>-small.json --tier small
   read the table, pick the dpi, floor and preparation (prep or raw) with the most `right` and the
   fewest `wrong` within the ceiling, and read the ablation rows for which step earns its place
   (a step whose removal does not lower `right`, or raises it, is one P284 may turn off). Then run
   the medium tier second at those alone:
     ... run "<corpus>" --out <outside>\bench-<firm|photos>-medium.json --models <outside>\medium-models --tier medium --dpi <d> --floor <f> --prep <prep|raw> --ablation off
   (the shipped variant is always measured too, so the two reports share a baseline row). A variant
   that says "not measured" is a result, not a failure. The run reads on the processor, in this
   process. The safety stop is still armed: no page starts after the one before it overran 60 seconds
   or after the document's 600, but a page already under way is unbounded, so if it seems stuck, wait;
   a page takes seconds, not minutes. A slow variant can park a multi-page scan through the stop, and
   that counts as a park in the numbers. The report is rewritten after every variant; a variant that
   failed is in it as "not measured" with the name of its error. The photos' seconds are their own
   (`photo_median`, `photo_worst`): P285 reads a photo at a long side of 3300, about 2.7 times the
   pixels it was read at, and P284 can split the photos' long side from the scans' if they run long.

5. THE BUILD CARRYING P282 AND P285 INSTALLED, then the same numbers after it.
   Jason (or the usual route) installs that build on this PC; wait until he says it is in, and
   until the first scheduled pass after it has run. That pass reads every document's verdict again,
   because the verdict cache moved with P285 (text-layer documents are quick; scans and photos are
   slow, once), so it takes longer than a usual pass: wait for it to finish before `review-codes`.
   A row already in Needs Review stays there until a person files it, so the count moves only on
   documents that arrive after the install. Then:
     .venv\Scripts\python -m tracker.api firm | .venv\Scripts\python tools\reader_bench.py review-codes --out <outside>\review-after.json
   and, in the office checkout:
     .venv\Scripts\python tools\backtest.py run "<firm corpus>" --ocr --out <outside>\backtest-after.json
   and, in ..\bench-before (the checkout that holds the recorded baseline):
     .venv\Scripts\python tools\backtest.py check --report <outside>\backtest-after.json
   Exit 1 is a finding to report, not to fix: say the two agreements it printed and stop there.
   These "after" numbers carry P282 and P285 together; the bench's raw and prepared rows are what
   tell the two apart.

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
- **The commit P282 stacks on for "before"** - `backtest.py` and `check`
  read the checkout they run in; P282's rule and P285's preparation are in
  the head Jason names, and by the time this runs `main` may hold them too. A
  baseline measured on either would already hold their change and could not
  show it.
- **The bench's raw rows are P285's "before"** - on the same code. `raw` is
  every step of the preparation off, and `dpi144-floor0.50-raw-small` is
  exactly the reading before P285, so the comparison of prepared against raw
  needs no second checkout; the checkout of step 1 is for P282 and for the
  baseline.
- **Nothing downloaded by the bench** - `ocr._refuse_downloads` stands under
  it; the medium models come from a person's approved command.
- **Counts and seconds only** - the standing rule that client data never
  enters a repository, a transcript or a Drive thread; the bench, the
  backtest and `review-codes` are built so their outputs hold none.
