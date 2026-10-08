; Tax Document Console - Windows installer (Inno Setup 6).
;
; Inno Setup is used because the Python standard library cannot build a
; Windows installer; it is free, and the installer it makes needs no
; administrator rights to run (pilot decision P4).
;
; Build it with "pilot\Build Pilot Installer.bat", which passes the two values
; below on the command line:
;   ISCC.exe /DAppVersion=0.3 /DSourceDir="...\Tax Document Console-win32-x64" setup.iss

#ifndef AppVersion
  #error AppVersion is required: compile with /DAppVersion=<version from pilot-content.js>
#endif
#ifndef SourceDir
  #error SourceDir is required: compile with /DSourceDir=<the packaged folder>
#endif

[Setup]
; Never change AppId: it is how an upgrade finds the copy it replaces.
AppId={{27812DF2-05B3-4844-81BA-E58F49D2BD7D}
AppName=Tax Document Console
AppVersion={#AppVersion}
AppPublisher=J Park & Associates, CPA
PrivilegesRequired=lowest
; UsePreviousAppDir is left at Inno Setup's default (yes), on purpose (P155,
; SPEC-rename R2): a PC that has the earlier name, Tax Document Tracker Pilot,
; is upgraded in place, in that program's own folder, because settings.json
; lives beside the program; an upgrade into a new folder would leave the
; earlier program runnable in the old one. Only a new install uses this folder.
DefaultDirName={localappdata}\Programs\Tax Document Console
DefaultGroupName=Tax Document Console
UsePreviousGroup=no
DisableProgramGroupPage=yes
OutputDir=..\..\build-portable\installer
OutputBaseFilename=Tax-Document-Console-Setup-{#AppVersion}
UninstallDisplayName=Tax Document Console {#AppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; The console icon (pilot SPEC-icon): the installer's own .exe, the wizard's
; side panel and corner image at the seven scalings Inno Setup 6 picks from
; (smallest first), and the entry in Settings > Apps.
SetupIconFile=..\brand\tax-document-console\installer\setup.ico
WizardImageFile=..\brand\tax-document-console\installer\wizard-large-1.bmp,..\brand\tax-document-console\installer\wizard-large-2.bmp,..\brand\tax-document-console\installer\wizard-large-3.bmp,..\brand\tax-document-console\installer\wizard-large-4.bmp,..\brand\tax-document-console\installer\wizard-large-5.bmp,..\brand\tax-document-console\installer\wizard-large-6.bmp,..\brand\tax-document-console\installer\wizard-large-7.bmp
WizardSmallImageFile=..\brand\tax-document-console\installer\wizard-small-1.bmp,..\brand\tax-document-console\installer\wizard-small-2.bmp,..\brand\tax-document-console\installer\wizard-small-3.bmp,..\brand\tax-document-console\installer\wizard-small-4.bmp,..\brand\tax-document-console\installer\wizard-small-5.bmp,..\brand\tax-document-console\installer\wizard-small-6.bmp,..\brand\tax-document-console\installer\wizard-small-7.bmp
UninstallDisplayIcon={app}\Tax Document Console.exe

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[InstallDelete]
; The earlier name's own files (P155): exact paths, never a wildcard.
Type: files; Name: "{app}\Tax Document Tracker Pilot.exe"
Type: files; Name: "{userprograms}\Tax Document Tracker Pilot\Tax Document Tracker Pilot.lnk"
Type: dirifempty; Name: "{userprograms}\Tax Document Tracker Pilot"
Type: files; Name: "{userdesktop}\Tax Document Tracker Pilot.lnk"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Tax Document Console"; Filename: "{app}\Tax Document Console.exe"; AppUserModelID: "com.jparkassociates.taxdocumentconsole"
Name: "{autodesktop}\Tax Document Console"; Filename: "{app}\Tax Document Console.exe"; Tasks: desktopicon; AppUserModelID: "com.jparkassociates.taxdocumentconsole"

[Run]
; The after-install step runs in [Code] below (CurStepChanged), not here:
; a [Run] entry cannot read the step's exit code, and the installer shows a
; small window when the step fails (Jason, 2026-10-08).
Filename: "{app}\Tax Document Console.exe"; Description: "Launch Tax Document Console"; Flags: postinstall nowait skipifsilent

; Uninstall removes this computer's scheduled task and the installed files,
; nothing else (P12). There is deliberately no [UninstallDelete] section: the
; clients folder, the program's data folder and settings.json are never the
; installer's to delete. A missing task is fine: schtasks fails quietly and the
; uninstall goes on. The task name is the product name (tracker.scheduling.TASK_NAME);
; the earlier name's task is removed too (P155), in case the app never started
; after the upgrade to remove it itself.
[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Tax Document Console"" /F"; Flags: runhidden; RunOnceId: "RemoveSchedule"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Tax Document Tracker Pilot"" /F"; Flags: runhidden; RunOnceId: "RemoveEarlierSchedule"

[Code]
// The after-install step through its setup door (pilot P218, Q1; Jason,
// 2026-10-08: "Yes, add to pilot"): the packaged API in its setup mode,
// given the settings folder and the product's name (the installer passes
// no environment), hidden, and waited for, so the Overview is prepared
// while the installer is still on screen - after the files are in place
// and before the finished page offers to launch the app. It runs on a
// silent install too.
//
// A step that fails never fails the install: the app runs the step again
// at its first launch, as it always has. It says so in a small window
// (Jason, 2026-10-08: "show a small failure message window if the step
// fails"), left out on a silent install so nothing waits for a click. The
// codes are tracker.runner's SETUP_STEP_FAILED and SETUP_OVERVIEW_NOT_READY;
// a step that could not even start counts as one that could not finish.
const
  SetupStepFailed = 1;
  SetupOverviewNotReady = 2;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Preparing Overview...';
    if not Exec(ExpandConstant('{app}\resources\tracker-api\tracker-api.exe'),
                '--after-install-setup --settings "' + ExpandConstant('{app}') + '" --product "Tax Document Console"',
                '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      ResultCode := SetupStepFailed;
    if WizardSilent then
      Exit;
    if ResultCode = SetupOverviewNotReady then
      MsgBox('Tax Document Console is installed, but the Overview could not be prepared. ' +
             'The first time you open it, it will take longer while it reads every household.',
             mbError, MB_OK)
    else if ResultCode <> 0 then
      MsgBox('Tax Document Console is installed, but its setup step could not finish. ' +
             'It will try again the first time you start the app, and the first Overview may take longer.',
             mbError, MB_OK);
  end;
end;
