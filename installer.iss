[Setup]
AppId={{7A3B7E9F-4E9E-4D3F-8C7A-1234567890AB}
AppName=App Frantoio
AppVersion=1.0.1
DefaultDirName={pf}\App Frantoio
DefaultGroupName=App Frantoio
OutputDir=dist\installer
OutputBaseFilename=App_Frantoio_1.0.1_Setup
SetupIconFile=app_frantoio\resources\app.ico
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Files]
Source: "dist\App Frantoio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "config.json"; DestDir: "{userappdata}\App_Frantoio"; Flags: onlyifdoesntexist


[Icons]
Name: "{group}\App Frantoio"; Filename: "{app}\App Frantoio.exe"; IconFilename: "{app}\resources\app.ico"
Name: "{commondesktop}\App Frantoio"; Filename: "{app}\App Frantoio.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crea icona sul Desktop"; GroupDescription: "Scorciatoie:"

[Run]
Filename: "{app}\App Frantoio.exe"; Description: "Avvia App Frantoio"; Flags: nowait postinstall skipifsilent