#ifndef Backend
  #error "Backend must be specified: /DBackend=cpu, cuda, rocm or xpu"
#endif
#if (Backend != "cpu") && (Backend != "cuda") && (Backend != "rocm") && (Backend != "xpu")
  #error "Unknown backend"
#endif
[Setup]
; Keep the legacy implicit AppId and install directory so updates reuse user models.
AppId=Ghostkiller Sound Cleaner V2
AppName=Ghostkiller Sound Toolbox
AppVersion=2.0.0
AppPublisher=Yasin Talha Gencsoy
DefaultDirName={autopf}\Ghostkiller Sound Cleaner V2
DefaultGroupName=Ghostkiller V2
OutputDir={#SourcePath}Setup
OutputBaseFilename=Ghostkiller_V2_Setup_{#Backend}
Compression=lzma2/ultra64
SolidCompression=yes
DiskSpanning=no
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.19045
PrivilegesRequired=admin
SetupIconFile={#SourcePath}logo.ico
LicenseFile={#SourcePath}lisans.txt

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourcePath}dist\Ghostkiller_Sound_Cleaner_V2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\models"; Permissions: users-modify

[Icons]
Name: "{autodesktop}\Ghostkiller Sound Toolbox"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; IconFilename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"
Name: "{group}\Ghostkiller Sound Toolbox"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; IconFilename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"
