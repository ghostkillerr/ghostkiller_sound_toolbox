"""Validate a distributable frozen bundle before invoking Inno Setup."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from app_version import read_application_version
from app_settings import write_json_atomic
from tools.release.preflight import (ROOT, validate_package_tree, sha256, checked_local_asset,
                                     validate_python_version, validate_ffmpeg_sources)
from tools.release.source_identity import source_digest


def find_compiler(compiler='ISCC.exe'):
    executable = shutil.which(str(compiler))
    if executable:
        return executable
    if Path(compiler).is_file():
        return str(Path(compiler).resolve())
    if str(compiler).lower() == 'iscc.exe':
        for variable in ('ProgramFiles','ProgramFiles(x86)'):
            base = os.environ.get(variable)
            if base:
                for version in ('7','6'):
                    candidate = Path(base)/f'Inno Setup {version}'/'ISCC.exe'
                    if candidate.is_file():
                        return str(candidate)
    raise FileNotFoundError('Inno Setup compiler not found. Supply --compiler with the ISCC.exe path.')


def validate_installer_input(directory, backend):
    root = Path(directory).resolve()
    validate_package_tree(root)
    internal = root / '_internal'
    info = json.loads((internal / 'build-info.json').read_text(encoding='utf-8'))
    if info.get('backend') != backend:
        raise ValueError('Installer backend does not match the frozen bundle.')
    if info.get('purpose') != 'release' or info.get('release_eligible') is not True:
        raise ValueError('Diagnostic bundles cannot become distributable installers.')
    try:
        python_version = tuple(int(part) for part in info['python'].split('.'))
    except (KeyError,AttributeError,ValueError) as error:
        raise ValueError('Frozen Python version is missing or invalid.') from error
    validate_python_version(python_version)
    if info.get('application_source_sha256') != source_digest():
        raise ValueError('Frozen application sources are outdated. Rebuild the EXE before creating an installer.')
    for name, key in ((f'{backend}.lock','dependency_lock_sha256'),('common.lock','common_lock_sha256')):
        if info.get(key) != sha256(ROOT/'requirements'/name):
            raise ValueError('Frozen bundle dependency locks are outdated: '+name)
    version = read_application_version(internal/'version.json')
    current = read_application_version(ROOT/'version.json')
    if version != current or info.get('application_version') != version:
        raise ValueError('Frozen application version is invalid or outdated.')
    for relative in ('Ghostkiller_Sound_Cleaner_V2.exe','Ghostkiller_Sound_Cleaner_V2.pkg','_internal/python312.dll',
                     '_internal/vcruntime140.dll','_internal/vcruntime140_1.dll','_internal/msvcp140.dll',
                     '_internal/ffmpeg.exe','_internal/ffprobe.exe',
                     '_internal/logo.ico','_internal/lisans.txt','_internal/THIRD_PARTY_NOTICES.md',
                     '_internal/update_helper.ps1',
                     '_internal/third_party/python/manifest.json',
                     '_internal/third_party/runtime/manifest.json',
                     '_internal/rvc/configs/24000.json','_internal/rvc/configs/32000.json',
                     '_internal/rvc/configs/40000.json','_internal/rvc/configs/48000.json',
                     '_internal/rvc/lib/algorithm/commons.py','_internal/rvc/lib/algorithm/synthesizers.py',
                     '_internal/training/vendor/config_32000.json',
                     '_internal/training/vendor/config_40000.json',
                     '_internal/training/vendor/config_48000.json',
                     '_internal/training/vendor/LICENSE','_internal/training/vendor/NOTICE.md',
                     '_internal/third_party/ffmpeg/manifest.json'):
        if not (root/relative).is_file() or (root/relative).stat().st_size == 0:
            raise ValueError('Required packaged file missing: '+relative)
    for directory, prefix, rates in (('rvc/configs','',(24000,32000,40000,48000)),
                                      ('training/vendor','config_',(32000,40000,48000))):
        for rate in rates:
            path = internal/directory/f'{prefix}{rate}.json'
            try:
                config = json.loads(path.read_text(encoding='utf-8'))
                if config['data']['sample_rate'] != rate or not isinstance(config['model'],dict):
                    raise ValueError('Config sample rate or model section is invalid.')
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError('Packaged model config invalid: '+str(path.relative_to(root))) from error
    for relative in ('rvc/lib/algorithm/commons.py','rvc/lib/algorithm/synthesizers.py'):
        if sha256(internal/relative) != sha256(ROOT/relative):
            raise ValueError('Packaged TorchScript source differs from application source: '+relative)
    if sha256(internal/'update_helper.ps1') != sha256(ROOT/'update_helper.ps1'):
        raise ValueError('Packaged update helper differs from application source.')
    runtime_root=internal/'third_party/runtime'
    runtime=json.loads((runtime_root/'manifest.json').read_text(encoding='utf-8'))
    if runtime.get('python')!=info['python'] or runtime.get('python_dll_sha256')!=sha256(internal/'python312.dll'):
        raise ValueError('Packaged CPython differs from runtime license/provenance material.')
    entries=runtime.get('files',[])
    if not {'LICENSE.txt','LICENSE.cpython.txt','PYTHON.json'}.issubset({item.get('path') for item in entries}):
        raise ValueError('Packaged CPython license material is incomplete.')
    for item in entries:
        checked_local_asset(runtime_root,item)
    ffmpeg = json.loads((internal/'third_party/ffmpeg/manifest.json').read_text(encoding='utf-8'))
    if ffmpeg.get('source_completeness') != 'complete':
        raise ValueError('Distributable FFmpeg source material is incomplete.')
    validate_ffmpeg_sources(ffmpeg)
    for category in ('licenses','sources','build_recipes'):
        entries = ffmpeg.get(category)
        if not isinstance(entries,list) or not entries:
            raise ValueError('Packaged FFmpeg material missing: '+category)
        for item in entries:
            checked_local_asset(internal/'third_party/ffmpeg',item)
    binaries = ffmpeg.get('binaries',[])
    if not {'ffmpeg.exe','ffprobe.exe'}.issubset({item.get('path') for item in binaries}):
        raise ValueError('Packaged FFmpeg binaries absent from manifest.')
    for item in binaries:
        checked_local_asset(internal,item)
    return version


def compile_installer(directory, backend, compiler):
    version = validate_installer_input(directory,backend)
    executable = find_compiler(compiler)
    info_path = Path(directory).resolve()/'_internal/build-info.json'
    info_digest = sha256(info_path)
    info = json.loads(info_path.read_text(encoding='utf-8'))
    output = ROOT/'Setup'
    output.mkdir(parents=True,exist_ok=True)
    filename = f'Ghostkiller_V2_Setup_{backend}_{version}.exe'
    # A successful compiler must produce a fresh file, never relabel an old output.
    with tempfile.TemporaryDirectory(prefix='.pending_',dir=output) as folder:
        stage = Path(folder)
        subprocess.run([executable,f'/DBackend={backend}',f'/DPackageDir={Path(directory).resolve()}',
                        f'/DAppVersion={version}',f'/O{stage}',str(ROOT/'Ghostkiller_Kurulum.iss')],
                       check=True,cwd=ROOT)
        installer = stage/filename
        if not installer.is_file() or installer.stat().st_size <= 2:
            raise ValueError('Compiler did not produce a fresh installer.')
        with installer.open('rb') as stream:
            if stream.read(2) != b'MZ':
                raise ValueError('Compiler output is not a Windows executable.')
        if any(stage.glob('*.bin')):
            raise ValueError('Update delivery requires a self-contained installer; sidecar .bin files are unsupported.')
        if sha256(info_path) != info_digest:
            raise ValueError('Frozen build metadata changed during installer compilation.')
        receipt = {'schema_version':1,'application_version':version,'backend':backend,
                   'purpose':'release','release_eligible':True,
                   'application_source_sha256':info['application_source_sha256'],
                   'build_info_sha256':info_digest,
                   'installer_script_sha256':sha256(ROOT/'Ghostkiller_Kurulum.iss'),
                   'installer':{'filename':filename,'sha256':sha256(installer),'size':installer.stat().st_size}}
        write_json_atomic(str(stage/Path(filename).with_suffix('.build.json')),receipt)
        target = output/filename
        os.replace(installer,target)
        os.replace(stage/Path(filename).with_suffix('.build.json'),target.with_suffix('.build.json'))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',required=True,choices=('cpu','cuda','xpu','rocm'))
    parser.add_argument('--package-dir',type=Path,default=ROOT/'dist/Ghostkiller_Sound_Cleaner_V2')
    parser.add_argument('--compiler',default='ISCC.exe')
    parser.add_argument('--check-only',action='store_true')
    args = parser.parse_args()
    if args.check_only:
        print('Validated installer input, version '+validate_installer_input(args.package_dir,args.backend))
    else:
        print('Created installer: '+str(compile_installer(args.package_dir,args.backend,args.compiler)))


if __name__=='__main__':
    main()
