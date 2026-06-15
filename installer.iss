; TaskMaster Windows 安装包 - Inno Setup 脚本
; 编译: ISCC.exe installer.iss
; 产物: dist/TaskMaster-1.0.0-Setup.exe

#define MyAppName "TaskMaster"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TaskMaster"
#define MyAppExeName "TaskMaster.exe"

[Setup]
AppId={{A4B3F8C9-2D7E-4F1A-9C5E-7B6D8E9F0A1B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; 允许非管理员安装到 %LOCALAPPDATA%\Programs (PrivilegesRequiredOverridesAllowed=dialog 二选一)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=TaskMaster-{#MyAppVersion}-Setup
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
; .NET / VC 运行时不需要,PyInstaller 已捆绑

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "开机自动启动 TaskMaster"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 把 PyInstaller 打的整目录全部塞进来
Source: "dist\TaskMaster\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 开机自启 —— 通过用户启动文件夹放快捷方式 (无需注册表权限)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
