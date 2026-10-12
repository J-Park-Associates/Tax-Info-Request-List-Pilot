# Pilot 0.4 - review-codes asks the firm summary itself (P286) - build handoff

Built by the builder session on branch `claude/suspicious-mendel-ebfdb8`
(from `main` at `62512fd`), against
[`../SPEC-review-codes-pipe.md`](../SPEC-review-codes-pipe.md). Nothing is
pushed. The review is a separate session. No client data is in this note: the
hand check ran on made-up pilot data and only code counts were looked at.

## What was built, by ruling

- **R1.** `python tools/reader_bench.py review-codes [--out <file>]` runs the
  firm command itself. The pipe is gone from the bench's docstring, parser
  help, `docs/tools.md`, `pilot/PROMPT-reader-bench.md` (both lines) and
  `pilot/mactest/PROMPT-OCR-SCANS.md` (the command line, and the paragraph that
  told the Mac session to retry a pipe; now it says the command answers in
  seconds, needs no retry, and anything else is a finding).
- **R2.** `_run_firm()` starts `[sys.executable, "-m", "tracker.api",
  runner.FIRM_COMMAND]` with stdin closed (`DEVNULL`), stdout and stderr kept,
  no `env` argument, `cwd=ROOT`, `timeout=runner.FILL_TIME_LIMIT_SECONDS`, and
  `CREATE_NO_WINDOW` where it exists. `subprocess` and `runner` are imported
  inside the helper, so the module's import block is untouched (R9).
- **R3 / R6.** stderr is captured, counted by non-blank lines, never shown. A
  failure sentence ends with "(it also wrote {lines} on stderr, not shown)";
  a success with stderr prints the counts as before and one line on the bench's
  stderr, exit 0. The six sentences are module constants in the review-codes
  section (`FIRM_NOT_STARTED`, `FIRM_TOO_LONG`, `FIRM_NO_REPLY`,
  `FIRM_NOT_AN_OBJECT`, `FIRM_REFUSED`, and the two stderr suffixes).
- **R4.** The limit is `runner.FILL_TIME_LIMIT_SECONDS`, imported, not copied.
- **R5.** `firm_reply_of(stdout, returncode)` drops blank lines, drops every
  line that is a JSON object under `progress.PROGRESS_KEY`, and takes the last
  line left. No line left, not a JSON object, a `failure`/`error` key or a
  nonzero exit each raise `BacktestError` by kind and exit code. The refusal
  kind is `failure.kind` when it is in `progress.FAILURE_KINDS`, else
  `unknown`. `review_codes`'s one sentence no longer mentions the pipe.
- **R7.** The bench never reads its own stdin (a test makes every read raise).
- **R8.** `tracker/api.py`, `tracker/resident.py`, `tracker/progress.py` are
  not touched.
- **R9.** In `tools/reader_bench.py` only the usage line, the one docstring
  sentence, the review-codes section, `_cmd_review_codes` and the parser help
  changed. `--out` is checked (refused inside the repository) before firm
  starts.
- **Section 4 documents.** `docs/tools.md`, the two prompts, the two italic
  "Changed by P286" lines in `pilot/SPEC-ocr-scans.md` (one under the code block
  after the usage listing, one inside the before-numbers bullet), the P286 row at
  the end of `pilot/DECISIONS.md`, and the two curated sentences in
  `docs/repo-map.curated.json` followed by `repo_map.py update`.
- **Tests** (`tests/test_reader_bench.py`): the two existing review-codes tests
  now feed `_run_firm` (the first behind two real count lines). The SPEC's nine
  new tests are at the end of the file, plus one extra (below), ten in all, with three small
  helpers (`a_firm_run`, `a_reply`, `counts_of`) there too. The new tests import
  `progress`, `runner`, `errors` and `subprocess` inside themselves, so the
  test file's import block is untouched.

## The gate

Each file its own process, run in parallel, no `-m "not corpus"`. 3.14 is
`../../../.venv`, 3.11 is `../../../.venv311`.

| File | 3.14 | 3.11 |
|---|---|---|
| tests/test_reader_bench.py | 28 passed | 28 passed |
| tests/test_layers.py | 31 passed | 31 passed |
| tests/test_single_source.py | 217 passed | 217 passed |
| tests/test_repo_map.py | 82 passed | 82 passed |
| tests/test_tripwire.py | 23 passed | 23 passed |
| tests/test_errors.py | 83 passed | 83 passed |

Also: `python -m ruff check .` passed; `repo_map.py update` then `check`
passed ("Map is current"); `vocab_report.py check` said "Report is current",
so no rebuild and no `test_vocab_report` run. Dead code: ruff reports none in
the changed files, and `io`, `json` and `sys` are still used in the test file.

## Hand check (made-up data, the scratchpad copies)

`TRACKER_SETTINGS_DIR` and `TRACKER_DATA_HOME` pointed at the scratchpad
copies. `firm-view.json` was deleted first. `review-codes` run twice from the
harness with no `< /dev/null`, under `/usr/bin/time -p`:

| Run | Elapsed (real) | Result |
|---|---|---|
| 1 (cold) | 0.46 s | printed the counts, exit 0 |
| 2 (warm) | 0.44 s | printed the same counts, exit 0 |

Both printed seven codes with 1 or 2 rows each. To confirm the first run was
really cold, `firm` was run directly once more after deleting the file: it
printed two count lines before its reply, and `review-codes` after deleting it
again printed the counts all the same. The old pipe's two failures (not JSON,
hang) cannot occur: counts are skipped by the progress rule and firm's input is
closed.

## Deviations from the SPEC

1. **`capture_output=True` in place of `stdout=PIPE, stderr=PIPE`.** The repo's
   ruff (UP022) refuses the two-PIPE spelling. They mean the same. The launch
   test asserts `capture_output is True` and that no `stdout`/`stderr` keyword
   is passed.
2. **One extra test**, `test_review_codes_refuses_an_out_inside_the_repository_before_firm_starts`,
   for section 3's "before firm starts" ordering, which the SPEC's list did not
   pin.
3. **`pilot/handoffs/` did not exist**; there was no earlier file to copy the
   shape from. This note follows the shape of the Part B section of
   `pilot/HANDOFF.md`, and the folder is new.
4. The work is one commit, and the map is current at it.

## Open

- Nothing for Jason. `firm` still waits on a terminal's stdin if someone types
  the old pipe's left-hand side (R7); stopping spec-reading commands from
  reading a terminal is a possible follow-up with its own SPEC (R8).
- The office's bench session and the Mac check prompts now carry the new
  command; neither has been run again. P285's merge touches the same files and
  should be clean if it keeps off the review-codes section.

## Review 1

Verdict: nothing blocking; one SHOULD and four NITs. This rebuild fixed
findings 1 to 4:

1. The stderr count now survives a reply without a `files` list: the bench reads
   the reply's counts inside the same step that adds the count to a failure
   sentence. A test covers it (firm exits 0, no `files`, one line on stderr).
2. The Mac prompt now asks for a record when a "reader bench:" sentence appears
   "instead of the counts or after them".
3. The count reads "1 line" or "N lines" everywhere it is spelled (the bench,
   the SPEC's R6 and this note).
4. This note's test count and commit paragraph are corrected.

Finding 5 (the commit trailer names Claude Fable 5.1) is left as it is: the
trailer states the model of the session that made the commit, and the session
sets it, not the project rule on which model builds. Jason is told in the
hand-back.
