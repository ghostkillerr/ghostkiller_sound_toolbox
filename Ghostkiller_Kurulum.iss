#ifndef FFmpegDir
#define FFmpegDir SourcePath + "tools\ffmpeg"
#endif
[Setup]
AppName=Ghostkiller Sound Cleaner V2
AppVersion=2.0.0
AppPublisher=Yasin Talha Gencsoy
DefaultDirName={autopf}\Ghostkiller Sound Cleaner V2
DefaultGroupName=Ghostkiller V2
OutputDir={#SourcePath}Setup
OutputBaseFilename=Ghostkiller_V2_Setup
Compression=lzma2/ultra64
SolidCompression=yes
DiskSpanning=no
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SetupIconFile={#SourcePath}logo.ico
LicenseFile={#SourcePath}lisans.txt

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourcePath}dist\Ghostkiller_Sound_Cleaner_V2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#FFmpegDir}\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#FFmpegDir}\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\models"; Permissions: users-modify

[Icons]
Name: "{autodesktop}\Ghostkiller Sound Cleaner V2"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; IconFilename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"
Name: "{group}\Ghostkiller Sound Cleaner V2"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; IconFilename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"
