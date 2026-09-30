"""Give the harness the API's vocabulary as JSON (SPEC-shell 14.4).

The harness runs on the words the joined engine sends. This branch's engine
does not yet carry S1's and S8a's words (the screen and menu blocks, the short
reasons, Title Case, the three link tooltips, the notice words, the rules'
short lines), so their reply is kept beside this file as a snapshot
(``vocab-mirror.json``: ``tracker.api._vocab()`` of branch
``claude/shell-s8a-links`` at 86569b0, the merge of S1 rebuild 3 and S8a
rebuild 3) and the harness draws from it. S6 joins the branches; then
``HARNESS_LIVE_VOCAB=1`` dumps this tree's own vocabulary instead, and the
snapshot goes. Run:  python pilot/harness/make_vocab.py out.json
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIRROR = HERE / "vocab-mirror.json"

if MIRROR.exists() and not os.environ.get("HARNESS_LIVE_VOCAB"):
    shutil.copyfile(MIRROR, sys.argv[1])
    raise SystemExit(0)

sys.path.insert(0, str(HERE.parents[1]))

os.environ.setdefault("JPA_TRACKER_HOME", tempfile.mkdtemp())

from tracker import api  # noqa: E402

with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(api._vocab(), out, ensure_ascii=False)
