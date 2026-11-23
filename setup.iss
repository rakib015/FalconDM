#define MyAppName "FalconDM"
#define MyAppVersion "2.8.2"
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
OutputBaseFilename=FalconDM-Setup-v2.8.2
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
Source: "browser_extension\*"; DestDir: "{app}\browser_extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_extension.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_extension.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "register_native_host.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autoprograms}\{#MyAppName}\Setup Browser Extension"; Filename: "{app}\install_extension.bat"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Windows Startup (Run key)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

; Chrome / Edge / Brave / Opera / Firefox Native Messaging Hosts (uninsdeletekey on uninstall)
Root: HKCU; Subkey: "Software\Google\Chrome\NativeMessagingHosts\com.falcondm.downloader"; ValueType: string; ValueData: "{userappdata}\FalconDM\native_messaging\com.falcondm.downloader.json"; Tasks: browserintegration; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts\com.falcondm.downloader"; ValueType: string; ValueData: "{userappdata}\FalconDM\native_messaging\com.falcondm.downloader.json"; Tasks: browserintegration; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.falcondm.downloader"; ValueType: string; ValueData: "{userappdata}\FalconDM\native_messaging\com.falcondm.downloader.json"; Tasks: browserintegration; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Mozilla\NativeMessagingHosts\com.falcondm.downloader"; ValueType: string; ValueData: "{userappdata}\FalconDM\native_messaging\com.falcondm.downloader_firefox.json"; Tasks: browserintegration; Flags: uninsdeletekey

[Run]
Filename: "{app}\register_native_host.bat"; Flags: runhidden; Tasks: browserintegration
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\install_extension.bat"; Description: "Open Browser Extension Setup (Chrome, Edge, Brave, Opera, Firefox)"; Flags: postinstall skipifsilent unchecked

