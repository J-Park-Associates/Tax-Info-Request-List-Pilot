"""Build the sandbox clients folder for the pilot's Windows check (P28).

The check is driven by Claude, which sees the screen, and generative AI
never reads a client document - so the only documents in play are the
made-up ones the suite's own fixtures build (``tests/samples.py``): one
household, one return, and a pile of fake documents waiting in its
"Drop files here" inbox. The folder is refused anywhere but under
``%USERPROFILE%\\PilotTest``, and an existing non-empty folder is refused
rather than mixed into, so a mistyped path can never write among real files.

It never writes the app's real data folder (F7, P193, R3). Building the
samples writes each return's record and the engine's store and checkpoint;
on 9/29 the script ran from inside the Claude desktop app, which Windows
redirects, and became the first writer of a private copy of the data folder
the app later read instead of the real one. So it builds under a throwaway
``TRACKER_DATA_HOME`` (a temporary folder, removed afterwards), and keeps
nothing of the engine's but the records inside the sample folder: the app's
first read seeds its checkpoint from those records, as it does for any
return it sees for the first time.

Run from the repository root with the checkout's virtual environment:
    .venv\\Scripts\\python.exe pilot\\wintest\\make_samples.py [target]
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
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

    from tracker import store
    from tracker.settings import ENV_DATA_HOME

    os.environ.pop(store.ENV_STORE, None)           # a named store would be written, not the throwaway one
    with tempfile.TemporaryDirectory(prefix="pilot-samples-") as throwaway:
        os.environ[ENV_DATA_HOME] = throwaway
        try:
            root = build_scratch_root(target)
        finally:
            store.close()                           # Windows cannot remove an open database
            logging.shutdown()                      # nor an open error log
            del os.environ[ENV_DATA_HOME]
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
