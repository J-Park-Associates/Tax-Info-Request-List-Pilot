# Screen picture and click tests

**Original file:** `pilot/harness/README.md`, `pilot/harness/shoot.mjs`, `pilot/harness/interact.mjs`, `pilot/harness/stub.js`, `pilot/harness/serve.mjs`, `pilot/harness/app-stub.js`, `pilot/harness/accel.js`, `pilot/harness/boot.js`, `pilot/harness/make_vocab.py`  
**Kind of file:** developer test kit (JavaScript and Python)  
**Tags:** Kind: Program file · Topic: Testing, App window  

## In one sentence
The harness draws the app's screens and clicks through them with made-up data, so the look and behavior can be checked without the real tracker.

## What it is
A *harness* is a rig that holds a program up so it can be tested. This one runs the app's real screen files in a web browser (Chromium, driven by a tool called Playwright) and feeds them from a fake tracker. It is never loaded by the app, never packaged, and the normal test runner does not run it. It uses made-up names only: the Smith Family, Rivera Design LLC, Ana Lopez and 500 generated households.

## What it does, step by step
- **`stub.js`:** the fake tracker. It replies in the same shapes as the real one and even handles writes from the side sheet, changing the made-up return so the screen moves on. Its words come from the real tracker's own vocabulary, and a test in `tests/test_shell.py` holds its replies to the real ones.
- **`make_vocab.py`:** dumps the real tracker's wording so the fake one never types its own.
- **`serve.mjs`:** a tiny local web server that hands the browser the app's files. In "real" mode it uses the real `app.js` with the fake tracker. In "double" mode it swaps in `app-stub.js`, a stand-in for `app.js`.
- **`accel.js`, `boot.js`:** map the keyboard shortcuts (Ctrl+1 to Ctrl+4, Ctrl+F, F5, F9) onto the app's menu, because a browser has no menu bar.
- **`shoot.mjs`:** takes screenshots of every scenario, light and dark, at two window sizes (1100 by 700 and 1400 by 900). It also covers the side sheet, dialogs, a high-contrast look and a quick run of the real `app.js`. It lists any problems it found.
- **`interact.mjs`:** acts like a person: clicks, types, presses Tab and Esc, opens the side sheet, right-clicks, and checks what happens each time.

To run the picture tool, use one command from the repository root: it takes a Python to use, an output folder and, optionally, scenario names. With no names it shoots them all.

## Why it matters to the firm
The screens are what staff will see every day. This rig lets a builder look at layout and try the clicks before the real engine is attached, and lets a reviewer confirm nothing on screen broke, all without any client data.

## What must never be changed without a programmer
- Putting real client names or data into the fake tracker.
- Loading any of this in the shipped app.
- Editing the fake tracker's words by hand. They must come from the real vocabulary.

## Words to know
- **Harness:** a rig that runs a program in a controlled setting.
- **Stub / double:** a fake stand-in for a real part.
- **Chromium / Playwright:** a browser and the tool that drives it like a person.
- **Scenario:** one screen situation to photograph.
- **Vocabulary:** the list of words the tracker supplies to the screen.
