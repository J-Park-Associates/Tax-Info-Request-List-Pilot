# Pilot build board (never merged)

This branch exists only to host the board: the draft pull request titled
"BOARD: pilot build coordination". Everything happens in that pull
request's comments.

## Who is here

| Lane | Session | Pull request |
|---|---|---|
| Orchestrator | ITDR Orchestrator <Pilot> | this board |
| A - names and installer | A: Pilot names and Installer | (opens its own) |
| B - badge, terms, tour | B: Pilot Content | #4 |
| C - schedule setting | C: Schedule Setting | (opens its own) |

## Protocol

1. **Post here, in one comment, whenever you:**
   - open a pull request;
   - finish a round;
   - are blocked;
   - need something from another lane;
   - disagree with the SPEC.

   Start the comment with your lane and a tag: `[A] BLOCKED:`, `[B] DONE:`, `[C] QUESTION:`,
   `[A] NEEDS-FROM-B:`.
2. **The orchestrator answers on this board.**
   - Its decisions start with `[ORCH] DECISION:`.
   - A decision that changes the SPEC is pushed to `main` as a numbered P-decision before it is
     posted.
   - Fetch `main` to pick it up: `git fetch origin main && git merge origin/main`, using a merge
     commit and never a rebase.
3. **After each round, read the whole board before you stop,** and act on every `[ORCH]` comment
   addressed to your lane.
4. **Only the orchestrator decides roadblocks.** Only Jason decides wording that testers see
   beyond the SPEC, legal text and money.
5. **Nothing is merged to `main` by a lane.** The integrate step merges B, then A, then C.
