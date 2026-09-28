; Tax Document Tracker Pilot - Windows installer (Inno Setup 6).
;
; Inno Setup is used because the Python standard library cannot build a
; Windows installer; it is free, and the installer it makes needs no
; administrator rights to run (pilot decision P4).
;
; Build it with "pilot\Build Pilot Installer.bat", which passes the two values
; below on the command line:
;   ISCC.exe /DAppVersion=0.1 /DSourceDir="...\Tax Document Tracker Pilot-win32-x64" setup.iss

#ifndef AppVersion
  #error AppVersion is required: compile with /DAppVersion=<version from pilot-content.js>
#endif
#ifndef SourceDir
  #error SourceDir is required: compile with /DSourceDir=<the packaged folder>
#endif

[Setup]
; Never change AppId: it is how an upgrade finds the copy it replaces.
AppId={{27812DF2-05B3-4844-81BA-E58F49D2BD7D}
AppName=Tax Document Tracker Pilot
AppVersion={#AppVersion}
AppPublisher=J Park & Associates, CPA
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Tax Document Tracker Pilot
DefaultGroupName=Tax Document Tracker Pilot
DisableProgramGroupPage=yes
OutputDir=..\..\build-portable\installer
OutputBaseFilename=Tax-Document-Tracker-Pilot-Setup-{#AppVersion}
UninstallDisplayName=Tax Document Tracker Pilot {#AppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Tax Document Tracker Pilot"; Filename: "{app}\Tax Document Tracker Pilot.exe"
Name: "{autodesktop}\Tax Document Tracker Pilot"; Filename: "{app}\Tax Document Tracker Pilot.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Tax Document Tracker Pilot.exe"; Description: "Launch Tax Document Tracker Pilot"; Flags: postinstall nowait skipifsilent

; Uninstall removes this computer's scheduled task and the installed files,
; nothing else (P12). There is deliberately no [UninstallDelete] section: the
; clients folder, the program's data folder and settings.json are never the
; installer's to delete. A missing task is fine: schtasks fails quietly and the
; uninstall goes on. The task name is the product name (tracker.scheduling.TASK_NAME).
[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Tax Document Tracker Pilot"" /F"; Flags: runhidden; RunOnceId: "RemoveSchedule"
