"""PyInstaller entry point for the portable app: the tracker API, and - given
``RUNNER_MODE_FLAG`` first - the scheduled job.

One executable plays both parts so the packaged app can install its own
schedule (the task's command is this executable in runner mode). The runner
is imported on its own, before ``tracker.api`` is touched, because importing
the API pulls in ``tracker.scheduling``, whose task name needs the product
name the Electron shell passes in the environment - and Task Scheduler
passes nothing. The job needs neither of the shell's variables: its command
line names the app's settings folder, the clients root is read from the
settings file there at every run (decision 131), and the log goes into that
root.

**And a third part: the reading's child** (decision 150). The pass reads
each document in a child process it can stop, started the one way Windows
has - a fresh copy of this executable, told on its command line that it is
a child. ``multiprocessing.freeze_support()`` is what recognises that
command line in a frozen build and runs the child instead of the API or the
job, so it comes first, before anything else looks at the arguments. Run
from source it does nothing.

**And the installer's door** (pilot P218, Q1). The pilot's installer runs
the after-install step through its setup door - so the first Overview after
an install is ready - by starting this executable with ``SETUP_MODE_FLAG``,
then the settings folder and the product's name, which it alone knows: the
installer passes no environment, and a frozen build has no package.json.
Both are put in the environment before ``tracker.after_install`` (and with
it ``tracker.scheduling``, which reads the product's name at import) is
imported.

**And the engine** (pilot P276): given ``tracker.resident.RESIDENT_FLAG``
alone, the API is imported at once and the process answers the commands the
app hands it, one at a time, over its standard input
(``tracker.resident.serve``), so a click does not wait for the import. It
replaces P220's warm spare, which ran one command and exited. A pass and the
after-install step are never handed to it.

**And a floor** (SPEC-mac R6, P243). A Mac app is dragged into Applications,
so there is no installer to refuse a Mac it was never proved on, and the
schedule runs this executable directly, without the shell. The check
(``tracker.settings.mac_floor_refusal``: Apple silicon, macOS 14 or later)
therefore comes second, right after ``freeze_support`` and before the
arguments are acted on: a refusal says the shell's own sentence on stderr and
exits 1 having read, written and locked nothing.
"""
import multiprocessing
import os
import sys

from tracker.runner import PRODUCT_FLAG, RUNNER_MODE_FLAG, SETTINGS_FLAG, SETUP_MODE_FLAG
from tracker.runner import main as run_pass
from tracker.settings import ENV_PRODUCT_NAME, ENV_SETTINGS_DIR, mac_floor_refusal


def told_product(argv: list[str]) -> str | None:
    """The product's name the scheduled job or the installer's door was given
    on its command line (``PRODUCT_FLAG``), or ``None``. Neither has the
    shell's environment, so the floor's sentence (R6) takes the name from here
    rather than type it a second time."""
    if PRODUCT_FLAG in argv[:-1]:
        return argv[argv.index(PRODUCT_FLAG) + 1] or None
    return None


def run_setup_step(argv: list[str]) -> int:
    """The after-install step through its setup door, for the installer:
    ``SETTINGS_FLAG <folder>`` and ``PRODUCT_FLAG <name>``, both required.
    It exits with the installer's codes (``runner.SETUP_STEP_FAILED``,
    ``runner.SETUP_OVERVIEW_NOT_READY``), which ``setup.iss`` turns into
    its failure window."""
    import argparse

    parser = argparse.ArgumentParser(prog=f"api_entry {SETUP_MODE_FLAG}")
    parser.add_argument(SETTINGS_FLAG, required=True, metavar="FOLDER")
    parser.add_argument(PRODUCT_FLAG, required=True, metavar="NAME")
    ns = parser.parse_args(argv)
    os.environ[ENV_SETTINGS_DIR] = ns.settings
    os.environ[ENV_PRODUCT_NAME] = ns.product
    from tracker.after_install import INSTALLER_CODES_FLAG, REASON_SETUP
    from tracker.after_install import main as after_install

    return after_install(["--reason", REASON_SETUP, INSTALLER_CODES_FLAG])


if __name__ == "__main__":
    multiprocessing.freeze_support()
    argv = sys.argv[1:]
    if refusal := mac_floor_refusal(product=told_product(argv)):
        sys.stderr.write(refusal + "\n")
        raise SystemExit(1)
    if argv[:1] == [RUNNER_MODE_FLAG]:
        raise SystemExit(run_pass(argv[1:]))
    if argv[:1] == [SETUP_MODE_FLAG]:
        raise SystemExit(run_setup_step(argv[1:]))
    from tracker.api import main
    from tracker.resident import RESIDENT_FLAG, serve

    # The engine (pilot P276): imported now, its commands read as they come.
    raise SystemExit(serve() if argv == [RESIDENT_FLAG] else main(argv))
