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
; An upgrade while the app or a scheduled pass is running (P115): before
; anything is deleted or copied, Windows is asked which programs hold the
; files being replaced, and the person is asked to let Setup close them
; (a silent install closes them without asking). "force" makes that close a
; forced one, so a pass that does not answer a polite close still ends. If
; the person declines, [InstallDelete] below still removes the old code's
; unlocked files and the copy stops at the first locked one; aborting then
; leaves neither version able to start, and running the installer again
; with the app closed repairs it. A pass closed half way is safe - every
; write goes through a temp that the next pass sweeps. Nothing is
; restarted: the schedule starts the next pass itself.
CloseApplications=force
RestartApplications=no

; An upgrade removes the old version's program code before copying the new
; (P115, narrowing P12): only the Electron shell's code folder and the frozen
; API's library folder, which the [Files] copy below replaces whole. Never the
; folder above them: the optional graphics card pack (gpu-runtime) sits beside
; tracker-api.exe and must survive an upgrade, and settings.json sits beside
; the app's own executable. Client files and the tracker's data folder are
; never under {app} at all.
[InstallDelete]
Type: filesandordirs; Name: "{app}\resources\app"
Type: filesandordirs; Name: "{app}\resources\tracker-api\_internal"

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
