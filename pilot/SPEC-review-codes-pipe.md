# Pilot 0.4 - review-codes asks the firm summary itself (P286) - SPEC

Status: **written before the build** (2026-10-11), branch
`claude/suspicious-mendel-ebfdb8` from `main` at `62512fd`. Decision
**P286** ([`DECISIONS.md`](DECISIONS.md)). The reader bench's `review-codes`
(P283, [`SPEC-ocr-scans.md`](SPEC-ocr-scans.md) section 2) counts Needs Review
by code from the `firm` command's reply, and every document tells a person to
feed it that reply through a pipe. The OCR Mac check
([`mactest/PROMPT-OCR-SCANS.md`](mactest/PROMPT-OCR-SCANS.md), step 4) saw the
pipe fail both ways it can: "the reply is not JSON", and a hang that ended at
once when interrupted. Both were reproduced on copies of made-up pilot data.
The office's bench session (`PROMPT-reader-bench.md`, steps 2a and 5) runs the
same pipe, so it has to be right before that run.

Nothing here reads a document, touches routing or changes what the app shows,
so the backtest baseline cannot move. The decision number appears only as
`P286`, so one search-and-replace renumbers it.

## 1. The problem as observed

The documented command is `python -m tracker.api firm | python
tools/reader_bench.py review-codes [--out <file>]` (`docs/tools.md` line 163,
the bench's docstring line 93, `PROMPT-reader-bench.md` lines 71 and 128,
`mactest/PROMPT-OCR-SCANS.md` line 127, `SPEC-ocr-scans.md` lines 876 and 992).
It fails at both ends of the pipe. `firm` itself works as designed.

**(1) "reader bench: the reply is not JSON".** P222 (`DECISIONS.md` line 217)
has `firm` print count lines on stdout before its reply when it reads
households afresh, `{"progress": {"v": 1, "event": "households", "done": n,
"total": t}}`, once at 0 and once per batch of 25 (`tracker/api.py`
`_say_count`, line 6255, called at 6315 and 6325; the format is
`tracker/progress.py` `count_line`, `PROGRESS_KEY` line 53, `COUNT_EVENT` line
62). The contract in `progress.py`'s docstring (lines 9-10), which
`app/main.js` follows: a stdout line under `progress` is a progress line, and
the reply is the only stdout line without that key, always last. The first
`firm` after a pass reads households afresh, because a pass changes household
fingerprints and the cache head carries the program; the next is answered
from the cache and prints the reply alone. `_cmd_review_codes`
(`tools/reader_bench.py` line 530) parses the whole of stdin as one JSON
value, so it fails on the first run and works on the second. Reproduced: run
1 printed two count lines and the reply, and the bench said "not JSON"; run 2
printed the reply alone, and the bench printed the counts. Nothing was on
stderr, and the resident engine was not involved.

**(2) The hang.** `firm` takes an optional page spec on stdin (P278), read to
the end of input by `api._read_spec` (line 1186; the read is line 1200,
`stream.buffer.read()`), as all 25 spec-taking commands do. The app always
writes the payload and ends the input: the resident engine hands it a buffer,
and `main.js` ends a spawned child's stdin. In a pipe typed at a terminal, or
run from Claude Code's harness (whose stdin is a socket), nobody ends `firm`'s
stdin. So it waits in `read()` until interrupted. A process sample showed the
main thread in `_io_FileIO_readall` under `_read_spec`. `< /dev/null` makes it
answer at once.

## 2. Rulings

**R1. `review-codes` stops being a pipe target and runs `firm` itself:
`python tools/reader_bench.py review-codes [--out <file>]`.** This fixes both
ends in one place, and there is nothing for a person or a prompt to remember.
*Rejected:* keeping the pipe and having the bench skip count lines. That fixes
(1) only. The hang is on `firm`'s end, and its fix would be a `< /dev/null`
that every person and every prompt must remember, the shape decision 209 rules
out. *Rejected:* a `firm` mode without count lines. P222's lines are a
contract the app reads, and a second output shape is a second thing to drift.

**R2. How `firm` is started (`_run_firm()`, the one seam).**
`subprocess.run([sys.executable, "-m", "tracker.api", runner.FIRM_COMMAND],
stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
cwd=ROOT, timeout=runner.FILL_TIME_LIMIT_SECONDS,
creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))`, with no `env`
argument: `tracker/runner.py`'s `fill_firm_cache` (lines 641-679) starts the
same command this way, but sends stdout and stderr nowhere and copies the
environment to add the product name. `_run_firm()` returns the
`CompletedProcess` or raises `BacktestError` for a timeout or an `OSError`
(R6), so the review-codes command catches nothing of `subprocess`.
- **Input closed.** `_read_spec` reads empty input as `{}` (line 1201), so no
  page is asked for and the reply is the whole one, byte for byte (P278). That
  reply's `files` list is what `review_codes` counts.
- **The current environment, unchanged** (no `env`, not a copy), so
  `TRACKER_SETTINGS_DIR`, `TRACKER_DATA_HOME` and `TRACKER_PRODUCT_NAME` reach
  the child exactly as the person set them.
- **The repository as its folder:** `ROOT`, the bench's own constant (line
  112, `Path(__file__).resolve().parent.parent`), which is what runner's fill
  uses. It holds `tracker/`, so `-m tracker.api` imports from this checkout.
- **Never frozen:** `tools/` ships in no build, so the bench always runs from a checkout.
- **`runner.FIRM_COMMAND`, not a literal "firm".** `tests/test_runner.py`
  already holds it to `api.COMMANDS`, so a rename cannot leave the bench
  asking for a command that is gone.

**R3. `firm`'s stderr is captured, counted and never shown.** `firm` says
everything as JSON on stdout and keeps tracebacks in its error log, so its
stderr is empty by design. Anything there escaped that design, for example an
interpreter traceback before the error log is open, or a library's warning.
Nobody has vetted its words, and the bench runs inside a Claude Code session
at the office, whose transcript client data must never enter. So the bench
says only how many lines there were (R6). *Rejected:* letting stderr through
to the terminal, for that reason.
*Rejected:* discarding stderr as runner's fill does. A non-empty stderr is
itself a finding, and it would go unseen.

**R4. Time limit: `runner.FILL_TIME_LIMIT_SECONDS` (300 s), imported.** It is
the same command doing the same work. The fill's limit is already set at over
four times the 65 s cold fill measured at 750 returns on the office PC
(SPEC-firm-cache-fill R5). When it runs out, `subprocess.run` stops the child
and the bench says so (R6). *Rejected:* no limit, because a silent wait is the
failure being fixed. *Rejected:* a number of its own, because two copies
would drift apart.

**R5. The reply is picked by the progress contract, in a pure helper:
`firm_reply_of(stdout: bytes, returncode: int) -> dict`.** The bench splits
stdout into lines and drops blank ones (a Windows `\r\n` is stripped). A line
that decodes as UTF-8 to a JSON object with `progress.PROGRESS_KEY` is a count
line and is ignored, however many there are: none on a warm cache, two or more
on a cold one. The reply is the last remaining line. If no line remains, or
that line is not a JSON object, the bench raises `BacktestError` (R6). If the
reply carries `failure` or `error`, or `returncode` is not 0, that is a
refusal (R6). Otherwise the reply goes to `review_codes`, whose counting does
not change. Only its one sentence (lines 468-469) loses "pipe the output of":
it becomes *the firm command's reply holds no list of files*. *Rejected:*
"the last line, whatever it is": the same answer under the contract, but
`main.js` reads the rule as `progress.py` states it, and so does this.

**R6. A failure is said by kind, never by its words.** In every case
`review-codes` exits 2 through `main`'s existing `BacktestError` handler, with
`reader bench: ` and one of these sentences, which are module constants in the
review-codes section:

| Case | Sentence |
|---|---|
| `firm` could not start (`OSError`) | `the firm command could not start ({kind}); nothing was counted` - `errors.error_class(exc)` |
| ran past the limit | `the firm command gave no reply within {minutes} minutes and was stopped; nothing was counted` |
| no line besides count lines | `the firm command printed no reply (exit {code}); nothing was counted` |
| last line not a JSON object | `the firm command's reply is not a JSON object (exit {code}); nothing was counted` |
| `failure`/`error`, or exit not 0 | `the tracker refused the firm summary ({kind}, exit {code}); the app's Overview says why, and an unexpected failure is in the tracker's error log` |

The `{kind}` of a refusal is `reply["failure"]["kind"]` when it is one of
`progress.FAILURE_KINDS` (stale, locked, refused, failed; decision 193's
envelope), and `unknown` otherwise. Each failure sentence ends with *(it also
wrote {lines} on stderr, not shown)* (`{lines}` reads "1 line" or "N lines") when stderr was not empty. On success
with a non-empty stderr, the counts print as usual, one line `reader bench:
the firm command also wrote {lines} on stderr, not shown` goes to the
bench's stderr, and the exit is 0. **The rule:** the bench never quotes a line
of `firm`'s output or the reply's `error` sentence. Those sentences name
folders (a clients root that cannot be walked, a held return's lock), so
quoting one could put a client's name on screen. That is the docstring's
"Nothing identifying leaves this tool" (lines 82-86), now stated for the reply
too. *Rejected:* quoting `error` for a clearer message, for that reason.

**R7. The piped mode is gone, and the bench never reads its own stdin.**
There is one way to run it. *Rejected:* detecting a pipe and refusing it.
Stdin may be a terminal, a pipe or a harness socket, and a pipe cannot be told
apart from a harness reliably. Anyone who types the old pipe anyway gets
counts from the bench's own `firm`, while the left-hand `firm` still waits on
the terminal as before (Ctrl-C ends it). That is why every document and prompt
that names the pipe changes in the same commit (section 4).

**R8. `tracker/api.py`, `tracker/resident.py` and `tracker/progress.py` are
not changed.** P222's count lines and P278's spec on stdin stand, and every
reader of `firm`'s stdout follows the one contract in `progress.py`.
Whether `firm`, or any spec-taking command, should stop reading stdin when it
is a terminal is out of scope. It is a possible follow-up only, with its own
SPEC, since it touches all 25 callers of `_read_spec`.

**R9. The edit stays inside the review-codes section, so it merges cleanly
with P285.** Another lane, P285 (branch `claude/ocr-prepare`, the reader's
preparation steps), is editing `tools/reader_bench.py` too. This change
touches only:
- the docstring's usage line (93) and the rule's sentence (85-86);
- the review-codes section (from line 457): the new constants, `_run_firm`,
  `firm_reply_of`, and `review_codes`'s one sentence;
- `_cmd_review_codes` (530-540);
- the review-codes parser help (565), which becomes *count Needs Review by
  code; runs the firm command itself*.

`subprocess`, `tracker.progress` and `tracker.runner` are imported at call
time, inside the two helpers, so the module's import block (96-132) stays
untouched. Precedent: `tools/backtest.py`'s `_harness`. `main`, including its
Ctrl-C sentence, is not touched. Ctrl-C during `review-codes` still exits 130
with the variants' sentence, which is harmless here; any rewording waits until
P285 has landed.

## 3. The exact behaviour

`python tools/reader_bench.py review-codes [--out <file>]`, from any folder
and with any stdin: refuse an `--out` inside the repository before `firm`
starts, as `run` does before anything is read (line 520), since a refusal
after a 300-second wait would waste it; start `firm` (R2; a timeout or
`OSError` exits 2, R6); `firm_reply_of(stdout, returncode)` (R5, R6);
`review_codes(reply)`; print and write the counts as today (`json.dumps(...,
indent=1, sort_keys=True)`, `write_json`); exit 0. The first run after a
pass and every later one answer alike, in the firm summary's own time.

## 4. Files touched

| File | What changes |
|---|---|
| `tools/reader_bench.py` | Only what R9 lists. |
| `tests/test_reader_bench.py` | The two review-codes tests (429-461) feed `_run_firm` instead of `sys.stdin`, plus the new tests in section 5. |
| `docs/tools.md` | Line 163 becomes `python tools/reader_bench.py review-codes [--out <file>]   # Needs Review, counted by code`. Lines 166-167: *`review-codes` runs the `firm` command itself, with nothing on its input, skips the count lines it prints first, and prints the count of each code over the rows waiting for a person, and nothing else. A refusal is said by its kind, never by its sentence.* |
| `pilot/PROMPT-reader-bench.md` | Lines 71 and 128: `.venv\Scripts\python tools\reader_bench.py review-codes --out <outside>\review-before.json` (and `review-after.json`). |
| `pilot/mactest/PROMPT-OCR-SCANS.md` | Line 127: `TRACKER_SETTINGS_DIR=... TRACKER_DATA_HOME=... .venv/bin/python tools/reader_bench.py review-codes --out ~/PilotTest/results/ocr-review-codes.json` (the variables go in front of the bench). Lines 134-136 are rewritten: *review-codes runs the firm command itself and answers in seconds, the first time and every time. It needs no retry. If it prints a "reader bench:" sentence instead of the counts or after them, or runs for more than a minute, record that word for word with the time: it is a finding.* |
| `pilot/SPEC-ocr-scans.md` | History stays as written. One italic line goes under the code block that ends at 877, and one under the bullet at 992-993, in the house's annotation form (as `SPEC-firm-cache-fill.md` line 75): *Changed by P286 (`SPEC-review-codes-pipe.md`): `review-codes` runs the firm command itself; the pipe is gone.* |
| `pilot/DECISIONS.md` | One row, P286 (section 7). |
| `docs/repo-map.curated.json` | `tools/reader_bench.py` notes: the last sentence gains *review-codes starts `python -m tracker.api firm` itself (stdin closed, the current environment, the repository as its folder, runner's fill limit), takes the reply as the last stdout line without the progress key, says a refusal by kind and exit code only, and counts firm's stderr without showing it (P286); its child writes the firm cache, as the pipe's firm did.* `tests/test_reader_bench.py` role: "review-codes printing code counts alone" becomes *review-codes running firm itself, skipping count lines, saying a refusal by kind alone, and printing code counts alone*. Then `python tools/repo_map.py update`. No new artifact edge: the bench writes nothing new itself. |

`pilot/HANDOFF.md` line 160 needs no change. It says `review-codes` counts
Needs Review by code from the `firm` command's reply, which stays true, and it
names no pipe.

There is no vocabulary note. No catalog keyword, case or matcher changes, so
`tools/vocab_report.py` has nothing to rebuild (`docs/tools.md` lines 21-24).
Its `check` runs in the gate to confirm that.

## 5. Tests (`tests/test_reader_bench.py`)

No test starts a real `firm`. A child that inherits the suite's environment
without `child_env()` is an unarmed child to the tripwire (decision 185), and
R5's helper is fed the bytes `progress.count_line` makes, the format's only
encoder, so the shape under test is the real one. The tests monkeypatch
`reader_bench._run_firm`, or `subprocess.run` for the launch test, returning
`subprocess.CompletedProcess`. Every reply is made up.

- `test_review_codes_counts_codes_and_prints_nothing_else` (rewritten): the
  same made-up reply, behind two count lines, through `_run_firm`.
- `test_review_codes_names_what_is_wrong_with_a_reply_and_exits_2`
  (rewritten): not JSON, no `files`, a list. Each exits 2 with `reader bench: `.
- `test_the_reply_is_the_last_stdout_line_without_the_progress_key`
- `test_count_lines_before_the_reply_are_ignored_however_many` (0, 2 and 5
  lines from `progress.count_line`, with `\n` and `\r\n` endings)
- `test_no_reply_or_a_reply_that_is_not_json_is_named_without_echoing_the_line`
  (the line carries a made-up name. It is in neither stdout nor stderr.)
- `test_a_refused_reply_is_said_by_its_kind_and_never_by_its_sentence` (each of
  `FAILURE_KINDS`, an unknown kind, and exit 1 with no `failure`. The made-up
  sentence's name and path are never printed.)
- `test_firm_is_started_with_stdin_closed_and_the_current_environment`
  (recorded `subprocess.run` call: the command with `runner.FIRM_COMMAND`,
  `stdin=DEVNULL`, `stdout` and `stderr` `PIPE`, no `env`, `cwd == ROOT`,
  `timeout == runner.FILL_TIME_LIMIT_SECONDS`, the creation flags)
- `test_a_firm_that_runs_too_long_or_cannot_start_is_said_by_kind`
  (`TimeoutExpired` and `PermissionError` from the recorded `subprocess.run`)
- `test_what_firm_wrote_on_stderr_is_counted_and_never_shown` (a failure and
  a success, each with a made-up name on stderr)
- `test_review_codes_never_reads_its_own_stdin` (`sys.stdin` whose `read`
  raises. The counts still print.)
- `test_the_usage_names_no_pipe` (no line naming `review-codes` in the
  docstring, `docs/tools.md`, `PROMPT-reader-bench.md` or
  `mactest/PROMPT-OCR-SCANS.md` holds `|`, and the parser help does not say
  stdin)

## 6. The gate

Before any push (there is no push from this lane; another session coordinates
the landing):
1. Delete dead code in the changed files: unused imports and locals,
   commented-out code, module-level names nothing uses. After the rewrite,
   check that `io`, `json` and `sys` are still used in the test file.
2. Run each file as its own process, under `../../../.venv/bin/python` (3.14)
   and `../../../.venv311/bin/python` (3.11), with `-m pytest -q` and never
   `-m "not corpus"`: `tests/test_reader_bench.py`, `tests/test_layers.py`,
   `tests/test_single_source.py`, `tests/test_repo_map.py`,
   `tests/test_tripwire.py` and `tests/test_errors.py`. The last two run
   because tests change (the house rule). No module imports the bench, so
   there are no importers' tests.
3. `python -m ruff check .`
4. `python tools/repo_map.py update`, then `python tools/repo_map.py check`.
5. `python tools/vocab_report.py check`. Only if it says stale: `build`, then
   `tests/test_vocab_report.py` under both interpreters.
6. Hand check, on made-up data only. Use throwaway `TRACKER_SETTINGS_DIR` and
   `TRACKER_DATA_HOME` with a made-up clients root, as in
   `mactest/PROMPT-OCR-SCANS.md` step 4, and a sorting pass. Then run
   `review-codes` twice from Claude Code's harness, with no `< /dev/null`.
   Both runs print the counts, and the first answers in seconds. Record both
   times in the hand-back.

## 7. The decision row (`pilot/DECISIONS.md`)

| P286 | 2026-10-11 | **`review-codes` asks the firm summary itself: `python tools/reader_bench.py review-codes [--out <file>]`, no pipe (SPEC-review-codes-pipe).** The bench starts `python -m tracker.api firm` with its input closed, the current environment and the repository as its folder, under the cache fill's 300-second limit. The reply is the last stdout line without the `progress` key, so P222's count lines are skipped. A refusal is said by its kind and exit code, never by its sentence. `firm`'s stderr is counted, never shown. The old pipe is gone, and the bench never reads its own input. `tracker/api.py`, `tracker/resident.py` and `tracker/progress.py` are unchanged: P222's count lines and P278's spec on stdin stand. | The OCR Mac check (mactest/PROMPT-OCR-SCANS.md, step 4) saw the documented pipe fail both ways. It said "the reply is not JSON" on the first `firm` after a pass, which prints P222's count lines before its reply. It hung because `firm` reads its page spec from stdin to the end, and nobody ended a terminal's. Both were reproduced on copies of made-up pilot data. |

If Jason approves it in words, his words go first in the Why, as in rows
P280-P283.

Nothing is open for Jason here: no money, client wording, client data or
season question. Nothing a person at the firm sees changes.
