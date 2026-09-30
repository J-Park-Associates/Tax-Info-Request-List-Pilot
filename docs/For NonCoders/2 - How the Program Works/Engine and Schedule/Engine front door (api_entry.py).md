# The engine's front door

**Original file:** `api_entry.py`  
**Kind of file:** program entry point (the first file that runs in the packed app)  
**Tags:** Kind: Program file · Topic: Engine, Schedule  

## In one sentence
This small file is the single door into the packed engine, and it decides which of three jobs to do: run the engine for the app, run the scheduled sorting pass, or act as a reading helper.

## What it is
The packed app has one engine program. This file is where that program starts. The freezing recipe (`api_entry.spec`) names it as its starting point. Because one program plays several parts, this file looks at how it was started and sends it the right way.

## What it does, step by step
1. **First, checks whether it is a reading helper.** The sorting pass reads each document in a separate helper process that it can stop (decision 150). Windows starts that helper as a fresh copy of this same program with a special note on its command line. A built-in Python step recognizes that note and runs the helper. This has to come first, before anything else looks at the command line. Run from source, this step does nothing.
2. **Checks whether it is the scheduled job.** If the first word on the command line is the runner flag, it runs the sorting pass (see the runner page) and exits with that pass's result.
3. **Otherwise, starts the engine** the app talks to (`tracker.api`) and exits with its result.

The sorting pass is loaded first and on its own. Loading the engine pulls in the scheduling part, which needs the product name that the Electron shell puts in the environment. Windows Task Scheduler passes no such thing. The scheduled job needs neither of the shell's settings: its command line names the settings folder, and the clients folder is read from the settings file at every run (decision 131).

## Why it matters to the firm
The packed app can register its own schedule because its scheduled task simply runs this same program in "sorting pass" mode. No separate Python is needed on the office computer.

## What must never be changed without a programmer
- **The order of the three checks.** The helper check must be first, or helpers would start the engine by mistake.
- **Loading the runner before the engine.** Reversing this can make the scheduled job fail with no product name.
- **The runner flag.** The scheduling code and this file must agree on it.

## Words to know
- **Entry point:** the first file that runs when a program starts.
- **Command line:** the words typed after a program's name when it starts.
- **Runner mode:** starting the program to do one sorting pass.
- **Child process (helper):** a second copy of a program started to do a small job that can be stopped.
- **Frozen:** packed so it runs without Python installed.
- **Task Scheduler:** the Windows tool that runs jobs on a timer.
