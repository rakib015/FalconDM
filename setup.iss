#define MyAppName "FalconDM"
#define MyAppVersion "2.8.0"
#define MyAppPublisher "FalconDM Community"
#define MyAppURL "https://falcondm.local"
#define MyAppExeName "FalconDM.exe"

[Setup]
AppId={{D37D6E91-829C-4A23-8B3B-8C4529F4D1E8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist_installer
OutputBaseFilename=FalconDM-Setup-v2.8.0
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Launch FalconDM automatically on Windows startup"; GroupDescription: "Windows Integration:"
Name: "browserintegration"; Description: "Register browser integration (Chrome, Edge, Firefox, Brave, Opera)"; GroupDescription: "Browser Integration:"; Flags: checkedonce

[Files]
Source: "dist\FalconDM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Windows Startup (Run key)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

; Chrome / Brave / Opera Native Messaging Host
Root: HKCU; Subkey: "Software\Google\Chrome\NativeMessagingHosts\com.falcondm.downloader"; ValueType: string; ValueData: "{app}\core\com.falcondm.downloader.json"; Tasks: browserintegration; Flags: uninsdeletekey
; Microsoft Edge Native Messaging Host
Root: HKCU; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts\com.falcondm.downloader"; ValueType: string; ValueData: "{app}\core\com.falcondm.downloader.json"; Tasks: browserintegration; Flags: uninsdeletekey
; Mozilla Firefox Native Messaging Host
Root: HKCU; Subkey: "Software\Mozilla\NativeMessagingHosts\com.falcondm.downloader"; ValueType: string; ValueData: "{app}\core\com.falcondm.downloader_firefox.json"; Tasks: browserintegration; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

