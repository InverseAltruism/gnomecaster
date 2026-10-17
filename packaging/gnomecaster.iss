; Inno Setup script for the Windows installer (Inno Setup 6.7 or later):
;   iscc /DAppVersion=1.0.0 packaging\gnomecaster.iss
; Installs for the current user only, so no administrator prompt; the app goes to
; %LOCALAPPDATA%\Programs\Gnomecaster. Expects PyInstaller's output in dist\Gnomecaster.

#ifndef AppVersion
  #error Pass the version: iscc /DAppVersion=x.y.z packaging\gnomecaster.iss
#endif

; one image per screen scaling; both are dark artwork, so dark mode uses the same ones
; (without the DynamicDark directives Inno shows its own stock image there)
#define SideImages "..\assets\brand\installer\side-202.png,..\assets\brand\installer\side-269.png,..\assets\brand\installer\side-336.png,..\assets\brand\installer\side-403.png,..\assets\brand\installer\side-430.png,..\assets\brand\installer\side-534.png"
; the app holds this mutex while it runs (app.MUTEX); Setup and Uninstall close the app first
#define AppMutex "Gnomecaster.Running"
#define SmallImages "..\assets\brand\installer\small-58.png,..\assets\brand\installer\small-77.png,..\assets\brand\installer\small-97.png,..\assets\brand\installer\small-116.png,..\assets\brand\installer\small-124.png,..\assets\brand\installer\small-159.png"

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
DisableWelcomePage=no
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
WizardImageFile={#SideImages}
WizardSmallImageFile={#SmallImages}
WizardImageFileDynamicDark={#SideImages}
WizardSmallImageFileDynamicDark={#SmallImages}
CloseApplications=no
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=This installs Gnomecaster, an AI helper you talk to inside World of Warcraft.%n%nAfter installing, Gnomecaster finds the game, adds its addon and connects an AI, in three short steps.
SelectTasksLabel2=Choose whether you want a desktop shortcut, then click Install.
FinishedLabel=Gnomecaster is installed. Open it to finish the setup: it finds World of Warcraft, adds the addon and connects an AI.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Gnomecaster\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; files of an older version that this one no longer ships
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Gnomecaster"; Filename: "{app}\Gnomecaster.exe"; AppUserModelID: "InverseAltruism.Gnomecaster"
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

// Called once the player has chosen to install or uninstall, before any file changes. Asks a
// running Gnomecaster to quit (--quit returns when its process has exited); if it still runs,
// as 1.0.0 does since it has no --quit, asks the player to quit it. False when they cancel.
// Inno's own AppMutex check would run before the Welcome page, so it is not used.
function CloseRunning: Boolean;
var
  ResultCode: Integer;
begin
  if CheckForMutexes('{#AppMutex}') and FileExists(ExpandConstant('{app}\Gnomecaster.exe')) then
    Exec(ExpandConstant('{app}\Gnomecaster.exe'), '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
  while Result and CheckForMutexes('{#AppMutex}') do
    Result := SuppressibleMsgBox('Gnomecaster is still running. Right-click its icon next to the clock, choose Quit Gnomecaster, then click OK.',
                                 mbError, MB_OKCANCEL, IDCANCEL) = IDOK;
end;

// An update: the player has set Gnomecaster up already, so there is nothing to choose (the
// shortcut choice is kept) and the pages say what an update does.
function IsUpdate: Boolean;
begin
  Result := WizardForm.PrevAppDir <> '';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpSelectTasks) and IsUpdate;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // the Ready page is off, so the page before it starts the install: its button says so
  if ((CurPageID = wpSelectTasks) or ((CurPageID = wpWelcome) and IsUpdate)) then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
  if (CurPageID = wpWelcome) and IsUpdate then
    WizardForm.WelcomeLabel2.Caption := 'This updates Gnomecaster to version {#AppVersion}. Your settings and the AI connection stay as they are.'
      + #13#10#13#10 + 'Click Install to update, or Cancel to exit Setup.';
  if (CurPageID = wpFinished) and IsUpdate then
    WizardForm.FinishedLabel.Caption := 'Gnomecaster is updated and keeps your settings.'
      + #13#10#13#10 + SetupMessage(msgClickFinish);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not CloseRunning then
    Result := 'Gnomecaster is still running, so Setup cannot replace it. Quit it from its icon next to the clock, then run Setup again.';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if (CurUninstallStep = usAppMutexCheck) and not CloseRunning then
    Abort;
  if (CurUninstallStep = usUninstall) and not UninstallSilent then
    if MsgBox('Also remove the Gnomecaster addon from World of Warcraft, and your Gnomecaster settings (including the AI connection)?',
              mbConfirmation, MB_YESNO) = IDYES then
      Exec(ExpandConstant('{app}\Gnomecaster.exe'), '--remove-everything', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

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
