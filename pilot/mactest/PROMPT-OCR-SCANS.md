# OCR for scans on a Mac - prompt for Claude Code on Jason's MacBook (P282, P283)

This is the Mac's share of checking `pilot/SPEC-ocr-scans.md`: that a scan
which shows its form number now files (P282), that the reader bench runs end
to end and writes counts only (P283), and that the Mac console installed from
the same commit does both. It uses **made-up documents only**, the ones the
suite's own fixtures draw. It is not the measurement: the firm's numbers come
from the office PC and `pilot/PROMPT-reader-bench.md`, and nothing here feeds
P284. A MacBook is a viewer and a build machine, never the computer that runs
a clients root (the runbook's "which machine runs the schedule").

## For Jason, before the session starts

1. The checkout is on `main` at or after the merge of pull request 45
   (`git log --oneline -1` names it), with `.venv` (Python 3.14) and
   `.venv311` (Python 3.11) built from the locks. `python` is not on this
   Mac's PATH; the prompt uses the two virtual environments by path.
2. The console in `/Applications` is the build of the same code: its
   `BUILD-INFO.txt` names the commit the merge brought in. Step 1 checks.
3. Step 5 (the console's own window) needs the Claude desktop app's computer
   use, and your yes: it changes the clients folder the installed console
   points at and sets the schedule up again. Without your yes it is skipped
   and recorded NOT VERIFIED, and the engine is still checked in step 4,
   through the installed build's own engine with throwaway folders.
4. Nothing is downloaded (the medium reader models stay absent, and the bench
   reports them as not measured, which is the right answer on a Mac), and
   nothing is committed or pushed unless you say so at the end.
5. Open Claude Code in the checkout and paste everything in the box below.

## The prompt

```
You are checking the OCR-for-scans change of Tax Document Console on this Mac, for Jason Park (a CPA,
not a programmer - report in plain English, in the software's own words: the request, the record,
Needs Review, the pass). Follow these rules the whole time:

SAFETY - never break these:
- Generative AI never reads a client financial document. Use ONLY the made-up documents this check
  draws under ~/PilotTest (every person in them is made up: John A. Smith, Jane R. Smith, Pat Q.
  Nobody). Never open, list or read any other folder or document on this computer. There is no
  firm corpus and no clients root on this Mac; if you find one, stop and tell Jason.
- Nothing is sent: no email, no upload, no push. Nothing is committed unless Jason says yes in
  step 7. Never trigger @claude in GitHub.
- Nothing is downloaded. The bench never fetches a model and you never run rapidocr's downloader;
  the medium tier is reported as not measured, and that is the expected result here.
- Never run `tools/backtest.py record`: the committed baseline is the firm's own number, and a
  made-up corpus must never overwrite it.
- Do not change the program's code. This is a check, not a fix. If something differs from what a
  step expects, record it word for word.
- Throwaway folders only for the engine: TRACKER_SETTINGS_DIR and TRACKER_DATA_HOME below point
  under ~/PilotTest. Never run the engine against the installed console's own data folder
  (~/Library/Application Support/tax-document-tracker-pilot) except in step 5, through the
  console's window, with Jason's yes.
- Never type, read, store or ask for the Mac's password; never use sudo; never turn off Gatekeeper
  or strip the quarantine mark. Start the console only from /Applications, quit it with Command-Q.
- If a permission rule of this session denies a folder or command a step needs, record that step
  NOT VERIFIED naming the rule and tell Jason; never work around a rule.

Python here is .venv/bin/python (3.14, the office's) and .venv311/bin/python (3.11, the floor).

1. WHERE THINGS STAND. In the checkout: `git status --porcelain` is empty and `git log --oneline -1`
   is on main at or after "Merge pull request #45" (Jason gives the hash if in doubt). Then
     grep Commit "/Applications/Tax Document Console.app/Contents/Resources/BUILD-INFO.txt"
   must name the commit that merge brought in (today 53b56e7; `git log --oneline -2 main` shows it
   under the merge). If the installed console is an older build, stop and tell Jason: he rebuilds and
   installs (`./build-mac.sh`, then the disk image into Applications) before this check means anything.
   Record both hashes, the macOS version (`sw_vers -productVersion`) and `uname -m` (must be arm64).

2. THE AFFECTED TESTS, each file its own process, under both interpreters, never with -m "not corpus":
     for py in .venv/bin/python .venv311/bin/python; do for t in test_router test_filer test_ocr test_content_check test_reader_bench test_backtest test_layers test_single_source test_repo_map; do echo "$py $t"; $py -m pytest -q tests/$t.py 2>&1 | tail -1; done; done
   Why these: router and filer carry P282's rule; ocr, content_check and reader_bench carry P283;
   backtest lends the bench its helpers; the last three are the guards every change runs. Not the
   whole suite (Jason, 2026-09-29). Record passed / skipped / failed per file and interpreter. In
   test_ocr a handful of skips is expected (the graphics-card pack and Windows-only paths); a skip
   whose reason says the reader could not be built is a finding. Also run
     .venv/bin/python -m ruff check . && .venv/bin/python tools/repo_map.py check
   and record both one-line answers.

3. THE MADE-UP CLIENTS FOLDER AND THE SCANS. If ~/PilotTest/Clients-ocr exists it is this check's
   own folder from an earlier run and nothing else; remove it, then:
     .venv/bin/python pilot/wintest/make_samples.py ~/PilotTest/Clients-ocr
   It prints the sample folder and the count of made-up documents in "Drop files here". Find the
   inbox and the return's folder (they are the only two paths you need):
     find ~/PilotTest/Clients-ocr -type d -name "Drop files here"
     find ~/PilotTest/Clients-ocr -type d -name "1040 - John A. Smith"
   Save the program printed under "THE SCAN BUILDER" at the end of this prompt as
   ~/PilotTest/ocr_scans_builder.py (outside the checkout) and run it from the checkout, fed on
   standard input so the checkout's own fixtures are importable:
     .venv/bin/python - "<the inbox>" ~/PilotTest/bench-corpus < ~/PilotTest/ocr_scans_builder.py
   It draws four more scans into the inbox (image-only PDFs, no text layer, so only the reader can
   say what they are) and a five-document bench corpus, and prints the year it used. The pile now
   holds, among the suite's usual made-up documents, five scans this check watches:
     a. Scanned forms.zip (from make_samples) - a zipped scan of a 1099-INT from Lakeside Credit Union
        to Jane R. Smith, title upright.         Expected: FILED under the interest-income request
        (its code is matched; the reason reads "... read from a scan that shows its form number"),
        the name confirmed. Before P282 this parked as Read From Scan Only.
     b. 1099-INT Harbor Mutual Savings scan.pdf - to John A. Smith, upright.   Expected: FILED, as a.
     c. 1099-INT Cedar Valley Bank sideways scan.pdf - the same kind of page turned a quarter turn.
        Expected: PARKED in Needs Review, or FILED under the interest-income request, and never
        under any other request. The reader turns tall crops itself, so a sideways page may keep
        its words out of order (then it parks as Read From Scan Only, guard 1), may lose them (then
        it parks as "matched no request, but its file name points at A02"; the first Mac run saw
        this), or may still read the title first (then it files). Record which happened.
     d. 1099-INT Pine Street Bank stranger scan.pdf - to Pat Q. Nobody, upright.
        Expected: PARKED in Needs Review; the reason is about the name on the page not matching
        anyone on the return (decision 128, unchanged). Record the exact words.
     e. W-2 Willow Lane Bakery scan.pdf - John A. Smith's W-2, upright.
        Expected: FILED under the W-2 request, as before P282 (a W-2 files on its required
        keywords, and P282 changes nothing for it), or PARKED as a near miss, "matched no request,
        but it shows the form number of A01; a person should confirm". The first Mac run saw the
        near miss: at today's 144 dpi the reader missed the third required phrase on this drawn
        page. That is a reading-quality data point for P284, recorded as such, not a failure of
        P282; landing under any other request would be. Record which happened and, if it parked,
        the reason word for word.
   Before the pass, record a fingerprint of every file in the inbox, so step 4 can show the
   originals moved byte for byte. The pile holds one deliberate sync placeholder (its name ends
   .driveupload); the pass leaves it in the inbox as "syncing", so it is left out here:
     (cd "<the inbox>" && find . -type f -not -name "*.driveupload" -exec shasum -a 256 {} + | sort -k2) > ~/PilotTest/results/ocr-before.sha256

4. THE PASS, WITH THE INSTALLED CONSOLE'S OWN ENGINE, nobody at the window. Throwaway folders,
   the way the schedule runs it (this is the walk's H10 shape):
     mkdir -p ~/PilotTest/ocr-settings ~/PilotTest/ocr-data ~/PilotTest/results
     TRACKER_SETTINGS_DIR=~/PilotTest/ocr-settings TRACKER_DATA_HOME=~/PilotTest/ocr-data .venv/bin/python -m tracker.settings ~/PilotTest/Clients-ocr
     TRACKER_PRODUCT_NAME="Tax Document Console" TRACKER_DATA_HOME=~/PilotTest/ocr-data "/Applications/Tax Document Console.app/Contents/Resources/tracker-api/tracker-api" --run --settings ~/PilotTest/ocr-settings --reminders never --log ~/PilotTest/results/ocr-runs.log
   Record the seconds it took and the last lines of ocr-runs.log (they hold made-up names only).
   Then read what the engine decided - counts first, then the rows:
     TRACKER_SETTINGS_DIR=~/PilotTest/ocr-settings TRACKER_DATA_HOME=~/PilotTest/ocr-data .venv/bin/python -m tracker.api firm | .venv/bin/python tools/reader_bench.py review-codes --out ~/PilotTest/results/ocr-review-codes.json
     TRACKER_SETTINGS_DIR=~/PilotTest/ocr-settings TRACKER_DATA_HOME=~/PilotTest/ocr-data .venv/bin/python -m tracker.api state --engagement "<the return's folder>"
   From the state: for each of the five scans a to e, which request it filed under and its reason
   sentence, or which Needs Review reason parked it. Compare with step 3's expectations; a
   difference is a finding, recorded, never fixed. Count how many rows Needs Review holds in all and
   how many of them are Read From Scan Only (review-codes prints that count by code): with P282 that
   count is 0, or 1 if c parked that way; the suite's own scanned sample in the pile files as it did
   before. If the pipe prints "the reply is not JSON", or hangs for more than a minute, stop it,
   record that word for word with the time, and run it once more; the first Mac run saw both, once
   each, and the retry answered at once.
   Byte for byte: every file that moved out of the inbox must be found under the client's folder
   for the year with the same fingerprint:
     (cd ~/PilotTest/Clients-ocr && find Clients -type f -not -path "*/Drop files here/*" -exec shasum -a 256 {} + | awk '{print $1}' | sort) > ~/PilotTest/results/ocr-after.hashes
     awk '{print $1}' ~/PilotTest/results/ocr-before.sha256 | sort | comm -23 - ~/PilotTest/results/ocr-after.hashes
   The comm line must print nothing (every original's fingerprint is still there). The parked scans
   are also moved, into the review folder; a review copy is a copy, the original keeps its bytes.
   Run the same pass a second time and read the state again: nothing changes, and the parked rows
   stay parked (a pass does not re-route a row already in Needs Review).

5. THE CONSOLE'S WINDOW - only with Jason's yes and computer use; otherwise NOT VERIFIED. It
   changes the installed console's clients folder and sets up the schedule, so build a second fresh
   folder for it (the engine's state of step 4 lives in a throwaway folder and must not be mixed in):
     .venv/bin/python pilot/wintest/make_samples.py ~/PilotTest/Clients-ocr-app
     .venv/bin/python - "<that folder's inbox>" ~/PilotTest/bench-corpus-unused < ~/PilotTest/ocr_scans_builder.py
   Open Tax Document Console from Applications (Gatekeeper's Open Anyway is Jason's; record the
   dialog's words). In Settings choose ~/PilotTest/Clients-ocr-app as the clients folder by typing
   its path (Command-Shift-G), never by browsing. The schedule sets itself up (a toast says so; no
   button pressed) and the first pass runs within a minute. Then, with screenshots into
   ~/PilotTest/results/screens-ocr: the return's page shows a and b and e filed, each with its
   reason on the row; Needs Review shows c as Read From Scan Only and d with its name reason; the
   Read From Scan Only row's hold says a person decides. Open c's row: Unfile is not offered for a
   parked row, and the review copy opens. Then Tools > Remove the Schedule From This Mac..., record
   the sentence, and quit with Command-Q. Leave the console as Jason keeps it: schedule removed.

6. THE BENCH ON THE MADE-UP CORPUS (P283's tool, end to end on a Mac). The builder wrote four scans
   to ~/PilotTest/bench-corpus: two upright 1099-INTs, a W-2 and a 1098 (no sideways page: its
   outcome is not fixed, and a bench row needs one right answer).
   Write the expectations skeleton outside the repository and fill it in (these are made-up pages,
   so you may):
     .venv/bin/python tools/backtest.py collect ~/PilotTest/bench-corpus --catalog 1040 --year <the year the builder printed> --out ~/PilotTest/bench-out/expectations.csv
   In the "expected" column put the request's identifier: A02 for the two 1099-INT files, A01 for
   the W-2, C01 for the 1098 (the 1040 catalog's interest-income, W-2 and mortgage-interest
   requests; `.venv/bin/python -m tracker.api templates` lists them, check there). Then:
     .venv/bin/python tools/reader_bench.py variants
     .venv/bin/python tools/reader_bench.py run ~/PilotTest/bench-corpus --expectations ~/PilotTest/bench-out/expectations.csv --out ~/PilotTest/bench-out/bench-mac.json
   Expected: `variants` prints 21 names and the first is dpi300-floor0.50-prep-small; `run` prints a
   table row as each variant finishes; the 8 medium variants read "not measured" (no models folder
   was given, and none was fetched); the 13 small variants each count 3 or 4 right on these clean
   drawn pages (the W-2 lands as a shortlist park when the reader misses one of its required
   phrases, as the first Mac run saw at every dpi), and the shipped variant (the first row under
   the header) is the one Part C is measured against. A variant that reads the W-2 well enough to
   file it is worth naming: it is the kind of difference P284 looks for. Record the shipped variant's seconds per page
   (median, worst, first load) and the whole run's minutes. Open bench-mac.json and confirm it
   holds counts, seconds, settings and codes only - no file name, folder, path or word of a page -
   and say so. Also, for the baseline tool on the same pages (never `record`):
     .venv/bin/python tools/backtest.py run ~/PilotTest/bench-corpus --ocr --expectations ~/PilotTest/bench-out/expectations.csv --out ~/PilotTest/bench-out/backtest-mac.json
   Record its agreement line (the first Mac run: 4 routed, 75% agreement, the W-2 parked).

7. REPORT. Write ~/PilotTest/results/RESULT-ocr-scans.md: the two hashes and the macOS version; the
   test table (file x interpreter: passed / skipped / failed); for each of the five scans, expected
   and seen; the Needs Review counts by code; the byte-for-byte check; the second pass; step 5's
   result or NOT VERIFIED and why; the bench table's shipped row and its seconds; the backtest's
   agreement; every difference, word for word. Then tell Jason in plain English: PASS or FAIL
   overall, and each finding. A step is PASS only if you saw it. Nothing is committed or pushed
   unless Jason says yes, and then only RESULT-ocr-scans.md, on a branch, as a draft pull request
   with "[skip ci]" in the message.

THE SCAN BUILDER (the program step 3 runs; it writes only under the two folders it is given):

import sys
from pathlib import Path

from tests import samples as s

inbox, corpus = Path(sys.argv[1]), Path(sys.argv[2])
corpus.mkdir(parents=True, exist_ok=True)

# The pile's four extra scans (step 3's b to e). Image-only pages: no text layer.
s.scanned_pdf(inbox / "1099-INT Harbor Mutual Savings scan.pdf",
              s.lines_1099_int("Harbor Mutual Savings", s.SCRATCH_CLIENT, s.YEAR))
s.scanned_pdf(inbox / "1099-INT Cedar Valley Bank sideways scan.pdf",
              s.lines_1099_int("Cedar Valley Bank", s.SCRATCH_CLIENT, s.YEAR), rotate=90)
s.scanned_pdf(inbox / "1099-INT Pine Street Bank stranger scan.pdf",
              s.lines_1099_int("Pine Street Bank", "Pat Q. Nobody", s.YEAR))
s.scanned_pdf(inbox / "W-2 Willow Lane Bakery scan.pdf",
              s.w2_lines(s.SCRATCH_CLIENT, "Willow Lane Bakery LLC", s.YEAR))

# The bench corpus (step 6): two upright 1099-INTs, a W-2 and a 1098, all upright.
s.scanned_pdf(corpus / "1099-INT Harbor Mutual Savings.pdf",
              s.lines_1099_int("Harbor Mutual Savings", s.SCRATCH_CLIENT, s.YEAR))
s.scanned_pdf(corpus / "1099-INT Riverside Savings Bank.pdf",
              s.lines_1099_int("Riverside Savings Bank", s.SCRATCH_CLIENT, s.YEAR))
s.scanned_pdf(corpus / "W-2 Willow Lane Bakery.pdf",
              s.w2_lines(s.SCRATCH_CLIENT, "Willow Lane Bakery LLC", s.YEAR))
s.scanned_pdf(corpus / "1098 Cedar Ridge Mortgage.pdf",
              s.form_1098_lines("Cedar Ridge Mortgage Company", s.SCRATCH_CLIENT, s.YEAR))
print(f"year {s.YEAR}; 4 scans added to the inbox, 4 pages in the bench corpus at {corpus}")
```

## Why the prompt reads as it does

- **Made-up documents only, and no measurement** - this Mac holds no corpus
  and runs no clients root; the standing rule keeps it that way. The numbers
  that choose P284 come from the office PC.
- **The installed build's own engine, in throwaway folders** - the point is
  that the Mac console Jason has in Applications carries the change, not only
  the checkout; running its frozen engine the way the schedule does, against
  folders under `~/PilotTest`, proves that without touching the console's own
  data (decision 186, P193).
- **Five scans** - two file on the new rule; one turned sideways shows what
  the rule does with a page whose lines may come back out of order (it files
  or it parks, and never lands anywhere else: nothing is guessed); one parks
  on the name (decision 128 unchanged); one files as it always did (required
  keyword, unchanged). Together they are the guards as a person would see them.
- **The bench without models** - the medium tier reported as not measured is
  the proof that the tool never downloads; the counts-only report is the
  proof that nothing of a page reaches a file a person might paste.
- **Never `record`** - the committed baseline belongs to the firm's own
  documents; a made-up corpus scoring well would only hide a real regression.
