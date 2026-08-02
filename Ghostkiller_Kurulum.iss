[Setup]
AppName=Ghostkiller Sound Cleaner V2
AppVersion=2.0
AppPublisher=Yasin Talha Gencsoy
DefaultDirName={autopf}\Ghostkiller Sound Cleaner V2
DefaultGroupName=Ghostkiller V2
OutputDir=C:\Users\User\Desktop\kodlamalar\cover\Setup
OutputBaseFilename=Ghostkiller_V2_Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=C:\Users\User\Desktop\kodlamalar\cover\logo.ico
LicenseFile=C:\Users\User\Desktop\kodlamalar\cover\lisans.txt

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "C:\Users\User\Desktop\kodlamalar\cover\dist\Ghostkiller_Sound_Cleaner_V2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\Users\User\Desktop\kodlamalar\ghostkiller_sound_cleaner\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\User\Desktop\kodlamalar\ghostkiller_sound_cleaner\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\Ghostkiller Sound Cleaner V2"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; IconFilename: "{app}\logo.ico"
Name: "{group}\Ghostkiller Sound Cleaner V2"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; IconFilename: "{app}\logo.ico"