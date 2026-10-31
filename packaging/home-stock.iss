; Inno Setup recipe for the Home Stock installer. Build both steps with scripts\build_installer.ps1,
; which freezes dist\HomeStock first and passes the version from home_stock.__version__.
; Installs per user (no administrator rights); the data in %LOCALAPPDATA%\Home Stock is never touched.

#ifndef AppVersion
  #error Pass /DAppVersion=x.y.z; scripts\build_installer.ps1 does
#endif

[Setup]
; Never change the AppId: it is how a new version finds and upgrades the installed one
AppId={{C597A26A-8613-4C64-8C73-758603AD161B}
AppName=Home Stock
AppVersion={#AppVersion}
AppVerName=Home Stock {#AppVersion}
AppPublisher=Gerruppa
VersionInfoVersion={#AppVersion}
; {autopf} is {localappdata}\Programs for a per-user install
DefaultDirName={autopf}\Home Stock
DefaultGroupName=Home Stock
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Home-Stock-{#AppVersion}-setup
SetupIconFile=..\src\home_stock\ui\assets\home-stock.ico
UninstallDisplayIcon={app}\HomeStock.exe
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
; force: the server process has no window to ask politely, and a silent install would abort on it
; (SQLite commits atomically, so ending it is safe)
CloseApplications=force

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; An upgrade replaces the bundled libraries whole, so no file of an older version lingers
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\HomeStock\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Home Stock"; Filename: "{app}\HomeStock.exe"
Name: "{autodesktop}\Home Stock"; Filename: "{app}\HomeStock.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\HomeStock.exe"; Description: "{cm:LaunchProgram,Home Stock}"; Flags: nowait postinstall skipifsilent
; A silent install (/SILENT /CLOSEAPPLICATIONS /NORESTART) skips the entry above: start the new version here
Filename: "{app}\HomeStock.exe"; Flags: nowait; Check: WizardSilent

[UninstallRun]
; The uninstaller does not close a running app as setup does, and its files would stay locked behind
Filename: "{sys}\taskkill.exe"; Parameters: "/F /T /IM HomeStock.exe"; Flags: runhidden; RunOnceId: "StopHomeStock"
