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
