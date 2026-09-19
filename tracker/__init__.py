"""Deterministic PBC document tracking over OneDrive or Google Drive.

See docs/ROADMAP.md for the build plan. Component modules:

- records       : the record types every layer names - the index row, the evidence, the routing decision, the engagement - and each one's own serialisation
- manifest      : the manifest workbook's schema, load/validate, status write-back
- scaffold      : folder scaffolding from the manifest
- validators    : tier 1-2 file checks + dry-run preview CLI
- content_check : tier 3 text extraction + rules + verdict cache
- scanner       : orchestrator (scan, resolve, write back)
- router        : deterministic routing of a dropped file to one request
- filer         : sort the drop folder, preserve originals, record where every one went
- review        : triage the parked files - a ranked shortlist with its reasons, filing nothing
- rollover      : build a returning client's list from their prior year
- reminder      : draft (never send) the client reminder email
- registry      : finds every engagement under the clients root (no registry file)
- runner        : the unattended pass (file -> scan -> weekly draft)
- scheduling    : generate the Task Scheduler / n8n job
- templates     : the per-form request catalog, the one place the checklists live
- locking       : the one lock per engagement that sort and scan both hold
- ledger        : the engagement's own append-only record of what was decided, written beside the workbooks under that lock
- store         : the database on this machine, rebuilt from the record; one file per clients root, and the index is read from it
- page          : the markup both of the firm's pages are drawn with: escaping, tables, the bytes a page is written as
- view          : the page a person opens, regenerated from the record and the readers every pass
- settings      : the settings file beside the app - the clients root and firm, written once
- reasons       : every refusal said once: the note, the client's ask, whose problem it is
- api           : the desktop app's command layer, one JSON command in, one JSON reply out

The standing rules below are the ones every module upholds. They are read
by the app (through the API's vocabulary) and pinned into CLAUDE.md, the
README, the roadmap and the knowledge map by tests/test_single_source.py,
so they are worded here and nowhere else.

The package imports nothing at load time (decision 99). Every component is
reached by its own name - ``from tracker import manifest`` - and
``tests/test_layers.py`` pins which layer each one sits in and that no
load-time import points upward. The re-exports that used to live here
were thirteen names no file consumed, and they were the package's one
load-time cycle.
"""

#: (headline, detail) - the detail names folders and the record by
#: placeholder so the scaffold's constants and ``records.THE_RECORD`` stay
#: the only copy of those words; see ``tracker.api.standing_rules`` for the
#: filled sentences.
STANDING_RULES: tuple[tuple[str, str], ...] = (
    ("No generative AI ever reads a client financial document.",
     "Every routing and status decision comes from deterministic rules in the manifest."),
    ("Originals are never altered.",
     "Files are moved byte for byte under their own names into {shared}/{pbc}/; "
     "all work happens on copies, and every move is recorded in {record}."),
    ("Nothing is guessed.",
     "A document is filed only when exactly one request accepts it - or, when one document "
     "names several forms as itself, when each of those forms is accepted by exactly one "
     "request. Ambiguous, contested and unrecognized files go to {review} for a person - "
     "misfiling a tax document is worse than not filing it."),
    ("Nothing is ever sent.",
     "The system drafts client emails and stops. There is no SMTP, no mail client and no "
     "network call in the reminder or scheduling path."),
)
