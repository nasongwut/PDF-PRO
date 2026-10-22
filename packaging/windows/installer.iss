; Inno Setup script for the PDF PRO Windows installer wizard.
; Build:  iscc /DAppVersion=1.0.0 /DSourceDir="..\..\dist\PDF PRO" packaging\windows\installer.iss
; (packaging/build_windows.ps1 and the GitHub workflow pass these values automatically)

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\PDF PRO"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif
#define AppName "PDF PRO"
#define AppExe "PDF PRO.exe"
#define RepoUrl "https://github.com/nasongwut/PDF-PRO"

[Setup]
AppId={{6B0F4D2C-9C51-4B0E-9E3B-5D2A1F7C8A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion} (Free)
AppPublisher=nasongwut — free software
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
AppCopyright=Free software (AGPL-3.0) — {#RepoUrl}
AppComments=PDF PRO is 100% free. Source code and credits: {#RepoUrl}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} {#AppVersion} Setup — free PDF editor
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\icons\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} (Free)
LicenseFile=LICENSE.txt
InfoBeforeFile=FREE-NOTICE.txt
OutputDir={#OutputDir}
OutputBaseFilename=PDF-PRO-{#AppVersion}-windows-setup
Compression=lzma2/max
SolidCompression=yes
CloseApplications=force
RestartApplications=no
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to PDF PRO {#AppVersion} — 100%% FREE
WelcomeLabel2=This wizard installs PDF PRO, a free PDF editor (Thai / English).%n%nPDF PRO is completely free: no fees, no ads, no tracking.%nโปรแกรมนี้ฟรี 100%% ไม่มีค่าใช้จ่าย ไม่มีโฆษณา%n%nCredits / source code:%n{#RepoUrl}
InfoBeforeLabel=Please read — this program is FREE / โปรดอ่าน — โปรแกรมนี้ฟรี
FinishedLabel=PDF PRO has been installed. It is free forever — if it helps you, please consider a donation or a ⭐ on GitHub:%n{#RepoUrl}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assocpdf"; Description: "Add ""Open with PDF PRO"" for PDF files"; GroupDescription: "File association:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "FREE-NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE-AGPL-3.0.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\PDF PRO on GitHub (free, donate)"; Filename: "{#RepoUrl}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFPRO.Document"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFPRO.Document"; ValueType: string; ValueName: ""; ValueData: "PDF Document (PDF PRO)"; Flags: uninsdeletekey; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFPRO.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\PDFPRO.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assocpdf
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Flags: uninsdeletekey

[Run]
; also runs after a silent in-app update so the new version starts again
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall
Filename: "{#RepoUrl}"; Description: "Visit PDF PRO on GitHub (free · credits · donate)"; Flags: shellexec postinstall skipifsilent unchecked nowait
