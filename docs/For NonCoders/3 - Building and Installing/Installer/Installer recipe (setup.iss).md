# The recipe that builds the Pilot installer

**Original file:** `pilot/installer/setup.iss`  
**Kind of file:** installer recipe (a script for a free tool called Inno Setup)  
**Tags:** Kind: Program file · Topic: Installer  

## In one sentence
This file tells Inno Setup how to turn the packaged program into one Setup file that a person can double-click to install "Tax Document Tracker Pilot".

## What it is
An *installer* is a small program that copies a bigger program onto a computer and adds icons for it. Someone has to write down what the installer should do. This file is that writing. It is read by *Inno Setup*, a free tool. The Python standard library cannot build a Windows installer, so Inno Setup is used (pilot decision P4).

The file is not run by hand. `pilot/Build Pilot Installer.bat` runs it and hands it two values: the version number and the folder that holds the packaged program. If either value is missing, the build stops with a clear error.

## What it does, step by step
1. **Names the product.** The product is "Tax Document Tracker Pilot", published by J Park & Associates, CPA. The Setup file is named `Tax-Document-Tracker-Pilot-Setup-<version>.exe` and is written to `build-portable/installer`.
2. **Needs no administrator rights.** It installs into the person's own folder under `Programs`, so no one has to be an administrator.
3. **Allows 64-bit Windows computers only.**
4. **Closes the running app on an upgrade** (P115). Before it replaces anything, Windows is asked which programs are using the files. The person is asked to let Setup close them. A silent install closes them without asking. Nothing is restarted, because the schedule starts the next sorting pass by itself.
5. **Clears out the old program code first.** Only two folders are removed: the shell's code folder and the frozen engine's library folder. The optional graphics card pack sits beside the engine and is left alone. The settings file is left alone.
6. **Copies every file** from the packaged folder into the install folder.
7. **Adds icons.** A Start menu icon always. A desktop icon only if the person ticks the box (it starts unticked).
8. **Offers to launch the app** at the end, but not in a silent install.
9. **On uninstall,** removes this computer's scheduled task (named "Tax Document Tracker Pilot") and the installed files. If the task is not there, the uninstall goes on quietly.

## Why it matters to the firm
This is how the Pilot reaches an office computer. An upgrade that finds the old copy and replaces it cleanly means nobody has to remove the old one first. The uninstall step means a removed program does not leave a scheduled job running behind.

## What must never be changed without a programmer
- **The AppId** (the long code in braces). It is how an upgrade finds the copy it replaces. Change it and an upgrade can no longer find the copy it should replace.
- **The two folders removed on upgrade.** Widening that list could delete the graphics card pack or the settings.
- **The uninstall.** It must never delete the clients folder, the program's data folder or `settings.json`. There is deliberately no "delete on uninstall" section. Those belong to the firm.
- **The task name.** It must match the name the program uses for its schedule.

## Words to know
- **Installer:** a program that installs another program.
- **Inno Setup:** a free tool that builds Windows installers.
- **Administrator rights:** the higher permission Windows sometimes asks for. This installer does not need it.
- **Task (scheduled task):** a job Windows runs on a timer.
- **AppId:** a fixed code that identifies this program to Windows.
- **Frozen engine:** the program's Python part, packed into a ready-to-run form (see the freezing recipe page).
