TAX DOCUMENT TRACKER - PORTABLE MARKETING DEMO
J Park & Associates, CPA
Version 1.1.0 - works with OneDrive AND Google Drive
==================================================

TO RUN THE DEMO
  Double-click:  Tax Document Tracker.exe
  That's it. Nothing to install, no internet needed.

  (If Windows shows a "Windows protected your PC" SmartScreen
   message: click "More info" then "Run anyway". This appears
   because the demo is not code-signed - it is safe.)

FIRST LAUNCH
  The app builds its own sample data automatically:
  - a sample engagement (Smith Family 2025 Form 1040)
  - a "Sample Client Documents" folder with the files you
    drag during the demo
  Both appear in a "demo-marketing" folder next to the exe.

PRESENTING
  The full presenter script is DEMO-SCRIPT.md (in this folder).
  A short version is always visible in the app's left panel.
  Use "New Engagement" to show the form-type picker (1040, 1120,
  1120-S, 1065, 1041, 990) and build a tailored request list live -
  name it after the prospect for maximum effect.
  Click "Reset Demo" between meetings - 10 seconds, fully fresh.

GOOGLE DRIVE PROSPECTS
  The sample documents include two Google Drive cases you can
  demo when the prospect uses Google Workspace:
    Donation Receipts 2025.gsheet            drag into D01
      A Google Sheets shortcut, not the spreadsheet. The scan
      accepts the real .xlsx and tells the client how to export
      the Sheet (File > Download > Excel) - forward that note
      to them verbatim.
    W-2 Jane Smith 2025.pdf.tmp.driveupload  drag into A01
      A Google Drive upload caught mid-sync. It is ignored - a
      half-uploaded file is never counted as delivered.
  Using OneDrive instead? Skip those two files; everything else
  in the demo is identical.

REQUIREMENTS
  Any 64-bit Windows 10/11 computer. Excel is optional but
  recommended (the "Open Manifest in Excel" step opens the
  tracking spreadsheet in whatever handles .xlsx).

CONTENTS
  Tax Document Tracker.exe      the demo app
  resources\                    app internals (incl. the scanner)
  DEMO-SCRIPT.md                full presenter walkthrough
  BUILD-INFO.txt                version / build date of this copy
  demo-marketing\               sample data (auto-created, safe to delete)
