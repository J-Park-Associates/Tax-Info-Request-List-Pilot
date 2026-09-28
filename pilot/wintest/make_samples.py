"""Build the sandbox clients folder for the pilot's Windows check (P28).

The check is driven by Claude, which sees the screen, and generative AI
never reads a client document - so the only documents in play are the
made-up ones the suite's own fixtures build (``tests/samples.py``): one
household, one return, and a pile of fake documents waiting in its
"Drop files here" inbox. The folder is refused anywhere but under
``%USERPROFILE%\\PilotTest``, and an existing non-empty folder is refused
rather than mixed into, so a mistyped path can never write among real files.

Run from the repository root with the checkout's virtual environment:
    .venv\\Scripts\\python.exe pilot\\wintest\\make_samples.py [target]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SANDBOX_PARENT = Path.home() / "PilotTest"


def main(argv: list[str]) -> int:
    target = Path(argv[0]) if argv else SANDBOX_PARENT / "Clients"
    target = target.resolve()
    if SANDBOX_PARENT.resolve() not in target.parents:
        print(f"Refused: {target} is not inside {SANDBOX_PARENT}. The sample folder lives only there.")
        return 2
    if target.exists() and any(target.iterdir()):
        print(f"Refused: {target} already holds files. Delete it first for a fresh sample set.")
        return 2
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "tests"))
    from samples import build_scratch_root  # the suite's own fake documents

    root = build_scratch_root(target)
    inboxes = [p for p in root.rglob("*") if p.is_dir() and p.name == "Drop files here"]
    count = sum(1 for inbox in inboxes for f in inbox.rglob("*") if f.is_file())
    if not inboxes or count == 0:
        print(f"Failed: no sample documents were made under {root}.")
        return 1
    print(f"Sample clients folder: {root}")
    print(f"Fake documents waiting in 'Drop files here': {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
