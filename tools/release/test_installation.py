"""Exercise the real Inno file rules in an isolated, non-admin local fixture.

Does not register/uninstall the real product or touch existing user models.
This is a local install/upgrade check, not clean Windows/UAC certification.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from tools.release.build_installer import find_compiler, validate_installer_input
from tools.release.preflight import ROOT, sha256


def replace_once(text, old, new):
    if text.count(old)!=1:
        raise ValueError('Installer fixture directive absent or ambiguous: '+old)
    return text.replace(old,new,1)


def run(package, backend, compiler, output):
    package=Path(package).resolve()
    validate_installer_input(package,backend)
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Acceptance output must be under this project build directory.')
    output.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='install_acceptance_',dir=output) as folder:
        stage=Path(folder)
        installed=stage/'installed'
        installed.mkdir()
        # Model/settings/training sentinel files simulate existing data. All of
        # them are synthetic and belong to this fixture; no real assets used.
        saved={}
        for relative in ('models/voice.pth','models/voice.index','models.json',
                         'settings.json','training_runs/session.json','outputs/keep.wav'):
            path=installed/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'preserve synthetic user data: '+relative.encode())
            saved[relative]=sha256(path)
        for name in ('ffmpeg.exe','ffprobe.exe'):
            (installed/name).write_bytes(b'obsolete codec fixture')
        script=(ROOT/'Ghostkiller_Kurulum.iss').read_text(encoding='utf-8')
        changes={
            'AppId=Ghostkiller Sound Cleaner V2':'AppId=GhostkillerPackagingAcceptanceFixture',
            'AppName=Ghostkiller Sound Toolbox':'AppName=Ghostkiller packaging acceptance fixture',
            'DefaultDirName={autopf}\\Ghostkiller Sound Cleaner V2':'DefaultDirName='+str(installed),
            'DefaultGroupName=Ghostkiller Sound Toolbox':'DefaultGroupName=Ghostkiller packaging acceptance fixture',
            'PrivilegesRequired=admin':'PrivilegesRequired=lowest\nUninstallable=no\nCreateUninstallRegKey=no',
            'SetupMutex=GhostkillerSoundToolboxSetup':'SetupMutex=GhostkillerPackagingAcceptanceFixture',
            'Compression=lzma2/ultra64':'Compression=lzma2/fast',
            'SolidCompression=yes':'SolidCompression=no',
        }
        for old,new in changes.items():
            script=replace_once(script,old,new)
        (stage/'Ghostkiller_Kurulum.iss').write_text(script,encoding='utf-8')
        for name in ('logo.ico','lisans.txt'):
            shutil.copyfile(ROOT/name,stage/name)
        command=[find_compiler(compiler), '/Q', '/O'+str(stage), '/FPackagingAcceptance',
                 '/DBackend='+backend, '/DPackageDir='+str(package),
                 '/DAppVersion='+validate_installer_input(package,backend),str(stage/'Ghostkiller_Kurulum.iss')]
        with (output/f'{backend}-compile.log').open('wb') as log:
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
        installer=stage/'PackagingAcceptance.exe'
        env=os.environ.copy()
        env['LOCALAPPDATA']=str(stage/'profile')
        env['TEMP']=env['TMP']=str(stage/'temp')
        env['HF_HOME']=str(stage/'hf-cache')
        env['HF_HUB_OFFLINE']=env['TRANSFORMERS_OFFLINE']='1'
        env['PYTHONUTF8']='1'
        # Global Python/tool/codec PATH entries must not help the installed EXE.
        system=Path(os.environ['SystemRoot'])
        env['PATH']=str(system/'System32')+os.pathsep+str(system)
        for name in ('temp','profile','hf-cache'):
            (stage/name).mkdir()
        subprocess.run([str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS',
                        '/DIR='+str(installed), '/LOG='+str(output/f'{backend}-install.log')],
                       check=True,timeout=600,env=env)
        retained=all(sha256(installed/name)==digest for name,digest in saved.items())
        legacy_removed=not any((installed/name).exists() for name in ('ffmpeg.exe','ffprobe.exe'))
        smoke_path=output/f'{backend}-installed-smoke.json'
        subprocess.run([str(installed/'Ghostkiller_Sound_Cleaner_V2.exe'),'--self-test',str(smoke_path)],
                       check=True,timeout=180,env=env,cwd=installed)
        smoke=json.loads(smoke_path.read_text(encoding='utf-8'))
        result={'ok':retained and legacy_removed and smoke.get('ok') is True,
                'backend':backend,'synthetic_user_data_preserved':retained,
                'legacy_root_codecs_removed':legacy_removed,
                'installed_frozen_smoke':smoke,'seconds':round(time.monotonic()-started,3),
                'scope':'Local non-admin fixture, actual Inno file rules (fast compression); no clean Windows, production UAC or uninstall test.'}
        (output/f'{backend}-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if not result['ok']:
            raise RuntimeError('Local installation acceptance failed; see result JSON.')
    print(json.dumps({key:value for key,value in result.items() if key!='installed_frozen_smoke'},ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir',type=Path,required=True)
    parser.add_argument('--backend',choices=('cpu','cuda'),required=True)
    parser.add_argument('--compiler',default='ISCC.exe')
    parser.add_argument('--output',type=Path,default=ROOT/'build/install_acceptance')
    args=parser.parse_args()
    run(args.package_dir,args.backend,args.compiler,args.output)


if __name__=='__main__':
    main()
