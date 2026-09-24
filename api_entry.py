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
"""
import sys

from tracker.runner import RUNNER_MODE_FLAG
from tracker.runner import main as run_pass

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[:1] == [RUNNER_MODE_FLAG]:
        raise SystemExit(run_pass(argv[1:]))
    from tracker.api import main

    raise SystemExit(main(argv))
