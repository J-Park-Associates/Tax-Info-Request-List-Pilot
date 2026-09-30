# Window doorway

**Original file:** `app/preload.js`  
**Kind of file:** program code (JavaScript), a small safe bridge  
**Tags:** Kind: Program file · Topic: Safety, App window  

## In one sentence
This 23-line file is the only doorway through which the app's screens can ask the outer shell to do anything.

## What it is
The app's screens run in a sealed box (a *sandbox*) so that nothing on the page can reach the computer directly. A *preload script* runs just as the page loads and places a few named buttons through the wall of that box. This file is that script. It builds one object called `tracker` that the page can use. Nothing else crosses over.

## What it does, step by step
It hands the page these tools, and only these:
1. **call** - send a command to the tracker (for example, "sort now") and get the reply.
2. **open** - open a file or folder in its usual program, or show it selected in File Explorer ("reveal"). The page may only name a path the tracker has reported. Anything else is refused by `main.js`.
3. **pickFolder** - show the standard "choose a folder" box.
4. **logError** - hand the page's own error text to the shell so it is saved in the error log instead of shown on screen.
5. **onProgress** - listen for progress lines while a sort is running.
6. **onAfterInstallDone** - hear that the background after-install step has finished, so the page can ask again and show what it left behind. Nothing is passed with that message (decision 209).
7. **menu** - a small pair of tools: hear that a menu item was chosen, and tell the shell which menu items apply now (or ask for a right-click menu). None of this reaches the tracker.

Each tool only sends a message. The real work, and the real checking, happen in `app/main.js`.

## Why it matters to the firm
A narrow doorway means a smaller chance that a bug or a trick on the page can touch client files. The page cannot read the disk, cannot start programs and cannot type its own paths. It can only ask, and the shell decides.

## What must never be changed without a programmer
- Adding a tool to the list. Each new tool is a new way in. The pilot rules say no new message channel may be added (decisions P10 and the pilot build plan, section 1), and a test enforces that the channel lists in this file and `main.js` stay as they are.
- Passing raw computer access (like file reading) through the wall.
- Removing the note that a path must be one the tracker reported.

## Words to know
- **Sandbox:** a sealed box that limits what a page may do.
- **Preload script:** a script that runs as the page loads and sets up the doorway.
- **IPC (message channel):** how the page and the shell send messages to each other.
- **Renderer:** the part of the app that draws the screens.
- **Reveal:** show a file selected inside its folder in File Explorer.
- **Tracker:** the Python program that does the real work.
