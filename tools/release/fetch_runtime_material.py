"""Vendor exact licenses/metadata from the selected standalone CPython build."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import hashlib
from tools.release.fetch_ffmpeg_material import download, asset
from tools.release.preflight import ROOT, sha256

ARCHIVE_URL='https://github.com/astral-sh/python-build-standalone/releases/download/20261009/cpython-3.12.15%2B20261009-x86_64-pc-windows-msvc-pgo-full.tar.zst'
ARCHIVE_SHA256='9c2898a218c233d3de889d6aede2fdd859c07a51bfbb360f19bb660536f74672'
INSTALL_URL='https://github.com/astral-sh/python-build-standalone/releases/download/20261009/cpython-3.12.15%2B20261009-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
INSTALL_SHA256='11ed9f8a6ac64fb1b5a55e40e305a6744a3f77a70863c8f8197a6e4349abc64a'


def main():
    archive=ROOT/'build/python_runtime_material/cpython-full.tar.zst'
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        download(ARCHIVE_URL,archive,ARCHIVE_SHA256)
    if sha256(archive)!=ARCHIVE_SHA256:
        raise ValueError('CPython full archive SHA-256 mismatch.')
    installed=archive.parent/'cpython-install.tar.gz'
    if not installed.exists():
        download(INSTALL_URL,installed,INSTALL_SHA256)
    if sha256(installed)!=INSTALL_SHA256:
        raise ValueError('CPython install-only archive SHA-256 mismatch.')
    with tarfile.open(installed) as stream:
        selected=[member for member in stream.getmembers() if member.isfile() and member.name.endswith('/python312.dll')]
        if len(selected)!=1:
            raise ValueError('Pinned runtime DLL missing from install-only archive.')
        installed_dll_hash=hashlib.sha256(stream.extractfile(selected[0]).read()).hexdigest()
    if sha256(Path(sys.base_prefix)/'python312.dll')!=installed_dll_hash:
        raise ValueError('Running CPython DLL does not match its pinned install-only archive.')
    output=ROOT/'third_party/runtime'
    output.mkdir(parents=True,exist_ok=True)
    members=subprocess.run(['tar.exe','-tf',str(archive)],capture_output=True,text=True,check=True).stdout.splitlines()
    selected=[name for name in members if name.startswith('python/licenses/') and name.endswith('.txt')]
    selected+=['python/PYTHON.json','python/install/LICENSE.txt','python/install/python312.dll']
    files=[]
    dll_hash=None
    for name in selected:
        data=subprocess.run(['tar.exe','-xOf',str(archive),name],capture_output=True,check=True).stdout
        if name=='python/install/python312.dll':
            dll_hash=hashlib.sha256(data).hexdigest()
            continue
        filename=Path(name).name
        if filename not in name or '..' in Path(name).parts:
            raise ValueError('Unexpected upstream runtime license path.')
        target=output/filename
        target.write_bytes(data)
        files.append(asset(target,output,source=ARCHIVE_URL+'#'+name))
    manifest={'python':'3.12.15','build':'20261009','provider':'Astral python-build-standalone',
              'archive':{'url':ARCHIVE_URL,'sha256':ARCHIVE_SHA256},
              'install_archive':{'url':INSTALL_URL,'sha256':INSTALL_SHA256},
              'full_archive_python_dll_sha256':dll_hash,
              'python_dll_sha256':installed_dll_hash,'files':files,
              'scope':'CPython build metadata and original upstream licenses, including optional components listed by that upstream build.'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'CPython DLL matched; vendored {len(files)} original license/metadata files.')


if __name__=='__main__':
    main()
