"""Dump the real API's vocabulary as JSON for the harness (SPEC-shell 14.4).

The harness lays SPEC 11's `screen` and `menu` blocks over it (stub.js), so
the words the old screen still uses are the real ones. Run:  python pilot/harness/make_vocab.py out.json
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("JPA_TRACKER_HOME", tempfile.mkdtemp())

from tracker import api  # noqa: E402

with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(api._vocab(), out, ensure_ascii=False)
