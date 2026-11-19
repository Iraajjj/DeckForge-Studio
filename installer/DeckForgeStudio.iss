; DeckForge Studio V4 - standard user-scoped installer, unsigned by default.
#define MyAppName "DeckForge Studio"
#define MyAppVersion "0.4.0"
#define MyAppExeName "DeckForgeStudio.exe"

[Setup]
AppId={{B270CF30-1BEF-4AC5-B59B-A066F748D2FD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=DeckForge Contributors
DefaultDirName={localappdata}\Programs\DeckForge Studio
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=DeckForgeStudio-V4-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible

[Files]
Source: "..\dist\DeckForgeStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch DeckForge Studio"; Flags: nowait postinstall skipifsilent
