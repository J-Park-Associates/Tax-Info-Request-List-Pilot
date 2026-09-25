# One-time update for the office computer — 2026-09-25

Set by Jason on 2026-09-25. It is written for the next Claude Code session
on the office computer, which can see files this cloud session could not.
Do every step, tell Jason in plain English what changed, then delete this
file and the matching section at the end of `CLAUDE.md` in one commit.

## Why

Claude Opus 5.5 was released on 2026-09-22. Anthropic describes it as
performing at roughly Fable 5.1's level on most work while costing about 40%
less than Opus 5, writing faster and less wordily. Jason has decided:

- **Fable is replaced by Opus 5.5 completely.** Opus 5.5 designs, writes the
  SPEC, builds and reviews. The review is done by a separate session or
  agent that did not build the change.
- **Instruction files are trimmed for efficiency**: no dead rules, no
  duplicated text, and no instruction to read a very large file whole when a
  targeted lookup will do.

## Step 1 — the global CLAUDE.md (applies to every project)

The file is `%USERPROFILE%\.claude\CLAUDE.md`. Read it first. Replace its
contents with the block below, then add back anything Jason wrote there
that the block does not already cover (and that is not about React,
Redux/Zustand, Tailwind, Framer Motion or `console.log` — none of his
projects use those). If you add something back, list it for Jason.

```
## How to talk to me
- I'm a CPA, not a programmer. Explain changes, problems and fixes in plain English; define any technical term in one sentence.
- Lead with the answer or the change. Skip pleasantries.
- When something breaks, state the root cause in one sentence before fixing it.

## How to change files
- No placeholders or truncated code. Edit with exact find-and-replace, or rewrite the whole file.
- One component or file at a time, verified before the next — unless a written SPEC or handoff already covers a larger batch.
- Match the project's existing stack (the tracker: the Python floor its pyproject.toml declares + plain-JavaScript Electron). Don't introduce frameworks or packages without saying why the standard library isn't enough.
- Anything that fetches data shows a clear error, a loading state and an empty state. Fail loudly; never skip silently.
- Remove debug prints and leftover logging before calling anything finished.

## Hard rule, everywhere
- Generative AI never reads client financial documents or moves client files. That work is deterministic rules or my trained model only.

## Which model for what
- Opus 5.5: default for design, SPECs, coding, code review, architecture, reconciliation logic, linked financial models, and tax / Regional Center research. High effort for design, SPECs and review; default effort for building to an approved SPEC.
- Sonnet 5: routine lookups, Excel formulas and cleanup, client-facing drafts. Escalate to Opus 5.5 if it struggles.
- Haiku 4.5: throwaway scripts and formatting only — never tax or regulation (its knowledge ends Feb 2025).
- Fable is not used.
```

## Step 2 — Claude Code settings and agents

Look in `%USERPROFILE%\.claude\` (`settings.json`, `agents\`, `commands\`,
`skills\`) and in this repository's `.claude\` folder if there is one. Where
a model is set to Fable, set it to Opus (`claude-opus-5-5`). Where a
prompt, agent or command says "Fable designs", "Fable reviews", "send it to
Fable" or similar, change it to Opus 5.5 under the rule above.

## Step 3 — the local markdown files

Search the office computer's working folders for markdown files that give
*instructions* to a future session: handoff templates, `CLAUDE.local.md`,
project memory files, the local mirror of Session Handoffs, loop or
scheduled-task prompts. In each one:

1. Replace every forward-looking Fable role with Opus 5.5.
2. Remove text that repeats `CLAUDE.md` or another instruction file; point to
   it instead.
3. Where a file says to read `docs/repo-map.md` or `docs/ROADMAP.md` whole,
   change it to the targeted lookups `CLAUDE.md` now describes.

**Do not rewrite history.** Past session notes, past CODE UPDATEs, dated
handoffs and decision-log rows that say Fable did something are records of
what happened; leave them as written.

## Step 4 — report

Tell Jason, in plain English, which files changed and what changed in each,
and record the same list in the next CODE UPDATE in Handoffs. Then delete
this file and the "One-time task for the office computer" section of
`CLAUDE.md` in one commit.
