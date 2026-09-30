# The Windows schedule: making the daily job

**Original file:** `tracker/scheduling.py`  
**Kind of file:** Python program module (about 850 lines; this page summarizes its opening explanation)  
**Tags:** Kind: Program file · Topic: Schedule  

## In one sentence
This module writes the definition of the daily job that runs the sorting pass, registers it with Windows Task Scheduler, and makes sure only one computer runs it.

## What it is
*Task Scheduler* is the part of Windows that runs jobs on a timer. This module produces the job's definition (an XML file), or an equivalent for a tool called n8n, and can register it. The job's command is the sorting pass, pointed at the app's settings folder. The packed app has no Python, so the job runs the app's own engine program in "runner mode" (see the front door page).

## What it does, step by step
1. **Names no clients folder.** The folder lives in the settings file only. It used to be copied into the job, so a changed folder left the job walking the old one, red every night (decision 131). Now changing it in the app is enough.
2. **Uses one task, not two.** The runner decides itself whether today is the draft day. A run missed on that day still drafts at the next run.
3. **Repeats through the day.** The defaults are start 07:00, every 120 minutes. The choices for "every" are 0 (once a day), 30, 60, 120, 240 and 480 minutes. Each run is capped at 2 hours.
4. **Registers the task** with the Windows `schtasks` command. Running it again is also how the schedule is changed. It runs locally and reaches no network.
5. **Picks the one computer** (decision 209). Setup, the app's first start after an upgrade, and the first clients folder saved all register through one function, but only on the computer named in a designation file in the firm's private folder. The first Windows computer to register claims it. Any other registers none and removes its own. Moving the schedule is one deliberate command on the new computer.
6. **Reads the designation file carefully.** It holds one computer name. An unreadable file is a failure, never a guess, and its contents are never repeated back.
7. **Says the next run** ("Next run: today at ..." or "tomorrow at ...") and gives plain sentences for each outcome, such as claimed, registered, elsewhere or off.
8. **Refuses unsafe text.** It checks the values placed into the job so nothing can be slipped into a command.

Nothing here sends email. The job files documents, updates the record and writes draft text files. A person sends them.

## Why it matters to the firm
The scheduled work only happens if this job exists on the right computer. One computer running it avoids two passes fighting over the same folders. The stated risk: the designation is detection, not a lock. If two desks claim before a sync carries the first claim, both can claim. The runbook's one-machine rule still applies.

## What must never be changed without a programmer
- **The task name.** It comes from the product name and the installer's uninstall step uses the same name.
- **The one-computer rule and designation file.**
- **The rule that the module loads no network library** (decision 194).
- **The quoting and refusal checks** for the job's command.

## Words to know
- **Task Scheduler:** the Windows timer for running jobs.
- **schtasks:** the Windows command that registers such jobs.
- **XML:** a text format for structured settings.
- **Designation file:** the file naming the one computer that runs the schedule.
- **n8n:** an automation tool; a second output format for the same job.
- **Runner mode:** the engine started to do one sorting pass.
