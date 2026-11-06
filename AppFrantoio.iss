; Installer ufficiale App Frantoio (Windows 64-bit), creato con Inno Setup 6.
; Esegue installazione/aggiornamento del binario senza gestire o eliminare
; config.json, database SQLite e file dell'utente.
#define AppName "App Frantoio"
#define AppVersion "0.2.1"
#define AppExe "App_Frantoio.exe"

[Setup]
AppId={{0F8AE0CF-78B4-4C33-9D45-5D04A62551CE}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=App Frantoio
DefaultDirName={localappdata}\Programs\App Frantoio
DefaultGroupName=App Frantoio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
WizardSizePercent=100
SetupIconFile=app_frantoio\resources\app.ico
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=dist\installer
OutputBaseFilename=Setup_App_Frantoio
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
MinVersion=10.0
LicenseFile=
UsePreviousAppDir=yes
AllowNoIcons=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; GroupDescription: "Collegamenti aggiuntivi:"; Flags: unchecked

[Files]
Source: "dist\App_Frantoio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\App Frantoio"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"
Name: "{autodesktop}\App Frantoio"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Description: "Avvia App Frantoio"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  // Non mostrare finestre bloccanti durante le installazioni silenziose CI.
  if WizardSilent then
  begin
    Result := True;
    exit;
  end;
  Result := (MsgBox(
    'Prima di aggiornare, chiudi App Frantoio e conserva una copia del database SQLite e della configurazione.' + #13#10 + #13#10 +
    'Il programma non cancella questi file; se in precedenza usavi una versione portabile con il database nella vecchia cartella, scegli quella stessa cartella oppure configura il percorso assoluto del database.' + #13#10 + #13#10 +
    'Vuoi continuare?',
    mbConfirmation, MB_YESNO) = IDYES);
end;
