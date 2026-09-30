# The recipe that packs the engine into one ready-to-run program

**Original file:** `api_entry.spec`  
**Kind of file:** freezing recipe (a build script for a tool called PyInstaller)  
**Tags:** Kind: Program file · Topic: Building, Engine  

## In one sentence
This file tells the build tool exactly how to pack the tracker's Python engine into a folder that runs on a computer with no Python installed.

## What it is
The tracker's engine is written in Python. A Windows office computer usually does not have Python. *Freezing* means bundling the engine, Python itself and every outside part into one folder with a normal `.exe` inside. The tool that does this is *PyInstaller*.

Instead of typing many options at build time, the choices are saved in this committed file. So what gets frozen is part of the exact version that gets built. The same recipe and the same pinned tool give the same result. `Build App.bat` runs it.

## What it does, step by step
1. **Reads the engine's name** from `app/package.json` (the setting `apiName`). That is the one place the name lives. The Electron shell (the window around the app) looks for the same name when it starts.
2. **Sets up the reader.** The reader (decision 169) is the text-recognition part that reads scanned pages. Its parts are loaded in a way the freezing tool cannot see by itself, so this file lists them by name. It leaves out the engines the app never uses: pytorch, paddle, openvino, mnn and tensorrt. The app uses only ONNX Runtime.
3. **Ships the reader's models inside the app.** Three model files and two settings files go into the package. Nothing is ever downloaded.
4. **Drops one big unused file.** OpenCV's video codec library (about 31 MB) is removed, because reading never uses it.
5. **Starts from `api_entry.py`,** the engine's front door (see that page).
6. **Builds a folder, not a single file.** It leaves compression off and keeps a console window mode.

## Why it matters to the firm
The office runs the packed program, not a Python install. A wrong recipe could ship a program that fails to start, or that quietly carries extra parts. Keeping models inside the app also supports the firm's rule that the program makes no network calls to do its job.

## What must never be changed without a programmer
- **The list of reader parts.** Remove one and reading scanned pages fails inside the package, even if it works from source.
- **The excluded engines and the removed codec file.** These were chosen after checking that nothing needed them.
- **The engine name source.** The shell and the installer expect that same name.

## Words to know
- **Freezing:** packing a Python program and its parts into a ready-to-run folder.
- **PyInstaller:** the tool that freezes.
- **Spec file:** the saved list of freezing choices.
- **Reader:** the text-recognition part that reads scans.
- **ONNX Runtime:** the engine that runs the reader's models.
- **Electron shell:** the window part of the app.
