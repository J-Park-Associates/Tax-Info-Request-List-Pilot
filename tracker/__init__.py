"""Client Document Tracker — deterministic PBC document tracking over OneDrive.

See docs/ROADMAP.md for the build plan. Component modules:

- manifest      : _manifest.xlsx schema, load/validate, status write-back
- scaffold      : folder scaffolding from the manifest
- validators    : tier 1-2 file checks + dry-run preview CLI
- content_check : tier 3 text extraction + rules + verdict cache
- scanner       : orchestrator (scan, resolve, write back)
- router        : deterministic routing of a dropped file to one request
- filer         : sort the drop folder, preserve originals, write _index.xlsx
- rollover      : build a returning client's list from their prior year
- reminder      : draft (never send) the client reminder email
- registry      : engagements.yaml — every engagement the scheduled run touches
- runner        : the unattended pass (file -> scan -> Saturday draft)
- scheduling    : generate the Task Scheduler / n8n job
- templates     : the per-form request catalog; templates/*.csv are generated from it
- locking       : the one lock per engagement that sort and scan both hold
"""

from tracker.manifest import (
    ManifestError,
    Override,
    RequestItem,
    Status,
    StatusUpdate,
    create_template,
    load_manifest,
    write_statuses,
)
from tracker.scaffold import (
    ScaffoldResult,
    assign_folders,
    folder_name_for,
    matches_identifier,
    scaffold_engagement,
)

__all__ = [
    "ManifestError",
    "Override",
    "RequestItem",
    "ScaffoldResult",
    "Status",
    "StatusUpdate",
    "assign_folders",
    "create_template",
    "folder_name_for",
    "load_manifest",
    "matches_identifier",
    "scaffold_engagement",
    "write_statuses",
]
