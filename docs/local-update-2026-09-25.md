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
- Opus 5.5: default for design, SPECs, coding, code review, architecture, reconciliation logic, linked financial models, and tax / Regional Center research. Default (medium) effort for most work; high for design, SPECs and review; xhigh or max only where it has been shown to help.
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

## Step 4 — prompts for unattended runs

Anthropic's Opus 5.5 prompting guide
(https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
recommends a standing instruction for runs nobody is watching (the loop and
scheduled-task prompts, not a conversation with Jason). Add it once at the
end of each such prompt, and keep the work in a checklist the session
updates:

```
A standing instruction from the user, the person you are working for. It is about how your turns end. A message with no tool call in it ends your turn, and the work stops there until you are asked to continue. The user has seen you end turns in four ways while work they asked for was still owed, and does not want any of them. One: a long summary of what was done that closes by announcing the next step and has no tool call, so the next thing never starts. Two: an offer to carry on with something unless the user would prefer otherwise, which stops to wait for an answer the user was not going to give. Three: a list of decisions for the user when, by your own account, none of them blocks the rest of the work. Four: deciding that this is a good place to report, because the turn has been long or a milestone is done. Status notes are welcome, and so are your recommendations on open decisions, but put them in the same message as your next tool call and carry on with whatever does not depend on the user's answer. If you notice yourself inviting the user to redirect you or offering to wait, delete it and do the next thing. The stops the user does want are the ones where nothing can move without them, or where the thing blocking you is deliberately protected from you. This does not override the need for confirmation on risky or destructive actions.
```

Per the same guide, also remove from any local prompt:

- lines telling Claude to "think carefully" or "think step by step" before
  answering — the effort setting controls that now;
- any request to write out its internal reasoning in the reply — Opus 5.5
  declines those. (Asking for the *reasons behind a design* in a SPEC or a
  docstring is fine; that is not the same thing.)

## Step 5 — install the Figma plugin for this project only

Jason needs Figma for the design system redesign in Step 6, and only now
and then after that. It must **not** be installed globally (user scope),
where it would load in every project. A cloud session tried it on
2026-09-25, but that container was temporary, and its network policy
refused the connection to `mcp.figma.com`.

From this repository's folder, run:

```
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin install figma@claude-plugins-official --scope local
claude plugin list
```

`--scope local` records the plugin in this folder's
`.claude\settings.local.json`, for Jason on this computer only. The
repository ignores `.claude/`, so it is never committed and no other
project or person gets it. `claude plugin list` must show
`figma@claude-plugins-official` with scope `local` and status enabled, and
no `user` scope entry. If an earlier user-scope install exists, remove it
with `claude plugin uninstall figma@claude-plugins-official --scope user`.

Restart Claude Code so the plugin loads. Then check that its connection to
Figma works: sign in to Figma when asked, and have a read-only Figma tool
answer. If the connection still fails, give Jason the exact error, skip
Step 6, and do not install a different Figma tool as a workaround.

Tell Jason how to switch it off between uses and back on when he needs it,
without reinstalling:

```
claude plugin disable figma@claude-plugins-official --scope local
claude plugin enable figma@claude-plugins-official --scope local
```

## Step 6 — start the design system redesign (SPEC first)

Jason wants the J Park & Associates design system brought up to modern
standards, with the "AI slop" removed, using the Figma plugin. The scope is
everything: tokens, components, the desktop app's screens and the client
reminder emails. Nothing is built without a written SPEC, so this session
writes the SPEC, gets Jason's approval, and stops there. Building happens
in later sessions, from the approved SPEC. Work at high effort.

The design system is a folder on this computer, beside the repository
(`tracker/page.py` says so). The cloud session could not see it. Find it,
and confirm the location with Jason before reading anything else in it.

1. **Audit, and show the evidence.** Read the design system folder and the
   two places the repository draws its look:
   - `app/renderer/style.css`. It is older than the design system and does
     not use it (decision 118 kept "the app's own page palette, older than
     the design system" as it was). It has its own navy and bright-blue
     palette, a navy gradient across the top bar and many hand-typed colors.
   - `PALETTE`, `FONT_SANS` and `FONT_SERIF` in `tracker/page.py`. These
     mirror the design system's tokens for the Outlook reminder, and a test
     holds them to the tokens.

   List what reads as AI slop, one finding per line, each with the file or
   Figma frame it is in. Examples to look for: decorative gradients,
   rounded corners and shadows on everything, generic blue or purple accents
   that are not the firm's colors, vague labels, emoji or icons standing in
   for words, filler copy, inconsistent spacing, low contrast, and colors
   typed by hand instead of taken from a token. Show Jason the list before
   proposing fixes.
2. **Write the SPEC.** Cover:
   - **Tokens:** color, type, spacing, radius, elevation, and light and
     dark modes. Each color must meet the WCAG AA contrast minimum, the
     accessibility standard for how readable text is against its
     background.
   - **Components:** buttons, status chips, cards, tables, inputs, toolbar
     and dialogs, each as a Figma component with its variants and states,
     bound to the tokens.
   - **Desktop app screens:** redesigned in Figma, then carried into
     `app/renderer/style.css` using the tokens, with no hand-typed colors.
   - **Reminder emails:** the four stages, still Outlook-safe (inline
     styles, email-safe font stacks). `PALETTE` and its test change in the
     same commit as the tokens.
   - **Build order:** tokens, then components, then screens, then code.
   - **Rules the redesign keeps:** the app stays plain JavaScript with no
     new frameworks; pages load no fonts, stylesheets or images from the
     network (`tracker/page.py`); the standing rules in `CLAUDE.md` are
     unchanged.
   - **Records to update:** a decision-log row in `docs/ROADMAP.md`, the
     `docs/repo-map.curated.json` entries the change touches (then
     `python tools/repo_map.py update`), and `docs/runbook.md` wherever
     it describes what a person sees.
3. **Get Jason's approval.** Save the SPEC where Jason keeps SPECs (ask him
   if it is not clear), show it to him in plain English, and make any
   changes he asks for. Do not start building in Figma or in code until he
   approves it.

## Step 7 — report

Tell Jason, in plain English, which files changed and what changed in each,
whether the Figma plugin is installed for this project only and connected, and where the design
system SPEC is saved and whether he approved it. Record the same list in the
next CODE UPDATE in Handoffs, naming the SPEC as the document the redesign
continues from. Then delete this file and the "One-time task for the office
computer" section of `CLAUDE.md` in one commit.
