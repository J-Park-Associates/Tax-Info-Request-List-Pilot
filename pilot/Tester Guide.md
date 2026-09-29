# Tax Document Tracker Pilot - Tester Guide

## 1. What this is

Tax Document Tracker Pilot keeps track of the tax documents your clients owe you. Your client drops everything into one folder; the program sorts, renames and lists what arrives, and drafts the reminder emails that you send yourself.

The four rules it never breaks:

- **No AI reads a client document.** Every sorting decision follows fixed rules, not a chatbot.
- **Your originals are never altered.** Files are moved as they are, under their own names. All work happens on copies.
- **Nothing is guessed.** A document is filed only when exactly one request on the list accepts it. Anything unclear goes to the **Needs Review** folder for you.
- **Nothing is ever sent.** The program drafts client emails and stops. You copy and send them from your own email.

This is a **pilot**: a first edition for a small group of firms. It works, but it is unfinished, and section 8 says plainly what it will not do yet.

## 2. Before you start

- You need a Windows 10 or 11 PC.
- Keep your usual backups.
- Try it first on a **copy** of a few client folders, not your live clients folder.

## 3. Install

1. Run `Tax-Document-Tracker-Pilot-Setup-<version>.exe`.
2. Windows may show a blue box, **"Windows protected your PC"** (Windows SmartScreen, its built-in warning for programs it does not recognize). This appears because the installer is not yet signed with a paid certificate. It does not mean anything is wrong. Click **More info**, then **Run anyway**.
3. Follow the steps. No administrator rights are needed.

## 4. First launch

1. Read the terms and accept them. The program does not open until you do.
2. A short tour starts, walking through each part of the program. You can replay it any time with the **Tour** button.
3. Choose your clients folder (the copy from section 2).

## 5. Your first household

1. Press **New household**.
2. Pick the return type (for example, a 1040).
3. Tick the documents you expect this client to send.

## 6. Try it

1. Press **Inbox**. This opens the household's drop folder.
2. Drop in a mix: a W-2, a 1099, a phone photo of a document, and one document the program will not know.
3. Press **Scan**.
4. Then look at what happened:
   - **The moved originals** - in the client's folder for the year, under their own names, untouched.
   - **The Prepared folder** - the organized, renamed working copies.
   - **Needs Review** - what the program would not guess at.
   - **Status** - what is in and what is still outstanding.
   - **The reminder** - after the weekly draft day, a drafted email listing what is missing. Nothing is sent; you copy it.

## 7. The schedule

The program can run a scan for you on a timer, so documents are sorted without you pressing **Scan**. It runs only on the computer where you set it up. Two computers should never run the schedule over the same clients folder.

Press **Schedule** to:

- turn the schedule **on or off**,
- choose the **time of day** it first runs,
- choose **how often** it repeats.

Pressing **Scan** by hand works whether the schedule is on or off.

## Screen effects

The header has a **Screen effects** picker with three choices:

- **Glass** (the default): see-through bars, cards and dialogs. Nothing runs continuously.
- **Glass with refraction**: adds a soft light that follows the pointer and a slowly drifting backdrop. Use it only on a PC with a graphics card.
- **Solid**: plain surfaces. Choose it over Remote Desktop, on a slow PC, or if scrolling stutters.

If Windows Transparency effects or Animation effects are switched off, the screen turns solid and still on its own, and the picker greys out and says why. Your choice is kept on this computer.

## 8. What it will not do yet

- Windows only.
- About 74 document kinds and 6 return types.
- Scans of paper are slow without the optional graphics pack.
- The installer is unsigned, so Windows shows a warning (section 3).
- It does not send email. You send the drafts yourself.

## 9. Uninstall

Open Windows **Settings**, then **Apps**, and remove **Tax Document Tracker Pilot**.

Uninstalling removes the program and its scheduled task. It leaves your clients folder, your settings and the program's data folder (`%LOCALAPPDATA%\tax-document-tracker-pilot`) where they are.

## 10. Problems and ideas

Email admin@jparkassociates.com.

Never attach client documents. Describe the problem in words, or send a screenshot with client names covered.
