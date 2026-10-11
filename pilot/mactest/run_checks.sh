#!/bin/bash
# ── The Mac check - the automated part (SPEC-mac R33, pilot decision P254) ──
# Run it in Terminal on an Apple silicon Mac, from a git clone or from GitHub's
# "Download ZIP":
#
#   bash pilot/mactest/run_checks.sh
#   bash pilot/mactest/run_checks.sh --tests test_pilot,test_after_install
#
# This is pilot/wintest/run_checks.ps1 for a Mac. Every step writes PASS / FAIL
# / NOT VERIFIED / INFO with its evidence to ~/PilotTest/results/checks.json,
# and a full log beside it. It installs no tool on its own: a missing one is
# reported with where to get it, and the script stops.
#
# --tests runs only the named test files (the components a change touched),
# each in its own process, side by side - the sorting engine's own tests are
# not rerun (Jason, 2026-09-29). The disk image is built once every one of
# them has ended: the build writes build-portable/ into the checkout, and the
# suite's end-of-run guard (decision 185) fails any file still running when a
# new folder appears there (P200, A1). Without --tests the whole suite runs. A
# file may be named bare, with .py, or as a path: test_pilot, test_pilot.py and
# tests/test_pilot.py are the same file (P200, N8).
#
# The checks that need a person at the Mac - the buyer's walk (SPEC-mac
# section 3) and the steps H2 to H14 - are the hands-on part, in PROMPT.md.
# This script never starts the app: its first start is the walk's, watched as
# it sets the schedule up. It reads no folder but this checkout and
# ~/PilotTest, and prints and stores no client's name: the only documents it
# touches are the made-up ones tests/samples.py builds.
#
# It runs under the /bin/bash 3.2 macOS ships (no mapfile, no ${x,,}, no
# associative array), as the three scripts of SPEC-mac R16 do.

cd "$(dirname "$0")/../.." || exit 1

# Before any other command: bash would otherwise look for python3, node, npm
# and git in this folder, or in a relative folder PATH names, before the
# folders that hold the real ones, so a file dropped here named like one of
# them would run instead (E-10). Only absolute folders are kept.
clean_path=""
old_ifs=$IFS
IFS=:
for dir in $PATH; do
  case "$dir" in
    /*) clean_path="${clean_path:+$clean_path:}$dir" ;;
  esac
done
IFS=$old_ifs
PATH=$clean_path

REPO=$PWD
TEST="$HOME/PilotTest"
RESULTS="$TEST/results"
LOG="$RESULTS/run_checks.log"
JSON="$RESULTS/checks.json"
mkdir -p "$RESULTS" || { echo "Could not make $RESULTS"; exit 1; }
: > "$LOG"

TESTS_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tests)
      [ $# -ge 2 ] || { echo "--tests needs a list of test files, e.g. --tests test_pilot,test_after_install"; exit 2; }
      TESTS_ARG="${TESTS_ARG:+$TESTS_ARG,}$2"
      shift 2
      ;;
    --tests=*)
      TESTS_ARG="${TESTS_ARG:+$TESTS_ARG,}${1#--tests=}"
      shift
      ;;
    *)
      echo "Usage: bash pilot/mactest/run_checks.sh [--tests test_a,test_b]"
      exit 2
      ;;
  esac
done

# ── Recording ──────────────────────────────────────────────────────────
# ── BEGIN recording helpers ──
# checks.json is written in pure bash, so a missing Python can still be
# recorded as the reason the check stopped. Every record rewrites the whole
# file, atomically, in the order the checks ran.
CHECK_NAMES=()
CHECK_ENTRIES=()

say() {
  local line
  line="[$(date +%H:%M:%S)] $1"
  echo "$line"
  echo "$line" >> "$LOG"
}

json_text() {
  # A JSON string's body: backslash and quote escaped, control characters out.
  printf '%s' "$1" | tr '\n\r\t' '   ' | tr -d '\000-\010\013\014\016-\037' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

write_json() {
  local count=${#CHECK_NAMES[@]} i=0 body=""
  while [ "$i" -lt "$count" ]; do
    body="$body${body:+,
}  \"$(json_text "${CHECK_NAMES[$i]}")\": ${CHECK_ENTRIES[$i]}"
    i=$((i + 1))
  done
  printf '{\n%s\n}\n' "$body" > "$JSON.tmp" && mv "$JSON.tmp" "$JSON"
}

record() {
  # record NAME RESULT EVIDENCE
  local n=${#CHECK_NAMES[@]}
  CHECK_NAMES[$n]="$1"
  CHECK_ENTRIES[$n]="{ \"result\": \"$(json_text "$2")\", \"evidence\": \"$(json_text "$3")\" }"
  write_json
  say "$1: $2 - $3"
}

# ── END recording helpers ──
verdict() { if [ "$1" = "0" ]; then echo PASS; else echo FAIL; fi; }
stop_here() { say "STOPPED: $1"; exit 1; }
# Runs a tool, copies everything it prints into the log, returns its exit code.
run() {
  "$@" >> "$LOG" 2>&1
}

# ── The named test files ───────────────────────────────────────────────
# Every name is found before anything else runs, so a typo stops the run at
# once and not after the environment has been installed.
# ── BEGIN test-file helpers ──
# The places a --tests value is looked for: the name with .py added when it
# has none, as typed and under tests/. Only a .py file is a test file, so
# "README.md" is looked for as README.md.py and found nowhere; the stop
# message names these same places, so it never says "test_x.py.py".
test_file_candidates() {
  case "$1" in
    *.py) echo "$1"; echo "tests/$1" ;;
    *) echo "$1.py"; echo "tests/$1.py" ;;
  esac
}
# The file a --tests value names, as a path from the repository; nothing found
# prints nothing and returns 1.
resolve_test_file() {
  local candidate
  for candidate in $(test_file_candidates "$1"); do
    if [ -f "$candidate" ]; then echo "$candidate"; return 0; fi
  done
  return 1
}
# The names in a comma-joined list, one per line, trimmed.
split_test_list() {
  printf '%s\n' "$1" | tr ',' '\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep -v '^$'
}
# ── END test-file helpers ──

FILES=()
if [ -n "$TESTS_ARG" ]; then
  SEEN=""
  NL="
"
  names=$(split_test_list "$TESTS_ARG")
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    case "$name" in
      *[!A-Za-z0-9_./-]*)
        record "tests" FAIL "not a test file name: $name"
        stop_here "check the --tests list"
        ;;
    esac
    if ! file=$(resolve_test_file "$name"); then
      looked=$(test_file_candidates "$name" | tr '\n' ' ' | sed 's/ $//; s/ / and /')
      record "tests" FAIL "no such test file: $name (looked for $looked; only .py files are test files)"
      stop_here "check the --tests list"
    fi
    # A file named twice runs once: "test_api" and "tests/test_api.py" are one
    # file, and two runs would write one output file. Compared by full path.
    full="$(cd "$(dirname "$file")" && pwd -P)/$(basename "$file")"
    case "$NL$SEEN$NL" in
      *"$NL$full$NL"*) continue ;;
    esac
    SEEN="$SEEN$NL$full"
    FILES[${#FILES[@]}]=$file
  done <<LIST
$names
LIST
  say "Test files to run: ${FILES[*]}"
fi

# ── 1. Tools ───────────────────────────────────────────────────────────
# The version the office runs, written once in pyproject.toml ([tool.office]);
# the floor is requires-python.
OFFICE_PYTHON=$(sed -n '/^\[tool.office\]/,/^\[/{s/^python-version *= *"\(.*\)"/\1/p;}' pyproject.toml)
FLOOR_MINOR=11
OFFICE_PYTHON=${OFFICE_PYTHON:-3.14}

missing=""
add_missing() { missing="${missing:+$missing | }$1"; }

# The bare Mac's /usr/bin/python3 and /usr/bin/git are stubs that open a
# dialog offering the Command Line Tools when they are run without them, so
# neither is run until the tools are there.
have_clt=0
xcode-select -p >/dev/null 2>&1 && have_clt=1

python_floor_ok() {
  "$1" -c "import sys; sys.exit(sys.version_info < (3, $FLOOR_MINOR))" >/dev/null 2>&1
}

PYTHON=""
for candidate in "python$OFFICE_PYTHON" python3; do
  found=$(command -v "$candidate" 2>/dev/null) || continue
  if [ "$found" = "/usr/bin/python3" ] && [ "$have_clt" = 0 ]; then continue; fi
  if python_floor_ok "$found"; then PYTHON=$found; break; fi
done

if [ "$(uname -s)" != "Darwin" ]; then
  record "tools" FAIL "this is $(uname -s), not a Mac; the Windows check is pilot/wintest/run_checks.ps1"
  stop_here "run this on an Apple silicon Mac"
fi
MAC_VERSION=$(sw_vers -productVersion 2>/dev/null)
MAC_MAJOR=${MAC_VERSION%%.*}
CHIP=$(uname -m)
TRANSLATED=$(sysctl -n sysctl.proc_translated 2>/dev/null)
if [ "$CHIP" != "arm64" ] || [ "$TRANSLATED" = "1" ]; then
  record "tools" FAIL "this Terminal reports $CHIP${TRANSLATED:+ (running under Rosetta)}; the app is built on Apple silicon, in a Terminal that is not under Rosetta"
  stop_here "open a Terminal on an Apple silicon Mac (Terminal's Get Info must not say Open using Rosetta)"
fi
if [ -z "$MAC_MAJOR" ] || [ "$MAC_MAJOR" -lt 14 ] 2>/dev/null; then
  record "tools" FAIL "macOS ${MAC_VERSION:-unreadable}; the app needs macOS 14 or later (SPEC-mac P243), so this Mac can only show the app's refusal (walk step 4)"
  stop_here "run the check on macOS 14 or later"
fi

[ "$have_clt" = 1 ] || add_missing "Command Line Tools (git, codesign) :  xcode-select --install"
[ -n "$PYTHON" ] || add_missing "Python $OFFICE_PYTHON :  the macOS installer from https://www.python.org/downloads/macos/"
command -v node >/dev/null 2>&1 || add_missing "Node.js (with npm) :  the LTS installer from https://nodejs.org/"
command -v npm >/dev/null 2>&1 || add_missing "npm :  it comes with the Node.js LTS installer from https://nodejs.org/"
for tool in codesign ditto hdiutil shasum file lipo; do
  command -v "$tool" >/dev/null 2>&1 || add_missing "$tool :  part of macOS; this Mac's system folders look damaged"
done
if [ "$have_clt" = 1 ]; then
  command -v git >/dev/null 2>&1 || add_missing "git :  xcode-select --install"
fi
if [ -n "$missing" ]; then
  record "tools" FAIL "missing: $missing"
  stop_here "install the missing tools (above), open a new Terminal window, run again"
fi
PYV=$("$PYTHON" -c "import sys; print('%d.%d.%d' % sys.version_info[:3])")
NODEV=$(node --version)
tools_result=PASS
tools_text="Python $PYV, Node $NODEV, git, macOS $MAC_VERSION on $CHIP"
case "$PYV" in
  "$OFFICE_PYTHON".*) ;;
  *)
    tools_result="NOT VERIFIED"
    tools_text="$tools_text; the office's Python is $OFFICE_PYTHON, so this run proves the floor ($PYV), not the office's interpreter"
    ;;
esac
record "tools" "$tools_result" "$tools_text"

# ── 2. Where the code came from: a clone, or GitHub's "Download ZIP" ───
if [ ! -e "$REPO/.git" ]; then
  # A ZIP has no history. The disk image build insists on a committed tree
  # (P13), so the check makes one local snapshot commit and says so.
  run git init -q
  run git add -A
  if ! run git -c user.name="Pilot Mac check" -c user.email="pilot-check@localhost" commit -q -m "Snapshot of the downloaded ZIP for the pilot Mac check"; then
    record "tree" FAIL "could not make the local snapshot commit"
    stop_here "see $LOG"
  fi
  head_sha=$(git rev-parse --short HEAD 2>/dev/null)
  record "tree" "NOT VERIFIED" "ZIP download committed as local snapshot $head_sha; cannot be compared with GitHub"
else
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  head_sha=$(git rev-parse --short HEAD 2>/dev/null)
  dirty=$(git status --porcelain 2>/dev/null)
  if [ -n "$dirty" ]; then
    record "tree" FAIL "uncommitted changes in the checkout"
    stop_here "commit or discard them first"
  fi
  if ! run env GIT_TERMINAL_PROMPT=0 git fetch origin; then
    record "tree" "NOT VERIFIED" "branch $branch at $head_sha, clean; GitHub could not be reached to compare"
  else
    # The port is checked on its own branch before it reaches main, so the
    # branch is compared with its own upstream; on main, or with none set,
    # with origin/main (the Windows check insists on main).
    against=$(git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>/dev/null)
    against=${against:-origin/main}
    behind=$(git rev-list --count "HEAD..$against" 2>/dev/null)
    behind=${behind:-unknown}
    where="branch $branch at $head_sha, behind $against by $behind"
    [ "$branch" = "main" ] || where="$where (not main: the commit under test is $head_sha)"
    if [ "$behind" = "0" ]; then
      record "tree" PASS "$where"
    else
      record "tree" FAIL "$where"
      stop_here "bring the checkout up to date (git pull)"
    fi
  fi
fi

# ── 3. Environment (hash-checked, as setup.command does) ───────────────
[ -d .venv ] || run "$PYTHON" -m venv .venv
VPY="$REPO/.venv/bin/python"
run "$VPY" -m pip install --disable-pip-version-check --require-hashes -r requirements.lock
e1=$?
run "$VPY" -m pip install --disable-pip-version-check --require-hashes --no-deps -r requirements-nodeps.lock
e2=$?
(cd app && run npm ci --no-audit --no-fund)
e3=$?
record "environment" "$([ "$e1$e2$e3" = "000" ] && echo PASS || echo FAIL)" "pip=$e1 pip-nodeps=$e2 npm-ci=$e3"
if [ "$e1$e2$e3" != "000" ]; then stop_here "the environment did not install; see $LOG"; fi

# The room the app measures on a Mac (P241, P244): as if the folder sat under
# a Windows root, so the limit is the default Windows's 259 and the root
# counts 48 characters.
ROOM=$("$VPY" -c "from tracker import layout; print(layout.short_paths(), layout.path_limit(), layout.WINDOWS_ROOT_LENGTH)" 2>>"$LOG")
if [ "$ROOM" = "True 259 48" ]; then
  record "room_as_windows" PASS "short_paths, path limit, Windows root length: $ROOM"
else
  record "room_as_windows" FAIL "short_paths, path limit, Windows root length: ${ROOM:-unreadable}; a Mac measures as the default Windows (True 259 48)"
fi

# ── 4. Checks: ruff, the map, and the tests ────────────────────────────
run "$VPY" -m ruff check .
ruff=$?
run "$VPY" tools/repo_map.py check
map=$?
record "ruff_and_map" "$(verdict "$((ruff + map))")" "ruff=$ruff map=$map"

export PYTHONIOENCODING=utf-8
if [ -n "$TESTS_ARG" ]; then
  OUTS=()
  PIDS=()
  i=0
  for file in "${FILES[@]}"; do
    out="$RESULTS/pytest-$(basename "$file" .py).txt"
    OUTS[$i]=$out
    "$VPY" -m pytest -q -p no:cacheprovider "$file" > "$out" 2>&1 &
    PIDS[$i]=$!
    i=$((i + 1))
  done
  say "Started ${#FILES[@]} test file(s) in parallel; the build starts when all have ended"
  i=0
  for file in "${FILES[@]}"; do
    wait "${PIDS[$i]}"
    code=$?
    summary=$(grep -E "passed|failed|error" "${OUTS[$i]}" 2>/dev/null | tail -1)
    record "tests $file" "$(verdict "$code")" "$summary (output: ${OUTS[$i]})"
    i=$((i + 1))
  done
else
  suite="$RESULTS/pytest.txt"
  "$VPY" -m pytest -q -n auto -p no:cacheprovider > "$suite" 2>&1
  code=$?
  summary=$(grep -E "passed|failed" "$suite" | tail -1)
  record "test_suite" "$(verdict "$code")" "$summary (full output: $suite)"
fi
unset PYTHONIOENCODING

# ── 5. Build the disk image (SPEC-mac R17) ─────────────────────────────
run /bin/bash "$REPO/build-mac.sh"
built=$?
DMG=$(ls -t build-portable/installer/*-mac-arm64.dmg 2>/dev/null | head -1)
if [ "$built" != "0" ] || [ -z "$DMG" ]; then
  record "build" FAIL "build-mac.sh exit $built; disk image found: $([ -n "$DMG" ] && echo yes || echo no) (log: $LOG)"
  stop_here "the disk image did not build"
fi
DMG_DIR=$(dirname "$DMG")
DMG_FILE=$(basename "$DMG")
if (cd "$DMG_DIR" && run shasum -a 256 -c "$DMG_FILE.sha256"); then
  record "build" PASS "$REPO/$DMG SHA-256 $(cut -d' ' -f1 "$DMG_DIR/$DMG_FILE.sha256")"
else
  record "build" FAIL "$DMG_FILE does not match its .sha256 file"
  stop_here "the disk image and its hash disagree"
fi

# ── 6. What the bundle holds (R13, R16, R17) ───────────────────────────
NAME=$(node -p "require('./app/package.json').productName")
API=$(node -p "require('./app/package.json').config.apiName")
APP="$REPO/build-portable/dist/$NAME-darwin-arm64/$NAME.app"
PLISTB=/usr/libexec/PlistBuddy
bundle_problems=""
note_problem() { bundle_problems="${bundle_problems:+$bundle_problems; }$1"; }
[ -d "$APP/Contents/Resources" ] || note_problem "no $NAME.app in the package"
if run codesign --verify --deep --strict "$APP"; then :; else note_problem "the seal does not verify"; fi
codesign -dv "$APP" 2>&1 | grep -q "Signature=adhoc" || note_problem "the signature is not ad hoc"
archs=$(lipo -archs "$APP/Contents/Resources/$API/$API" 2>/dev/null)
[ "$archs" = "arm64" ] || note_problem "the frozen API is ${archs:-unreadable}, not arm64 alone"
grep -q "^Commit:   $(git rev-parse HEAD)$" "$APP/Contents/Resources/BUILD-INFO.txt" 2>/dev/null || note_problem "BUILD-INFO.txt is not in Contents/Resources or names another commit"
wanted=$("$PLISTB" -c "Print :LSMinimumSystemVersion" "$REPO/app/assets/Info-mac.plist" 2>/dev/null)
found=$("$PLISTB" -c "Print :LSMinimumSystemVersion" "$APP/Contents/Info.plist" 2>/dev/null)
[ -n "$wanted" ] && [ "$wanted" = "$found" ] || note_problem "LSMinimumSystemVersion is ${found:-missing}, the plist says ${wanted:-missing}"
for key in NSDesktopFolderUsageDescription NSDocumentsFolderUsageDescription NSDownloadsFolderUsageDescription; do
  "$PLISTB" -c "Print :$key" "$APP/Contents/Info.plist" >/dev/null 2>&1 || note_problem "$key is missing from the app's Info.plist"
done
icon=$("$PLISTB" -c "Print :CFBundleIconFile" "$APP/Contents/Info.plist" 2>/dev/null)
case "$icon" in *.icns) ;; *) icon="$icon.icns" ;; esac
[ -n "$icon" ] && [ -f "$APP/Contents/Resources/$icon" ] || note_problem "the app's icon file is missing"
if [ -z "$bundle_problems" ]; then
  record "bundle" PASS "ad-hoc seal verifies; frozen API arm64; BUILD-INFO.txt names this commit; LSMinimumSystemVersion $found; folder strings and icon present"
else
  record "bundle" FAIL "$bundle_problems"
fi

# ── 7. The frozen smoke (R13, R31): the package answers and reads ──────
# The frozen API runs the way the build workflow runs the Windows one: it
# answers `list` in JSON with no clients root set, then makes one dry pass
# over a scratch root and must read the pile as the source does - including
# the scan only the reader can file, which starts a reading child under
# "spawn". Its data and settings are throwaway folders of its own, so this
# never touches the app's real data folder, which the walk starts clean.
SMOKE="$TEST/smoke"
rm -rf "${SMOKE:?}"
mkdir -p "$SMOKE/data" "$SMOKE/settings" "$SMOKE/build-data" || stop_here "could not make $SMOKE"
API_EXE="$APP/Contents/Resources/$API/$API"
smoke_problems=""
note_smoke() { smoke_problems="${smoke_problems:+$smoke_problems; }$1"; }
smoke_env() {
  env "TRACKER_PRODUCT_NAME=$NAME" "TRACKER_DATA_HOME=$SMOKE/data" "TRACKER_SETTINGS_DIR=$SMOKE/settings" "$@"
}
listed=$(smoke_env "$API_EXE" list 2>>"$LOG")
if ! printf '%s' "$listed" | "$VPY" -c "import json, sys; sys.exit(0 if isinstance(json.load(sys.stdin), dict) else 1)" 2>>"$LOG"; then
  note_smoke "list did not answer one JSON object"
fi
# The scratch root is built with a throwaway data home, as make_samples.py does.
env "TRACKER_DATA_HOME=$SMOKE/build-data" "$VPY" -c "import sys; from tests.samples import build_scratch_root; build_scratch_root(sys.argv[1])" "$SMOKE/clients" >>"$LOG" 2>&1 \
  || note_smoke "the scratch root could not be built"
smoke_env "$VPY" -m tracker.settings "$SMOKE/clients" >>"$LOG" 2>&1 || note_smoke "the scratch root could not be set"
frozen=$(smoke_env "$API_EXE" --run --settings "$SMOKE/settings" --dry-run --reminders always --log "$SMOKE/runs.log" 2>&1)
frozen_code=$?
source_pass=$(smoke_env "$VPY" -m tracker.runner "$SMOKE/clients" --dry-run --reminders always 2>&1)
source_code=$?
printf '%s\n--- the source ---\n%s\n' "$frozen" "$source_pass" >> "$LOG"
[ "$frozen_code" = "0" ] || note_smoke "the frozen dry pass exited $frozen_code"
[ "$source_code" = "0" ] || note_smoke "the source's dry pass exited $source_code"
lines_of() { printf '%s\n' "$1" | grep -E '^[[:space:]]+(OK|ERROR|SKIP)[[:space:]]'; }
frozen_lines=$(lines_of "$frozen")
if [ -z "$frozen_lines" ]; then
  note_smoke "the package's dry pass printed no OK, ERROR or SKIP line to compare"
elif [ "$frozen_lines" != "$(lines_of "$source_pass")" ]; then
  note_smoke "the package read the pile differently from the source"
fi
# The pile holds a scan only the reader can file. A package or a source that
# cannot start the reader says so (content_check's warm-up) and parks the scan;
# both reading the pile alike would then prove nothing, so neither may say it.
if printf '%s\n%s\n' "$frozen" "$source_pass" | grep -q "The reader cannot run"; then
  note_smoke "the reader could not run (a reading child did not start under spawn, or a library is missing)"
fi
head -1 "$SMOKE/runs.log" 2>/dev/null | grep -q "reader=processor" || note_smoke "the run log's first line names no processor"
# R31: a footprint that cannot be read is no cap, and is said once on the
# error log. On a Mac that sentence must not be there.
unreadable=$("$VPY" -c "from tracker import ocr; print(ocr.MEMORY_UNREADABLE.split('(')[0].strip())" 2>>"$LOG")
if [ -n "$unreadable" ] && grep -qF "$unreadable" "$SMOKE/data/tracker-errors.log" 2>/dev/null; then
  note_smoke "the error log says the reading's memory could not be read (proc_pid_rusage failed)"
fi
cp "$SMOKE/runs.log" "$RESULTS/smoke-runs.log" 2>/dev/null
if [ -z "$smoke_problems" ]; then
  record "frozen_smoke" PASS "list answered JSON; one dry pass read the pile as the source does, the scan included; reader=processor; memory readable"
else
  record "frozen_smoke" FAIL "$smoke_problems (output in $LOG)"
fi

# ── 8. Sample clients folder (made-up documents only) ──────────────────
sample="$TEST/Clients"
if [ -e "$sample" ]; then
  record "sample_folder" PASS "$sample already exists (kept from an earlier run)"
else
  run "$VPY" pilot/wintest/make_samples.py
  record "sample_folder" "$(verdict "$?")" "$sample (made-up documents from tests/samples.py, by pilot/wintest/make_samples.py)"
fi

# ── 9. How to install the app (walk steps 1 to 3) ──────────────────────
# This script never installs or opens the app: its first open is the walk's,
# watched as it asks macOS's questions and sets the schedule up.
record "install_by_hand" INFO "not installed here; open $REPO/$DMG and drag the app onto Applications (walk step 2); never run it from build-portable"

say "Automated part done. Results: $JSON"
exit 0
