"""Build a small Inno launcher and its data slices in one offline ZIP.

This is a manual-install artifact. The existing single-EXE updater protocol
must not consume it. Neither building nor inspecting it runs the installer.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from app_settings import write_json_atomic
from tools.release.build_installer import find_compiler, validate_installer_input
from tools.release.preflight import ROOT, sha256


def compile_offline_installer(directory, backend, compiler='ISCC.exe', output_dir=None):
    version = validate_installer_input(directory, backend)
    executable = find_compiler(compiler)
    info_path = Path(directory).resolve() / '_internal/build-info.json'
    info_digest = sha256(info_path)
    info = json.loads(info_path.read_text(encoding='utf-8'))
    output = Path(output_dir or ROOT / 'Setup').resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = f'Ghostkiller_V2_Setup_{backend}_{version}'
    filename = stem + '_offline.zip'
    with tempfile.TemporaryDirectory(prefix='.offline-pending-', dir=output) as temporary:
        stage = Path(temporary)
        subprocess.run([executable, f'/DBackend={backend}', '/DOfflineBundle=1',
                        f'/DPackageDir={Path(directory).resolve()}', f'/DAppVersion={version}',
                        f'/O{stage}', str(ROOT / 'Ghostkiller_Kurulum.iss')], check=True, cwd=ROOT)
        launcher = stage / (stem + '.exe')
        slices = sorted(stage.glob(stem + '-*.bin'))
        if not launcher.is_file() or not slices or launcher.stat().st_size > 5 * 1024**2:
            raise ValueError('Offline installer requires a small launcher and data slices.')
        with launcher.open('rb') as stream:
            if stream.read(2) != b'MZ':
                raise ValueError('Offline launcher is not a Windows executable.')
        if any(not path.is_file() or path.stat().st_size == 0 for path in slices):
            raise ValueError('Empty offline installer data slice.')
        if sha256(info_path) != info_digest:
            raise ValueError('Frozen build metadata changed during installer compilation.')
        guide = stage / 'ONCE_OKU.txt'
        guide.write_text(
            'Ghostkiller Sound Toolbox ' + version + '\n\n'
            '1. ZIP dosyasına sağ tıklayıp Tümünü ayıkla seçeneğini kullanın.\n'
            '2. Açılan klasördeki ' + launcher.name + ' dosyasını çalıştırın.\n'
            '3. .bin dosyalarını setup ile aynı klasörde tutun; ZIP içinden doğrudan çalıştırmayın.\n\n'
            'İnternet gerekmez; uygulama ve CUDA/CPU çalışma ortamı pakettedir.\n'
            'Ses modelleri ilk kullanımda ayrıca hazırlanır. Mevcut 2.1.0 üzerine kurulabilir.\n'
            'Bu paket küçük setup dosyası kullanır; donanıma bağlı kurulum süresi devam eder.\n',
            encoding='utf-8')
        files = [launcher, *slices, guide]
        entries = [{'filename': path.name, 'size': path.stat().st_size, 'sha256': sha256(path)} for path in files]
        archive = stage / filename
        # Inno already compressed the data; recompressing it only wastes time.
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for path in files:
                bundle.write(path, path.name)
        receipt = {'schema_version': 1, 'format': 'offline-zip', 'application_version': version,
                   'backend': backend, 'purpose': 'release', 'release_eligible': True,
                   'application_source_sha256': info['application_source_sha256'],
                   'build_info_sha256': info_digest,
                   'installer_script_sha256': sha256(ROOT / 'Ghostkiller_Kurulum.iss'),
                   'setup_filename': launcher.name, 'files': entries,
                   'installer': {'filename': filename, 'size': archive.stat().st_size, 'sha256': sha256(archive)}}
        receipt_path = archive.with_suffix('.build.json')
        write_json_atomic(str(receipt_path), receipt)
        target = output / filename
        os.replace(archive, target)
        os.replace(receipt_path, target.with_suffix('.build.json'))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', required=True, choices=('cpu', 'cuda'))
    parser.add_argument('--package-dir', required=True, type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--compiler', default='ISCC.exe')
    args = parser.parse_args()
    print(compile_offline_installer(args.package_dir, args.backend, args.compiler, args.output_dir))


if __name__ == '__main__':
    main()
