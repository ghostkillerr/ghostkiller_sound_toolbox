#ifndef Backend
  #error "Backend must be specified: /DBackend=cpu, cuda, rocm or xpu"
#endif
#ifndef PackageDir
  #error "Use python -m tools.release.build_installer to validate the package and supply PackageDir"
#endif
#ifndef AppVersion
  #error "AppVersion must be taken from the validated packaged version.json"
#endif
#if !FileExists(PackageDir + "\Ghostkiller_Sound_Cleaner_V2.exe")
  #error "Packaged application executable is missing"
#endif
#if (Backend != "cpu") && (Backend != "cuda") && (Backend != "rocm") && (Backend != "xpu")
  #error "Unknown backend"
#endif
[Setup]
; Keep the legacy implicit AppId and install directory so updates reuse user models.
AppId=Ghostkiller Sound Cleaner V2
AppName=Ghostkiller Sound Toolbox
AppVersion={#AppVersion}
AppPublisher=Yasin Talha Gencsoy
DefaultDirName={autopf}\Ghostkiller Sound Cleaner V2
DefaultGroupName=Ghostkiller Sound Toolbox
OutputDir={#SourcePath}Setup
OutputBaseFilename=Ghostkiller_V2_Setup_{#Backend}_{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
#ifdef OfflineBundle
; A small launcher avoids a multi-gigabyte PE before the wizard can appear.
DiskSpanning=yes
DiskSliceSize=2000000000
#else
; Retained for the existing single-file automatic update protocol.
DiskSpanning=no
#endif
SetupLogging=yes
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19045
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
SetupMutex=GhostkillerSoundToolboxSetup
UninstallDisplayIcon={app}\Ghostkiller_Sound_Cleaner_V2.exe
WizardStyle=modern
SetupIconFile={#SourcePath}logo.ico
LicenseFile={#SourcePath}lisans.txt

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; These legacy codecs belonged to the installer. Models and user data are preserved.
Type: files; Name: "{app}\ffmpeg.exe"
Type: files; Name: "{app}\ffprobe.exe"

[Dirs]
Name: "{app}\models"; Permissions: users-modify

[Icons]
Name: "{autodesktop}\Ghostkiller Sound Toolbox"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Ghostkiller Sound Toolbox"; Filename: "{app}\Ghostkiller_Sound_Cleaner_V2.exe"; WorkingDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Kısayollar:"; Flags: checkedonce

[Code]
function OpenProcess(DesiredAccess: LongWord; InheritHandle: Boolean; ProcessId: LongWord): THandle;
  external 'OpenProcess@kernel32.dll stdcall';
function WaitForSingleObject(Handle: THandle; Milliseconds: LongWord): LongWord;
  external 'WaitForSingleObject@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ParentId: Integer;
  ParentHandle: THandle;
begin
  Result := '';
  ParentId := StrToIntDef(ExpandConstant('{param:GKUPDATEPID|0}'), 0);
  if ParentId <> 0 then begin
    if (ParentId < 0) or not FileExists(ExpandConstant('{app}\Ghostkiller_Sound_Cleaner_V2.exe')) then begin
      Result := 'Güncelleme hedefi geçersiz.';
      Exit;
    end;
    ParentHandle := OpenProcess($00100000, False, ParentId);
    if ParentHandle <> 0 then begin
      try
        if WaitForSingleObject(ParentHandle, 30000) <> 0 then
          Result := 'Program kapanmadı. Güncellemeyi Ayarlardan yeniden deneyin.';
      finally
        CloseHandle(ParentHandle);
      end;
    end else if DLLGetLastError <> 87 then
      Result := 'Programın kapandığı doğrulanamadı.';
  end;
end;
