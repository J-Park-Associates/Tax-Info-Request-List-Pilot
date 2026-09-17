"""Puts the repository root on ``sys.path`` so the tests can ``import tracker``
and ``tests.samples`` from any working directory.

``pythonpath`` in pyproject.toml does the same for pytest; this file is
here for the tools that run a test module directly (an editor's runner,
``python -m pytest tests/test_x.py`` from elsewhere) and for pytest's
rootdir detection, which anchors on it.
"""

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
