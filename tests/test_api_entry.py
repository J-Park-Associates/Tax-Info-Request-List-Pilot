"""Tests for api_entry.py — the packaged app's one executable, in both parts.

The claim: given RUNNER_MODE_FLAG first it is the scheduled job and needs
none of the environment the Electron shell gives the API (Task Scheduler
passes nothing); without the flag it is the API, one JSON object out.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from tracker.manifest import RequestItem, create_template
from tracker.runner import RUNNER_MODE_FLAG
from tracker.scaffold import MANIFEST_FILENAME, scaffold_engagement
from tracker.settings import ENV_PRODUCT_NAME, ENV_SETTINGS_DIR

REPO = Path(__file__).resolve().parent.parent


def run_entry(args: list[str]) -> tuple[int, bool, str]:
    """Run api_entry.py in a fresh interpreter with the shell's variables
    stripped; report the exit code, whether tracker.api was imported, stdout."""
    env = {k: v for k, v in os.environ.items() if k not in (ENV_PRODUCT_NAME, ENV_SETTINGS_DIR)}
    probe = textwrap.dedent(f"""
        import runpy, sys
        sys.argv = ["api_entry.py"] + {args!r}
        try:
            runpy.run_path("api_entry.py", run_name="__main__")
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
        else:
            code = 0
        sys.stdout.write("\\nAPI_IMPORTED=%s EXIT=%s\\n" % ("tracker.api" in sys.modules, code))
    """)
    done = subprocess.run([sys.executable, "-c", probe], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    body, _, marker = done.stdout.rpartition("API_IMPORTED=")
    imported, exit_code = marker.split()
    return int(exit_code.removeprefix("EXIT=")), imported == "True", body


def test_runner_mode_runs_a_pass_without_importing_the_api_layer(tmp_path):
    root = tmp_path / "Clients"
    engagement = root / "Smith 2025"
    engagement.mkdir(parents=True)
    create_template(engagement / MANIFEST_FILENAME, [RequestItem(identifier="A01", document="W-2")])
    scaffold_engagement(engagement)

    code, api_imported, out = run_entry([RUNNER_MODE_FLAG, str(root), "--dry-run", "--reminders", "never"])

    assert code == 0, out
    assert api_imported is False          # so Task Scheduler's empty environment is enough
    assert "Smith 2025" in out


def test_without_the_flag_the_entry_is_the_api(monkeypatch):
    code, api_imported, out = run_entry(["templates"])
    assert code == 0 and api_imported is True
    assert out.strip().startswith("{") and out.strip().endswith("}")
