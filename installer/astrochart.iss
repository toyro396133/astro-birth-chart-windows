#ifndef AppVersion
  #error AppVersion must be passed with /DAppVersion=x.y.z
#endif

[Setup]
AppId=AstroBirthChart.Windows
AppName=AstroBirthChart
AppVersion={#AppVersion}
AppVerName=AstroBirthChart {#AppVersion}
AppPublisher=AstroBirthChart
AppPublisherURL=https://github.com/toyro396133/astro-birth-chart-windows
AppSupportURL=https://github.com/toyro396133/astro-birth-chart-windows/issues
AppUpdatesURL=https://github.com/toyro396133/astro-birth-chart-windows/releases
DefaultDirName={localappdata}\Programs\AstroBirthChart
DefaultGroupName=AstroBirthChart
UsePreviousAppDir=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SourceDir=..
OutputDir=dist\installer
OutputBaseFilename=AstroBirthChart-Setup
SetupMutex=AstroBirthChart.Installer
VersionInfoVersion={#AppVersion}
Compression=lzma2/max
SolidCompression=yes
DiskSpanning=no
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
CreateUninstallRegKey=yes
UninstallDisplayName=AstroBirthChart
UninstallDisplayIcon={app}\AstroBirthChart.exe
DisableProgramGroupPage=yes
DisableDirPage=no
SetupLogging=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\AstroBirthChart\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installer\installed-by-setup.marker"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\AstroBirthChart"; Filename: "{app}\AstroBirthChart.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\AstroBirthChart"; Filename: "{app}\AstroBirthChart.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\AstroBirthChart.exe"; Description: "Launch AstroBirthChart"; Flags: nowait postinstall skipifsilent
