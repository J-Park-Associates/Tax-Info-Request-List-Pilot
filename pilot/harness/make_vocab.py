"""Give the harness the API's vocabulary as JSON (SPEC-shell 14.4).

The harness runs on the words the engine sends: ``tracker.api._vocab()`` of
this tree, dumped live every time. (Until S6b a snapshot of the S1/S8a branch
stood in, ``vocab-mirror.json``, because this branch's engine did not yet
carry those words; the branches are joined and the snapshot is gone.)
Run:  python pilot/harness/make_vocab.py out.json
"""

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

os.environ.setdefault("JPA_TRACKER_HOME", tempfile.mkdtemp())

from tracker import api  # noqa: E402

with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(api._vocab(), out, ensure_ascii=False)
