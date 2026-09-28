# Pilot session prompts

Copy-paste prompts for the parallel builds, the review, the fixes and the
integration (P23). Open Prompts 1, 2 and 3 at the same time.

Order: **1, 2, 3 in parallel** -> **4 Review** (when all three draft pull
requests exist) -> **5 Fix** in each build session that has findings ->
**6 Integrate** -> Jason's Windows check.

## How to run them

Every session is opened on the repository **J-Park-Associates/Tax-Info-Request-List-Pilot**. The
model to pick is shown above each prompt.

---
**Prompt 1: Build A: names and installer** (model: Sonnet)
```
You are Build A for the Tax Document Tracker Pilot. Read, in order, and nothing else first:
pilot/README.md, pilot/DECISIONS.md, pilot/SPEC.md (your parts: section 3a, then sections 10, 13, 14,
and the installer tests in section 11). Use `python tools/repo_map.py show <file>` for any module;
never read docs/repo-map.md whole.

Build exactly what those sections say, nothing more:
1. First commit: the section 3a renames (package name, productName, pyproject name, DATA_HOME_NAME,
   README and ROADMAP first lines) and the P19 deny-list change in .claude/settings.json with its
   test. Run the name-sensitive tests listed in 3a.
2. Then: pilot/installer/setup.iss, "pilot/Build Pilot Installer.bat", "pilot/Tester Guide.md",
   tests/test_pilot_installer.py.
Do not touch app/renderer/ (Build B) or the schedule code (Build C).

Environment: `pip install -r requirements.lock` fails in the cloud. Make a venv and install the
pinned versions you need from requirements.lock (start with pytest ruff pypdf openpyxl; add pins as
imports fail). The pilot-content.js file comes from Build B; use a temporary copy in the section 4
shape inside your test.

Gate before pushing (CLAUDE.md): delete dead code in changed files, then `python -m ruff check .`,
`python tools/repo_map.py update` then `check`, and the affected tests. Commit with "[skip ci]" in
the message. Push your session branch and open a DRAFT pull request to main titled
"Build A: pilot names and installer", its body listing what you built and the test results. Update
pilot/HANDOFF.md in the same branch (what's done, anything left). Then stop and report in plain
English.
```

---
**Prompt 2: Build B: badge, terms screen, tour** (model: Sonnet)
```
You are Build B for the Tax Document Tracker Pilot. Read, in order, and nothing else first:
pilot/README.md, pilot/DECISIONS.md, pilot/SPEC.md (your parts: sections 2 to 9 and the pilot/tour
tests in section 11). Use `python tools/repo_map.py show <file>`; never read docs/repo-map.md whole.

Build exactly what those sections say: app/renderer/pilot-content.js (copy the section 7 and 8 JSON
exactly - the wording is approved), pilot.js, tour.js, pilot-style.css, the four index.html lines
of section 3, tests/test_pilot.py, tests/test_tour.py. Do not touch the section 3a names (Build A)
or the schedule code (Build C). No edits to app.js, main.js, preload.js or style.css.

Environment: `pip install -r requirements.lock` fails in the cloud. Make a venv and install pinned
versions from requirements.lock as needed (start with pytest ruff pypdf openpyxl).

Check it in the running app if you can (the `run` skill, a scratch root from
tests/samples.py::build_scratch_root): terms show once and cannot be escaped; the tour starts after
accepting; each step highlights its element or shows its fallback.

Gate before pushing (CLAUDE.md): dead code out, `python -m ruff check .`,
`python tools/repo_map.py update` then `check`, the affected tests including test_layers and
test_single_source. Commit with "[skip ci]" in the message. Push your session branch and open a
DRAFT pull request to main titled "Build B: pilot badge, terms and tour". Update pilot/HANDOFF.md in
the same branch. Then stop and report in plain English.
```

---
**Prompt 3: Build C: schedule setting** (model: Sonnet)
```
You are Build C for the Tax Document Tracker Pilot. Read, in order, and nothing else first:
pilot/README.md, pilot/DECISIONS.md, pilot/SPEC.md section 12 (all of it) and section 15. Use
`python tools/repo_map.py show <file>` for tracker/scheduling.py, settings.py, after_install.py,
api.py, runner.py and app/renderer/app.js; never read docs/repo-map.md whole; read only the line
ranges you change.

Build exactly section 12: the saved preference in settings.json, check_start / check_every, every
registration path using the saved choice, the "off" outcome, the launch comparison, the
set-schedule command and vocabulary, the Schedule button after #btn-edit and the dialog, the
once-a-day wording, the last-pass amber rule, the runbook passages, and the tests in 12.8. Do not
touch the pilot badge, terms or tour files (Build B) or the section 3a names (Build A).

Environment: `pip install -r requirements.lock` fails in the cloud. Make a venv and install pinned
versions from requirements.lock as needed.

Gate before pushing (CLAUDE.md): dead code out, `python -m ruff check .`,
`python tools/repo_map.py update` then `check`, and the affected tests: test_scheduling,
test_settings, test_after_install, test_api, test_runner, test_single_source, test_layers,
test_repo_map - plus the own test file of every module that imports a changed one. Commit with
"[skip ci]" in the message. Push your session branch and open a DRAFT pull request to main titled
"Build C: schedule setting". Update pilot/HANDOFF.md in the same branch. Then stop and report in
plain English.
```

---
**Prompt 4: Review** (model: Opus, high effort; open it when all three draft pull requests exist)
```
You are the reviewer for the Tax Document Tracker Pilot. You did not build anything. Read
pilot/README.md, pilot/DECISIONS.md and pilot/SPEC.md, then review the three open draft pull
requests (Build A, Build B, Build C) against the SPEC, one at a time.

For each: check it does exactly what its SPEC sections say (no more, no less), that the standing
rules hold (no AI reads documents, originals never altered, nothing guessed, nothing sent), that the
tests make the claims the SPEC lists and pass (run them in a venv with pinned versions from
requirements.lock), and look for real bugs. Also check the three will merge cleanly in the order
B -> A -> C (index.html is edited by B and C; the map is regenerated, never hand-merged).

Write numbered findings per build to pilot/reviews/review-1.md (finding, file:line, why it
matters, what would fix it), commit it with "[skip ci]" on your session branch, and post each
build's findings as one comment on its pull request. If a build has no findings, say so. Do not
fix anything yourself. Report in plain English which builds are clean and which need fixes.
```

---
**Prompt 5: Fix** (paste into the **same** build session that built it, only if it has findings)
```
The review is in: read pilot/reviews/review-1.md (fetch the reviewer's branch or read the comment
on your pull request) and fix only the findings for your build - nothing else. Rerun only the tests
the fixes touch, plus ruff and the map check. Commit with "[skip ci]", push to the same branch, and
reply on the pull request listing each finding number and what you changed. Report in plain
English.
```

---
**Prompt 6: Integrate and prepare the release** (model: Opus; open it when the fixes are pushed)
```
You integrate the Tax Document Tracker Pilot. Read pilot/README.md, pilot/DECISIONS.md,
pilot/SPEC.md and pilot/reviews/review-1.md. For each finding, confirm the fix on its pull request;
if a finding survived its fix, fix it yourself.

Then merge the pull requests into main in the order B, A, C, each as a merge commit (never squash
or rebase). After each merge: resolve index.html by keeping both sides, run
`python tools/repo_map.py update`, run ruff, the map check and the affected tests, and commit with
"[skip ci]". After the last merge, run every test named in SPEC sections 3a, 11 and 12.8, and check
section 15's done criteria.

Finish by writing pilot/RELEASE.md: the version (from app/renderer/pilot-content.js), the exact
steps for Jason on the office PC (install Inno Setup 6, run "pilot\Build Pilot Installer.bat", the
section 4 Windows check from pilot/HANDOFF.md, tag pilot-<version>, send the installer plus
"pilot/Tester Guide.md" to testers), and anything left open. Update pilot/HANDOFF.md, push main,
and report in plain English.
```
---

## Then Jason, on the office PC (about 30 minutes)
1. Install Inno Setup 6.
2. Pull `main` and run `pilot\Build Pilot Installer.bat`.
3. Install the pilot, accept the terms, run the tour on a copy of client folders, and try the
   Schedule dialog.
4. Uninstall, and confirm the client folders and the data folder remain.
5. Tag the release `pilot-0.1` and send it.
