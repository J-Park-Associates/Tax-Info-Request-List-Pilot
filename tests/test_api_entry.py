"""Tests for api_entry.py — the packaged app's one executable, in both parts.

The claim: given RUNNER_MODE_FLAG first it is the scheduled job and needs
none of the environment the Electron shell gives the API (Task Scheduler
passes nothing); without the flag it is the API, one JSON object out.
The job is given its settings folder on its command line, as Task
Scheduler gives it, and needs nothing else from the environment
(decision 185).
"""

import subprocess
import sys
import textwrap
from pathlib import Path

from tests.conftest import child_env, make_engagement
from tracker.manifest import RequestItem
from tracker.runner import RUNNER_MODE_FLAG, SETTINGS_FLAG
from tracker.settings import ENV_PRODUCT_NAME, ENV_SETTINGS_DIR

REPO = Path(__file__).resolve().parent.parent


def run_entry(args: list[str]) -> tuple[int, bool, str, bool]:
    """Run api_entry.py in a fresh interpreter with the shell's variables
    stripped; report the exit code, whether tracker.api was imported, stdout,
    and whether a child process was started (decision 150's reading)."""
    env = child_env(drop=(ENV_PRODUCT_NAME,) + ((ENV_SETTINGS_DIR,) if args[:1] == [RUNNER_MODE_FLAG] else ()))
    probe = textwrap.dedent(f"""
        import runpy, sys
        sys.argv = ["api_entry.py"] + {args!r}
        try:
            runpy.run_path("api_entry.py", run_name="__main__")
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
        else:
            code = 0
        spawned = any(name.startswith("multiprocessing.popen_spawn") for name in sys.modules)
        sys.stdout.write("\\nAPI_IMPORTED=%s EXIT=%s SPAWNED=%s\\n"
                         % ("tracker.api" in sys.modules, code, spawned))
    """)
    done = subprocess.run([sys.executable, "-c", probe], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    body, _, marker = done.stdout.rpartition("API_IMPORTED=")
    imported, exit_code, spawned = marker.split()
    return (int(exit_code.removeprefix("EXIT=")), imported == "True", body,
            spawned == "SPAWNED=True")


def test_runner_mode_runs_a_pass_without_importing_the_api_layer(tmp_path):
    root = tmp_path / "Clients"
    make_engagement(root, [RequestItem(identifier="A01", document="W-2")],
                    household="Smith Family")

    code, api_imported, out, _spawned = run_entry([RUNNER_MODE_FLAG, str(root),
                                                   SETTINGS_FLAG, str(tmp_path / "app"), "--dry-run",
                                                   "--reminders", "never"])

    assert code == 0, out
    assert api_imported is False          # so Task Scheduler's empty environment is enough
    assert "Smith Family 2025 1040 - Test Client" in out     # the label, as every list says it


def test_without_the_flag_the_entry_is_the_api(monkeypatch):
    code, api_imported, out, _spawned = run_entry(["templates"])
    assert code == 0 and api_imported is True
    assert out.strip().startswith("{") and out.strip().endswith("}")


def test_a_reading_child_is_recognised_before_anything_reads_the_arguments():
    """Decision 150: the pass reads each document in a child process, and
    in the frozen build that child is this executable started again with
    ``multiprocessing``'s own arguments. ``freeze_support()`` has to see
    them first, or the child would be taken for the API or the job."""
    import ast

    tree = ast.parse((REPO / "api_entry.py").read_text(encoding="utf-8"))
    [guard] = [node for node in tree.body if isinstance(node, ast.If)]
    assert ast.unparse(guard.test) == "__name__ == '__main__'"
    assert ast.unparse(guard.body[0]) == "multiprocessing.freeze_support()"


def test_runner_mode_reads_a_drop_in_a_child_and_files_it(tmp_path):
    """The job, run the way Task Scheduler runs it, reads a drop in the
    child the pass can stop (decision 150) - no suite fixture turns the
    child off in a process of its own - and the drop is filed on what the
    child read."""
    from tests.conftest import named_page
    from tests.test_scanner import text_pdf
    from tracker.layout import inbox_of

    root = tmp_path / "Clients"
    engagement = make_engagement(root, [RequestItem(
        identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
        min_size_kb=0, required_keywords=("W-2",))], household="Smith Family")
    text_pdf(inbox_of(engagement) / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    code, _api_imported, out, spawned = run_entry([RUNNER_MODE_FLAG, str(root),
                                                   SETTINGS_FLAG, str(tmp_path / "app"), "--dry-run",
                                                   "--reminders", "never"])

    assert code == 0, out
    assert spawned                                   # the drop was read in a child
    assert "filed 1," in out                         # and filed on what the child read


def test_the_setup_mode_runs_the_after_install_step_with_what_its_command_line_names(tmp_path, monkeypatch, capsys):
    """Pilot P218, Q1: the installer starts the packaged executable with
    ``SETUP_MODE_FLAG``, the settings folder and the product's name - it has
    no environment to give - and the after-install step runs through its
    setup door with both in place. In this process, so the suite's own
    after-install fakes (the test cache it may not clear) hold; the order
    of imports is ``test_pilot_installer``'s static claim."""
    import json
    import os
    import runpy

    from tracker import after_install
    from tracker.runner import PRODUCT_FLAG, SETUP_MODE_FLAG

    # setenv first records the variables as they were (set or not), so the
    # teardown restores them after run_setup_step writes os.environ itself.
    for name in (ENV_PRODUCT_NAME, ENV_SETTINGS_DIR):
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)
    settings = tmp_path / "installed"
    settings.mkdir()
    entry = runpy.run_path(str(REPO / "api_entry.py"), run_name="api_entry")

    code = entry["run_setup_step"]([SETTINGS_FLAG, str(settings), PRODUCT_FLAG, "Fabricated Product"])

    assert os.environ[ENV_SETTINGS_DIR] == str(settings)
    assert os.environ[ENV_PRODUCT_NAME] == "Fabricated Product"
    assert code == 0, capsys.readouterr().out
    record = json.loads(after_install.record_path().read_text(encoding="utf-8"))
    assert record["reason"] == after_install.REASON_SETUP
    assert SETUP_MODE_FLAG == "--after-install-setup"
    capsys.readouterr()


def test_the_entry_given_the_spare_flag_waits_for_its_command():
    """Pilot P220: the packaged executable started as a spare imports the
    API, then runs the one command the shell hands it on stdin - the reply a
    fresh ``templates`` gives - and, handed nothing, exits quietly."""
    import json

    from tracker.api import SPARE_FLAG

    def entry(args, stdin: bytes):
        return subprocess.run([sys.executable, "api_entry.py", *args], cwd=REPO, env=child_env(),
                              input=stdin, capture_output=True, timeout=120)

    fresh = entry(["templates"], b"")
    warm = entry([SPARE_FLAG], json.dumps({"argv": ["templates"]}).encode() + b"\n")
    assert fresh.returncode == warm.returncode == 0, warm.stderr
    assert warm.stdout == fresh.stdout and warm.stdout.strip().startswith(b"{")
    idle = entry([SPARE_FLAG], b"")
    assert idle.returncode == 0 and idle.stdout == b""
