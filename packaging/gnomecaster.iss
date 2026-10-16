; Inno Setup script for the Windows installer (Inno Setup 6.7 or later):
;   iscc /DAppVersion=1.0.0 packaging\gnomecaster.iss
; Installs for the current user only, so no administrator prompt; the app goes to
; %LOCALAPPDATA%\Programs\Gnomecaster. Expects PyInstaller's output in dist\Gnomecaster.

#ifndef AppVersion
  #error Pass the version: iscc /DAppVersion=x.y.z packaging\gnomecaster.iss
#endif

[Setup]
; AppId identifies the app across versions: never change it, or updates install side by side
AppId={{6D1B6C4E-3F0A-4C1E-9B7D-5A2E8F4C9D21}
AppName=Gnomecaster
AppVersion={#AppVersion}
AppVerName=Gnomecaster {#AppVersion}
AppPublisher=InverseAltruism
AppPublisherURL=https://github.com/InverseAltruism/gnomecaster
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Gnomecaster
VersionInfoCompany=InverseAltruism
PrivilegesRequired=lowest
DefaultDirName={autopf}\Gnomecaster
DefaultGroupName=Gnomecaster
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist
OutputBaseFilename=Gnomecaster-Setup-{#AppVersion}
SetupIconFile=..\assets\brand\gnomecaster.ico
UninstallDisplayIcon={app}\Gnomecaster.exe
UninstallDisplayName=Gnomecaster
WizardStyle=modern dynamic
WizardImageFile=..\assets\brand\installer\side-202.png,..\assets\brand\installer\side-269.png,..\assets\brand\installer\side-336.png,..\assets\brand\installer\side-403.png,..\assets\brand\installer\side-430.png,..\assets\brand\installer\side-534.png
WizardSmallImageFile=..\assets\brand\installer\small-58.png,..\assets\brand\installer\small-77.png,..\assets\brand\installer\small-97.png,..\assets\brand\installer\small-116.png,..\assets\brand\installer\small-124.png,..\assets\brand\installer\small-159.png
; the app creates this mutex while it runs, so Setup and Uninstall ask to quit it first
AppMutex=Gnomecaster.Running
CloseApplications=no
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=This installs Gnomecaster, an AI helper you talk to inside World of Warcraft.%n%nAfter installing, Gnomecaster finds the game, adds its addon and connects an AI, in three short steps.
FinishedLabel=Gnomecaster is installed. It opens now to finish the setup.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Gnomecaster\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; files of an older version that this one no longer ships
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Gnomecaster"; Filename: "{app}\Gnomecaster.exe"
Name: "{autodesktop}\Gnomecaster"; Filename: "{app}\Gnomecaster.exe"; Tasks: desktopicon

[Registry]
; "Start with Windows" is a setting inside the app; uninstalling removes it
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Gnomecaster"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Gnomecaster.exe"; Description: "Open Gnomecaster"; Flags: nowait postinstall skipifsilent

[Code]
// Gnomecaster's window is Microsoft Edge WebView2. Windows 11 includes it and most Windows 10
// PCs have it; when it is missing, Setup downloads Microsoft's installer and runs it for this
// user. Detection and the download link follow Microsoft's WebView2 distribution guide.
const
  WebView2Key = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

var
  DownloadPage: TDownloadWizardPage;

function HasVersion(Root: Integer; Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function WebView2Installed: Boolean;
begin
  Result := HasVersion(HKLM, 'SOFTWARE\WOW6432Node\' + WebView2Key) or HasVersion(HKLM, 'SOFTWARE\' + WebView2Key)
    or HasVersion(HKCU, 'Software\' + WebView2Key);
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage('Getting Microsoft Edge WebView2', 'Gnomecaster shows its window with WebView2, which this PC does not have yet.', nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if (CurPageID = wpWelcome) and not WebView2Installed then begin
    DownloadPage.Clear;
    DownloadPage.Add(WebView2Url, 'MicrosoftEdgeWebview2Setup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or not WebView2Installed then
          MsgBox('WebView2 could not be installed. Gnomecaster installs anyway; if its window stays empty, install WebView2 from https://developer.microsoft.com/microsoft-edge/webview2/', mbInformation, MB_OK);
      except
        MsgBox('WebView2 could not be downloaded (' + GetExceptionMessage + '). Gnomecaster installs anyway; if its window stays empty, install WebView2 from https://developer.microsoft.com/microsoft-edge/webview2/', mbInformation, MB_OK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;
