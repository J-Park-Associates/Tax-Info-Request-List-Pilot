# Window page and its safety rule

**Original file:** `app/renderer/index.html`  
**Kind of file:** web page skeleton (HTML) for the app's one screen  
**Tags:** Kind: Program file · Topic: Safety, App window  

## In one sentence
This is the frame of the app's single screen: the side panel, the top bar, the notice area, the side sheet and the list of script files that bring it to life, all sitting under a strict safety rule.

## What it is
*HTML* is the language that describes what is on a web page. The app is a web page in a desktop window, and this file is its skeleton. It holds empty slots and buttons. The words, colours and content are filled in later by script files, using text the tracker supplies. The file's own comments say it types none of the words itself.

## What it does, step by step
1. **Sets the safety rule.** Near the top, a *Content Security Policy (CSP)* says that nothing may load except the app's own files. In plain terms: no script written inside the page, no picture or font from the internet, nothing from anywhere else. The rule starts with "allow nothing" and then lists what is permitted: the app's own scripts, styles, fonts, and pictures (plus small embedded pictures).
2. **Loads the styling files** (several stylesheets, including the pilot's own).
3. **Lays out the shell.** A side panel with four sections (Overview, Needs Review, Reminders, Clients), a header with breadcrumbs, a search box and a sort button, and a notice area where failures and warnings stay until a person dismisses them (decision 193). Notices have Retry and Dismiss buttons that are written right into the page, so a notice still works before any other words have arrived.
4. **Holds the side sheet.** A panel that slides in for checking a file and for the week's reminder. The reminder area shows the letter as it will read, with buttons to approve or copy it. The comments state that there is no send button and no mail link anywhere in the app.
5. **Loads the scripts last,** in a fixed order: two small helper libraries for tooltips, then the app's scripts, the pilot's scripts and the tour.

## Why it matters to the firm
The safety rule keeps the screen from running anything that did not ship with the app. The page is built from tracker data using safe building blocks, never by pasting in HTML text, so a strange file name or client name cannot become a hidden instruction. This supports the standing rules that nothing is sent and nothing is guessed.

## What must never be changed without a programmer
- The safety rule line. Loosening it opens the screen to outside code.
- Adding inline scripts, inline styles or "on click" style attributes. Tests reject them.
- Moving or rewording existing lines. Many tests check this file's exact text. The pilot rules let the pilot add only a few lines (decisions P10, P40).
- Typing words into the page by hand. Words come from the tracker so they are kept in one place.
- The order of the script files at the bottom.

## Words to know
- **HTML:** the language that describes the parts of a web page.
- **CSP (Content Security Policy):** a rule inside the page saying what it may load.
- **Inline script:** program code typed directly inside the page instead of in its own file.
- **Sheet:** a panel that slides in from the side over the screen.
- **Notice:** a message bar that stays until a person dismisses it.
- **Stylesheet:** a file that says how the page looks.
